---
name: wow-pb-audit
description: Audit the local copy of a Product Brain chat (PRD, RFC or epic) against its packet and the context pack, and produce corrections to paste back into the chat. Use after each Product Brain chat, or when wow-guide recommends wow-pb-audit.
---

# wow-pb-audit

## Steps

1. The user copies the full chat into `wow/pb/chats/<doc>.md` (`prd`, `rfc` or `epic-E<n>`) and the document
   from Product Brain's panel into `wow/pb/chats/<doc>.final.md`: the chat only says "I filled it", the panel
   holds what Product Brain actually wrote.
2. Run `wow pbchat audit <doc> --deep`. The deep mode asks an independent reviewer (Codex) for
   unsupported statements; without a reviewer it exits 2, then run it without `--deep` and say so.
3. Exit 1: show the corrections block verbatim so the user pastes it into Product Brain, then wait
   for the user to update the chat copy and audit again.
4. Exit 0: the chat is approved; the audit file `wow/pb/chats/<doc>.audit.json` records it.
5. "Fix in Product Brain's document editor": Product Brain left a section with template placeholders
   (`{{api_a_name}}`…) while the packet filled it. Its merge appends a block it cannot match by name after
   the template rows (the IRIS RFC API landed as an uncounted "D", so the document stopped at 97%). The
   chat cannot repair it. Show the block verbatim and tell the user to replace that whole section in the
   panel's document editor, then copy the panel again into `<doc>.final.md` and re-run the audit. This
   works with only the panel copy; the chat copy is not required for it.
6. Review only the `+`/`-` lines the audit prints ("Product Brain changed N lines against the packet"):
   a registro packet already scores 100%, so every change is Product Brain's own. Keep it, or paste a
   correction that restores the packet line.
7. Corrections go first: the chat for what the agent can redo, and Product Brain's document editor for the
   rest (its markdown stays editable after the export; the audit prints the sections to paste). Only when the
   owner decides not to correct a document does the audit stay at changes_required. It holds the later phases
   only until the epic is exported: once it has a Jira key, an unapproved audit is a recommended step, not a gate
   (Product Brain only registers the work), unless a human rejected it with `--decide rejected`.
   The user decides, not you: hand them `wow pbchat audit <doc> --decide approved|rejected --reason "<why>"`,
   with a reason that names what diverges and why it is accepted. It only answers an existing changes_required
   audit, keeps the findings on record and stores `approved_by_human` with author, reason and date; `wow state`
   lets it through, never a `rejected_by_human` one. A new audit of the same material (chat copy, panel copy and
   packet, by fingerprint) keeps the decision and the deep reviewer's findings; once any of them changes, the
   decision is dropped and the audit says so.

## Rules

- Measure, do not speculate: a value you can measure (a count, a time, a commit, a URL, a status) is measured before you state it, and cited. Every repo, branch, commit or URL you hand out must exist and be reachable on the remote's default branch: check it (`wow ref check`). What cannot be measured is labelled as an inference and never presented as a cause.
- IDs defined earlier in the conversation (E1, D10, C14, AC1, WU-005, US-001) get a few-word gloss the first time each message mentions them, e.g. "E2 (cifras del motor al día)": the user must not have to scroll back to know what they are.
- Never edit an `.audit.json` by hand and never mark a chat approved yourself: `--decide` is the user's command, run by the user.
- A closed chat (100%) with a failing audit is still not done: Product Brain checklists are not evidence.
