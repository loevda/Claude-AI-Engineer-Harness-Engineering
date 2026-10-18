---
# TODO: Write the YAML frontmatter for this skill. It must include:
#
#   name: deploy-check
#   description: (one line naming what the skill does)
#   context: fork                    ← runs in a forked sub-agent (the key piece)
#   argument-hint: "..."             ← QUOTE any value containing a colon. Unquoted
#                                      `argument-hint: <foo: bar>` parses as a NESTED
#                                      MAPPING and breaks frontmatter loading.
#   allowed-tools: a READ-ONLY allowlist (Read, Grep, Glob, granular Bash sub-commands
#                  like Bash(git status:*) and Bash(gh pr view:*) — no Edit, Write,
#                  NotebookEdit, or unrestricted Bash).
#
# A note on schema drift: the current Claude Code IDE LSP (2026-05) may not list
# `context` or `allowed-tools` in its skill-frontmatter completions. That's the LSP
# lagging the product spec, not a problem with your file — see Troubleshooting in
# the exercise instructions.
name: deploy-check
description: Run the team's read-only pre-deployment validation checklist against the working tree
context: fork
argument-hint: "<target-branch | current>"
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash(git status:*)
  - Bash(git diff:*)
  - Bash(git log:*)
  - Bash(gh pr view:*)
  - Bash(gh pr checks:*)
---

# /deploy-check

Runs the team's pre-deployment validation checklist against the current working tree and the branch you're about to ship. Read-only by design — this skill never modifies files, never pushes, never deploys. It returns a single structured summary so the calling session can decide whether to proceed.

## Why this is a skill (not a CLAUDE.md addition)

<!--
TODO: Write a 2-3 line decision rubric explaining why /deploy-check is a SKILL
      rather than always-loaded CLAUDE.md guidance.

      The contrast you must convey:
        - Skill: on-demand, forked, task-specific. You only need it right before a
          deploy. It produces verbose intermediate output (file enumeration, diff
          parsing, check execution traces) that has no value once the summary is
          known.
        - CLAUDE.md: always-loaded, universal. Conventions that need to be present
          in every session (e.g. "tests are co-located", "throw ApiError for
          validation failures") belong here.

      Without this contrast, teammates default to dumping everything into CLAUDE.md
      and end up with a 600-line monolith that wastes context on every session.

      Rule-of-thumb summary at the end: on-demand / forked / task-specific → skill;
      always-loaded / universal → CLAUDE.md.
-->

Use a **skill** for work that is on-demand, forked, and task-specific: `/deploy-check`
is only needed in the minutes before a deploy, and it produces verbose intermediate
output (file enumeration, diff parsing, check traces) that has zero value once the
pass/fail summary is known. Use **CLAUDE.md** for always-loaded, universal
conventions that must be present in every session — "tests are co-located", "throw
`ApiError` for validation failures".

Rule of thumb: on-demand / forked / task-specific → skill; always-loaded /
universal → CLAUDE.md. Dumping deploy logic into CLAUDE.md would bloat every session
with content relevant only at deploy time.

## Why `context: fork`

<!--
TODO: Write the rationale paragraph for `context: fork`. It MUST do two things:

  (a) Explicitly state that the goal is to keep verbose intermediate output OUT OF
      THE MAIN SESSION / conversation. A deploy check walks the working tree,
      inspects diffs, and runs several enumeration passes — none of that has any
      value to the calling session once we know whether to ship. Only the
      structured summary should return to the main conversation.

  (b) Note that `context: fork` is a Claude Code PRODUCT FEATURE operating at the
      skill-invocation layer, conceptually analogous to the Architect's Playbook
      *Branching Reality* pattern (which describes session-level forking via
      `fork_session`). Mention both so a reader who knows the Playbook can map the
      mental model.
-->

The goal of `context: fork` is to keep the verbose intermediate output of the deploy
check **out of the main session**. A deploy check walks the working tree, inspects
diffs, and runs several enumeration passes — none of that has any value to the
calling conversation once we know whether to ship. Running it in a fork means only
the structured summary returns to the main session; the file lists, diff hunks, and
check traces stay isolated in the fork and never consume the main context window.

`context: fork` is a Claude Code **product feature** that operates at the
skill-invocation layer: the harness spins up a separate sub-agent context for the
skill and returns only its final summary. It is conceptually analogous to the
Architect's Playbook *Branching Reality* pattern, which describes session-level
forking via `fork_session` to explore a path without polluting the primary line of
work. Same mental model, different layer: the Playbook forks whole sessions;
`context: fork` forks a single skill invocation.

## Checks

Run all three. Each check produces a pass-or-fail verdict; if any fails, the overall summary is **fail**.

<!--
TODO: Write at least THREE pre-deployment checks. For each check, declare:

  - Detect: the exact command(s) or signal(s) that determine whether the
            condition holds.
  - Pass:   what a passing result looks like.
  - Fail:   what a failing result looks like, including what to surface in the
            verdict-summary so the author can act on it.

Suggested checks (you may substitute equivalents if your team's deploy
shape needs different ones):

  1. Uncommitted changes — `git status --porcelain` returns empty.
  2. Migrations up-to-date with code — every new repository import in the diff
     since the target branch is backed by a migration file in the same branch.
  3. CI checks green on the open PR — `gh pr view --json statusCheckRollup`
     reports all required checks as SUCCESS.
-->

### Check 1 — Uncommitted changes

- Detect: run `git status --porcelain` and count the output lines.
- Pass: the command returns empty output — the working tree is clean, so what you're shipping is exactly what's committed.
- Fail: any line is returned. Surface the count and the first few paths in the verdict detail (e.g. "3 uncommitted files: src/api/orders/refund.ts, ...") so the author can commit or stash before deploying.

### Check 2 — Migrations up-to-date with code

- Detect: diff the branch against the target (`git diff <target>...HEAD -- src/db/`) and list every new repository import or schema-touching function; then list the migration files added in the same branch under the migrations directory.
- Pass: every new repository read/write introduced in the diff is backed by a migration file added in this branch — no code references a column or table that has no migration.
- Fail: a new repository function references a table/column with no matching migration in the branch. Surface the offending module and the missing migration so the author adds a forward migration before deploying.

### Check 3 — CI green on the open PR

- Detect: run `gh pr view --json statusCheckRollup` for the current branch's PR and read each check's `status`/`conclusion`.
- Pass: every required check reports SUCCESS (or the rollup is empty because there are no required checks).
- Fail: any required check is FAILURE, PENDING, or ERROR. Surface the failing check names and their state in the verdict detail so the author knows what to fix or wait on before shipping.

## Output format

Return exactly this shape to the main session:

```
verdict: pass | fail
checks:
  - name: <check-name>
    status: pass | fail
    detail: <one line or empty>
```

Do not include the raw `git status`, raw diff hunks, or full check logs in the returned summary — those stay in the fork. If the author wants to investigate a failed check, they can re-invoke the skill targeting that single check or run the underlying command themselves.

## Personalization

<!--
TODO: Add a short note explaining that this skill is project-scoped
      (`.claude/skills/deploy-check/`) so the whole team gets the same checks.
      Mention that a teammate who wants a stricter personal variant — say, one
      that additionally fails when the diff exceeds 500 lines without a long
      enough PR description — can create a parallel skill at
      `~/.claude/skills/deploy-check-strict/` with a different name. Their
      variant will not be committed to the repo and will not affect teammates.
-->

This skill is **project-scoped** (`.claude/skills/deploy-check/`), so every teammate
gets the identical set of checks through version control. If you want a stricter
personal variant — say, one that additionally fails when the diff exceeds 500 lines
without a proportionally long PR description — create a parallel skill at
`~/.claude/skills/deploy-check-strict/` with a different `name`. Your variant lives
in your home directory, is not committed to the repo, and does not affect anyone
else's `/deploy-check`.

## What this skill deliberately does not do

- It never pushes, deploys, or runs migrations. The `allowed-tools` allowlist is read-only by construction; even if a future maintainer adds `Write` here, the team's `/review` command should catch the change.
- It does not run the test suite. Tests have their own pre-merge gate in CI; duplicating that here would slow every deploy check without adding signal.
- It does not check for secrets in code. That's the job of the `gitleaks` pre-commit hook, which fails the commit, not the deploy.
