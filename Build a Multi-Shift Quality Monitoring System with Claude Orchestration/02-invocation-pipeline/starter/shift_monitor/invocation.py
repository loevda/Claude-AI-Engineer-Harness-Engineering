"""Three invocation shapes.

thin     — prompt only.
rich     — hot state + new defects.
resumed  — prior partial findings + new defects since the last manifest step.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from .state import HotState

InvocationShape = Literal["thin", "rich", "resumed"]


@dataclass(frozen=True)
class Invocation:
    shape: InvocationShape
    prompt: str


def thin(prompt: str) -> Invocation:
    # TODO: Return an Invocation with shape="thin" and the prompt unchanged.
    # The thin shape is for one-shot calls that don't need any project state.
    return Invocation(shape="thin", prompt=prompt)


def rich(
    role: str, hot_state: HotState, new_defects: Sequence[Mapping[str, Any]]
) -> Invocation:
    # TODO: Build a rich prompt that includes:
    #   - A one-line role framing ("You are the on-call {role} for Northridge Plant 3.")
    #   - A "## Current hot state" section listing recent_defect_hashes,
    #     current_shift_summary, active_alerts, threshold_statuses.
    #   - A "## New defects since last shift" section enumerating each new defect
    #     (id / ts / shift / component / severity / description).
    #   - A trailing instruction asking for: Summary, Findings, Recommended
    #     actions, and an Updated hot state proposal as a JSON block.
    # Return an Invocation with shape="rich" and the rendered prompt.
    lines: list[str] = [
        f"You are the on-call {role} for Northridge Plant 3.",
        "",
        "## Current hot state",
        f"- Recent defect hashes: {', '.join(hot_state.recent_defect_hashes)}",
        f"- Current shift summary: {hot_state.current_shift_summary}",
        f"- Active alerts: {hot_state.active_alerts}",
        f"- Threshold statuses: {hot_state.threshold_statuses}",
        "",
        "## New defects since last shift",
    ]
    if not new_defects:
        lines.append("- (none)")
    else:
        for d in new_defects:
            lines.append(
                f"- {d['id']} / {d['ts']} / {d['shift']} / {d['component']} / "
                f"{d['severity']} / {d['description']}"
            )
    lines.extend(
        [
            "",
            "Produce a shift report with: Summary, Findings, Recommended actions, "
            "and an Updated hot state proposal as a JSON block.",
        ]
    )
    return Invocation(shape="rich", prompt="\n".join(lines))


def resumed(
    session_id: str,
    summary: str,
    latest_message: str,
    prior_steps: Sequence[Mapping[str, Any]],
    new_defects: Sequence[Mapping[str, Any]],
) -> Invocation:
    # TODO: Build a resumed prompt with three required sections:
    #   - "## Prior partial findings" — one line per prior step, showing its
    #     `name` and a truncated representation of its `payload`.
    #   - "## Prior summary" — the supplied summary string.
    #   - "## New defects since last partial step" — enumerate new_defects
    #     (id / ts / component / severity / description), or "- (none)" if empty.
    # Close with the latest_message under "## Latest instruction".
    # Return an Invocation with shape="resumed".
    lines: list[str] = [
        f"Resuming session {session_id}.",
        "",
        "## Prior partial findings",
    ]
    if not prior_steps:
        lines.append("- (none)")
    else:
        for step in prior_steps:
            payload_repr = str(step.get("payload", {}))[:120]
            lines.append(f"- {step.get('name', '?')}: {payload_repr}")
    lines.extend(
        [
            "",
            "## Prior summary",
            summary,
            "",
            "## New defects since last partial step",
        ]
    )
    if not new_defects:
        lines.append("- (none)")
    else:
        for d in new_defects:
            lines.append(
                f"- {d['id']} / {d['ts']} / {d['component']} / "
                f"{d['severity']} / {d['description']}"
            )
    lines.extend(["", "## Latest instruction", latest_message])
    return Invocation(shape="resumed", prompt="\n".join(lines))
