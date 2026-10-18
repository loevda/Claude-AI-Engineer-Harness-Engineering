# Plan mode vs. direct execution — team decision guide

Choosing between Claude Code's **plan mode** (investigate and propose before changing anything) and **direct execution** (change code immediately) is the single biggest leverage point in how the team uses the harness day-to-day. The wrong mode at either extreme costs us: plan mode for trivial fixes is friction; direct execution for architectural changes burns context and produces rework.

<!--
TODO: Add a blockquote citation for the Knight-Webb "SWE Is Becoming Plan and Review"
      anchor talk that frames this decision.

      IMPORTANT: source the citation from the Module 8 curriculum doc's anchor-talks
      table. Do NOT cite the Architect's Playbook — the Playbook contains zero
      plan-mode content and citing it would be a fabrication. The Knight-Webb talk
      lives in the curriculum doc, not the Playbook.
-->

> "SWE Is Becoming Plan and Review" — Knight-Webb, anchor talk from the Module 8
> curriculum. The framing that motivates this whole guide: the engineer's job shifts
> from typing the change to deciding *what* gets changed and reviewing it, so choosing
> the right mode (plan vs. direct) is the leverage point. Sourced from the Module 8
> curriculum anchor-talks table, not the Architect's Playbook.

This doc walks four concrete decisions against our codebase: one plan-mode example, one direct-execution example, one Explore-subagent example, and one combined-workflow example.

---

## 1. Plan-mode example

<!--
TODO: Write a plan-mode worked example against this codebase. Requirements:

  - Touch AT LEAST THREE real files in src/. A natural candidate is extracting a
    shared `useCart(userId)` hook into src/hooks/ from three components that
    currently duplicate the pattern:
      - src/components/Cart/Cart.tsx
      - src/components/Checkout/Checkout.tsx
      - src/components/MiniCart/MiniCart.tsx
    (All three exist in this repo — confirm before referencing.)

  - State the reasoning that maps to Task 3.4: large-scale changes, multiple
    valid approaches, architectural decisions, multi-file modifications.

  - EXPLICITLY cite "prevent costly rework" (or equivalent phrasing) as the value
    of planning before committing. This is the Knight-Webb principle.

  - File-path rule: if you mention a file in backticks, it must actually exist
    in the repo. For hypothetical/future files (e.g. the extraction target that
    doesn't exist yet), use PROSE form (no backticks) instead. Otherwise the
    validator will flag a dangling reference.
-->

**Task:** extract the duplicated cart-loading logic into a shared `useCart(userId)`
hook so three components stop re-implementing the same fetch + loading + error
pattern.

**Files touched (all real, all currently duplicating the pattern):**

- `src/components/Cart/Cart.tsx`
- `src/components/Checkout/Checkout.tsx`
- `src/components/MiniCart/MiniCart.tsx`

The extraction target — a new hook module under the hooks directory (prose, not a
path yet, because the file does not exist until the plan is approved) — would become
the single source of truth all three components import from.

**Why this is plan-mode work:** it is a large-scale, multi-file change with multiple
valid approaches (a context-backed hook vs. a fetch-and-cache hook vs. lifting state
to a provider), and it forces an architectural decision about where cart state
lives. Planning first lets us lay out the proposed hook signature and the three call
sites before any code changes, so we **prevent costly rework** that would come from
picking the wrong shape and having to unwind it across three surfaces. This is the
Knight-Webb principle in action: decide and review before committing the change.

---

## 2. Direct-execution example

<!--
TODO: Write a direct-execution worked example. Requirements:

  - Target a single, well-scoped change in ONE function. A natural candidate is
    adding a `min: 0` validation to the quantity field in the orders schema or
    handler:
      - src/api/orders/handler.ts (or src/api/_schemas/orders.ts)
    Confirm the file exists before referencing it.

  - State the reasoning that maps to Task 3.4: simple, well-scoped changes.

  - Convey the bar for "direct execution": you (the author) already know what
    the diff looks like before invoking Claude. If you can describe the change
    in one sentence and predict the patch, skip planning.
-->

**Task:** tighten the `quantity` field in the order-create schema so a zero or
negative quantity is rejected at the boundary.

**File touched:** `src/api/_schemas/orders.ts` — a single one-line change to the
`quantity` validator on `orderCreateSchema` (e.g. adding `.min(1)` / `min: 0`
guard to the existing `z.number().int()`).

**Why this is direct-execution work:** it is a simple, well-scoped change confined
to one function's schema. Before invoking Claude I already know exactly what the diff
looks like — one line, one field, predictable patch. The bar for skipping planning is
"you can describe the change in one sentence and predict the patch"; here that is
trivially true, so planning would be pure friction.

---

## 3. Explore-subagent example

<!--
TODO: Write an Explore-subagent worked example. Requirements:

  - A real discovery task in this codebase. A natural candidate: "find every
    place we call `processRefund`" — the answer touches src/api/orders/refund.ts,
    src/api/billing/issue.ts, and src/services/payment.ts. Confirm the files
    and the call sites exist before referencing them.

  - State the reasoning that maps to Task 3.4: isolating verbose discovery output
    and returning summaries to preserve main conversation context.

  - REFERENCE THE SCRATCHPAD PATTERN (Architect's Playbook). The Explore sub-agent
    should write its working notes to a scratchpad file (e.g. tmp/refund-callsites.md)
    so the inventory survives the main session's context window. Name it
    explicitly — "scratchpad pattern" should appear in your text.
-->

**Task:** "find every place we call `processRefund`" so we can assess the blast
radius before changing its signature.

**Discovery result (all real call sites):**

- `src/services/payment.ts` — defines `processRefund`.
- `src/api/orders/refund.ts` — imports and awaits `processRefund`.
- `src/api/billing/issue.ts` — imports and awaits `processRefund`.

**Why this is Explore-subagent work:** the discovery pass is noisy — grep traces,
import scans, and partial matches that we will throw away once the inventory is
known. Running it in an Explore sub-agent **isolates the verbose discovery output**
and returns only the summary (the three call sites) to the main conversation, so the
main session's context is preserved. Following the **scratchpad pattern** from the
Architect's Playbook, the Explore sub-agent writes its working notes to a scratchpad
file (e.g. a refund-callsites notes file under a tmp directory) so the full
inventory survives even after the main session's context window rolls over.

---

## 4. Combined workflow — plan mode for investigation, then direct execution

<!--
TODO: Write a combined-workflow worked example. This is the most subtle of the
      four — developers often see plan mode and direct execution as binary. The
      combined workflow uses plan mode for the DISCOVERY part (where you don't
      yet know the call-site list) and direct execution for the MECHANICAL part
      (where the rename is keystrokes once the list is known).

      Requirements:

      - A real change in this codebase where investigation should precede edits.
        A natural anchor: renaming `ordersRepo.findById` → `ordersRepo.getById`
        in src/db/orders.ts to align with a team naming convention
        (get* for single-row reads, find* for multi-row). The investigation
        question is "where is findById called, and are any of them dynamic
        (constructed string lookups grep would miss)?" — plan mode handles that.
        Once the call-site list is in hand, the rename itself is mechanical:
        direct execution.

      - State the reasoning that maps to Task 3.4: "Combining plan mode for
        investigation with direct execution for implementation."

      - Show the flow as a 3-step sequence: (1) plan mode investigates and
        proposes; (2) you approve the plan; (3) direct execution applies the
        rename and runs tests.
-->

**Task:** rename `ordersRepo.findById` → `ordersRepo.getById` in `src/db/orders.ts`
to align with the team naming convention (`get*` for single-row reads, `find*` for
multi-row).

**Why this is a combined workflow:** the rename is mechanical *once you know the call
sites*, but you do not know them up front, and some could be dynamic (constructed
string lookups that a plain grep would miss). This is the canonical case for
**combining plan mode for investigation with direct execution for implementation** —
the two modes are not binary; you use each where it pays.

**The 3-step flow:**

1. **Plan mode investigates and proposes.** In plan mode, ask "where is
   `findById` called, and are any of those calls dynamic (string-constructed
   lookups grep would miss)?" The plan enumerates every call site and flags any
   dynamic access that needs manual review, then proposes the rename and the exact
   files to touch.
2. **You approve the plan.** You review the call-site list, confirm no dynamic
   lookups are hiding, and approve.
3. **Direct execution applies the rename and runs tests.** With the list in hand,
   the rename is keystrokes — update `src/db/orders.ts` and each confirmed call
   site, then run the test suite to confirm nothing broke.

---

## Quick reference

| Situation | Mode |
|-----------|------|
| Single function, fix is obvious, you can predict the diff | Direct execution |
| Multi-file refactor, API shape is debatable | Plan mode |
| Discovery / inventory across the codebase, you'll throw away the intermediate steps | Explore subagent |
| Investigation-then-mechanical-change | Plan mode → direct execution |
| Architectural decision (which database, which queue) | Plan mode, possibly with a fork to compare options |

When in doubt: plan mode is recoverable (you can switch to execution), but direct execution on a complex change is not. Default to plan when uncertain.
