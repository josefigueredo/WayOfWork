from __future__ import annotations

import unittest

from helpers import make_project, write
from sources import repo

H = "0123456789abcdef"


class ContextPackTest(unittest.TestCase):
    def test_empty_project(self):
        self.assertEqual(repo.context_pack_status(make_project()),
                         {"facts": False, "pending_file": False, "pending_open": 0})

    def test_counts_unchecked_items_only(self):
        project = make_project()
        write(project, "wow/context-pack/facts.md", "# Facts\n")
        write(project, "wow/context-pack/pending-owner.md",
              "- [ ] North Star\n- [x] SLA: [SIN DEFINIR] (accepted)\n  - [ ] rollout\n")
        self.assertEqual(repo.context_pack_status(project),
                         {"facts": True, "pending_file": True, "pending_open": 2})


class PacketTest(unittest.TestCase):
    def test_ok_stale_missing(self):
        project = make_project()
        write(project, "wow/pb/prd.md", f"<!-- wow: manifest-hash={H} -->\n# PRD\n")
        write(project, "wow/pb/rfc.md", "<!-- wow: manifest-hash=ffffffffffffffff -->\n")
        write(project, "wow/pb/epic-E1.md", f"<!-- wow: manifest-hash={H} -->\n")
        self.assertEqual(repo.packet_status(project, H, ["E1", "E2"]),
                         {"prd": "ok", "rfc": "stale", "epics": {"E1": "ok", "E2": "missing"}})


if __name__ == "__main__":
    unittest.main()
