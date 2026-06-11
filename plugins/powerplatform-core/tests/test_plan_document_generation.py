from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import plan_document_generation  # type: ignore


DOCUMENT_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:sdt>
      <w:sdtPr>
        <w:alias w:val="DocumentTitle" />
        <w:tag w:val="DocumentTitle" />
        <w:text />
      </w:sdtPr>
      <w:sdtContent>
        <w:p><w:r><w:t>Example Title</w:t></w:r></w:p>
      </w:sdtContent>
    </w:sdt>
  </w:body>
</w:document>
"""


class PlanDocumentGenerationTests(unittest.TestCase):
    def test_build_document_plan_maps_existing_controls_and_flags_missing_required_ones(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            (repo / "Word Templates").mkdir()
            (repo / "Contoso.Sample.Business").mkdir()
            (repo / "Contoso.Sample.Plugins").mkdir()
            (repo / "Contoso.Sample.Data").mkdir()
            template_path = repo / "Word Templates" / "NotificationTemplate.docx"
            with zipfile.ZipFile(template_path, "w") as archive:
                archive.writestr("word/document.xml", DOCUMENT_XML)

            payload = plan_document_generation.build_document_plan(
                {
                    "path": "Word Templates",
                    "templateName": "NotificationTemplate.docx",
                    "placeholderMappings": [
                        {"tag": "DocumentTitle", "source": "ec_title"},
                        {"tag": "MissingTag", "source": "ec_missing", "required": True},
                    ],
                },
                repo,
            )

            self.assertEqual(payload["documentCount"], 1)
            self.assertEqual(payload["riskLevel"], "high")
            self.assertEqual(payload["sourceAreas"]["wordTemplates"], "Word Templates")
            document = payload["documents"][0]
            self.assertEqual(document["missingRequiredCount"], 1)
            self.assertEqual(document["mappedPlaceholders"][0]["tag"], "DocumentTitle")


if __name__ == "__main__":
    unittest.main()
