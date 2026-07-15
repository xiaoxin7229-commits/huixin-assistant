import unittest
from pathlib import Path
from unittest.mock import patch

import app as app_module


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class TextToSpeechTests(unittest.TestCase):
    def setUp(self):
        app_module.app.config.update(TESTING=True)
        self.client = app_module.app.test_client()

    def test_three_supported_languages_return_mp3(self):
        for language in ("zh-CN", "zh-HK", "en-US"):
            with self.subTest(language=language), patch.object(
                app_module, "synthesize_speech", return_value=b"ID3-test-audio"
            ) as synthesize:
                response = self.client.post(
                    "/api/tts",
                    json={"text": "惠芒go语音测试", "language": language},
                )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.mimetype, "audio/mpeg")
            self.assertEqual(response.headers["X-TTS-Provider"], "edge-tts")
            self.assertIn("no-store", response.headers["Cache-Control"])
            synthesize.assert_called_once_with("惠芒go语音测试", language)

    def test_tts_validates_empty_long_and_unknown_language(self):
        empty = self.client.post("/api/tts", json={"text": "", "language": "zh-CN"})
        too_long = self.client.post(
            "/api/tts",
            json={"text": "问" * (app_module.MAX_TTS_TEXT_LENGTH + 1), "language": "zh-CN"},
        )
        unknown = self.client.post(
            "/api/tts", json={"text": "测试", "language": "fr-FR"}
        )

        self.assertEqual(empty.status_code, 400)
        self.assertEqual(too_long.status_code, 400)
        self.assertEqual(unknown.status_code, 400)
        self.assertTrue(empty.get_json()["fallback"])
        self.assertTrue(too_long.get_json()["fallback"])
        self.assertTrue(unknown.get_json()["fallback"])

    def test_tts_failure_returns_safe_fallback_signal(self):
        with patch.object(
            app_module, "synthesize_speech", side_effect=RuntimeError("backend detail")
        ):
            response = self.client.post(
                "/api/tts", json={"text": "测试朗读", "language": "zh-CN"}
            )

        self.assertEqual(response.status_code, 503)
        self.assertTrue(response.get_json()["fallback"])
        self.assertIn("设备自带语音", response.get_json()["error"])
        self.assertNotIn("backend detail", response.get_data(as_text=True))

    def test_frontend_uses_cloud_tts_with_browser_fallback_and_smooth_scroll(self):
        script = (PROJECT_ROOT / "static" / "script.js").read_text(encoding="utf-8")

        self.assertIn('fetch("/api/tts"', script)
        self.assertIn("speakWithBrowser(text)", script)
        self.assertIn('behavior: "smooth"', script)
        self.assertIn("scrollChatIntoView();", script)

    def test_render_requirements_pin_edge_tts(self):
        requirements = (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8")

        self.assertIn("edge-tts==7.2.8", requirements)


if __name__ == "__main__":
    unittest.main()
