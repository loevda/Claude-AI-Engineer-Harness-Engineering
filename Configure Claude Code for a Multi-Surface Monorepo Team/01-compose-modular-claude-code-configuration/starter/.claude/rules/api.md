---
description: Conventions enforced only when editing Node.js API handler files under src/api/
paths:
  # TODO: add glob(s) that activate this rule when Claude edits files under src/api/
  - "src/api/**/*"
---

# API handler rules

<!--
TODO: Write at least one concrete, non-trivial convention for editing files under
      src/api/. Pull from `.claude/standards/api.md` (already complete) for context,
      but write something more specific than the standard — a rule that ONLY fires
      when editing API handler files. For example: handler signature shape, error-type
      enforcement, or repository-import boundaries.
-->

These rules load only when editing files under `src/api/`. They layer enforcement on
top of the always-on `.claude/standards/api.md`.

## Handler signature

- Every handler is `export async function name(req: Request): Promise<{ status: number; body: unknown }>`. Returning the `{ status, body }` object is mandatory — never write to the response object directly.
- Validate the request body at the top of the handler with the shared `zod` schema from `src/api/_schemas/` before touching any repository. Do not re-validate downstream.

## Error discipline

- Raise `ApiError(status, code, message)` for every expected failure (validation, not-found, auth). A bare `throw new Error(...)` inside a handler is a review-blocking violation — it surfaces as an opaque 500 and hides the real cause.
- Never swallow an exception with an empty `catch {}`. If you catch, add context and rethrow as an `ApiError`.

## Import boundaries

- Handlers reach data ONLY through repository modules under `src/db/` (e.g. `import { ordersRepo } from "@/db/orders"`). A raw `pool.query(...)` or a SQL string literal inside a handler file is forbidden — it bypasses the repository layer.
- Do not import from `src/components/` or any UI module inside `src/api/`; the API surface must stay free of frontend dependencies.
