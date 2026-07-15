import json
import re
import unittest
from pathlib import Path, PurePosixPath

from services.knowledge_service import KnowledgeService
from services.retrieval_service import RetrievalService


PROJECT_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_ROOT = PROJECT_ROOT / "knowledge"
CATALOG_PATH = KNOWLEDGE_ROOT / "catalog.json"
MIGRATED_SOURCES = {
    "国家资助政策知识库.pdf",
    "惠州本地知识库.pdf",
    "助农知识库.pdf",
    "社区服务知识库.pdf",
    "青年成长知识库 .pdf",
}
MVP_DOMAINS = {"student-aid", "local", "agriculture", "community", "youth"}
REQUIRED_HEADINGS = {
    "# 基本介绍",
    "# 适用对象",
    "# 核心内容",
    "# 办理流程",
    "# 常见问题",
    "# 注意事项",
    "# 来源",
}
ASCII_PATH = re.compile(r"^[a-z0-9/-]+\.md$")


class KnowledgeMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        cls.documents = cls.catalog["documents"]
        cls.migrated = [
            document
            for document in cls.documents
            if document["source_title"] in MIGRATED_SOURCES
        ]
        cls.service = KnowledgeService(CATALOG_PATH)

    def test_all_markdown_paths_exist(self):
        missing = [
            document["file"]
            for document in self.documents
            if not (KNOWLEDGE_ROOT / PurePosixPath(document["file"])).is_file()
        ]
        self.assertEqual(missing, [])

    def test_document_ids_are_unique(self):
        ids = [document["id"] for document in self.documents]
        self.assertEqual(len(ids), len(set(ids)))

    def test_catalog_is_readable_by_knowledge_service(self):
        self.assertEqual(self.service.get_statistics()["errors"], [])

    def test_published_documents_have_sources(self):
        for document in self.documents:
            if document["status"] != "published":
                continue
            self.assertTrue(document["source_title"].strip(), document["id"])
            self.assertTrue(document["source_organization"].strip(), document["id"])

    def test_all_five_mvp_domains_have_documents_and_published_content(self):
        migrated_domains = {document["domain"] for document in self.migrated}
        published_domains = {
            document["domain"]
            for document in self.documents
            if document["status"] == "published"
        }
        self.assertTrue(MVP_DOMAINS.issubset(migrated_domains))
        self.assertTrue(MVP_DOMAINS.issubset(published_domains))

    def test_mvp_domains_have_five_to_ten_migrated_documents(self):
        for domain in MVP_DOMAINS:
            count = sum(document["domain"] == domain for document in self.migrated)
            self.assertGreaterEqual(count, 5, domain)
            self.assertLessEqual(count, 10, domain)

    def test_catalog_paths_use_lowercase_ascii_and_hyphens(self):
        invalid = [
            document["file"]
            for document in self.documents
            if not ASCII_PATH.fullmatch(document["file"])
            or "_" in document["file"]
            or document["file"] != document["file"].lower()
        ]
        self.assertEqual(invalid, [])

    def test_migrated_markdown_has_frontmatter_and_required_sections(self):
        for document in self.migrated:
            text = (KNOWLEDGE_ROOT / document["file"]).read_text(encoding="utf-8")
            self.assertTrue(text.startswith("---\n"), document["file"])
            for heading in REQUIRED_HEADINGS:
                self.assertIn(heading, text, document["file"])

    def test_unconfirmed_specific_policy_documents_stay_draft(self):
        high_risk_draft_ids = {
            "student-aid-student-loan-application-reference",
            "student-aid-military-service-aid-reference",
            "local-huizhou-vocational-college-grant",
            "youth-startup-support-consultation",
        }
        status_by_id = {document["id"]: document["status"] for document in self.documents}
        self.assertEqual(
            {status_by_id[document_id] for document_id in high_risk_draft_ids},
            {"draft"},
        )

    def test_frontmatter_is_not_exposed_as_retrieval_content(self):
        migrated_chunk_text = "\n".join(
            chunk["content"]
            for chunk in self.service.chunks
            if chunk["document_id"].startswith(("local-", "agriculture-", "community-", "youth-"))
        )
        self.assertNotIn("source_organization:", migrated_chunk_text)
        self.assertNotIn("risk_level:", migrated_chunk_text)

    def test_rag_retrieves_each_mvp_domain(self):
        retrieval = RetrievalService(self.service)
        cases = {
            "student-aid": "交不起学费可以走绿色通道吗",
            "local": "惠州本地政策应该去哪里核实",
            "agriculture": "农产品直播带货前要准备什么",
            "community": "老年人不会用手机怎么到社区办事",
            "youth": "高校毕业生求职怎么防骗",
        }
        for expected_domain, question in cases.items():
            results = retrieval.retrieve(question)
            self.assertTrue(results, question)
            self.assertEqual(results[0]["domain"], expected_domain, question)


if __name__ == "__main__":
    unittest.main()
