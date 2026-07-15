import json
import re
import unittest
from pathlib import Path

from services.knowledge_service import KnowledgeService
from services.retrieval_service import RetrievalService


PROJECT_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_ROOT = PROJECT_ROOT / "knowledge"
CATALOG_PATH = KNOWLEDGE_ROOT / "catalog.json"
NEW_DOCUMENT_IDS = {
    "student-aid-source-based-student-loans",
    "student-aid-guangdong-student-aid",
    "student-aid-application-process",
    "student-aid-terminology",
    "student-aid-official-contacts",
    "student-aid-faq",
}


class StudentAidKnowledgeV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        cls.documents = {item["id"]: item for item in cls.catalog["documents"]}
        cls.service = KnowledgeService(CATALOG_PATH)
        cls.retriever = RetrievalService(cls.service)

    def test_new_documents_are_cataloged_and_loadable(self):
        self.assertTrue(NEW_DOCUMENT_IDS.issubset(self.documents))
        self.assertEqual(self.service.get_statistics()["errors"], [])
        for document_id in NEW_DOCUMENT_IDS:
            document = self.documents[document_id]
            self.assertEqual(document["status"], "published")
            self.assertTrue(document["source_title"])
            self.assertTrue(document["source_organization"])
            self.assertTrue(document["source_url"].startswith("https://"))
            self.assertTrue((KNOWLEDGE_ROOT / document["file"]).is_file())

    def test_faq_contains_exactly_one_hundred_numbered_questions(self):
        faq = (KNOWLEDGE_ROOT / "student-aid" / "faq.md").read_text(encoding="utf-8")
        questions = re.findall(r"^### (\d+)\.", faq, flags=re.MULTILINE)
        self.assertEqual(questions, [str(number) for number in range(1, 101)])

    def test_oral_and_local_questions_retrieve_expected_documents(self):
        cases = {
            "家庭经济困难没钱上学怎么办": "student-aid",
            "广东学生资助政策有哪些": "student-aid-guangdong-student-aid",
            "95593是什么电话": "student-aid-official-contacts",
            "首次申请需要什么材料": "student-aid-application-process",
        }
        for question, expected in cases.items():
            results = self.retriever.retrieve(question)
            self.assertTrue(results, question)
            if expected == "student-aid":
                self.assertEqual(results[0]["domain"], expected)
            else:
                self.assertEqual(results[0]["document_id"], expected)

    def test_student_aid_retrieval_includes_answer_guidance(self):
        results = self.retriever.retrieve("95593是什么电话")
        self.assertIn("【回答规范】", results[0]["content"])
        self.assertIn("【政策解读】", results[0]["content"])

    def test_non_student_aid_result_does_not_include_student_aid_guidance(self):
        results = self.retriever.retrieve("农产品直播带货要准备什么")
        self.assertTrue(results)
        self.assertNotIn("【回答规范】", results[0]["content"])


if __name__ == "__main__":
    unittest.main()

