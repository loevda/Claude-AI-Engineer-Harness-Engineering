---
description: Conventions enforced only when editing co-located test files (*.test.ts / *.test.tsx)
paths:
  # TODO: add glob(s) that activate this rule for co-located test files anywhere in
  # the tree. Tests are co-located: Foo.tsx lives next to Foo.test.tsx — so the glob
  # needs to cross-cut both the components tree and the API tree.
  - "**/*.test.ts"
  - "**/*.test.tsx"
---

# Test file rules

<!--
TODO: Write at least one concrete, non-trivial convention for editing co-located
      test files (*.test.ts / *.test.tsx). Think about what should layer ON TOP of
      the React or API rules when the file under test sits in those directories.
      Examples: assertion-style enforcement, test-data-builder usage, forbidden
      patterns (snapshots, setTimeout, DB mocking).
-->

These rules load only when editing co-located `*.test.ts` / `*.test.tsx` files. They
layer ON TOP of the React or API rules that already apply to the file under test.

## Assertion style

- Assert on user-visible behavior and rendered output, not internal hook state or private fields. A component test queries the rendered DOM (`getByRole`, `getByText`); an API handler test calls the handler function directly with a request shape and asserts on the returned `{ status, body }`.
- Prefer explicit assertions over snapshots. `toMatchSnapshot()` is forbidden for new tests — snapshot churn trains reviewers to rubber-stamp diffs and hides real regressions.

## Test data

- Build fixtures with the shared test-data builders in `tests/builders/` (e.g. `makeOrder({ status: "paid" })`). Do not hand-construct full domain objects inline; that couples tests to unrelated fields and breaks on every schema change.

## Forbidden patterns

- No `setTimeout` / `sleep` for synchronization — use the framework's awaitable wait helpers (`waitFor`, `findBy*`). Timed sleeps make tests flaky and slow.
- No mocking of the database layer. Repository tests hit the real PostgreSQL test instance configured by Docker Compose in CI; a mocked DB test that hides a broken migration is exactly what burned this team.
