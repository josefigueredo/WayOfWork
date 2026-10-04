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


DOC_PACKET = """<!-- wow: manifest-hash=0123456789abcdef -->
## Riesgos
| Riesgo | Mitigacion |
| --- | --- |
| No aplica | No aplica |

## SLA
No aplica: registro.
"""
DOC_FINAL = """## Riesgos
| Riesgo   | Mitigacion |
|---|---|
| No aplica | No aplica |
| Caída del agente | Circuit breaker con reintentos |

## SLA
99.9% mensual.
"""


class DocChangesTest(unittest.TestCase):
    def test_only_what_product_brain_added_or_removed_by_section(self):
        project = make_project()
        write(project, "wow/pb/rfc.md", DOC_PACKET)
        write(project, "wow/pb/chats/rfc.final.md", DOC_FINAL)
        changes = pbaudit.doc_changes(project, "rfc")
        self.assertEqual(changes, [
            {"op": "+", "section": "Riesgos", "text": "| Caída del agente | Circuit breaker con reintentos |"},
            {"op": "-", "section": "SLA", "text": "No aplica: registro."},
            {"op": "+", "section": "SLA", "text": "99.9% mensual."}])

    def test_no_final_copy_means_no_changes_to_show(self):
        project = make_project()
        write(project, "wow/pb/rfc.md", DOC_PACKET)
        self.assertIsNone(pbaudit.doc_changes(project, "rfc"))

    def test_audit_carries_the_changes(self):
        project = make_project()
        write(project, "wow/pb/rfc.md", DOC_PACKET)
        write(project, "wow/pb/chats/rfc.md", "Product Brain: listo.\n")
        write(project, "wow/pb/chats/rfc.final.md", DOC_PACKET.split("\n", 1)[1])
        self.assertEqual(pbaudit.audit(project, "rfc")["pb_changes"], [])


API_PACKET = """<!-- wow -->
### Especificaciones de API (Contrato)

#### A. Sin endpoints nuevos
- Endpoint: `No aplica`
- Descripcion: el sitio no expone API
- Request:
No aplica
- Response:
No aplica

### Modelo de Datos
No aplica
"""
# What Product Brain left in its panel in the IRIS pilot: A-C untouched, the content appended as D (uncounted).
API_FINAL = """### Especificaciones de API (Contrato)

#### A. {{api_a_name}}
- Endpoint: `{{api_a_endpoint}}`
- Descripcion: {{api_a_description}}

#### D. Sin endpoints nuevos
- Endpoint: `No aplica`

### Modelo de Datos
No aplica
"""


class EditorFixTest(unittest.TestCase):
    def test_a_section_left_with_placeholders_gets_the_packet_section_to_paste(self):
        project = make_project()
        write(project, "wow/pb/rfc.md", API_PACKET)
        write(project, "wow/pb/chats/rfc.final.md", API_FINAL)
        [fix] = pbaudit.editor_fixes(project, "rfc")
        self.assertEqual(fix["section"], "### Especificaciones de API (Contrato)")
        self.assertIn("#### A. Sin endpoints nuevos", fix["replace_with"])
        self.assertNotIn("{{", fix["replace_with"])
        self.assertNotIn("#### D.", fix["replace_with"])
        self.assertIn("placeholder", fix["reason"])

    def test_no_fix_when_the_panel_kept_the_packet(self):
        project = make_project()
        write(project, "wow/pb/rfc.md", API_PACKET)
        write(project, "wow/pb/chats/rfc.final.md", API_PACKET.split("\n", 1)[1])
        self.assertEqual(pbaudit.editor_fixes(project, "rfc"), [])

    def test_cli_prints_the_fix_with_only_the_panel_copy(self):
        from helpers import run_cli
        project = make_project()
        write(project, "wow/pb/rfc.md", API_PACKET)
        write(project, "wow/pb/chats/rfc.final.md", API_FINAL)
        code, out, _ = run_cli(["pbchat", "audit", "rfc", "--project", str(project)])
        self.assertEqual(code, 1)
        self.assertIn('replace the section "### Especificaciones de API (Contrato)"', out)
        self.assertIn("#### A. Sin endpoints nuevos", out)


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


class NegationScopeTest(unittest.TestCase):
    def test_negation_only_covers_its_own_clause(self):
        result = pbaudit.audit(setup(chat="No hay API Gateway; agregar Okta como IdP.\n"), "prd")
        self.assertEqual([i["term"] for i in result["inventions"]], ["Okta"])


class TemplateAwareAuditTest(unittest.TestCase):
    def test_template_heading_and_negation_do_not_whitelist(self):
        packet = "### API Gateway\n| Tecnologia | No aplica: no hay API Gateway |\n### SLA\n[SIN DEFINIR] — no hay SLA acordado\n"
        project = make_project()
        write(project, "wow/pb/rfc.md", packet)
        write(project, "wow/pb/chats/rfc.md", "Usamos Kong como API Gateway con circuit breaker y un SLA de 99,9%.\n")
        terms = [i["term"] for i in pbaudit.audit(project, "rfc")["inventions"]]
        self.assertEqual(terms, ["API Gateway", "SLA", "circuit breaker", "Kong"])

    def test_template_headings_in_the_chat_are_not_affirmations(self):
        project = make_project()
        write(project, "wow/pb/rfc.md", "### API Gateway\n| Tecnologia | No aplica: sitio estático |\n")
        chat = "### API Gateway\n| Tecnologia | No aplica: sitio estático |\n### SLA\nNo aplica: sin acuerdo.\n"
        write(project, "wow/pb/chats/rfc.md", chat)
        self.assertEqual(pbaudit.audit(project, "rfc")["inventions"], [])

    def test_authoritative_completion_wins(self):
        project = make_project()
        write(project, "wow/pb/chats/prd.md", "El PRD llega al 100%.\n**Completitud del documento:** 96% · Pendiente: Metadata\n")
        self.assertEqual(pbaudit.audit(project, "prd")["completion_pct"], 96)


if __name__ == "__main__":
    unittest.main()
