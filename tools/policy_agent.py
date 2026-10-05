import re
import unicodedata

from langchain.tools import tool

from config import POLICY_FILE


def _normalize(text: str) -> set[str]:
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return set(re.findall(r"[a-z0-9]+", text))


def _retrieve_sections(question: str, document: str, limit: int = 4) -> list[str]:
    
    sections = [s.strip() for s in re.split(r"(?=^##\s)", document, flags=re.MULTILINE) if s.strip()]
    if not sections:
        return [document.strip()]

    query_words = _normalize(question)
    scored = []
    for section in sections:
        section_words = _normalize(section)
        score = len(query_words & section_words)
        scored.append((score, section))

    scored.sort(key=lambda item: item[0], reverse=True)
    relevant = [section for score, section in scored if score > 0][:limit]
    return relevant or sections[:limit]


@tool
def answer_policy(question: str) -> str:
    """Tra cứu tài liệu nội quy thư viện để cung cấp nguồn cho câu trả lời chính sách."""
    if not POLICY_FILE.exists():
        return (
            "Không tìm thấy tài liệu nội quy. "
            "Hãy tạo file data/policy.md trước khi hỏi về nội quy."
        )

    document = POLICY_FILE.read_text(encoding="utf-8").strip()
    if not document:
        return "Tài liệu nội quy đang trống."

    sections = _retrieve_sections(question, document)
    return "\n\n".join(sections)
