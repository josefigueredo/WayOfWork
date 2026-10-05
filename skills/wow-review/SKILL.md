---
name: wow-review
description: Run an independent, anchored review with a different model (Codex, else Copilot) for a plan's readiness, a Jira story's diff, an epic's cumulative diff, or a document of claims. Use when a phase needs an independent verdict, when the user says "review this story/epic/plan", or when wow-guide recommends `wow review`.
---

# wow-review

The host model never reviews its own work. This skill only runs the command and reports.

## Commands

- `wow review --set readiness --ref plan` — anchors R1–R5 over PLAN.md + manifest.
- `wow review --set story --ref <JIRA-KEY> --repo <child-repo>` — anchors: the story's AC ids in specs/*/spec.md. The story is found by its key in the header, on a `**Jira:**` line under it, or through its `[USn]` in tasks.md; scenarios without ids are numbered AC1, AC2… in order and the packet says they are derived.
- `wow review --set epic --ref <E1> --repo <child-repo>` — anchors: the epic's done_when.
  Story and epic packets carry the GitHub Actions runs of the repo's HEAD (`gh run list --commit`), so CI and
  deploy criteria are judged on evidence; push the commit and let CI finish before reviewing those.
- `wow review --set standards --ref <KEY|E1> --repo <child-repo>` — second axis: the diff against the repo's
  standards (installed Spec-Kit golden rules, else CONTRIBUTING/AGENTS.md), not the story. Code smells only warn.
  Kept apart as `<ref>.standards`; decide its HITL with `--ref <ref>.standards`. wow-guide recommends it once
  on the epic; it never blocks closing.
- `wow review --set claims --ref <name> --doc <path> --repo <repo>` — anchors: C1, C2… claim ids.

Use `--base <ref>` when the diff base is not `main`.

## Reading the result

- Exit 0: approved. Report it and stop.
- Exit 1: changes required, waiting for a changed diff, or escalated to HITL. Quote each BLOCKER line
  verbatim. Fix only valid BLOCKERs; WARNING and NIT never reopen a review.
  In Spec-Kit projects, fixes go through `/spec-kit.refactor` so they stay on record.
- Exit 2: could not evaluate (no reviewer, no anchors, empty diff, unparseable output). Report the message.

## Rules

- Measure, do not speculate: a value you can measure (a count, a time, a commit, a URL, a status) is measured before you state it, and cited. Every repo, branch, commit or URL you hand out must exist and be reachable on the remote's default branch: check it (`wow ref check`). What cannot be measured is labelled as an inference and never presented as a cause.
- IDs defined earlier in the conversation (E1, D10, C14, AC1, WU-005, US-001) get a few-word gloss the first time each message mentions them, e.g. "E2 (cifras del motor al día)": the user must not have to scroll back to know what they are.
- Never rerun a review without changing the diff after a BLOCKER: wow refuses and so should you.
- After 3 rounds with a BLOCKER the review is HITL: present the BLOCKERs to the user and stop.
- Only the user decides a HITL review: present each BLOCKER and offer approve / reject as a choice (with the host's
  multiple-choice question tool if it has one; the reason goes in the free-text answer). Record their verdict with
  `wow review --decide approved|rejected --reason "<why, per BLOCKER>" --ref <REF>`: it works only after HITL,
  keeps the reviewer's rounds, and is stored as `approved_by_human` / `rejected_by_human`, never as `approved`.
- Do not argue with the reviewer across rounds.
- After each /spec-kit.sync-status, run `wow close --epic <E1> --subtasks` (dry run): it lists the open
  subtasks of stories Spec-Kit already closed; ask before `--apply`.
- Once the epic review is approved, run `wow close --epic <E1>` (dry run): /spec-kit.sync-status closes only
  stories, this lists the subtasks and the epic still open in Jira; an open story is reported as Spec-Kit's
  anomaly (missing `- jira:` key or sync-status not run) and blocks the run. Show the list and ask the user before
  `wow close --epic <E1> --apply`: it writes to Jira.
