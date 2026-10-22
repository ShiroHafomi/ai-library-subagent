"""Tool tra cứu chính sách bằng RAG (không tự suy đoán)."""
from langchain_core.tools import tool
from rag.store import retrieve_policy


@tool
def answer_policy(question: str) -> str:
    """Truy xuất các đoạn nội quy liên quan bằng Gemini Embeddings và Chroma."""
    try:
        matches = retrieve_policy(question)
    except (RuntimeError, ValueError, ImportError, OSError) as exc:
        return f'Không thể tra cứu nội quy: {exc}'
    if not matches:
        return 'Không tìm thấy thông tin phù hợp trong tài liệu nội quy.'
    return '\n\n'.join(
        f"Nguồn: {doc.metadata.get('source', 'không rõ')}"
        f" | vị trí: {doc.metadata.get('start_index', 'không rõ')}"
        f" | {'NỘI QUY DEMO' if doc.metadata.get('is_demo') else 'tài liệu'}\n"
        f'{doc.page_content}' for doc, _ in matches
    )
