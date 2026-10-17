"""Anti-pattern audit.

Verifies, by static AST analysis, that the agentic loop does NOT:
- use string-membership tests against text content to drive control flow
- use an integer-literal iteration cap as its primary stopping mechanism
- omit reference to `stop_reason` as the loop-breaking signal

And that the package broadly does not branch on `claim_type` equality
outside of the tool-schema definitions and the cost-estimate module.

Each test parses the relevant file with `ast` and walks the tree. There are
no runtime imports of claims_intake here — the audit is static, so it works
even if loop.py / tools.py do not run end-to-end.
"""

from __future__ import annotations

import ast
from pathlib import Path

PKG = Path(__file__).resolve().parents[1] / "claims_intake"
LOOP_PY = PKG / "loop.py"


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


# ---------------------------------------------------------------------------
# Anti-pattern 1 — no string-membership tests against assistant text in the loop
# ---------------------------------------------------------------------------
def test_no_string_membership_against_text_in_loop() -> None:
    """No `"some_token" in <something>` expressions in loop.py.

    Heuristic: any `ast.Compare` node using `ast.In` whose `left` operand is a
    string `ast.Constant` is flagged. The loop has no legitimate reason to test
    for the presence of a magic string inside the model's output — that would be
    natural-language-driven control flow.
    """
    # TODO:Parse LOOP_PY into an AST. Walk every node. For each
    # ast.Compare, look at its `ops` — if any op is ast.In AND `node.left` is an
    # ast.Constant holding a `str`, append `ast.unparse(node)` to an offenders list.
    # Assert the offenders list is empty; include the offending expressions in the
    # failure message so a reader can find the bad line.
    tree = _parse(LOOP_PY)
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            if any(isinstance(op, ast.In) for op in node.ops) and isinstance(
                node.left, ast.Constant
            ) and isinstance(node.left.value, str):
                offenders.append(ast.unparse(node))
    assert not offenders, (
        "loop.py must not test for magic strings inside model output "
        f"(natural-language-driven control flow): {offenders}"
    )


# ---------------------------------------------------------------------------
# Anti-pattern 2 — no integer-literal iteration cap as the primary stop mechanism
# ---------------------------------------------------------------------------
def test_no_integer_literal_iteration_cap_in_loop() -> None:
    """No `for _ in range(<int literal>)` and no `while <var> < <int literal>` in loop.py.

    Token/wall-clock/config-sourced budgets are explicitly allowed because they
    read their cap from a `Budget` instance (an attribute access or a function
    arg), not from a literal. If you need a cap, pass it in.
    """
    # TODO:Walk LOOP_PY's AST. Flag:
    #   - any ast.For whose iter is `range(<int literal>, ...)`
    #     (ast.Call to a Name "range" with at least one Constant int arg)
    #   - any ast.While whose test is an ast.Compare with an int Constant on the right
    # Assert the offenders list is empty. Mention "use a Budget instead" in the failure
    # message so the reader sees the recommended fix.
    tree = _parse(LOOP_PY)
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.For):
            iter_ = node.iter
            if (
                isinstance(iter_, ast.Call)
                and isinstance(iter_.func, ast.Name)
                and iter_.func.id == "range"
                and any(
                    isinstance(arg, ast.Constant) and isinstance(arg.value, int)
                    for arg in iter_.args
                )
            ):
                offenders.append(ast.unparse(node))
        elif isinstance(node, ast.While):
            test = node.test
            if isinstance(test, ast.Compare) and any(
                isinstance(cmp, ast.Lt) for cmp in test.ops
            ):
                for comparator in test.comparators:
                    if isinstance(comparator, ast.Constant) and isinstance(
                        comparator.value, int
                    ):
                        offenders.append(ast.unparse(node))
    assert not offenders, (
        "loop.py must not use an integer-literal iteration cap as its primary stop "
        f"mechanism — use a Budget instead: {offenders}"
    )


# ---------------------------------------------------------------------------
# Positive evidence — stop_reason is the value that breaks the while loop
# ---------------------------------------------------------------------------
def test_stop_reason_is_loop_control() -> None:
    """loop.py references `stop_reason` AND a `while` loop exits via return/raise on it."""
    # TODO:Parse LOOP_PY. Walk the tree:
    #   1. Assert there is at least one reference to `stop_reason` (either as an
    #      ast.Attribute named `stop_reason` or an ast.Name named `stop_reason`).
    #   2. Find every ast.While node. For at least one of them, the unparsed body
    #      must mention BOTH "stop_reason" AND ("return" OR "raise"). That is what
    #      "the loop exits on stop_reason" looks like at the AST level.
    # Fail with a clear message if either condition is missing.
    tree = _parse(LOOP_PY)
    has_stop_reason = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "stop_reason":
            has_stop_reason = True
        if isinstance(node, ast.Name) and node.id == "stop_reason":
            has_stop_reason = True
    assert has_stop_reason, "loop.py must reference stop_reason as the loop control signal"

    while_nodes = [n for n in ast.walk(tree) if isinstance(n, ast.While)]
    assert while_nodes, "loop.py must contain a while loop"
    exits_on_stop_reason = any(
        "stop_reason" in ast.unparse(while_node)
        and ("return" in ast.unparse(while_node) or "raise" in ast.unparse(while_node))
        for while_node in while_nodes
    )
    assert exits_on_stop_reason, (
        "at least one while loop in loop.py must exit (return/raise) on stop_reason"
    )


# ---------------------------------------------------------------------------
# Decision-tree-in-Python — no `if claim_type == "..."` branches in the package
# ---------------------------------------------------------------------------
def test_no_claim_type_equality_branching_in_package() -> None:
    """Decision logic about claim type lives in the model, not in Python.

    tools.py is exempt (it defines the enum in input_schema).
    pricing.py is exempt (it may map claim_type to per-queue cost weights).
    """
    # TODO:Walk every .py file under PKG (recursively). Skip tools.py,
    # pricing.py, and __init__.py. For each file, parse the AST, find every ast.Compare
    # whose operators include ast.Eq and whose left operand is a Name/Attribute named
    # "claim_type" compared against a string Constant. Collect "filename:lineno: <expr>"
    # for each match. Assert the list is empty; recommend in the failure message that
    # you move the decision into the model via tool calls.
    offenders: list[str] = []
    for py_file in sorted(PKG.rglob("*.py")):
        if py_file.name in {"tools.py", "pricing.py", "__init__.py"}:
            continue
        tree = _parse(py_file)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare):
                continue
            if not any(isinstance(op, ast.Eq) for op in node.ops):
                continue
            left = node.left
            left_name = None
            if isinstance(left, ast.Name):
                left_name = left.id
            elif isinstance(left, ast.Attribute):
                left_name = left.attr
            if left_name != "claim_type":
                continue
            for comparator in node.comparators:
                if isinstance(comparator, ast.Constant) and isinstance(
                    comparator.value, str
                ):
                    offenders.append(
                        f"{py_file.name}:{node.lineno}: {ast.unparse(node)}"
                    )
    assert not offenders, (
        "decision logic about claim type belongs in the model via tool calls, not "
        f"Python equality branches: {offenders}"
    )
