---
name: wow-pack
description: Generate the Product Brain packets (PRD, RFC and one per epic) in the exact shape of Product Brain's templates, fill their {{placeholders}} with the mode's prompt, and verify locally that Product Brain will score them 100%. Use before any Product Brain chat or when wow-guide recommends `wow pack`.
---

# wow-pack

## Steps

1. Run `wow manifest lint --pb`; fix the manifest first if it reports missing mode, components, stories or Gherkin.
2. Run `wow pack prd`, `wow pack rfc` and `wow pack epic --id E<n>` for each epic.
   Exit 1 means the packet exists: only use `--force` if you accept losing filled fields.
3. Fill every `{{placeholder}}` following the prompt for the plan mode (plan.mode in wow/plan/manifest.json):
   - brownfield: references/brownfield-prd.md, references/brownfield-rfc.md
   - greenfield: references/greenfield-prd.md, references/greenfield-rfc.md
   - every epic: references/epic.md
4. Run `wow pack check prd`, `wow pack check rfc` and `wow pack check epic --id E<n>` until each exits 0.
   The prediction uses Product Brain's own completion rules (reference/product-brain/README.md).
5. Tell the user to paste `wow/pb/preamble.md` first, then the packet, using model 3.1 Pro; for the RFC,
   index or attach the repositories in Product Brain so it verifies contracts against code.

## Rules

- Unknown text fields: `[SIN DEFINIR] — <what is missing and who decides>`, plus an open-question row.
- Unknown enums and dates in an epic stay as `{{field}}` and go to the owner: an invalid value breaks the Jira export.
- Never rename headings or remove template tables; Product Brain maps fields by structure.
