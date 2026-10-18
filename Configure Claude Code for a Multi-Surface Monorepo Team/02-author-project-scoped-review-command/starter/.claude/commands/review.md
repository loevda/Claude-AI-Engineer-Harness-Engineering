---
# TODO: Write the YAML frontmatter for this command. It must include:
#
#   description:   one line, ≥10 characters, naming what the command does
#   argument-hint: short description of how to pass a target (PR ref, diff range, or file path)
#   allowed-tools: a list of READ-ORIENTED tools only — no Edit, Write, NotebookEdit, or
#                  unrestricted Bash.
#
# Granular Bash sub-command allowlisting is the canonical pattern. For example:
#   - Bash(git diff:*)
#   - Bash(git log:*)
#   - Bash(gh pr view:*)
# This lets you allow READ operations on git without unlocking the full shell. The
# command should be able to run `git diff`, `git log`, `gh pr view`, `gh pr checks`,
# etc. — but NOT `git push`, `git commit`, or arbitrary `Bash(...)`.
description: Run the e-commerce team's PR review checklist against a PR ref, diff range, or file
argument-hint: "<pr-number | HEAD~1..HEAD | path/to/file>"
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash(git diff:*)
  - Bash(git log:*)
  - Bash(git show:*)
  - Bash(git status:*)
  - Bash(gh pr view:*)
  - Bash(gh pr diff:*)
  - Bash(gh pr checks:*)
---

# /review — team PR review

You are reviewing the diff identified by `$ARGUMENTS` against this repository's conventions. Apply the path-scoped rules in `.claude/rules/` (they auto-load based on the files touched) and the shared standards in `.claude/standards/`.

## Phase 1 — Interview pattern

<!--
TODO: Write the interview-pattern subsection. The reviewer agent should ask clarifying
      questions BEFORE reporting findings whenever the author's intent is ambiguous.

      Why this matters (and why it's not obvious on first read): without an interview
      step, the reviewer commits to a confidently-wrong verdict on ambiguous changes —
      e.g. a refactor that touched no test files. The author then has to argue against
      a "no test coverage" finding when the behavior was already covered upstream. The
      interview pattern asks first.

      Name at least three concrete trigger conditions where the reviewer should
      interview rather than report. Suggested triggers:
        - dependency changes (package.json or pyproject.toml diffs)
        - public API response shape changes or DB column changes
        - refactors with no corresponding test changes
        - changes that touch multiple surfaces (API + components + DB) at once
-->

Before reporting any finding, scan the diff for ambiguity and ask the author to
resolve it first. Do not commit to a verdict when the intent is unclear — ask.

Trigger an interview (ask clarifying questions and wait for the answer) when any of
these conditions hold:

- **Dependency changes** — the diff touches `package.json`, `package-lock.json`,
  `pyproject.toml`, or `poetry.lock`. Ask whether the new dependency is justified or
  whether an existing one already covers it before flagging it.
- **Public contract changes** — an API response shape, a DB column, or an exported
  function signature changed. Ask whether downstream consumers were checked and
  whether this is an intentional breaking change.
- **Refactor with no test changes** — production code moved or was restructured but
  no test file was touched. Ask whether the behavior was already covered upstream
  before reporting "missing test coverage."
- **Multi-surface change** — the same PR touches API + components + DB at once. Ask
  what the single intent is; a sprawling diff often hides an unstated goal.

If none of these fire, proceed straight to reporting. The interview is for genuine
ambiguity, not a delay tactic.

## Phase 2 — Review criteria

<!--
TODO: Write the explicit must-report vs. skip taxonomy. The point of explicit criteria
      (vs vague "be thorough" instructions) is that two teammates running this command
      on the same PR should reach the same verdict.

      Must report: at minimum, name categories for bugs (logic errors, missing await,
      race conditions, off-by-one), security (raw SQL with user input, missing auth,
      secrets in code, dangerouslySetInnerHTML), convention violations the path-scoped
      rules catch, breaking changes, and migration safety.

      Skip: at minimum, name categories the reviewer should NOT block on — minor
      formatting (Prettier handles it), naming bikeshed when the name is fine, personal
      stylistic preferences not encoded in rules/standards, and TODOs that already have
      tracked tickets.

      The skip list is what keeps false positives from destroying author trust.
-->

Two teammates running `/review` on the same PR must reach the same verdict. Use
this explicit taxonomy rather than a vague "be thorough."

**Must report** (block-worthy categories):

- **Bugs** — logic errors, missing `await`, race conditions, off-by-one, unhandled
  null/undefined on a reachable path.
- **Security** — raw SQL with user input, missing auth/authorization check, secrets
  or credentials committed in code, `dangerouslySetInnerHTML` on unsanitized input.
- **Convention violations** — anything a path-scoped rule in `.claude/rules/` catches
  (e.g. a handler returning `{ status: 404 }` instead of throwing `ApiError`).
- **Breaking changes** — public API shape, exported signature, or event contract
  changed without a migration/compat note.
- **Migration safety** — a schema change that is not forward-only, or new repository
  code with no backing migration.

**Skip** (do NOT report — these erode trust with false positives):

- **Minor formatting** — Prettier/ESLint owns this; never comment on it.
- **Naming bikeshed** — when the name is perfectly fine, do not propose alternatives.
- **Personal style preferences** — anything not encoded in `rules/` or `standards/` is
  not a review finding.
- **TODOs with a tracked ticket** — a `// TODO (#1234)` that has a ticket is fine; do
  not flag it.

## Phase 3 — Bundling: interacting vs. independent findings

<!--
TODO: Write the bundling guidance. The contrast is hard to internalize without a
      concrete pair of examples (which you'll write in the Examples section below).

      Interacting findings: those that overlap or affect the same fix. Bundle into
      ONE detailed message with all context. Example: a missing `await` and a missing
      transaction wrapper on the same function — the author needs to see them together
      because the fix changes both lines.

      Independent findings: separate functions, separate files, no shared fix. Report
      SEQUENTIALLY as discrete items so each piece of feedback is actionable.

      Give a one-line heuristic for telling them apart (e.g. "if fixing A changes the
      code B references, they are interacting").
-->

**Interacting findings** share a single fix — they overlap or affect the same lines.
Bundle them into ONE detailed message so the author sees the whole picture at once.
Example: a missing `await` and a missing transaction wrapper on the same function —
the fix rewrites both lines together, so reporting them separately would force the
author to re-derive the connection.

**Independent findings** live in separate functions or files with no shared fix.
Report them sequentially, as discrete items, so each piece of feedback is
individually actionable and the author can land fixes one at a time.

**Heuristic:** if fixing finding A changes the code that finding B references, they
are interacting — bundle them. Otherwise they are independent — report separately.

## Phase 4 — Output format

For each finding, produce:

```
[severity] path/to/file.ts:line
finding: <one-sentence description>
fix: <one-sentence recommendation>
```

Severity is `bug` | `security` | `convention` | `breaking`. End with a one-line verdict: `approve`, `comment`, or `request-changes`.

## Examples

<!--
TODO: Write at least TWO concrete input/output examples using the format above.

Per Task 3.5, examples are the difference between a command that produces
consistent output across team members and one that produces wildly varying output.

Example 1 — INDEPENDENT findings. Show a diff with two unrelated convention
violations on the same file (e.g. a handler returning a `{ status: 404 }` shape
instead of throwing ApiError, AND a raw SQL call that bypasses the repository
layer). Report each as a separate `[convention]` finding. End with a verdict.

Example 2 — INTERACTING findings. Show a diff where multiple problems share a
single fix (e.g. a refundOrder handler that has missing awaits AND no transaction
wrapper AND wrong ordering between paymentService and DB writes). Bundle them
into ONE `[bug]` finding that lists the three issues together because the fix
changes the same three lines. End with a verdict.
-->

### Example 1 — independent findings (report separately)

**Input:** a diff to `src/api/orders/get.ts`:

```diff
 export async function getOrder(id: string) {
-  const order = await db.query("SELECT * FROM orders WHERE id = $1", [id]);
-  if (!order) return { status: 404, body: null };
-  return { status: 200, body: order };
+  const order = await db.query("SELECT * FROM orders WHERE id = $1", [id]);
+  if (!order) return { status: 404, body: { error: "not found" } };
+  return { status: 200, body: order };
 }
```

**Output:**

```
[convention] src/api/orders/get.ts:3
finding: handler returns a `{ status: 404 }` shape instead of throwing `ApiError(404, ...)`.
fix: replace the `if (!order) return ...` with `if (!order) throw new ApiError(404, "NOT_FOUND", \`order ${id} not found\`);`.
verdict: request-changes

[convention] src/api/orders/get.ts:2
finding: handler calls `db.query` with raw SQL, bypassing the repository layer.
fix: call `ordersRepo.findById(id)` from `src/db/orders.ts` instead of a raw query.
verdict: request-changes
```

These two findings are independent — different lines, no shared fix — so they are
reported as separate items.

### Example 2 — interacting findings (bundle into one)

**Input:** a diff to `src/api/orders/refund.ts`:

```diff
+export async function refundOrder(id: string, amount: number) {
+  const order = ordersRepo.findById(id);
+  const updated = ordersRepo.markRefunded(id);
+  paymentService.refund(order.paymentId, amount);
+  return { status: 200, body: updated };
+}
```

**Output:**

```
[bug] src/api/orders/refund.ts:2-4
finding: three interacting issues on the same code path —
  (1) `ordersRepo.findById` is not awaited, so `order` is a Promise and `order.paymentId` is undefined;
  (2) `ordersRepo.markRefunded` is not awaited either;
  (3) the writes are not wrapped in `withTransaction`, so a paymentService failure leaves the DB marked-refunded with no money moved.
fix: wrap the body in `await withTransaction(async (tx) => { ... })`, await each repo call, and order the writes so `paymentService.refund` runs before `markRefunded`.
verdict: request-changes
```

These are bundled into ONE finding because the fix rewrites the same three lines and
the author must see the ordering constraint as a whole.

## Notes

- This command is project-scoped (`.claude/commands/review.md`) so everyone on the team gets the same review. If you want to layer personal preferences (e.g. a stricter accessibility check on your own PRs), put a `~/.claude/commands/review-strict.md` in your home directory — it will not affect teammates.
- If a finding requires running code or modifying files to verify, ask the author to run a specific check rather than attempting it from the review session. This command's `allowed-tools` are read-only by design.
