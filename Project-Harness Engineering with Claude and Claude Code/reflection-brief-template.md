# Reflection Brief — Harness Engineering Capstone

**Name:** David Loevenbruck
**Date:** October 26th, 2026

Replace each `→` with your answer. **Every answer cites at least one artifact from your own runs**, a run ID, file path, token count, claim outcome, or test count. Uncited answers do not pass. 3–6 sentences each unless noted. Paste short artifact snippets where they help.

**Environment**

- Model(s): claude-haiku-4-5-20251001
- OS / Python: Linux (Ubuntu 26.04) / Python 3.13
- Approx. API spend: $0.39 USD total (Systems 1–3; System 4 ran offline with recorded responses)

---

## Part 1 — Per-system

### System 1 — Agentic loop

1. **Loop control.** Quote the `stop_reason` sequence from one trace. Name the file and function that decides continue-vs-stop, and how.
   → 
   
   From `traces/claim_04_neighbor_injury.jsonl` (run `20261024_000327`), the stop_reason sequence is: `"tool_use"` → `"tool_use"` → `"tool_use"` → `"tool_use"` → `"end_turn"`. The decision lives in `claims_intake/loop.py`, function `run()`. 
   
   The `while True` loop calls the API, then branches on `response.stop_reason`: if `"end_turn"` it returns a `FinalState`; if `"tool_use"` it dispatches each tool block via `tool_executor()` and continues; any other value raises `UnexpectedStopReason`. 
   
   The loop never inspects the model's text content to decide whether to continue, only the structured API field. This made sense to me coming from traditional workflow engines where you parse output strings to figure out what happened; seeing the API itself hand you a structured termination signal makes the whole control flow feel almost boring, which is exactly what you want in production.

2. **Anti-pattern.** Name one anti-pattern `test_antipatterns.py` checks for. What would break in your run if the loop used it?
   → 
   
   `test_no_string_membership_against_text_in_loop` flags any `"some_token" in <model_output>` expression in `loop.py`. If the loop used string membership to decide routing, it would be fragile, because the model might mention "escalate" in a rationale sentence without actually calling the terminal tool. 
   
   In my run, `claim_01_kitchen_fire` ends with `stop_reason: "end_turn"` and no terminal tool; the backstop escalates it, but the fixture expects `routed`, so this is a routing miss. A string-membership check on the model's output text could have been misled in either direction, matching "property damage" and forcing a route, or matching "fire" and forcing an escalation, neither driven by the actual structured decision.

3. **Tool design.** Pick two tools with overlapping inputs. How do the descriptions prevent misrouting? What did a structured tool error let the agent do that a generic string would not?
   → 
   
   `route_to_adjuster` and `escalate_to_human` are the true overlapping pair: both are terminal tools that end the claim, and the model must pick exactly one. The descriptions in `tools.py` separate them by the 0.6 confidence threshold: `route_to_adjuster` is "TERMINAL TOOL. Route this claim to the matching adjuster queue. Call this exactly once when classification confidence is at least 0.6 and severity has been assessed", while `escalate_to_human` is "TERMINAL TOOL. Escalate this claim to a human reviewer when classification confidence is below 0.6 even after clarification, or when the claim cannot be routed safely".
   
   For structured errors, `route_to_adjuster` in `tools.py` returns `{"is_error": true, "error_category": "permanent", "is_retryable": false, "message": "classify_claim must be called before routing"}` when called before `classify_claim` (and an equivalent message for `assess_severity`). This is the code's behavior (not visible in the submitted traces, which record tool calls but not tool results), but the design principle is clear: a structured JSON error with a specific `message` field lets the model self-correct on the next turn, whereas a generic "Error" string would give no actionable guidance.

4. **Your numbers.** Quote the turn count and cost for one claim. How does it differ from the README sample, and why?
   → 
   
   `claim_04_neighbor_injury` took **5 turns** and cost **$0.0224** (17,768 input + 932 output tokens). My run cost **$0.1339** total with **4 routed and 4 escalated**, roughly 2.7× the README's $0.05 estimate, and I initially thought something was broken. 
   
   Four escalations out of eight seemed completely off from the documented "7 routed, 1 escalated." I spent a good twenty minutes digging through the traces before realizing the backstop in `run.py` was doing exactly its job: the model (`claude-haiku-4-5-20251001`) kept ending its turn after fact-gathering without calling a terminal tool, so the system conservatively escalated. 
   
   The escalated claims (01, 02, 03) each used only 2–3 turns because the model stopped early, while the routed claims (04, 05, 07, 08) used the full 4–5 turn pipeline.
### System 2 — Context strategy

5. **The reduction.** From `budget.json`: baseline tokens, assembled tokens, reduction %. Which section dominates the assembled context, and why keep it verbatim?
   → From `budget.json` (run `20261024-001109`): baseline = **38,708 tokens**, assembled = **16,908 tokens**, reduction = **56.32%**. The `active` section dominates at **15,789 tokens** (93.4% of the assembled context). 
   
    It is kept verbatim because it represents the live payment-method update issue the customer is still discussing, and the model needs the exact turn-by-turn dialogue to answer follow-up questions about the current troubleshooting state. The `assemble.py` docstring explains the position-aware layout: the active segment sits at the bottom boundary of the context window, closest to where the model generates its response, so full turn detail there maximizes answerability for the live issue. Any summarization of this segment risks losing the conversational flow that lets the model trace which troubleshooting step failed and why.

6. **Summarize vs preserve.** State the rule for what gets summarized vs kept byte-exact, citing your per-section token numbers.
   → 
   
   The rule in `compressor.py` is: **resolved segments get LLM-summarized; the active segment is preserved byte-exact.** The code checks `if seg.status == "resolved"` → calls `summarize_segment()` (one Claude call per segment); otherwise it joins the raw rendered turns with no transformation. 
   
   The numbers prove the asymmetry: the refund segment compressed from **12,334 input → 355 output tokens** (97% reduction), subscription from **11,475 → 552 tokens** (95% reduction), while the active segment stays at **15,789 tokens** untouched. 
   
   The case_facts block adds only **204 tokens** of structured extraction at the top. The rationale: resolved issues are closed, so their narrative can be safely condensed to key outcomes without losing answerable facts; the active issue is still ongoing and every turn may contain the detail the next question targets.

7. **Facts block.** Compare `eval.jsonl` to `eval_control.jsonl`. Which question regressed, and what does that prove?
   → 
   
   The control ran only Q1 and Q6. **Q6 regressed** while Q1 still passed without the case_facts block. Q6 asks for the exact status token of the payment-method update issue, expected answer: `in_progress`. 
   
   With the full context, the model answers correctly: `"payment_update_status: in_progress"`. Without case_facts, the model responds: *"there is no structured status token or case record status explicitly stated"* and produces a long unfocused answer of 256 tokens trying to infer from narrative. The raw transcript never contains the token `in_progress` (0 matches in `transcript_48turns.json`), so the block carries a structured value the narrative lacks. One caveat: the block is not deterministic. `case_facts.py` extracts it with one LLM call (`case_facts_call.json`), and its extraction prompt lists `in_progress` as an example status token.

### System 3 — Claude Code config

8. **Path-scoped rules.** Quote the glob frontmatter from one rule file. Why is it better than a directory-level CLAUDE.md for cross-cutting conventions?
   → 
   
   From `rule_api.md` frontmatter: `paths:` / `- "src/api/**/*"`. From `rule_tests.md` frontmatter: `paths:` / `- "**/*.test.tsx"` / `- "**/*.test.ts"`. Path-scoped rules beat directory-level `CLAUDE.md` because they match by glob pattern across the entire tree, not by filesystem containment. 
   
   The test rule (`**/*.test.ts`) fires on test files co-located anywhere, like `src/api/orders/get.test.ts`, `src/components/Cart.test.tsx`, etc., without needing a `CLAUDE.md` in every subdirectory. A directory-level file would require duplicating the same test conventions in `src/api/CLAUDE.md`, `src/components/CLAUDE.md`, `src/db/CLAUDE.md`, etc., and would silently miss any new directory added later.

9. **Forked skill.** Quote the `context: fork` and `allowed-tools` lines. What does running forked + read-only buy you? What breaks without it?
   → 
   
   From `skill_deploy_check.md` frontmatter:

   ```yaml
   context: fork
   allowed-tools:
     - Read
     - Grep
     - Glob
     - Bash(git status:*)
     - Bash(git diff:*)
     - Bash(git log:*)
     - Bash(git rev-parse:*)
     - Bash(git ls-files:*)
     - Bash(gh pr view:*)
     - Bash(gh pr checks:*)
   ```

   Running forked keeps the verbose intermediate output (file enumerations, diff hunks, `git status` dumps) isolated in the sub-agent — only the structured pass/fail summary returns to the main session. 
   
   Without `context: fork`, every deploy check would pollute the main conversation with its intermediate output, degrading context quality for the actual work. The read-only `allowed-tools` set is checked by `tool_allowlist.py:write_capable_tools`, which uses a default-deny approach: anything not in the read-only tools list or the safe Bash prefix list is flagged as write-capable. If a future maintainer adds `Write` or `Edit` to the skill's `allowed-tools`, running `python -m ecommerce_team_config .` would flag it as a violation.

10. **Scope.** From the validator output: project-level vs user-level scope. Give one example of each from this config.
    → 
    
    The validator (`__main__.py:_check_claude_md`) calls `distinguishes_project_vs_user_scope()` which checks that `CLAUDE.md` documents both scopes. The `CLAUDE.md` scope table says user-level config is "**Not shared via version control** — they stay on your laptop and never reach teammates." **Project-level example:** `.claude/commands/review.md` lives in git, every teammate gets the same `/review` checklist automatically. **User-level example:** the `CLAUDE.md` scope table lists `~/.claude/CLAUDE.md` and `~/.claude/commands/` for personal preferences like commit-message style or editor snippets, which are invisible to the validator because it only scans the repo's `.claude/` tree.

### System 4 — Orchestration

11. **Push work down.** Defects the SQL query returned vs warm-tier total. Name the indexed query. Why does the model never see the full history?
    → 
    
    The warm tier holds **40 total defects** (from `fixtures/defects.json`); the indexed query `SELECT * FROM defects WHERE ts > ? ORDER BY ts DESC LIMIT ?` (using `idx_defects_ts ON defects(ts)`) returned **17** for `since=2026-04-01T00:00:00Z`. 
    
    The model never sees the full history because `pipeline.py:run_shift()` loads the hot state first, then calls `warm.defects_since(since_ts, limit=50)` to get only the filtered rows before building the prompt. Only the 17 filtered rows enter `build_rich_prompt()`. The SQL engine does the filtering; the model receives a pre-scoped slice sized to fit in context, not the entire defect corpus. Note: my submitted run used `RecordedClaudeClient`, so the model's analytical response came from a fixture rather than a live API call, but the filtering pipeline before the model call is the same code path that a live run would use.

12. **Crash recovery.** The resume-vs-fresh decision and its staleness threshold (`recovery.py`). Why is a fresh start with an injected summary sometimes more reliable than resuming?
    → 
    
    `recovery.py` defines `STALE_RESUME_THRESHOLD_MINUTES = 30`, roughly 1/16 of an 8-hour shift (per its docstring). `decide()` returns `"resume"` only if the manifest has steps, is not complete, and `now - last_step.ts <= 30 min`; otherwise it returns `"fresh"`. A stale partial is rebuilt from the manifest's already-captured findings, injected as "Prior partial findings" and a "Prior summary" (the `resumed` shape in `invocation.py`), which gives the model a clean context instead of continuing a working set that may be hours old; file corruption is not the reason, since `write_atomic()` in `state.py` already prevents half-written state. In my submitted run (`system4/shift_output.txt`) this path was not exercised: the CLI and `run_shift` never call `decide()`, `Manifest` or the fork helpers, which are otherwise covered by unit tests (`test_us03_crash_recovery.py`, `test_us04_fork_scratchpad.py`; 33 passed in `system4/test_output.log`). Fork isolation: `fork.py:fork_for_hypothesis()` copies `hot_state.json` into `forks_root/<id>/`, each fork's scratchpad lives at `forks_root/<id>/scratchpad.jsonl`, and findings reach the main scratchpad only through an explicit `merge_findings()` call, so isolation holds by directory convention. I exercised that path separately with `system4/fork_demo.py` (output in `system4/fork_demo_output.txt`): two forks of my `hot_state.json` left the main state's hash unchanged (`110086f286fa379d`), kept their scratchpads separate, and only the explicit `merge_findings()` call grew the main scratchpad from 5 to 7 entries.

13. **Small state.** Byte size of your `hot_state.json`. Why does the budget matter for a system run once per shift, indefinitely?
    → 
    
    `hot_state.json` is **965 bytes**, well under the `HOT_STATE_BYTE_BUDGET = 5_120` defined in `state.py`. The budget matters because the system runs 3× per day, every day, indefinitely. Without a cap, the serialized state would grow and consume an ever-larger fraction of the 200K context window, leaving less room for the actual defect data and reasoning. 
    
    Two mechanisms enforce the cap: `recent_defect_hashes` is bounded at 20 entries via Pydantic's `max_length` constraint, and `write_atomic()` raises a `ValueError` if the serialized payload exceeds 5,120 bytes, acting as a hard stop. `_trim_to_budget()` in `pipeline.py` drops the last alert from `active_alerts` until the state fits, which means the most recent alert gets sacrificed first. This guarantees every shift gets a fixed context allocation: ~1 KB of state + ~50 defect rows + the prompt template, regardless of how long the system has been running.

---

## Part 2 — Synthesis

*Graded on connecting two or more systems. Cite a named file/artifact from each.*

14. **Three layers.** Point to a file/artifact for each layer and justify.
    
    → **Model:** System 1's `classify_claim` tool schema (`tools.py`) — the model decides claim type, confidence, and rationale; no Python `if claim_type == "..."` branching exists (enforced by `test_no_claim_type_equality_branching_in_package`). In System 4, the design intent is that `pipeline.py:run_shift()` sends the filtered defects to the model and receives back `current_shift_summary` and `active_alerts` as analytical output. However, my submitted run used `RecordedClaudeClient` (a fixture-based client), so the summary came from a pre-recorded response rather than a live model call. The architectural separation is still visible in the code: the model's role is to summarize and alert, the code's role is to filter and persist.
    
    → **Harness:** System 1's `loop.py:run()` — wraps the model call with `stop_reason` triage, raises `UnexpectedStopReason` on anything unexpected, and uses `Budget` as a safety net. System 3's `tool_allowlist.py:write_capable_tools()` — the validator uses a default-deny approach: anything outside the read-only tools list and the safe Bash prefix list is flagged as write-capable, which includes bare `Bash`, `WebFetch`, `Write`, `Edit`, and any unknown tool name. Whenever the validator is run, it flags any write-capable entry in the `/deploy-check` skill's `allowed-tools` (my run: `system3/validator_output.txt` = `OK`).
    
    → **Orchestration:** System 4's `pipeline.py:run_shift()` — coordinates the full shift cycle: hot-state load → SQL pre-filter → prompt build → model call → parse response → `_trim_to_budget` → `write_atomic` → scratchpad append. System 3's `context: fork` in `skill_deploy_check.md` — orchestrates an isolated sub-agent session whose verbose output never contaminates the parent, similar in spirit to the per-hypothesis isolation System 4's `fork.py` provides, though `fork.py` isolates by copying state into separate directories rather than by running a sub-agent session.

15. **Deterministic vs prompt.** Cite one behavior guaranteed in code (terminal tool, read-only allowlist, atomic write, byte budget) and one guided by prompt. When is each right?
    → 
    
    **Code-guaranteed:** System 4's `state.py:write_atomic()`, which writes to a temp file, fsyncs, then `os.replace()`. The hot state on disk is either fully old or fully new; a crash mid-write can never leave a half-written file. Similarly, System 3's `tool_allowlist.py:write_capable_tools()` uses a default-deny check: any tool not in the read-only list or the safe Bash prefix list is flagged as write-capable, so the `/deploy-check` skill's allowed-tools set is verified to contain no write-capable entries. 
    
    **Prompt-guided:** System 1's tool description says "Call this exactly once per claim" for `classify_claim`, and "If confidence is below 0.6, prefer escalate_to_human", the model *should* follow these, but nothing in `loop.py` enforces the count or the threshold. Code guarantees are right when the consequence of violation is structural (corrupted state, unauthorized mutation). Prompt guidance is right when the decision requires judgment that can't be reduced to a predicate (when is confidence "low enough"?).

16. **Context, two faces.** Compare context management in System 2 (intra-session) and System 4 (cross-session) with cited numbers from both. Same principle, different mechanism — how?
    → 
    
    **Same principle:** only put what's needed in the context window; everything else lives outside. **System 2 (intra-session):** baseline transcript is 38,708 tokens; `compressor.py` summarizes the resolved sections via LLM calls (refund 12,334→355, subscription 11,475→552) while keeping the active section byte-exact (15,789 tokens), and `assemble.py:build()` lays them out, yielding 16,908 assembled tokens, a 56.32% reduction within a single conversation. **System 4 (cross-session):** the warm tier holds 40 defects, but `warm.py:defects_since()` returns only 17 via SQL pre-filter; the hot state carried between shifts is 965 bytes. The model never sees the full 40-row history, only the filtered slice plus a compact summary. 
    
    **Different mechanism:** System 2 uses lossy LLM summarization because the information is unstructured prose that must be compressed while preserving answerability (Q6 shows the case_facts block is what preserves exact structured values). System 4 uses SQL filtering for the defect data (deterministic, auditable), but the `current_shift_summary` and `active_alerts` in the hot state are themselves model-written and overwritten each shift, so there IS a form of summarization drift across shifts. The difference is that System 4's drift is bounded by the 5,120-byte budget and the `recent_defect_hashes` cap of 20, which limit how much state can accumulate, though not how far the model-written summary can wander.

17. **Reliability you can't see in one run.** Name one behavior a test guarantees that a single successful run would not reveal. Why does it matter before shipping?
    → 
    
    System 1's `test_no_string_membership_against_text_in_loop` in `test_antipatterns.py`, a single successful run of the claims loop would pass whether the loop uses `stop_reason` triage OR a fragile `"escalate" in response_text` check, because on a clean run both produce the same outcome. The test catches the common form of the anti-pattern statically via AST analysis (any `"literal" in x` comparison in `loop.py`) before it ever ships; it would not flag a `not in`, a `.find()` call, or a variable on the left-hand side. 
    
    Similarly, System 3's `write_capable_tools()` validator catches a future maintainer adding `Write` to the `/deploy-check` skill's `allowed-tools`, the skill would still "work" in a demo, but the safety property (read-only by construction) would be silently broken. Both matter before shipping because they protect **invariants that are invisible at runtime**: the loop's correctness doesn't depend on the text content, and the skill's safety doesn't depend on the model's good behavior. Without these tests, a passing demo gives false confidence that the architectural guarantee still holds.

18. **Blast radius.** Pick one system. What's the blast radius if it misbehaves, and what's the kill switch? Ground it in that system's tools, enforcement points, and state.
    → 
    
    **System 1 (Claims Intake).** The most dangerous failure mode is the loop routing a claim to the wrong adjuster queue, that's direct financial harm to a policyholder. The guard in `tools.py:_t_route_to_adjuster()` is a precondition check: it refuses to route if `classify_claim` or `assess_severity` haven't been called yet, returning a structured error instead of writing a bad record. However, it does NOT validate that the `queue` argument matches the classification result, so a wrong-queue routing is still possible if the model passes an inconsistent queue value.

    Beyond that, `Budget.check()` bounds the cost of a runaway loop, and the backstop in `run.py` catches any claim that ends without a terminal call. The blast radius is bounded to one claim at a time since each gets its own `ClaimSession`, but the worst case is not just a conservative escalation, it could be a wrong routing that a human reviewer has to catch downstream.

---

## Part 3 — Honest assessment

19. **What broke.** One thing that failed first try in your environment, and how you fixed it. (If nothing, what you checked to be sure.)
    → 
    
    When I first ran System 2's suite, 2 of the 30 tests were skipped (28 passed, 2 skipped), because they depend on the run artifacts that only the later pipeline step produces. They are `test_assembled_context_active_segment_byte_exact` and `test_budget_json_section_counts_sum_consistently` in `test_antipatterns.py`, which call `pytest.skip("no run artifacts available — run `python -m retail_context.run --build` first")` when no run directory exists. 
    
    I fixed it by running `python -m retail_context.run --all` first, which produced run `20261024-001109` with `budget.json` and `context.md`, then re-running the suite. My submitted `system2/test_output.log` shows both tests as PASSED (30 passed). The lesson: "all tests pass" can be misleading when some tests are conditionally skipped, so check the skip count is zero, not just the pass count.

20. **What you'd change.** One architectural decision you'd make differently, grounded in what you observed.
    → 
    
    In System 1, **3 of 8 claims** (01, 02, 03) were expected to route but ended with `stop_reason: "end_turn"` without calling a terminal tool, and the backstop escalated them conservatively. (Claim 06 also ended without a terminal call, but it is the designed low-confidence fixture with `expected_outcome: "escalated"`, so that one is correct.) The architectural decision I'd change: instead of escalating immediately, inject a **nudge message** ("You have gathered facts but haven't called a terminal tool. Please call `route_to_adjuster` or `escalate_to_human` now.") and re-enter the loop so the model can finish the job.

    This would recover cases where the model simply "forgot" the final step rather than genuinely being unable to decide, and claims 01 and 03 each used only 2 turns and cost under $0.01 ($0.009 and $0.0085). A single turn in these traces costs about $0.004–0.005, and completing the route takes roughly three more calls (`classify_claim` plus `assess_severity`, then `route_to_adjuster`, then the closing `end_turn`), so about $0.013 extra, still small in absolute terms. The current design treats "model stopped talking" as equivalent to "model couldn't decide," but for claims like 01 (kitchen fire, clear property damage, all facts recorded), a nudge could push toward a proper routing instead of a conservative escalation. Claim 03 is different: its fixture is flagged `ambiguous: true` (property_damage vs liability), so a nudge there could legitimately end in an escalation.
