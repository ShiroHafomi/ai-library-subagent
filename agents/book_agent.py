"""Book Subagent dùng SQL tools LangChain, không có câu SQL viết sẵn."""
from tools.book_tools import create_book_sql_tools

BOOK_SYSTEM_PROMPT = """
Bạn là Book Subagent của thư viện. Bạn chỉ tra cứu sách bằng SQL SELECT.
- Dùng sql_db_list_tables/sql_db_schema để xem schema thật của bảng books.
- Tạo SELECT phù hợp với câu hỏi (tên, tác giả, thể loại, tình trạng sách).
- Trước mỗi truy vấn phải dùng sql_db_query_checker, sau đó sql_db_query.
- Chỉ đọc bảng books; không truy vấn bảng khác hoặc dữ liệu nhạy cảm.
- Không dùng INSERT, UPDATE, DELETE, DDL, hoặc nhiều câu lệnh trong một lần gọi.
- Giới hạn tối đa 20 kết quả nếu người dùng không yêu cầu rõ ràng.
- Không suy đoán schema, không bịa kết quả; trả lời tiếng Việt.
- Quyền chỉ đọc phải được áp dụng ở tài khoản MySQL, không chỉ bằng prompt.
""".strip()


def create_book_subagent(model):
    return {
        'name': 'book-agent',
        'description': 'Tra cứu sách bằng LangChain SQL Toolkit chỉ đọc theo system prompt.',
        'system_prompt': BOOK_SYSTEM_PROMPT,
        'tools': create_book_sql_tools(model),
    }
