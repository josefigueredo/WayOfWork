---
name: wow-review
description: Run an independent, anchored review with a different model (Codex, else Copilot) for a plan's readiness, a Jira story's diff, an epic's cumulative diff, or a document of claims. Use when a phase needs an independent verdict, when the user says "review this story/epic/plan", or when wow-guide recommends `wow review`.
---

# wow-review

The host model never reviews its own work. This skill only runs the command and reports.

## Commands

- `wow review --set readiness --ref plan` — anchors R1–R5 over PLAN.md + manifest.
- `wow review --set story --ref <JIRA-KEY> --repo <child-repo>` — anchors: the story's AC ids in specs/*/spec.md.
- `wow review --set epic --ref <E1> --repo <child-repo>` — anchors: the epic's done_when.
- `wow review --set claims --ref <name> --doc <path> --repo <repo>` — anchors: C1, C2… claim ids.

Use `--base <ref>` when the diff base is not `main`.

## Reading the result

- Exit 0: approved. Report it and stop.
- Exit 1: changes required, waiting for a changed diff, or escalated to HITL. Quote each BLOCKER line
  verbatim. Fix only valid BLOCKERs; WARNING and NIT never reopen a review.
  In Spec-Kit projects, fixes go through `/spec-kit.refactor` so they stay on record.
- Exit 2: could not evaluate (no reviewer, no anchors, empty diff, unparseable output). Report the message.

## Rules

- Never rerun a review without changing the diff after a BLOCKER: wow refuses and so should you.
- After 3 rounds with a BLOCKER the review is HITL: present the BLOCKERs to the user and stop.
- Only the user decides a HITL review. Record their verdict with
  `wow review --decide approved|rejected --reason "<why, per BLOCKER>" --ref <REF>`: it works only after HITL,
  keeps the reviewer's rounds, and is stored as `approved_by_human` / `rejected_by_human`, never as `approved`.
- Do not argue with the reviewer across rounds.
