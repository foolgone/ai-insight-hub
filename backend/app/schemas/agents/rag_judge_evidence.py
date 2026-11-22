"""Shared v3 evidence quote validation for RAG Judge.

This module is intentionally dependency-free (stdlib only) and lives in the
schemas layer so both the Agent and the Service can import it without breaking
the layered architecture.

Contract:
- ``quote.strip()`` must be a verbatim contiguous substring of
  ``context.strip()`` for the cited ``C1..Cn``.
- No fuzzy matching, no quote rewriting, no answer-as-evidence.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Sequence

ABSENCE_MARKERS: tuple[str, ...] = (
    "未提及",
    "未说明",
    "未规定",
    "未涉及",
    "没有提及",
    "没有说明",
)
_CLAUSE_SPLIT = re.compile(r"[，,；;。！？!?\n]")
_SENTENCE_DELIMS = "。！？\n"
_MAX_QUOTE_CHARS = 300
_MAX_EXCERPT_CHARS = 300


@dataclass(frozen=True)
class QuoteCheck:
    claim_id: str
    context_id: str
    quote: str
    ok: bool
    error: str | None = None
    context_excerpt: str | None = None


class QuoteContractError(ValueError):
    """Raised by the Agent precheck to enter the existing one-shot repair path."""


@lru_cache(maxsize=1)
def quote_validator_sha256() -> str:
    """Code fingerprint for freeze/report traceability."""
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def build_context_map(contexts: Sequence[str]) -> dict[str, str]:
    """Map C1..Cn to the exact contexts passed to the Judge."""
    return {f"C{index}": str(content) for index, content in enumerate(contexts, 1)}


def _get(value: Any, key: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(key)
    return getattr(value, key, None)


def _first_sentence(text: str) -> str | None:
    stripped = text.strip()
    if not stripped:
        return None
    end = len(stripped)
    for index, char in enumerate(stripped):
        if char in _SENTENCE_DELIMS:
            end = index + 1
            break
    return stripped[:end][:_MAX_EXCERPT_CHARS]


def _sentence_excerpt(context: str, quote: str) -> str | None:
    """Return the full context sentence containing the best matching span.

    The excerpt is for repair feedback only; it never participates in scoring.
    """
    if not context.strip():
        return None
    if not quote.strip():
        return _first_sentence(context)
    matcher = SequenceMatcher(None, quote, context, autojunk=False)
    match = matcher.find_longest_match(0, len(quote), 0, len(context))
    if match.size == 0:
        return _first_sentence(context)
    start = 0
    for index in range(match.b - 1, -1, -1):
        if context[index] in _SENTENCE_DELIMS:
            start = index + 1
            break
    end = len(context)
    for index in range(match.b + match.size, len(context)):
        if context[index] in _SENTENCE_DELIMS:
            end = index + 1
            break
    excerpt = context[start:end].strip()
    if not excerpt:
        return _first_sentence(context)
    return excerpt[:_MAX_EXCERPT_CHARS]


def check_quote(
    *,
    quote: str,
    context_id: str,
    context_map: Mapping[str, str],
    claim_id: str = "",
) -> QuoteCheck:
    """Strictly validate one quote against one cited context."""
    text = str(quote or "").strip()
    context = context_map.get(context_id)
    if not context_id or context is None:
        return QuoteCheck(
            claim_id=claim_id,
            context_id=context_id,
            quote=text,
            ok=False,
            error="unknown_context_id",
        )
    if not text:
        return QuoteCheck(
            claim_id=claim_id,
            context_id=context_id,
            quote=text,
            ok=False,
            error="empty_quote",
        )
    if text not in context.strip():
        return QuoteCheck(
            claim_id=claim_id,
            context_id=context_id,
            quote=text,
            ok=False,
            error="quote_not_found",
            context_excerpt=_sentence_excerpt(context, text),
        )
    return QuoteCheck(
        claim_id=claim_id,
        context_id=context_id,
        quote=text,
        ok=True,
    )


def check_claims_evidence(
    claims: Sequence[Any],
    context_map: Mapping[str, str],
) -> list[QuoteCheck]:
    """Validate all evidence refs on factual claims, preserving model order."""
    checks: list[QuoteCheck] = []
    for index, claim in enumerate(claims, 1):
        claim_id = str(_get(claim, "claim_id") or f"cl{index}")
        refs = _get(claim, "evidence_refs") or []
        for ref in refs:
            checks.append(
                check_quote(
                    quote=str(_get(ref, "quote") or ""),
                    context_id=str(_get(ref, "context_id") or ""),
                    context_map=context_map,
                    claim_id=claim_id,
                )
            )
    return checks


def format_quote_contract_error(
    checks: Sequence[QuoteCheck],
    *,
    max_errors: int = 5,
    max_chars: int = 2000,
) -> str:
    """Build a bounded, actionable repair message for the existing repair round."""
    failures = [check for check in checks if not check.ok]
    lines = [
        "quote_contract_violation: evidence quote must be a contiguous substring "
        "of the cited context.",
    ]
    for check in failures[:max_errors]:
        quote = (check.quote or "")[:_MAX_QUOTE_CHARS]
        lines.append(
            f"- claim_id={check.claim_id or '?'} "
            f"context_id={check.context_id or '?'} "
            f"code={check.error or 'quote_not_found'}"
        )
        lines.append(f'  quote="{quote}"')
        if check.context_excerpt:
            excerpt = check.context_excerpt[:_MAX_EXCERPT_CHARS]
            lines.append(f'  context_excerpt="{excerpt}"')
    if len(failures) > max_errors:
        lines.append(f"- ... {len(failures) - max_errors} more error(s)")
    lines.append(
        "fix: copy one complete contiguous span from contexts; do not copy answer "
        "bold/quoted/paraphrased text. If no contiguous span supports the claim, "
        "set support_status=insufficient_evidence and remove evidence_refs."
    )
    message = "\n".join(lines)
    if len(message) > max_chars:
        return message[: max_chars - 1] + "…"
    return message


def detect_mixed_absence(claim_text: str) -> bool:
    """Detect a factual claim that also contains an absence clause.

    This is a repair/warning heuristic, not a scoring rule. It deliberately
    requires a factual clause in addition to the absence marker so a pure
    absence claim is not flagged.
    """
    text = str(claim_text or "").strip()
    if not text:
        return False
    clauses = [part.strip() for part in _CLAUSE_SPLIT.split(text) if part.strip()]
    if not clauses:
        return False
    absence_clauses = [
        clause for clause in clauses if any(marker in clause for marker in ABSENCE_MARKERS)
    ]
    if not absence_clauses:
        return False
    factual_clauses = [clause for clause in clauses if clause not in absence_clauses]
    if factual_clauses:
        return True
    return False


__all__ = [
    "ABSENCE_MARKERS",
    "QuoteCheck",
    "QuoteContractError",
    "build_context_map",
    "check_claims_evidence",
    "check_quote",
    "detect_mixed_absence",
    "format_quote_contract_error",
    "quote_validator_sha256",
]
