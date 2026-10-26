"""Exercise System 4's fork path end-to-end and prove the forks stay isolated.

Run from the System 4 solution venv, with the capstone's submitted hot_state.json:

    python fork_demo.py hot_state.json shift_scratchpad.jsonl fork_demo_output

Everything is written under the output directory; the inputs are never modified.
No API call is made (the fork helpers are pure file operations).
"""

from __future__ import annotations

import hashlib
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

from shift_monitor import fork
from shift_monitor.scratchpad import Scratchpad, ScratchpadEntry


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def entry(hyp: str, evidence: str, conclusion: str) -> ScratchpadEntry:
    return ScratchpadEntry(
        hypothesis_id=hyp, evidence=evidence, conclusion=conclusion, ts=datetime.now(UTC)
    )


def main(hot_src: Path, pad_src: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    main_hot = out / "main" / "hot_state.json"
    main_pad = out / "main" / "shift_scratchpad.jsonl"
    main_hot.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(hot_src, main_hot)
    shutil.copyfile(pad_src, main_pad)

    before = {"hot_state": sha(main_hot), "main_scratchpad": sha(main_pad)}
    print(f"main BEFORE : hot_state={before['hot_state']} scratchpad={before['main_scratchpad']}")

    forks_root = out / "forks"
    h1 = fork.fork_for_hypothesis(main_hot, "H1-lot-contamination", forks_root)
    h2 = fork.fork_for_hypothesis(main_hot, "H2-night-shift-process", forks_root)
    print(f"forked      : {h1.name}, {h2.name}")
    print(f"fork copies identical to main at fork time: "
          f"{sha(h1 / 'hot_state.json') == before['hot_state'] == sha(h2 / 'hot_state.json')}")

    p1, p2 = Scratchpad(h1 / "scratchpad.jsonl"), Scratchpad(h2 / "scratchpad.jsonl")
    p1.append(entry("H1-lot-contamination", "5 same-lot defects on capacitor-bank-C-7",
                    "Supports lot 2026-0430-B dielectric defect; quarantine the lot."))
    p2.append(entry("H2-night-shift-process", "15/17 defects on night shift",
                    "Supports a night-shift process issue; audit shift C handling."))

    after_forks = {"hot_state": sha(main_hot), "main_scratchpad": sha(main_pad)}
    print(f"main AFTER forks written : hot_state={after_forks['hot_state']} "
          f"scratchpad={after_forks['main_scratchpad']}")
    print(f"main untouched by forks  : {before == after_forks}")

    c1 = [e.conclusion for e in p1.read()]
    c2 = [e.conclusion for e in p2.read()]
    print(f"H1 scratchpad entries: {len(c1)}; H2 scratchpad entries: {len(c2)}")
    print(f"no cross-contamination   : {not set(c1) & set(c2)}")

    fork.merge_findings([h1 / "scratchpad.jsonl", h2 / "scratchpad.jsonl"], main_pad)
    merged = Scratchpad(main_pad).read()
    print(f"main AFTER explicit merge_findings: {len(merged)} entries "
          f"(hot_state still {sha(main_hot)}, unchanged: {sha(main_hot) == before['hot_state']})")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
