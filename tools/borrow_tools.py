from datetime import datetime, timedelta

from langchain_core.tools import tool
from database.connection import get_connection


@tool
def borrow_book(
    member_id: int,
    book_id: int,
    loan_days: int,
    confirmed: bool = False,
) -> str:
    """
    Thực hiện giao dịch mượn sách trong thư viện.

    Args:
        member_id: Mã thành viên.
        book_id: Mã sách cần mượn.
        loan_days: Số ngày mượn đã được xác minh
            từ chính sách thư viện.
        confirmed: Trạng thái xác nhận yêu cầu mượn.

    Returns:
        Kết quả thực hiện giao dịch mượn sách.
    """

    # Đây chỉ là kiểm tra cơ bản.
    # confirmed do LLM cung cấp không phải xác thực an toàn.
    if not confirmed:
        return "Yêu cầu mượn sách chưa được xác nhận."

    if member_id <= 0 or book_id <= 0:
        return "Mã thành viên hoặc mã sách không hợp lệ."

    if loan_days <= 0:
        return "Thời hạn mượn không hợp lệ."

    connection = None
    cursor = None

    try:
        connection = get_connection()
        connection.start_transaction()

        cursor = connection.cursor(dictionary=True)

        # 1. Khóa và kiểm tra thành viên
        cursor.execute(
            """
            SELECT id, name, status
            FROM members
            WHERE id = %s
            FOR UPDATE
            """,
            (member_id,),
        )

        member = cursor.fetchone()

        if member is None:
            connection.rollback()
            return "Không tìm thấy thành viên."

        if member["status"] != "active":
            connection.rollback()
            return "Tài khoản thành viên không hoạt động."

        # 2. Khóa và kiểm tra sách
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
            return "Không tìm thấy sách."

        if not book["is_available"]:
            connection.rollback()
            return f"Sách '{book['title']}' hiện không thể mượn."

        # 3. Tạo thời gian mượn và hạn trả
        borrowed_at = datetime.now()
        due_at = borrowed_at + timedelta(days=loan_days)

        # 4. Tạo phiếu mượn
        cursor.execute(
            """
            INSERT INTO borrow_records (
                member_id,
                book_id,
                borrowed_at,
                due_at,
                status
            )
            VALUES (%s, %s, %s, %s, 'borrowed')
            """,
            (
                member_id,
                book_id,
                borrowed_at,
                due_at,
            ),
        )

        record_id = cursor.lastrowid

        # 5. Cập nhật trạng thái sách
        cursor.execute(
            """
            UPDATE books
            SET is_available = 0
            WHERE id = %s
            """,
            (book_id,),
        )

        # 6. Lưu toàn bộ thay đổi
        connection.commit()

        return (
            "Mượn sách thành công!\n"
            f"Mã phiếu mượn: {record_id}\n"
            f"Thành viên: {member['name']}\n"
            f"Sách: {book['title']}\n"
            f"Ngày mượn: {borrowed_at:%d/%m/%Y}\n"
            f"Hạn trả: {due_at:%d/%m/%Y}"
        )

    except Exception:
        if connection is not None:
            connection.rollback()

        return "Có lỗi cơ sở dữ liệu khi thực hiện mượn sách."

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None:
            connection.close()