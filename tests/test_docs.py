"""The docs are what a new install reads: every relative link, image and anchor lands, and the index covers every skill."""
from __future__ import annotations

import re
import unittest

from pathlib import Path

from helpers import ROOT

DOCS = ROOT / "docs"
PAGES = [ROOT / "README.md", DOCS / "instalacion.md", DOCS / "instalacion-detallada.md", DOCS / "showcase.md", DOCS / "referencia.md"]
SKILLS = sorted(p.name for p in (ROOT / "skills").iterdir() if (p / "SKILL.md").is_file())


def slug(heading: str) -> str:
    """GitHub's anchor for a heading: lowercase, punctuation dropped, spaces to hyphens."""
    text = re.sub(r"[^\w\- ]", "", heading.strip().lower())
    return text.replace(" ", "-")


def anchors(path: Path) -> set:
    return {slug(m.group(2)) for m in re.finditer(r"^(#{1,6}) (.+)$", path.read_text(encoding="utf-8"), re.M)}


class DocsTest(unittest.TestCase):
    def test_every_page_exists(self):
        for page in PAGES:
            self.assertTrue(page.is_file(), f"{page} is missing")

    def test_every_relative_link_and_image_lands_on_a_file_and_an_anchor(self):
        link = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)\)")
        for page in PAGES:
            for target in link.findall(page.read_text(encoding="utf-8")):
                if re.match(r"[a-z]+:", target):  # https:, mailto:
                    continue
                path, _, fragment = target.partition("#")
                dest = (page.parent / path).resolve() if path else page
                self.assertTrue(dest.exists(), f"{page.name} links to {target}, which does not exist")
                if fragment and dest.suffix == ".md":
                    self.assertIn(fragment, anchors(dest), f"{page.name} links to {target}: no such heading")

    def test_the_index_links_each_skill_to_the_showcase_and_the_install_guide(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertEqual(len(SKILLS), 7)
        for skill in SKILLS:
            rows = [line for line in readme.splitlines() if line.startswith(f"| **`{skill}`**")]
            self.assertEqual(len(rows), 1, f"README has no index row for {skill}")
            self.assertIn("docs/showcase.md#", rows[0])
            self.assertIn("docs/instalacion.md#", rows[0])

    def test_the_showcase_table_lists_each_skill(self):
        showcase = (DOCS / "showcase.md").read_text(encoding="utf-8")
        for skill in SKILLS:
            self.assertIn(f"| `{skill}` |", showcase)

    def test_the_docs_name_the_jira_variables_the_code_reads(self):
        # config.resolve_jira_credentials reads IC_JIRA_* from the shell and .env.local; the docs must not tell a new
        # install to set variables wow does not read there
        for page in (DOCS / "instalacion.md", DOCS / "instalacion-detallada.md"):
            text = page.read_text(encoding="utf-8")
            for name in ("IC_JIRA_BASE_URL", "IC_JIRA_USER_EMAIL", "IC_JIRA_API_TOKEN"):
                self.assertIn(name, text, f"{page.name} does not name {name}")

    def test_every_image_has_its_html_source(self):
        for png in (DOCS / "img").glob("*.png"):
            self.assertTrue((DOCS / "img" / "src" / (png.stem + ".html")).is_file(), f"{png.name} has no source in img/src")


if __name__ == "__main__":
    unittest.main()
