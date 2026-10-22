import unittest
from unittest.mock import patch

from tools.policy_agent import answer_policy


class AnswerPolicyTests(unittest.TestCase):
    @patch("tools.policy_agent.POLICY_FILE")
    def test_returns_only_relevant_policy_document_content(self, policy_file):
        policy_file.exists.return_value = True
        policy_file.read_text.return_value = (
            "## Thời hạn mượn\nThời hạn trong tài liệu là 14 ngày.\n"
            "## Bảo quản sách\nGiữ gìn sách cẩn thận."
        )

        result = answer_policy.invoke({"question": "thời hạn mượn"})

        self.assertIn("14 ngày", result)
        self.assertNotIn("Giữ gìn sách", result)
        policy_file.read_text.assert_called_once_with(encoding="utf-8")

    @patch("tools.policy_agent.POLICY_FILE")
    def test_reports_missing_document_without_inventing_policy(self, policy_file):
        policy_file.exists.return_value = False

        result = answer_policy.invoke({"question": "thời hạn mượn"})

        self.assertIn("Không tìm thấy tài liệu nội quy", result)
        policy_file.read_text.assert_not_called()

    @patch("tools.policy_agent.POLICY_FILE")
    def test_reports_when_question_has_no_matching_section(self, policy_file):
        policy_file.exists.return_value = True
        policy_file.read_text.return_value = "## Gia hạn\nMột lần nếu đủ điều kiện."

        result = answer_policy.invoke({"question": "số lượng thành viên"})

        self.assertIn("không tìm thấy thông tin phù hợp", result.lower())
        self.assertNotIn("Một lần", result)


if __name__ == "__main__":
    unittest.main()
