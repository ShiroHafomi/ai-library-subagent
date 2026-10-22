import logging
from datetime import datetime, timedelta

from langchain_core.tools import tool
from pydantic import StrictInt

from database.connection import get_connection
from tools.transaction_context import get_trusted_transaction_context

logger = logging.getLogger(__name__)


@tool
def borrow_book(book_id: StrictInt) -> str:
    """Mượn sách theo mã sách; quyền và chính sách lấy từ tầng ứng dụng đáng tin cậy."""
    try:
        context = get_trusted_transaction_context()
    except (RuntimeError, TypeError, ValueError) as exc:
        return str(exc)

    # Keep this guard for direct callers that bypass the StrictInt tool schema.
    if isinstance(book_id, bool) or not isinstance(book_id, int) or book_id <= 0:
        return "Mã sách không hợp lệ."

    connection = None
    cursor = None
    transaction_started = False

    try:
        connection = get_connection()
        connection.start_transaction()
        transaction_started = True
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT id, name, status
            FROM members
            WHERE id = %s
            FOR UPDATE
            """,
            (context.member_id,),
        )
        member = cursor.fetchone()
        if member is None:
            connection.rollback()
            transaction_started = False
            return "Không tìm thấy thành viên đã được xác thực."
        if member["status"] != "active":
            connection.rollback()
            transaction_started = False
            return "Tài khoản thành viên không hoạt động."

        cursor.execute(
            """
            SELECT id, title, is_available
            FROM books
            WHERE id = %s
            FOR UPDATE
            """,
            (book_id,),
        )
        book = cursor.fetchone()
        if book is None:
            connection.rollback()
            transaction_started = False
            return "Không tìm thấy sách."
        if not book["is_available"]:
            connection.rollback()
            transaction_started = False
            return f"Sách '{book['title']}' hiện không thể mượn."

        cursor.execute(
            """
            SELECT COUNT(*) AS active_count
            FROM borrow_records
            WHERE member_id = %s AND status = 'borrowed'
            """,
            (context.member_id,),
        )
        active_count = cursor.fetchone()["active_count"]
        if active_count >= context.max_active_loans:
            connection.rollback()
            transaction_started = False
            return "Thành viên đã đạt giới hạn mượn theo chính sách đã xác thực."

        borrowed_at = datetime.now()
        due_at = borrowed_at + timedelta(days=context.loan_days)
        cursor.execute(
            """
            INSERT INTO borrow_records (
                member_id, book_id, borrowed_at, due_at, status
            )
            VALUES (%s, %s, %s, %s, 'borrowed')
            """,
            (context.member_id, book_id, borrowed_at, due_at),
        )
        record_id = cursor.lastrowid

        cursor.execute(
            "UPDATE books SET is_available = 0 WHERE id = %s",
            (book_id,),
        )
        if cursor.rowcount != 1:
            connection.rollback()
            transaction_started = False
            return "Không thể cập nhật trạng thái sách; giao dịch đã được hủy."

        connection.commit()
        transaction_started = False
        return (
            "Mượn sách thành công!\n"
            f"Mã phiếu mượn: {record_id}\n"
            f"Thành viên: {member['name']}\n"
            f"Sách: {book['title']}\n"
            f"Ngày mượn: {borrowed_at:%d/%m/%Y}\n"
            f"Hạn trả: {due_at:%d/%m/%Y}"
        )
    except Exception:
        logger.exception("Borrow transaction failed")
        if connection is not None and transaction_started:
            connection.rollback()
        return "Có lỗi cơ sở dữ liệu khi thực hiện mượn sách; giao dịch không thành công."
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()
