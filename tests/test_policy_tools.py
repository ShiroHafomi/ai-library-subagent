import unittest
from unittest.mock import patch

from tools.policy_agent import answer_policy


class AnswerPolicyTests(unittest.TestCase):
    @patch("tools.policy_agent.retrieve_policy")
    def test_returns_relevant_rag_document_content(self, retrieve_policy):
        document = type("Document", (), {
            "page_content": "Thời hạn trong tài liệu là 14 ngày.",
            "metadata": {"source": "policy.md", "start_index": 0, "is_demo": True},
        })()
        retrieve_policy.return_value = [(document, 0.9)]

        result = answer_policy.invoke({"question": "thời hạn mượn"})

        self.assertIn("14 ngày", result)
        self.assertIn("policy.md", result)
        retrieve_policy.assert_called_once_with("thời hạn mượn")

    @patch("tools.policy_agent.retrieve_policy", return_value=[])
    def test_reports_missing_document_without_inventing_policy(self, retrieve_policy):
        result = answer_policy.invoke({"question": "thời hạn mượn"})

        self.assertIn("Không tìm thấy thông tin phù hợp", result)
        retrieve_policy.assert_called_once_with("thời hạn mượn")

    @patch("tools.policy_agent.retrieve_policy", side_effect=RuntimeError("index missing"))
    def test_reports_retrieval_error_without_inventing_policy(self, retrieve_policy):
        result = answer_policy.invoke({"question": "số lượng thành viên"})

        self.assertIn("Không thể tra cứu nội quy", result)
        self.assertNotIn("Một lần", result)


if __name__ == "__main__":
    unittest.main()
