from __future__ import annotations

import unittest

from helpers import make_project, write
from sources import pbchat


class ParseTest(unittest.TestCase):
    def test_closed_by_hundred_percent(self):
        self.assertTrue(pbchat.parse_chat("Con esto, el PRD llega al 100%.")["closed"])

    def test_closed_by_phrase(self):
        self.assertTrue(pbchat.parse_chat("Jose: dalo por cerrado")["closed"])
        self.assertTrue(pbchat.parse_chat("¡Perfecto! Damos por cerrado el PRD")["closed"])

    def test_open_chat(self):
        self.assertFalse(pbchat.parse_chat("Completamos 60% del documento")["closed"])

    def test_anchors_unique_sorted(self):
        text = "AC2: x\nAC1: y\nE1.C1: done\nAC1 again"
        self.assertEqual(pbchat.parse_chat(text)["anchors"], ["AC1", "AC2", "E1.C1"])


class StatusTest(unittest.TestCase):
    def test_missing_chat(self):
        self.assertEqual(pbchat.chat_status(make_project(), "prd"),
                         {"present": False, "closed": False, "audit": None})

    def test_chat_with_audit(self):
        project = make_project()
        write(project, "wow/pb/chats/prd.md", "... llega al 100%")
        write(project, "wow/pb/chats/prd.audit.json", '{"verdict": "approved"}')
        self.assertEqual(pbchat.chat_status(project, "prd"), {"present": True, "closed": True, "audit": "approved"})

    def test_unparseable_audit_is_unknown(self):
        project = make_project()
        write(project, "wow/pb/chats/rfc.md", "open")
        write(project, "wow/pb/chats/rfc.audit.json", "{nope")
        self.assertEqual(pbchat.chat_status(project, "rfc")["audit"], "unknown")


class ClosureTest(unittest.TestCase):
    def test_bare_hundred_percent_does_not_close(self):
        self.assertFalse(pbchat.parse_chat("Requerimos 100% de disponibilidad")["closed"])
        self.assertTrue(pbchat.parse_chat("**Completitud del documento:** 100% (documento completo).")["closed"])


if __name__ == "__main__":
    unittest.main()
