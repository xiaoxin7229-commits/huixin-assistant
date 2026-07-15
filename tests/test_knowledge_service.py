import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from services.knowledge_service import KnowledgeService


class KnowledgeServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)

    def base_document(self, **overrides):
        document = {
            "id": "student-aid-test",
            "title": "测试知识",
            "file": "student-aid/test-document.md",
            "domain": "student-aid",
            "audiences": ["student", "parent"],
            "region": "全国",
            "keywords": ["测试", "资助"],
            "source_title": "测试来源",
            "source_organization": "测试机构",
            "source_url": "https://example.com/source",
            "source_date": "2026-01-01",
            "updated_at": "2026-07-14",
            "reviewed_at": "2026-07-14",
            "status": "published",
            "risk_level": "verify-officially",
            "suggested_questions": ["推荐问题是什么？"],
        }
        document.update(overrides)
        return document

    def write_markdown(self, relative_path, content="# 测试\n\n## 第一节\n\n正文。"):
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def write_catalog(self, documents):
        path = self.root / "catalog.json"
        path.write_text(
            json.dumps({"version": "1.0", "documents": documents}, ensure_ascii=False),
            encoding="utf-8",
        )
        return path

    def build_service(self, documents, markdown=None):
        for document in documents:
            file_value = document.get("file")
            if file_value and markdown is not False:
                self.write_markdown(file_value, markdown or "# 测试\n\n## 第一节\n\n正文。")
        return KnowledgeService(self.write_catalog(documents))

    def test_catalog_loads_normally(self):
        service = self.build_service([self.base_document()])

        self.assertEqual(service.get_statistics()["errors"], [])
        self.assertEqual(len(service.documents), 1)

    def test_duplicate_id_is_detected(self):
        first = self.base_document()
        second = deepcopy(first)
        second["file"] = "student-aid/second-document.md"
        self.write_markdown(first["file"])
        self.write_markdown(second["file"])
        service = KnowledgeService(self.write_catalog([first, second]))

        self.assertTrue(any("duplicate id" in error for error in service.get_statistics()["errors"]))
        self.assertEqual(len(service.published_documents), 1)

    def test_missing_file_is_detected(self):
        service = KnowledgeService(self.write_catalog([self.base_document()]))

        self.assertTrue(any("file does not exist" in error for error in service.get_statistics()["errors"]))

    def test_invalid_domain_is_detected(self):
        service = self.build_service([self.base_document(domain="unknown-domain")])

        self.assertTrue(any("invalid domain" in error for error in service.get_statistics()["errors"]))

    def test_invalid_audience_is_detected(self):
        service = self.build_service([self.base_document(audiences=["student", "unknown"])])

        self.assertTrue(any("invalid audiences" in error for error in service.get_statistics()["errors"]))

    def test_invalid_status_is_detected(self):
        service = self.build_service([self.base_document(status="reviewing")])

        self.assertTrue(any("invalid status" in error for error in service.get_statistics()["errors"]))

    def test_draft_document_is_not_available(self):
        service = self.build_service([self.base_document(status="draft")])

        self.assertEqual(service.get_statistics()["draft"], 1)
        self.assertEqual(len(service.published_documents), 0)
        self.assertEqual(len(service.chunks), 0)

    def test_archived_document_is_not_available(self):
        service = self.build_service([self.base_document(status="archived")])

        self.assertEqual(service.get_statistics()["archived"], 1)
        self.assertEqual(len(service.published_documents), 0)
        self.assertEqual(len(service.chunks), 0)

    def test_published_document_loads(self):
        service = self.build_service([self.base_document()])

        self.assertEqual(len(service.published_documents), 1)
        self.assertGreater(len(service.chunks), 0)

    def test_chinese_level_two_and_three_headings_are_split_naturally(self):
        markdown = """# 测试文档

文档说明。

## 二级标题

二级正文。

### 三级标题

三级正文。
"""
        service = self.build_service([self.base_document()], markdown=markdown)

        section_titles = [chunk["section_title"] for chunk in service.chunks]
        self.assertEqual(section_titles, ["测试文档", "二级标题", "三级标题"])
        self.assertEqual(service.chunks[0]["heading_level"], 1)
        self.assertEqual(service.chunks[1]["heading_level"], 2)
        self.assertEqual(service.chunks[2]["heading_level"], 3)

    def test_empty_markdown_does_not_crash(self):
        document = self.base_document()
        self.write_markdown(document["file"], "")
        service = KnowledgeService(self.write_catalog([document]))

        stats = service.get_statistics()
        self.assertEqual(stats["errors"], [])
        self.assertEqual(stats["available_documents"], 1)
        self.assertEqual(stats["available_chunks"], 0)
        self.assertTrue(any("is empty" in warning for warning in stats["warnings"]))

    def test_statistics_are_correct(self):
        documents = [
            self.base_document(id="published", file="student-aid/published.md"),
            self.base_document(id="draft", file="student-aid/draft.md", status="draft"),
            self.base_document(id="archived", file="student-aid/archived.md", status="archived"),
        ]
        service = self.build_service(documents)

        stats = service.get_statistics()
        self.assertEqual(stats["total_documents"], 3)
        self.assertEqual(stats["published"], 1)
        self.assertEqual(stats["draft"], 1)
        self.assertEqual(stats["archived"], 1)
        self.assertEqual(stats["available_documents"], 1)
        self.assertEqual(stats["available_chunks"], 1)

    def test_empty_source_url_is_not_fabricated(self):
        service = self.build_service(
            [self.base_document(source_url="", status="draft")]
        )

        self.assertEqual(service.documents[0]["source_url"], "")
        self.assertTrue(
            any("no URL was generated" in warning for warning in service.get_statistics()["warnings"])
        )

    def test_current_student_aid_documents_all_load(self):
        project_catalog = Path(__file__).resolve().parents[1] / "knowledge" / "catalog.json"
        service = KnowledgeService(project_catalog)
        expected_ids = {
            "student-aid-overview",
            "student-aid-scholarships-and-grants",
            "student-aid-student-loans",
            "student-aid-green-channel",
            "student-aid-hardship-assessment",
            "student-aid-repayment-and-credit",
        }
        loaded_ids = {document["id"] for document in service.published_documents}

        self.assertEqual(service.get_statistics()["errors"], [])
        self.assertTrue(expected_ids.issubset(loaded_ids))


if __name__ == "__main__":
    unittest.main()
