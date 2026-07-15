import io
import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import app as app_module


class HuixinAssistantTests(unittest.TestCase):
    def setUp(self):
        app_module.app.config.update(TESTING=True)
        self.client = app_module.app.test_client()

    def test_homepage_uses_official_huimango_assets_and_disables_unconfigured_vision(self):
        with patch.dict(
            os.environ,
            {"VISION_API_KEY": "", "VISION_BASE_URL": "", "VISION_MODEL": ""},
        ):
            response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn("你好，我是惠芒go", page)
        self.assertIn("images/huimango-hero.png", page)
        self.assertIn("images/huimango-avatar.png", page)
        self.assertIn("暂未配置", page)
        self.assertIn('href="#questions"', page)
        self.assertIn("诚信还款专题", page)

    def test_topic_and_unknown_topic(self):
        self.assertEqual(self.client.get("/topic/admission").status_code, 200)
        self.assertEqual(self.client.get("/topic/not-found").status_code, 404)

    def test_chat_input_validation(self):
        empty = self.client.post("/api/chat", json={"message": ""})
        too_long = self.client.post("/api/chat", json={"message": "问" * 501})
        private = self.client.post("/api/chat", json={"message": "我的手机号是13800138000"})

        self.assertIn("请输入", empty.get_json()["answer"])
        self.assertIn("问题过长", too_long.get_json()["answer"])
        self.assertIn("保护个人隐私", private.get_json()["answer"])

    def test_chat_disables_thinking_and_returns_answer(self):
        response_payload = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="这是测试回答。"))]
        )
        create = Mock(return_value=response_payload)
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create))
        )

        with patch.dict(
            os.environ,
            {
                "DEEPSEEK_API_KEY": "test-key",
                "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
                "DEEPSEEK_MODEL": "deepseek-v4-flash",
            },
        ), patch.object(app_module, "OpenAI", return_value=fake_client):
            response = self.client.post("/api/chat", json={"message": "什么是绿色通道？"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["answer"], "这是测试回答。")
        request_args = create.call_args.kwargs
        self.assertEqual(request_args["extra_body"], {"thinking": {"type": "disabled"}})
        self.assertEqual(request_args["model"], "deepseek-v4-flash")

    def test_chat_api_error_is_safe(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}), patch.object(
            app_module, "OpenAI", side_effect=RuntimeError("secret backend detail")
        ):
            response = self.client.post("/api/chat", json={"message": "我能申请助学贷款吗？"})

        self.assertEqual(response.status_code, 503)
        self.assertIn("暂时无法连接", response.get_json()["answer"])
        self.assertNotIn("secret", response.get_data(as_text=True))

    def test_image_analysis_requires_explicit_vision_model(self):
        with patch.dict(
            os.environ,
            {"VISION_API_KEY": "", "VISION_BASE_URL": "", "VISION_MODEL": ""},
        ):
            response = self.client.post(
                "/api/analyze-image",
                data={"image": (io.BytesIO(b"not-a-real-image"), "notice.png")},
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 503)
        self.assertIn("图片识别功能尚未配置", response.get_json()["answer"])


if __name__ == "__main__":
    unittest.main()
