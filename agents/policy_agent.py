from tools.policy_agent import answer_policy

POLICY_SUBAGENT = {
    "name": "policy-agent",
    "description": (
        "Chuyên tra cứu và trả lời nội quy thư viện: thời hạn mượn, số lượng "
        "sách tối đa, gia hạn, trả sách, phí phạt và các quy định sử dụng thư viện."
    ),
    "system_prompt": """
Bạn là Policy Subagent của thư viện.

Nhiệm vụ duy nhất: trả lời câu hỏi về nội quy/chính sách.
- Bắt buộc gọi answer_policy với câu hỏi cần tra cứu.
- Chỉ sử dụng thông tin được trả về từ tài liệu nội quy.
- Không tự bịa, suy đoán hoặc bổ sung quy định không có trong tài liệu.
- Nếu tài liệu không hỗ trợ câu trả lời, nói rõ không tìm thấy thông tin trong nội quy.
- Không tra cứu database sách.
- Trả kết quả ngắn gọn, chính xác để Main Agent tổng hợp.
""".strip(),
    "tools": [answer_policy],
    "mode": "isolated",
}
