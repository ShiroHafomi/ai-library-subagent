import logging
from datetime import datetime

from langchain_core.tools import tool
from pydantic import StrictInt

from database.connection import get_connection
from tools.transaction_context import get_trusted_transaction_context

logger = logging.getLogger(__name__)

# Keep this lookup parameterized and member-scoped. The raw toolkit query tool
# accepts arbitrary SQL and must not expose circulation rows across members.
def _select_member_active_loans(cursor, member_id, book_title):
    sql = """
        SELECT br.id AS record_id, b.id AS book_id, b.title,
               br.borrowed_at, br.due_at
        FROM borrow_records AS br
        JOIN books AS b ON b.id = br.book_id
        WHERE br.member_id = %s AND br.status = 'borrowed'
    """
    params = [member_id]
    if book_title:
        sql += " AND b.title LIKE %s"
        params.append(f"%{book_title}%")
    sql += " ORDER BY br.id LIMIT 20"
    cursor.execute(sql, tuple(params))
    return cursor.fetchall()


# Transaction-critical reads stay on the write cursor to retain ownership,
# status, and FOR UPDATE guarantees; toolkit queries run independently.
def _lock_borrow_record(cursor, record_id, member_id):
    cursor.execute(
        """
        SELECT id, member_id, book_id, status
        FROM borrow_records
        WHERE id = %s AND member_id = %s
        FOR UPDATE
        """,
        (record_id, member_id),
    )
    return cursor.fetchone()


def _lock_book(cursor, book_id):
    cursor.execute(
        """
        SELECT id, title
        FROM books
        WHERE id = %s
        FOR UPDATE
        """,
        (book_id,),
    )
    return cursor.fetchone()


def _mark_record_returned(cursor, record_id, returned_at):
    cursor.execute(
        """
        UPDATE borrow_records
        SET status = 'returned', returned_at = %s
        WHERE id = %s AND status = 'borrowed'
        """,
        (returned_at, record_id),
    )
    return cursor.rowcount


def _count_active_book_loans(cursor, book_id):
    cursor.execute(
        """
        SELECT COUNT(*) AS active_count
        FROM borrow_records
        WHERE book_id = %s AND status = 'borrowed'
        """,
        (book_id,),
    )
    return cursor.fetchone()["active_count"]


def _set_book_availability(cursor, book_id, available):
    cursor.execute(
        "UPDATE books SET is_available = %s WHERE id = %s",
        (1 if available else 0, book_id),
    )


@tool
def find_active_loans(book_title: str = "") -> str:
    """Tra cứu các lượt mượn đang hoạt động của thành viên trong trusted context."""
    try:
        context = get_trusted_transaction_context()
    except (RuntimeError, TypeError, ValueError) as exc:
        return str(exc)

    title = book_title.strip()
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        records = _select_member_active_loans(
            cursor, context.member_id, title
        )
    except Exception:
        logger.exception("Active-loan lookup failed")
        return "Không thể tra cứu lượt mượn lúc này. Vui lòng thử lại sau."
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()

    if not records:
        return "Không tìm thấy lượt mượn đang hoạt động phù hợp."
    return "\n".join(
        f"Mã phiếu: {row['record_id']} | Sách: {row['title']} | "
        f"Mã sách: {row['book_id']} | Ngày mượn: {row['borrowed_at']} | "
        f"Hạn trả: {row['due_at']}"
        for row in records
    )


@tool
def return_book(record_id: StrictInt) -> str:
    """Trả sách theo mã phiếu; quyền và xác nhận lấy từ tầng ứng dụng."""
    try:
        context = get_trusted_transaction_context(require_confirmation=True)
    except (RuntimeError, TypeError, ValueError) as exc:
        return str(exc)

    # Keep this guard for direct callers that bypass the StrictInt tool schema.
    if isinstance(record_id, bool) or not isinstance(record_id, int) or record_id <= 0:
        return "Mã phiếu mượn không hợp lệ."

    if context.confirmed_action != "return" or context.confirmed_resource_id != record_id:
        return "Giao dịch bị từ chối: xác nhận CLI không khớp với phiếu cần trả."

    connection = None
    cursor = None
    transaction_started = False

    try:
        connection = get_connection()
        connection.start_transaction()
        transaction_started = True
        cursor = connection.cursor(dictionary=True)

        record = _lock_borrow_record(cursor, record_id, context.member_id)
        if record is None:
            connection.rollback()
            transaction_started = False
            return "Không tìm thấy phiếu mượn."
        if record["member_id"] != context.member_id:
            connection.rollback()
            transaction_started = False
            return "Từ chối trả sách: tài khoản đã xác thực không có quyền với phiếu mượn này."
        if record["status"] == "returned":
            connection.rollback()
            transaction_started = False
            return "Phiếu mượn này đã được trả trước đó."
        if record["status"] != "borrowed":
            connection.rollback()
            transaction_started = False
            return "Phiếu mượn không ở trạng thái đang mượn."

        book = _lock_book(cursor, record["book_id"])
        if book is None:
            connection.rollback()
            transaction_started = False
            return "Không tìm thấy sách tương ứng; giao dịch đã được hủy."

        returned_at = datetime.now()
        if _mark_record_returned(cursor, record_id, returned_at) != 1:
            connection.rollback()
            transaction_started = False
            return "Phiếu mượn đã được xử lý hoặc không thể cập nhật."

        is_available = _count_active_book_loans(cursor, record["book_id"]) == 0
        _set_book_availability(cursor, record["book_id"], is_available)

        connection.commit()
        transaction_started = False
        return (
            "Trả sách thành công!\n"
            f"Mã phiếu mượn: {record_id}\n"
            f"Tên sách: {book['title']}\n"
            f"Ngày trả: {returned_at:%d/%m/%Y}\n"
            "Trạng thái: Đã trả"
        )
    except Exception:
        logger.exception("Return transaction failed")
        if connection is not None and transaction_started:
            connection.rollback()
        return "Có lỗi cơ sở dữ liệu khi thực hiện trả sách; giao dịch không thành công."
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()
