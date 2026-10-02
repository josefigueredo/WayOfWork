---
name: wow-pack
description: Generate the Product Brain packets (PRD, RFC and one per epic) from the upstream manifest and Brief, then fill only their narrative sections from the context pack. Use before any Product Brain chat or when wow-guide recommends `wow pack`.
---

# wow-pack

## Steps

1. Run `wow pack prd`, `wow pack rfc` and `wow pack epic --id E<n>` for each epic.
   Exit 1 means the packet already exists: only use `--force` if you accept losing filled sections.
2. Fill ONLY the `<!-- wow:fill … -->` markers, using facts from `wow/context-pack/` with their tags
   [MEDIDO], [ESTIMACIÓN] or [SIN DEFINIR]. Never edit generated lines (stories, AC ids, story points,
   the manifest-hash header): regenerate instead.
3. RFC: write it as engineering manager / tech lead, with discarded alternatives and their reasons.
   If you cite context claims by id (C1, C2…), verify the RFC with
   `wow review --set claims --ref rfc --doc wow/pb/rfc.md`.
4. Tell the user to paste `wow/pb/preamble.md` first, then the packet, using model 3.1 Pro.

## Rules

- Anything not in the context pack is [SIN DEFINIR], never a plausible guess.
- Packets are Spanish: they are pasted into Product Brain.
