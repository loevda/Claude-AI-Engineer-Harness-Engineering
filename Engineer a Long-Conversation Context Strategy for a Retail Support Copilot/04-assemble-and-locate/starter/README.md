# Retail Customer Support Context Strategy

**Course:** Claude Certified Architect — Foundations / Course 1, Harness Engineering
**Module:** 2 — Context Engineering Foundations
**Status:** Starter scaffold — implement the TODO-marked sections (reference solution in `../solution/`)
**Build:** Python 3.11+, `anthropic` SDK, runs in Docker with `$ANTHROPIC_API_KEY`

This is the starter scaffold — you fill in the TODO-marked sections; the reference solution lives in `../solution/`. The system designs a context-management strategy for a 48-turn retail customer-support conversation that spans three issues — a refund inquiry (resolved), a subscription cancellation (resolved), and a payment-method update (active). The raw transcript is ~35,000 tokens; the assembled context is **the project's measurable output**, recorded in `runs/<run_id>/context.md` alongside `budget.json` (token accounting) and `eval.jsonl` (evaluation results against the compressed context).

The defining architectural choice is **application-side context engineering**: the harness owns the assembly, compression, and pruning decisions, not the model. This is the pattern to apply for context engineering ("trim verbose tool outputs … *before they accumulate in context*"). The cookbook labs demonstrate the *server-side* counterpart (`clear_tool_uses_20250919`, `compact_20260112`) — see "What I'd do next" below for the contrast.

---

## Context-window anatomy

<!-- TODO (Exercise 4): Replace this section with the five-layer context-window
     anatomy diagram (system prompt → CLAUDE.md → memory → conversation history
     → current turn) AND a one-paragraph note locating *this project's* work on
     one specific layer. The diagram can be ASCII or Mermaid — the point is
     that a reviewer can read a labeled box and find the corresponding section
     of `runs/<id>/context.md`. -->

```
┌───────────────────────────────────────────────────────────┐
│ 1. System prompt            — persona, behavior, rules       │
├───────────────────────────────────────────────────────────┤
│ 2. CLAUDE.md / project memory — repo-wide standing context  │
├───────────────────────────────────────────────────────────┤
│ 3. Long-term memory / retrieved docs — RAG, prior cases      │
├───────────────────────────────────────────────────────────┤
│ 4. Conversation history  ◄── THIS PROJECT OPERATES HERE     │
│      • # Case Facts                 (top boundary, ≤600 tok)│
│      • # Resolved: Refund inquiry   (middle, compressed)    │
│      • # Resolved: Subscription …   (middle, compressed)    │
│      • # Active issue: Payment …    (bottom boundary, exact)│
├───────────────────────────────────────────────────────────┤
│ 5. Current user turn — the new question being asked          │
└───────────────────────────────────────────────────────────┘
```

This project's work lives entirely on **layer 4 — the conversation-history layer**.
The harness (not the model) rewrites that layer before it is ever sent: it extracts
a dense `# Case Facts` block to the top, compresses the two resolved threads into
the middle, and pins the still-open payment-method thread verbatim at the bottom,
immediately above the current user turn. Each labeled box above maps one-to-one to
a level-1 (`#`) section in `runs/<id>/context.md`, so a reviewer can read a box
and find the exact bytes the model saw.

## Why this layout?

<!-- TODO (Exercise 4): Replace this section with 3-5 sentences naming WHY
     case facts sit at the top, resolved summaries sit in the middle, and the
     active segment sits verbatim at the bottom. Cite at minimum:
       (a) the "lost in the middle" attention effect,
       (b) the resolved-vs-active fidelity tradeoff, and
       (c) the pass-complete-history baseline this project deliberately deviates
           from (only for resolved threads, where coherence is no longer load-
           bearing). The "scratchpad" synonym for the case-facts block is worth
           naming. -->

The layout is engineered around the **"lost in the middle" attention effect**: a
long-context model attends most reliably to the beginning and end of the window and
least reliably to its middle. We therefore place the highest-value, hardest-to-
recompute facts — the structured `# Case Facts` block (a *scratchpad* of durable
transactional facts) — at the **top boundary**, and the live, turn-by-turn payment-
method thread at the **bottom boundary**, right against the current user turn, so
both sit in the high-attention zones. The resolved threads go to the low-attention
middle because they are the cheapest to lose precision on. This encodes the
**resolved-vs-active fidelity tradeoff**: the active thread is still load-bearing
for the next agent action, so it is preserved **byte-exact** (verbatim turns 29–48),
while the resolved threads — whose coherence is no longer load-bearing — are
summarized and allowed to lose narrative detail. In doing so we deliberately
deviate from the naive **pass-complete-history baseline** (send all 48 turns
untouched): we keep full fidelity only where it still matters (the active thread)
and compress only where it no longer does (the resolved threads), cutting the
window by more than half without sacrificing any decision-critical fact.

## Before / after token budget

<!-- TODO (Exercise 4): Replace this section with a one-line statement of the
     token-counting methodology actually used (sourced from `tokens.methodology()`
     and recorded in `budget.json`), followed by a Markdown table populated from
     `runs/<id>/budget.json` showing per-section + assembled total + baseline +
     reduction-percentage. The table is *sourced from* `budget.json`, not
     narrated — anyone re-running the pipeline should regenerate the same table
     (modulo a few percent of drift if the Anthropic endpoint is used). -->

**Methodology (from `tokens.methodology()`, recorded in `budget.json`):**
`len(text) / 3.8` heuristic (no API key available). When `ANTHROPIC_API_KEY` is
set, every number below is instead sourced from the model-authoritative Anthropic
`messages.count_tokens` endpoint — expect a few percent of drift between the two
paths. The table is regenerated from `runs/<id>/budget.json` on every run; the
`active` and `case_facts` rows are deterministic, while the two `resolved_*` rows
are LLM-generated and vary with the summarization model (capped at ≤ 500 tokens
each by the compression prompt).

| Section | Context layer | Tokens (heuristic) |
|---|---|---:|
| Baseline — raw 48-turn transcript | — | 47,144 |
| `# Case Facts` | top boundary | 142 |
| `# Resolved: Refund inquiry` | middle (LLM summary) | ≤ 500 |
| `# Resolved: Subscription cancellation` | middle (LLM summary) | ≤ 500 |
| `# Active issue: Payment-method update` | bottom boundary (verbatim) | 19,538 |
| **Assembled total** | — | **≈ 20,700** |
| **Reduction vs baseline** | — | **≈ 56%** |

The verbatim active thread dominates the assembled window (~19.5k of ~20.7k
tokens); the entire compression win comes from collapsing the two resolved
threads (originally ~28 turns) into ≤ 1k of summary while keeping the case-facts
scratchpad tiny at the top.

## Eval results

Six questions span all three issues. Pass threshold ≥ 5/6 against the assembled context. A control variant strips the case-facts block; at least one of Q1/Q6 must fail in the control, proving the block carries information the summaries don't.

From `runs/20260519-124910/eval.jsonl`:

| # | Question (source) | Result | Model answer (excerpt) |
|---|---|:-:|---|
| Q1 | Actual refund amount for ORD-77310? (case facts) | ✅ | "...processed for order ORD-77310 was **$22.14**..." |
| Q2 | Why did the customer cancel their subscription? (subscription summary) | ✅ | "...due to a **duplicate charge**..." |
| Q3 | Failure code on the current payment-method update? (active verbatim) | ✅ | "...is **AVS_MISMATCH**..." |
| Q4 | Last-4 of the new card the customer is trying to add? (active verbatim) | ✅ | "...are **7782**..." |
| Q5 | Did the customer receive their subscription proration refund? (subscription summary) | ✅ | "...not yet... processed and initiated, but not yet received..." |
| Q6 | Structured status of the payment-method update issue? (case facts) | ✅ | "...the structured status token... is `in_progress`..." |
|   | **Total** | **6/6** |   |

**Control variant** (case-facts block stripped, Q1 + Q6 only):

| # | Result | Notes |
|---|:-:|---|
| Q1 | ✅ (unexpected pass) | The refund summary preserved `$22.14` verbatim, so the answer is still recoverable without the case-facts block. |
| Q6 | ❌ (expected fail) | The structured token `in_progress` appears only in the case-facts block; the active verbatim describes the state in prose ("still trying to figure out...") but never uses the snake_case status token. This is the strict load-bearing demonstration. |

The mixed control result is honest about how compression works in practice: when the summarizer preserves a numeric value (Q1), the case-facts block becomes a *cheaper* path to the same answer rather than the *only* path. Q6 demonstrates the strict case — case-facts is the only source of structured tokens.

See [`runs/20260519-124910/eval.jsonl`](runs/20260519-124910/eval.jsonl) and [`eval_control.jsonl`](runs/20260519-124910/eval_control.jsonl) for raw model answers.

## Quickstart

```bash
export ANTHROPIC_API_KEY=sk-ant-...

# Build the assembled context + run all evals + control:
python -m retail_context.run --all

# Build the assembled context only (no eval calls):
python -m retail_context.run --build

# Try a stronger summarization model:
python -m retail_context.run --all --model claude-sonnet-4-6
```

Artifacts land in `runs/<run_id>/`:
- `context.md`         — the assembled context (read this first)
- `budget.json`        — token accounting + methodology
- `case_facts_call.json` — LLM call log for case-facts extraction
- `eval.jsonl`         — per-question results
- `eval_control.jsonl` — control variant (Q1, Q6 with case facts stripped)

## What I'd do next

- **Session resumption** — when the same customer returns 4 hours later, do we reload the verbatim active segment or re-extract case facts and start fresh? The case-facts block is the right *durable* artifact to carry across `--resume`; the verbatim active section becomes stale (tool results referenced by turn-id may have expired in the backend).

- **Server-side context editing** is the modern API-level alternative this project deliberately does not use. The Anthropic Messages API exposes:
  - **`clear_tool_uses_20250919`** (beta `context-management-2025-06-27`) — drops stale tool-result blocks server-side, transparent to the model. Preferable to this project's `pruner.py` when the *whole tool result* can be dropped (vs preserving 5 of 40 fields).
  - **`compact_20260112`** (beta `compact-2026-01-12`) — server-side rolling compression of old turns. Preferable to this project's resolved-segment summarizer when the cutoff between "compressible" and "not" is *temporal* rather than *issue-based*.
  Application-side pruning (this project) wins when (a) the field-level keep-set is decision-specific, (b) the resolved-vs-active boundary is semantic, not chronological, or (c) you need the auditable artifact (`context.md`) for compliance review. Server-side editing wins on simplicity and zero application-layer state.

- **"Lost in the middle" negative variant** — re-run eval against an assembled context where the case-facts block is placed in the middle instead of the top. If Q1 and Q6 degrade, the position effect is empirically demonstrated, not just diagrammed.

- **Summarize the active segment too** — a stand-out experiment that demonstrates the fidelity-loss the verbatim choice avoids. Run Q3 and Q4 against a context where the active segment was *also* run through the compressor.

---

## Repo layout

```
module-02-retail-context-strategy/
├── pyproject.toml
├── README.md
├── retail_context/
│   ├── __init__.py
│   ├── __main__.py
│   ├── client.py               # Claude API + Claude Code CLI fallback
│   ├── tokens.py               # canonical token-count function
│   ├── transcript.py           # loader + segmentation
│   ├── case_facts.py           # extraction into persistent block
│   ├── pruner.py               # deterministic tool-output pruning
│   ├── compressor.py           # resolved-segment summarization
│   ├── assemble.py             # position-aware assembly
│   ├── evaluate.py             # eval-question runner
│   ├── run.py                  # CLI entry point
│   └── prompts/
│       └── compression_prompt.md
├── data/
│   ├── transcript_48turns.json     # 48-turn fixture, 3 issues
│   ├── lookup_order_response.json  # 57-field tool response fixture
│   └── eval_questions.json
├── scripts/
│   └── generate_transcript.py      # one-shot fixture authoring (Sonnet 4.6)
├── tests/
│   ├── test_transcript.py
│   ├── test_pruner.py
│   ├── test_assemble.py
│   └── test_antipatterns.py
└── runs/
    └── <run_id>/
        ├── context.md
        ├── budget.json
        ├── case_facts_call.json
        ├── eval.jsonl
        └── eval_control.jsonl
```
