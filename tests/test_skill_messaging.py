from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def frontmatter(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return ""
    parts = text.split("---", 2)
    block = parts[1] if len(parts) >= 3 else ""
    # Collapse whitespace so phrases that wrap across lines in a folded YAML
    # scalar (description: >) still match as contiguous substrings.
    return re.sub(r"\s+", " ", block)


class SkillMessagingTests(unittest.TestCase):
    def test_core_skill_description_markets_power_platform_development(self) -> None:
        # The top-level SKILL.md pointer and the orchestrator skill both carry the
        # marketing description as a folded YAML scalar, so assert against the
        # whole frontmatter block rather than a single line.
        for skill_path in (
            REPO_ROOT / "SKILL.md",
            REPO_ROOT / "skills" / "powerplatform-core" / "SKILL.md",
        ):
            fm = frontmatter(skill_path)
            self.assertIn("Microsoft Power Platform", fm, msg=str(skill_path))
            self.assertIn("Dataverse", fm, msg=str(skill_path))
            self.assertIn("plug-ins", fm, msg=str(skill_path))
            self.assertIn("PCF controls", fm, msg=str(skill_path))
        # The top-level pointer specifically positions Core as a coding-agent skill.
        self.assertIn("coding-agent skill", frontmatter(REPO_ROOT / "SKILL.md"))

    def test_core_readme_markets_the_plugin(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        lowered = readme.lower()
        self.assertIn("Microsoft Power Platform", readme)
        self.assertIn("Dataverse", readme)
        self.assertIn("coding-agent", lowered)
        self.assertIn("preflight", lowered)
        self.assertIn("## Install", readme)
        self.assertIn("## The skills", readme)

    def test_command_bar_guidance_prefers_javascript_rules(self) -> None:
        schema_skill = (REPO_ROOT / "skills" / "dataverse-schema" / "SKILL.md").read_text(encoding="utf-8")
        client_reference = (REPO_ROOT / "references" / "client-customization.md").read_text(encoding="utf-8")
        execution_reference = (REPO_ROOT / "references" / "execution-automation.md").read_text(encoding="utf-8")

        # The JavaScript-CustomRule-over-XML-ValueRule guidance now lives in the
        # client-facing domain skill, while the reference files keep the canonical detail.
        self.assertIn("JavaScript `CustomRule`", schema_skill)
        self.assertIn("ValueRule", schema_skill)
        self.assertIn("Avoid XML `ValueRule`", client_reference)
        self.assertIn("do not try the form-ribbon helper first", client_reference)
        self.assertIn("RibbonDiffXml Recovery Path", execution_reference)
        self.assertIn("10-30 minute duration window", execution_reference)
        self.assertIn("bump version before import", execution_reference)


if __name__ == "__main__":
    unittest.main()
