import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import app as app_module
from services.retrieval_service import get_default_retrieval_service


def fake_openai_client(answer="这是测试回答。"):
    payload = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=answer))]
    )
    create = Mock(return_value=payload)
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    return client, create


class RetrievalServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.retriever = get_default_retrieval_service(force_reload=True)

    def test_student_loan_question_finds_student_loans(self):
        results = self.retriever.retrieve("助学贷款是不是高利贷？")

        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]["document_id"], "student-aid-student-loans")

    def test_grant_question_finds_scholarships_and_grants(self):
        results = self.retriever.retrieve("国家助学金怎么申请？")

        self.assertGreater(len(results), 0)
        self.assertTrue(
            all(
                result["document_id"] == "student-aid-scholarships-and-grants"
                for result in results
            )
        )

    def test_green_channel_question_finds_green_channel(self):
        results = self.retriever.retrieve("交不起学费，可以走绿色通道吗？")

        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]["document_id"], "student-aid-green-channel")

    def test_unrelated_question_does_not_recall_student_aid(self):
        self.assertEqual(self.retriever.retrieve("今天天气怎么样？"), [])

    def test_result_source_comes_from_catalog(self):
        result = self.retriever.retrieve("生源地信用助学贷款在哪里申请？")[0]

        self.assertEqual(result["source"]["organization"], "全国学生资助管理中心")
        self.assertEqual(result["url"], "https://www.xszz.edu.cn/")
        self.assertNotIn("模型", result["source"]["title"])

    def test_oral_student_loan_expression_is_supported(self):
        results = self.retriever.retrieve("家里困难，想借钱读书怎么办？")

        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]["document_id"], "student-aid-student-loans")


class RetrievalApiTests(unittest.TestCase):
    def setUp(self):
        app_module.app.config.update(TESTING=True)
        self.client = app_module.app.test_client()

    def test_no_result_falls_back_to_policy_md(self):
        fake_client, create = fake_openai_client()
        empty_retriever = SimpleNamespace(retrieve=Mock(return_value=[]))

        with patch.dict(
            os.environ,
            {"DEEPSEEK_API_KEY": "test-key", "USE_KNOWLEDGE_RETRIEVAL": "true"},
        ), patch.object(app_module, "OpenAI", return_value=fake_client), patch.object(
            app_module,
            "get_default_retrieval_service",
            return_value=empty_retriever,
        ):
            response = self.client.post("/api/chat", json={"message": "今天天气怎么样？"})

        self.assertEqual(response.status_code, 200)
        prompt = create.call_args.kwargs["messages"][1]["content"]
        self.assertIn("# 惠心小助资助政策知识库", prompt)
        self.assertEqual(response.get_json()["sources"], [])
        self.assertEqual(response.get_json()["suggested_questions"], [])

    def test_old_api_request_remains_compatible_when_flag_is_false(self):
        fake_client, _create = fake_openai_client()

        with patch.dict(
            os.environ,
            {"DEEPSEEK_API_KEY": "test-key", "USE_KNOWLEDGE_RETRIEVAL": "false"},
        ), patch.object(app_module, "OpenAI", return_value=fake_client), patch.object(
            app_module, "get_default_retrieval_service"
        ) as retrieval_getter:
            response = self.client.post("/api/chat", json={"message": "什么是绿色通道？"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["answer"], "这是测试回答。")
        self.assertEqual(response.get_json()["sources"], [])
        retrieval_getter.assert_not_called()

    def test_extended_request_fields_are_accepted_without_memory(self):
        fake_client, _create = fake_openai_client()

        with patch.dict(
            os.environ,
            {"DEEPSEEK_API_KEY": "test-key", "USE_KNOWLEDGE_RETRIEVAL": "false"},
        ), patch.object(app_module, "OpenAI", return_value=fake_client):
            response = self.client.post(
                "/api/chat",
                json={
                    "message": "什么是国家助学金？",
                    "audience": "student",
                    "history": [
                        {"role": "user", "content": "我是大学新生。"},
                        {"role": "assistant", "content": "你好。"},
                    ],
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["answer"], "这是测试回答。")

    def test_deepseek_receives_retrieved_chunks_not_full_policy(self):
        fake_client, create = fake_openai_client()
        retriever = get_default_retrieval_service(force_reload=True)

        with patch.dict(
            os.environ,
            {"DEEPSEEK_API_KEY": "test-key", "USE_KNOWLEDGE_RETRIEVAL": "true"},
        ), patch.object(app_module, "OpenAI", return_value=fake_client), patch.object(
            app_module,
            "get_default_retrieval_service",
            return_value=retriever,
        ):
            response = self.client.post(
                "/api/chat",
                json={"message": "助学贷款是不是高利贷？"},
            )

        self.assertEqual(response.status_code, 200)
        prompt = create.call_args.kwargs["messages"][1]["content"]
        self.assertIn("【检索到的相关知识片段】", prompt)
        self.assertIn("国家助学贷款基本说明", prompt)
        self.assertNotIn("2026 年中央财政下达学生资助补助经费超过 1600 亿元", prompt)

        payload = response.get_json()
        self.assertGreater(len(payload["sources"]), 0)
        self.assertEqual(
            payload["sources"][0]["organization"],
            "全国学生资助管理中心",
        )
        self.assertGreater(len(payload["suggested_questions"]), 0)


if __name__ == "__main__":
    unittest.main()
