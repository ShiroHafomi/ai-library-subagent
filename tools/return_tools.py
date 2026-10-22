import logging
from datetime import datetime

from langchain_core.tools import tool
from pydantic import StrictInt

from database.connection import get_connection
from tools.transaction_context import get_trusted_transaction_context

logger = logging.getLogger(__name__)


@tool
def return_book(record_id: StrictInt) -> str:
    """Trả sách theo mã phiếu; quyền và xác nhận lấy từ tầng ứng dụng."""
    try:
        context = get_trusted_transaction_context()
    except (RuntimeError, TypeError, ValueError) as exc:
        return str(exc)

    # Keep this guard for direct callers that bypass the StrictInt tool schema.
    if isinstance(record_id, bool) or not isinstance(record_id, int) or record_id <= 0:
        return "Mã phiếu mượn không hợp lệ."

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
            SELECT id, member_id, book_id, status
            FROM borrow_records
            WHERE id = %s
            FOR UPDATE
            """,
            (record_id,),
        )
        record = cursor.fetchone()
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

        cursor.execute(
            """
            SELECT id, title
            FROM books
            WHERE id = %s
            FOR UPDATE
            """,
            (record["book_id"],),
        )
        book = cursor.fetchone()
        if book is None:
            connection.rollback()
            transaction_started = False
            return "Không tìm thấy sách tương ứng; giao dịch đã được hủy."

        returned_at = datetime.now()
        cursor.execute(
            """
            UPDATE borrow_records
            SET status = 'returned', returned_at = %s
            WHERE id = %s AND status = 'borrowed'
            """,
            (returned_at, record_id),
        )
        if cursor.rowcount != 1:
            connection.rollback()
            transaction_started = False
            return "Phiếu mượn đã được xử lý hoặc không thể cập nhật."

        cursor.execute(
            """
            SELECT COUNT(*) AS active_count
            FROM borrow_records
            WHERE book_id = %s AND status = 'borrowed'
            """,
            (record["book_id"],),
        )
        is_available = cursor.fetchone()["active_count"] == 0
        cursor.execute(
            "UPDATE books SET is_available = %s WHERE id = %s",
            (1 if is_available else 0, record["book_id"]),
        )

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
