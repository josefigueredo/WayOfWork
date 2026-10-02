---
name: wow-pb-audit
description: Audit the local copy of a Product Brain chat (PRD, RFC or epic) against its packet and the context pack, and produce corrections to paste back into the chat. Use after each Product Brain chat, or when wow-guide recommends wow-pb-audit.
---

# wow-pb-audit

## Steps

1. The user copies the full chat into `wow/pb/chats/<doc>.md` (`prd`, `rfc` or `epic-E<n>`).
2. Run `wow pbchat audit <doc> --deep`. The deep mode asks an independent reviewer (Codex) for
   unsupported statements; without a reviewer it exits 2, then run it without `--deep` and say so.
3. Exit 1: show the corrections block verbatim so the user pastes it into Product Brain, then wait
   for the user to update the chat copy and audit again.
4. Exit 0: the chat is approved; the audit file `wow/pb/chats/<doc>.audit.json` records it.

## Rules

- Never edit an `.audit.json` by hand and never mark a chat approved yourself.
- A closed chat (100%) with a failing audit is still not done: Product Brain checklists are not evidence.
