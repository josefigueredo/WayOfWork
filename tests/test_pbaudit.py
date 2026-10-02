from __future__ import annotations

import json
import unittest

from helpers import make_project, write
import pack
import pbaudit
import schema

PACKET = "<!-- wow: manifest-hash=0123456789abcdef -->\n### H1\n  - AC1: schema exists\n  - AC2: audit row\n- E1.C1: done\n"
CHAT = pack.PREAMBLE + """
Product Brain: Completé el documento. El PRD llega al 100%.
- AC1: schema exists
- E1.C1: done
La plataforma funciona como un marketplace con comprador y vendedor.
Jose: no hay API Gateway, corregilo.
✅ Los KPIs están documentados.
✅ El alcance está explícito (sección Alcance).

## 15. Preguntas abiertas

1. ¿Se incorpora la etapa de plan
   a la máquina de estados?
2. ¿Qué North Star define el owner?

Product Brain: ¿Querés profundizar?
"""


def setup(chat=CHAT, context=""):
    project = make_project()
    write(project, "wow/pb/prd.md", PACKET)
    write(project, "wow/pb/chats/prd.md", chat)
    if context:
        write(project, "wow/context-pack/facts.md", context)
    return project


class AuditTest(unittest.TestCase):
    def test_full_audit(self):
        result = pbaudit.audit(setup(), "prd")
        self.assertEqual(schema.validate(result, schema.load_schema("pbchat-audit")), [])
        self.assertEqual(result["verdict"], "changes_required")
        self.assertTrue(result["closed"])
        self.assertEqual(result["completion_pct"], 100)
        self.assertEqual(result["expected_anchors"], ["AC1", "AC2", "E1.C1"])
        self.assertEqual(result["missing_anchors"], ["AC2"])
        self.assertEqual([i["term"] for i in result["inventions"]], ["marketplace", "comprador/vendedor"])
        self.assertEqual([c["text"] for c in result["unsupported_checks"]], ["✅ Los KPIs están documentados."])
        self.assertEqual(result["open_questions"],
                         ["¿Se incorpora la etapa de plan a la máquina de estados?", "¿Qué North Star define el owner?"])
        self.assertIn("AC2", result["corrections_to_paste"])
        self.assertIn("regla 4", result["corrections_to_paste"])

    def test_preamble_and_negations_are_not_inventions(self):
        result = pbaudit.audit(setup(chat=pack.PREAMBLE + "\nJose: no hay API Gateway y no es Okta.\n"), "prd")
        self.assertEqual(result["inventions"], [])

    def test_terms_in_context_pack_are_allowed(self):
        project = setup(context="- C1: IRIS es un marketplace interno con comprador y vendedor [MEDIDO] (fuente: README.md)\n")
        self.assertEqual(pbaudit.audit(project, "prd")["inventions"], [])

    def test_clean_chat_is_approved_without_corrections(self):
        chat = "Product Brain: llega al 100%\n- AC1: x\n- AC2: y\n- E1.C1: z\n"
        result = pbaudit.audit(setup(chat=chat), "prd")
        self.assertEqual((result["verdict"], result["corrections_to_paste"]), ("approved", ""))

    def test_missing_chat_raises_and_write_audit(self):
        project = make_project()
        with self.assertRaises(FileNotFoundError):
            pbaudit.audit(project, "rfc")
        result = pbaudit.audit(setup(), "prd")
        path = pbaudit.write_audit(make_project(), result)
        self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["doc"], "prd")


class DeepAuditTest(unittest.TestCase):
    def test_parse_inventions_and_verdict_required(self):
        text = "VERDICT: CHANGES_REQUIRED\nINVENTION 12 — North Star del 30% — no figura en el contexto\n"
        self.assertEqual(pbaudit.parse_inventions(text), [
            {"term": "North Star del 30%", "line": 12, "text": "no figura en el contexto", "source": "reviewer"}])
        import review
        with self.assertRaises(review.ReviewOutputError):
            pbaudit.parse_inventions("no verdict here")

    def test_prompt_excludes_preamble_and_numbers_chat(self):
        prompt = pbaudit.build_deep_prompt(setup(), "prd")
        self.assertNotIn("Reglas para este documento", prompt.split("--- CHAT")[1])
        self.assertIn("marketplace", prompt)
        self.assertRegex(prompt, r"\n\d+: ")


if __name__ == "__main__":
    unittest.main()
