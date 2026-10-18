"""Case-facts extraction into a persistent block at the top of context.

Extraction is LLM-driven: one Claude call against the full transcript that returns
strict JSON for the 12 required fields. This is commonly called a *scratchpad* — same
concept, different word: a dense structured block that survives compression and is
placed at the top boundary of context so the model can recover transactional facts
without scanning thousands of tokens of narrative.

Missing-field behavior raises `CaseFactExtractionError` listing the gaps — silent
null-fill is forbidden.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from retail_context.client import complete_with_system, get_model
from retail_context.transcript import Transcript

# TODO (Exercise 2): Replace with the 12-field contract for the case-facts block.
# Order matters — the to_markdown() rendering uses this order so the block is
# reviewer-readable and the model can re-find a value by name. Each name appears
# verbatim in the extraction system prompt as the JSON key the LLM must return.
#
# Required fields (12 total): customer_id; refund_order_id, refund_amount_usd,
# refund_status; subscription_id, subscription_plan, subscription_cancel_reason,
# subscription_status; active_payment_method_last4, new_payment_method_last4,
# payment_update_failure_code, payment_update_status.
REQUIRED_FIELDS: tuple[str, ...] = (
    "customer_id",
    "refund_order_id",
    "refund_amount_usd",
    "refund_status",
    "subscription_id",
    "subscription_plan",
    "subscription_cancel_reason",
    "subscription_status",
    "active_payment_method_last4",
    "new_payment_method_last4",
    "payment_update_failure_code",
    "payment_update_status",
)


# TODO (Exercise 2): Replace with a dataclass that carries the 12 fields above
# with explicit Python types (str for IDs / status tokens / last4 strings,
# float for refund_amount_usd). Then implement to_markdown(self) -> str so the
# block renders with a level-1 `# Case Facts` header and the three subgroups
# (Customer / Refund (resolved) / Subscription (resolved) / Payment update
# (active)) as bold inline labels. The rendering is part of the contract:
# fixed key order, Markdown headers, reviewer-readable.
@dataclass
class CaseFacts:
    customer_id: str
    refund_order_id: str
    refund_amount_usd: float
    refund_status: str
    subscription_id: str
    subscription_plan: str
    subscription_cancel_reason: str
    subscription_status: str
    active_payment_method_last4: str
    new_payment_method_last4: str
    payment_update_failure_code: str
    payment_update_status: str

    def to_markdown(self) -> str:
        # Render the block with a level-1 header and the four subgroups as bold
        # inline labels, in the fixed REQUIRED_FIELDS order so a reviewer (and the
        # model) can re-find any value by name. Identifiers and snake_case status
        # tokens are emitted verbatim — never paraphrased.
        lines = [
            "# Case Facts",
            "",
            "**Customer:**",
            f"- customer_id: {self.customer_id}",
            "",
            "**Refund (resolved):**",
            f"- refund_order_id: {self.refund_order_id}",
            f"- refund_amount_usd: {self.refund_amount_usd}",
            f"- refund_status: {self.refund_status}",
            "",
            "**Subscription (resolved):**",
            f"- subscription_id: {self.subscription_id}",
            f"- subscription_plan: {self.subscription_plan}",
            f"- subscription_cancel_reason: {self.subscription_cancel_reason}",
            f"- subscription_status: {self.subscription_status}",
            "",
            "**Payment update (active):**",
            f"- active_payment_method_last4: {self.active_payment_method_last4}",
            f"- new_payment_method_last4: {self.new_payment_method_last4}",
            f"- payment_update_failure_code: {self.payment_update_failure_code}",
            f"- payment_update_status: {self.payment_update_status}",
        ]
        return "\n".join(lines) + "\n"


class CaseFactExtractionError(ValueError):
    def __init__(self, missing: list[str], raw: dict[str, Any]):
        super().__init__(f"case-facts extraction missing required fields: {missing}")
        self.missing = missing
        self.raw = raw


# TODO (Exercise 2): Replace with the system prompt that drives the extraction.
# The prompt must require Claude to return EXACTLY one JSON object with the
# 12 REQUIRED_FIELDS as keys, with the right types (refund_amount_usd is a
# number, last4 are zero-padded strings, status tokens preserved verbatim).
# Missing fields are null — DO NOT invent. Output is JSON only — no prose,
# no markdown, no code fences. The prompt is reviewed for its strict-schema
# intent; the reviewer reads it to decide whether following it would reliably
# produce a parseable JSON with every required field.
_SYSTEM_PROMPT = """\
You are a precise data-extraction engine for a retail customer-support case record.

Read the transcript provided by the user and return EXACTLY ONE JSON object that
carries the case facts. The object MUST have exactly these twelve keys and no
others:

  customer_id                  (string)  customer identifier, e.g. "CUST-88421"
  refund_order_id              (string)  order id the refund applies to, e.g. "ORD-77310"
  refund_amount_usd            (number)  the actual refunded amount as a JSON number, e.g. 22.14
  refund_status                (string)  snake_case status token, e.g. "processed"
  subscription_id              (string)  subscription identifier, e.g. "SUB-22119"
  subscription_plan            (string)  plan name, e.g. "Pantry Plus Monthly"
  subscription_cancel_reason   (string)  snake_case reason token, e.g. "duplicate_charge"
  subscription_status          (string)  snake_case status token, e.g. "cancelled_with_prorated_refund"
  active_payment_method_last4  (string)  last four digits as a zero-padded string, e.g. "4242"
  new_payment_method_last4     (string)  last four digits as a zero-padded string, e.g. "7782"
  payment_update_failure_code  (string)  snake_case failure code, e.g. "AVS_MISMATCH"
  payment_update_status        (string)  snake_case status token, e.g. "in_progress"

Rules:
  - Return ONLY the JSON object. No prose, no explanation, no markdown, no code
    fences. The first character must be '{' and the last must be '}'.
  - Preserve identifiers, amounts, and snake_case status tokens EXACTLY as they
    appear in the transcript. Do not reformat, round, or paraphrase them.
  - refund_amount_usd must be a JSON number (no quotes, no currency symbol).
  - The last4 values must be strings, zero-padded to four digits.
  - If a value is genuinely absent from the transcript, set that key to null.
    NEVER invent, guess, or infer a value that is not stated.
  - Include all twelve keys even if some are null.
"""


def _parse_json(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        if raw.rstrip().endswith("```"):
            raw = raw.rsplit("```", 1)[0]
    return json.loads(raw)


def extract(
    transcript: Transcript,
    *,
    model: str | None = None,
    log_path: Path | None = None,
) -> CaseFacts:
    # TODO (Exercise 2): Run the extraction call and validate the result.
    #
    # 1. Build the user message: f"Transcript:\n\n{transcript.full_text}".
    #
    # 2. Call complete_with_system(_SYSTEM_PROMPT, user, model=model,
    #    max_tokens=2048). It returns (text, input_tokens, output_tokens).
    #
    # 3. Parse the response text with _parse_json (handles a stray ``` fence).
    #
    # 4. If a `log_path` was given, write a JSON log containing the model
    #    name, the input/output token counts, and the raw parsed dict. This
    #    is the `case_facts_call.json` artifact the reviewer audits.
    #
    # 5. Validate that every name in REQUIRED_FIELDS is present in the parsed
    #    dict and is not None and not the empty string. If anything is
    #    missing, raise CaseFactExtractionError(missing=..., raw=...) — DO
    #    NOT silently fill with null.
    #
    # 6. Construct and return a CaseFacts. Cast types explicitly:
    #    str(...) for ID/status fields, float(...) for refund_amount_usd.
    user = f"Transcript:\n\n{transcript.full_text}"
    text, input_tokens, output_tokens = complete_with_system(
        _SYSTEM_PROMPT, user, model=model, max_tokens=2048
    )
    parsed = _parse_json(text)

    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_payload = {
            "model": model or get_model(),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "raw": parsed,
        }
        log_path.write_text(json.dumps(log_payload, indent=2))

    missing = [
        name
        for name in REQUIRED_FIELDS
        if name not in parsed or parsed[name] is None or parsed[name] == ""
    ]
    if missing:
        raise CaseFactExtractionError(missing=missing, raw=parsed)

    return CaseFacts(
        customer_id=str(parsed["customer_id"]),
        refund_order_id=str(parsed["refund_order_id"]),
        refund_amount_usd=float(parsed["refund_amount_usd"]),
        refund_status=str(parsed["refund_status"]),
        subscription_id=str(parsed["subscription_id"]),
        subscription_plan=str(parsed["subscription_plan"]),
        subscription_cancel_reason=str(parsed["subscription_cancel_reason"]),
        subscription_status=str(parsed["subscription_status"]),
        active_payment_method_last4=str(parsed["active_payment_method_last4"]),
        new_payment_method_last4=str(parsed["new_payment_method_last4"]),
        payment_update_failure_code=str(parsed["payment_update_failure_code"]),
        payment_update_status=str(parsed["payment_update_status"]),
    )


def to_dict(facts: CaseFacts) -> dict[str, Any]:
    return asdict(facts)
