---
name: wow-pack
description: Generate the Product Brain packets (PRD, RFC and one per epic) as registro packets - Product Brain's exact template shape, real content only where the plan orients the epic, an explicit "No aplica" everywhere else - and verify locally that Product Brain scores them 100% and will not break them. Use before any Product Brain chat or when wow-guide recommends `wow pack`.
---

# wow-pack

Product Brain records the work; it does not plan it. The plan (`wow/plan/`) already carries the decisions, so the
packets only register them in the shape Product Brain and Jira expect.

## Steps

1. Run `wow manifest lint --pb`; fix the manifest first if it reports missing mode, components, stories or Gherkin.
   Check that `wow/plan/PLAN.md` has `- Goal:`, `- Problem:`, `- Constraints:`, `- Non-goals:` and `## Contexto`.
2. Run `wow pack prd`, `wow pack rfc` and `wow pack epic --id E<n>` for each epic.
   PRD and RFC come out complete: nothing to fill. Exit 1 means the packet exists: `--force` regenerates it.
3. Run `wow pack check prd`, `wow pack check rfc` and `wow pack check epic --id E<n>` until each exits 0.
   Besides the predicted %, it fails on what Product Brain breaks or leaks into Jira: context-pack ids (C14, D2),
   "(tarea x.y)" suffixes, list items with commas (Product Brain splits them), and API blocks beyond A, B and C.
   Fix the manifest or the Brief and regenerate; do not hand-edit around a finding.
4. Tell the user to paste `wow/pb/preamble.md` first, then the packet, using model 3.1 Pro.
   Product Brain's answer is reviewed with `wow pbchat audit`, never trusted as is.

## Rules

- Measure, do not speculate: a value you can measure (a count, a time, a commit, a URL, a status) is measured before you state it, and cited. Every repo, branch, commit or URL you hand out must exist and be reachable on the remote's default branch: check it (`wow ref check`). What cannot be measured is labelled as an inference and never presented as a cause.
- IDs defined earlier in the conversation (E1, D10, C14, AC1, WU-005, US-001) get a few-word gloss the first time each message mentions them, e.g. "E2 (cifras del motor al día)": the user must not have to scroll back to know what they are.
- Epic enums and dates still come from `product` in the manifest: an invalid value breaks the Jira export.
- Never rename headings or remove template tables; Product Brain maps fields by structure.
- `--full` (deprecated) emits PRD/RFC with `{{placeholders}}` for an LLM to fill with the legacy prompts
  (references/brownfield-prd.md, references/brownfield-rfc.md, references/greenfield-prd.md,
  references/greenfield-rfc.md). Use it only if an owner asks for a planning-grade PRD or RFC.
  references/epic.md still guides filling the `product` and `story` fields of the manifest.
