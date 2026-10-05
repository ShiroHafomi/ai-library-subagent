from langchain.tools import tool

from database.connection import get_connection

_VALID_STATUSES = {"", "available", "borrowed"}


@tool
def search_books(
    title: str = "",
    author: str = "",
    category: str = "",
    status: str = "",
) -> str:
    """Tìm sách theo tên, tác giả, thể loại hoặc trạng thái available/borrowed."""
    title = title.strip()
    author = author.strip()
    category = category.strip()
    status = status.strip().lower()

    if status not in _VALID_STATUSES:
        return "Trạng thái không hợp lệ. Chỉ dùng 'available' hoặc 'borrowed'."

    query = """
        SELECT id, title, author, category, is_available
        FROM books
        WHERE 1=1
    """
    params: list[object] = []

    if title:
        query += " AND LOWER(title) LIKE LOWER(%s)"
        params.append(f"%{title}%")
    if author:
        query += " AND LOWER(author) LIKE LOWER(%s)"
        params.append(f"%{author}%")
    if category:
        query += " AND LOWER(category) LIKE LOWER(%s)"
        params.append(f"%{category}%")
    if status == "available":
        query += " AND is_available = 1"
    elif status == "borrowed":
        query += " AND is_available = 0"

    query += " ORDER BY title LIMIT 50"

    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(query, params)
        rows = cursor.fetchall()
    finally:
        cursor.close()
        connection.close()

    if not rows:
        return "Không tìm thấy sách phù hợp."

    results = []
    for row in rows:
        availability = "Sẵn sàng" if row["is_available"] else "Đã được mượn"
        results.append(
            f'{row["id"]} - {row["title"]} - {row["author"]} - '
            f'{row["category"]} - {availability}'
        )
    return "\n".join(results)
