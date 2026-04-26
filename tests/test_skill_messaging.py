from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class SkillMessagingTests(unittest.TestCase):
    def test_core_skill_description_markets_power_platform_development(self) -> None:
        skill_text = (REPO_ROOT / "SKILL.md").read_text(encoding="utf-8")
        description = re.search(r"description:\s*(.+)", skill_text)

        self.assertIsNotNone(description)
        description_text = description.group(1)
        self.assertIn("Microsoft Power Platform and Dataverse development", description_text)
        self.assertIn("coding-agent skill", description_text)
        self.assertIn("plug-ins", description_text)
        self.assertIn("PCF controls", description_text)

    def test_core_readme_opens_with_plain_english_value(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn(
            "PowerPlatform-Core is a coding-agent skill for Microsoft Power Platform and Dataverse development.",
            readme,
        )
        self.assertIn("## How It Works", readme)
        self.assertIn("discover repo context", readme.lower())
        self.assertIn("approved targeted paths", readme.lower())


if __name__ == "__main__":
    unittest.main()
