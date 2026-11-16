"""Phase 3E Prompt v1.1.1 six-case dry-run.

Inputs read-only; writes only the two dry-run artifacts; no DB/network:
- loads the frozen acceptance matrix + fixtures;
- builds a synthetic v1.1.1 Faithfulness output from matrix claims and parses it
  with the **production** Schema (``FaithfulnessOutput``);
- computes F with the **production** Service (``_faithfulness_score``):
  supported / scorable, non_factual excluded, evidence + contradiction checks;
- simulates C/R candidates against the matrix ranges;
- runs negative/boundary tests to prove production checks reject known-bad mutations.

It does NOT call an LLM/Judge, access the network, write the database, or
produce real Judge scores. C/R values are simulated candidates, not model output.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any, Callable

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parents[2]
BACKEND = REPO_ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.schemas.agents.rag_judge import (  # noqa: E402
    JUDGE_SCHEMA_V2,
    FaithfulnessOutput,
    RagJudgeInput,
)
from app.services.rag_judge_service import _faithfulness_score  # noqa: E402

MATRIX = ROOT / "prompt-v1.1.1-acceptance-matrix.json"
FIXTURES = ROOT / "prompt-v1.1.1-fixtures.json"
REPORT = ROOT / "dry-run-v1.1.1-report.md"
RESULTS = ROOT / "dry-run-v1.1.1-results.json"

CASE_ORDER = ("Q23", "Q35", "Q36", "Q21#3", "Q11", "Q29")
FACTUAL = "factual_claim"
NON_FACTUAL = "non_factual"
RUBRIC_BANDS = ((0.0, 0.2), (0.3, 0.4), (0.5, 0.6), (0.7, 0.8), (0.9, 1.0))

# Simulated C/R candidates. F is computed; C/R need an LLM output that this
# dry-run deliberately does not generate. Values sit inside the rubric bands.
CR_CANDIDATES: dict[str, dict[str, list[tuple[float, str]]]] = {
    "Q23": {
        "answer_correctness": [(0.10, "base")],
        "answer_relevancy": [(0.75, "base")],
    },
    "Q35": {
        "answer_correctness": [(0.95, "target")],
        "answer_relevancy": [(0.95, "base")],
    },
    "Q36": {
        "answer_correctness": [
            (0.55, "v1.0.0-no-disclosure"),
            (0.95, "disclosure-variant"),
        ],
        "answer_relevancy": [(0.95, "base")],
    },
    "Q11": {
        "answer_correctness": [(0.95, "base")],
        "answer_relevancy": [(0.95, "base")],
    },
    "Q29": {
        "answer_correctness": [(0.95, "base")],
        "answer_relevancy": [(0.95, "base")],
    },
}

# Acceptance anchors that must not drift from the matrix.
LABEL_ASSERTIONS: dict[str, dict[str, dict[str, Any]]] = {
    "Q23": {
        "cl1": {
            "claim_type": FACTUAL,
            "claim_subtype": "policy",
            "support_status": "unsupported",
            "is_contradictory": True,
            "contradiction_with": ["cl2"],
        },
        "cl7": {"claim_type": NON_FACTUAL, "claim_subtype": "absence"},
        "cl8": {"claim_type": NON_FACTUAL, "claim_subtype": "advice"},
    },
    "Q35": {
        "cl5": {"claim_type": NON_FACTUAL, "claim_subtype": "absence", "support_status": None},
        "cl8": {"claim_type": NON_FACTUAL, "claim_subtype": "advice"},
    },
    "Q36": {
        "cl8": {
            "claim_type": FACTUAL,
            "claim_subtype": "conflict",
            "support_status": "supported",
            "is_contradictory": False,
            "evidence_count_min": 2,
        }
    },
    "Q21#3": {
        "cl4": {"support_status": "insufficient_evidence", "is_contradictory": False},
        "cl5": {"support_status": "insufficient_evidence"},
        "cl6": {"claim_type": NON_FACTUAL, "claim_subtype": "advice"},
    },
    "Q11": {
        "cl4": {
            "claim_type": FACTUAL,
            "claim_subtype": "policy",
            "support_status": "insufficient_evidence",
        },
        "cl5": {
            "claim_type": FACTUAL,
            "claim_subtype": "policy",
            "support_status": "insufficient_evidence",
        },
        "cl6": {"claim_type": NON_FACTUAL, "claim_subtype": "advice"},
    },
    "Q29": {
        "cl1": {"claim_type": NON_FACTUAL, "claim_subtype": "absence"},
        "cl2": {"claim_type": NON_FACTUAL, "claim_subtype": "meta"},
        "cl3": {"claim_type": NON_FACTUAL, "claim_subtype": "advice"},
    },
}


def load_inputs() -> tuple[dict[str, Any], dict[str, Any]]:
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    fixtures = {
        c["case_id"]: c
        for c in json.loads(FIXTURES.read_text(encoding="utf-8"))["cases"]
    }
    return matrix, fixtures


def build_payload(
    case: dict[str, Any],
    mutate: Callable[[list[dict[str, Any]]], None] | None = None,
) -> dict[str, Any]:
    claims = []
    for source in case["expected_claims"]:
        claims.append(
            {
                "claim_id": source["claim_id"],
                "claim": source["claim"],
                "claim_type": source["claim_type"],
                "claim_subtype": source.get("claim_subtype"),
                "support_status": source.get("support_status"),
                "is_contradictory": source.get("is_contradictory", False),
                "contradiction_with": list(source.get("contradiction_with") or []),
                "evidence_refs": [dict(item) for item in source.get("evidence_refs") or []],
                "reason": source.get("why", ""),
            }
        )
    if mutate is not None:
        mutate(claims)
    return {"claims": claims, "reason": "dry-run synthetic output"}


def parse_output(payload: dict[str, Any]) -> tuple[FaithfulnessOutput | None, list[str]]:
    try:
        return FaithfulnessOutput.model_validate(payload), []
    except ValidationError as exc:
        return None, [f"schema: {error['loc']}: {error['msg']}" for error in exc.errors()]


def score_with_service(
    payload: dict[str, Any], fixture: dict[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    """Production Service scoring: F + evidence checks + validation errors."""
    contexts = [item["content"] for item in fixture["answer_contexts"]]
    score, details, skip_reason = _faithfulness_score(
        payload, contexts=contexts, schema_version=JUDGE_SCHEMA_V2
    )
    f = {
        "status": "skipped" if skip_reason else "evaluated",
        "score": score,
        "skip_reason": skip_reason,
        "scorable_claim_count": details.get("scorable_claim_count", 0),
        "supported_claim_count": details.get("supported_claim_count", 0),
        "unsupported_claim_count": details.get("unsupported_claim_count", 0),
        "insufficient_evidence_count": details.get("insufficient_evidence_count", 0),
        "non_factual_count": details.get("non_factual_count", 0),
        "absence_count": details.get("absence_count", 0),
        "document_conflict_count": details.get("document_conflict_count", 0),
        "contradiction_count": details.get("contradiction_count", 0),
        "insufficient_evidence_rate": details.get("insufficient_evidence_rate"),
        "all_insufficient": details.get("all_insufficient", False),
    }
    evidence_checks = list(details.get("evidence_validation") or [])
    semantic_errors = [
        f"{item.get('claim_id')}: {item.get('message')}"
        for item in details.get("validation_errors") or []
    ]
    return f, evidence_checks, semantic_errors


def parse_ranges(text: str) -> list[tuple[float, float]]:
    return [
        (float(low), float(high))
        for low, high in re.findall(
            r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)", text
        )
    ]


def check_f_target(f: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    text = case["expected_scores"].get("faithfulness", "")
    errors: list[str] = []
    if "status=skipped" in text:
        if f["status"] != "skipped":
            errors.append("expected skipped but faithfulness was evaluated")
        if f["skip_reason"] != "no_scorable_claims":
            errors.append(f"expected skip_reason=no_scorable_claims, got {f['skip_reason']}")
        return {
            "status": "skipped",
            "target_range": None,
            "in_range": f["status"] == "skipped",
            "errors": errors,
        }

    match = re.search(
        r"target_range=(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)", text
    )
    if not match:
        return {
            "status": "invalid",
            "target_range": None,
            "in_range": False,
            "errors": ["missing target_range in matrix"],
        }
    low, high = float(match.group(1)), float(match.group(2))
    in_range = (
        f["status"] == "evaluated"
        and f["score"] is not None
        and low <= f["score"] <= high
    )
    if not in_range:
        errors.append(
            f"supported/scorable={f['score']}, target_range={low}-{high}"
        )
    return {
        "status": f["status"],
        "target_range": [low, high],
        "in_range": in_range,
        "errors": errors,
    }


def rubric_band(value: float) -> str | None:
    for low, high in RUBRIC_BANDS:
        if low <= value <= high:
            return f"{low:.1f}-{high:.1f}"
    return None


def outside_value(ranges: list[tuple[float, float]]) -> float:
    for probe in (1.0, 0.0, 0.5):
        if not any(low <= probe <= high for low, high in ranges):
            return probe
    return 0.99


def simulate_cr(case: dict[str, Any]) -> dict[str, Any]:
    cid = case["id"]
    simulated: dict[str, Any] = {}
    for metric in ("answer_correctness", "answer_relevancy"):
        text = case["expected_scores"].get(metric)
        if not text:
            simulated[metric] = {
                "status": "not_applicable",
                "reason": "matrix has no target for this case",
                "errors": [],
            }
            continue
        ranges = parse_ranges(text)
        candidates = CR_CANDIDATES.get(cid, {}).get(metric, [])
        entries = []
        errors: list[str] = []
        for index, (value, label) in enumerate(candidates):
            target = ranges[min(index, len(ranges) - 1)]
            in_range = target[0] <= value <= target[1]
            band = rubric_band(value)
            if not in_range:
                errors.append(
                    f"{metric}[{label}]={value} outside {target[0]}-{target[1]}"
                )
            if band is None:
                errors.append(f"{metric}[{label}]={value} is a rubric gap value")
            entries.append(
                {
                    "label": label,
                    "value": value,
                    "target_range": [target[0], target[1]],
                    "in_range": in_range,
                    "rubric_band": band,
                }
            )
        probe = outside_value(ranges)
        probe_in_range = any(low <= probe <= high for low, high in ranges)
        if probe_in_range:
            errors.append(f"{metric} negative probe {probe} was accepted")
        simulated[metric] = {
            "status": "simulated",
            "ranges": [[low, high] for low, high in ranges],
            "candidates": entries,
            "negative_probe": {
                "value": probe,
                "in_range": probe_in_range,
                "rejected": not probe_in_range,
            },
            "errors": errors,
        }
    return simulated


def _check(name: str, ok: bool | None, detail: str = "") -> dict[str, Any]:
    return {"name": name, "ok": ok, "detail": detail}


def check_constraints(
    case_id: str, output: FaithfulnessOutput, f: dict[str, Any], cr: dict[str, Any]
) -> list[dict[str, Any]]:
    claims = {claim.claim_id: claim for claim in output.claims if claim.claim_id}
    checks: list[dict[str, Any]] = []

    if case_id == "Q23":
        cl1 = claims.get("cl1")
        correctness = cr.get("answer_correctness", {})
        c_value = correctness.get("candidates", [{}])[0].get("value")
        checks = [
            _check("cl1 remains factual", cl1 is not None and cl1.claim_type == FACTUAL),
            _check(
                "cl1 contradictory_with=['cl2']",
                cl1 is not None
                and cl1.is_contradictory
                and cl1.contradiction_with == ["cl2"],
            ),
            _check(
                "F != 1.0",
                f["status"] == "evaluated" and f["score"] != 1.0,
                f"F={f['score']}",
            ),
            _check("C <= 0.3 (v1.0.0 regression)", c_value is not None and c_value <= 0.3, f"C={c_value}"),
            _check(
                "C not in 0.3-0.6",
                c_value is not None and not (0.3 <= c_value <= 0.6),
                f"C={c_value}",
            ),
            _check(
                "wrong_facts non-empty",
                None,
                "requires Judge output; not produced in dry-run",
            ),
        ]
    elif case_id == "Q35":
        cl5 = claims.get("cl5")
        correctness = cr.get("answer_correctness", {})
        c_value = correctness.get("candidates", [{}])[0].get("value")
        checks = [
            _check(
                "cl5 non_factual/absence",
                cl5 is not None
                and cl5.claim_type == NON_FACTUAL
                and cl5.claim_subtype == "absence",
            ),
            _check("cl5 support_status is null", cl5 is not None and cl5.support_status is None),
            _check("C >= 0.7", c_value is not None and c_value >= 0.7, f"C={c_value}"),
            _check(
                "F >= 0.8",
                f["status"] == "evaluated" and f["score"] is not None and f["score"] >= 0.8,
                f"F={f['score']}",
            ),
            _check("no region penalty", None, "requires Judge semantics; not machine-checkable"),
            _check("no transit-time requirement", None, "requires answer semantics; not machine-checkable"),
        ]
    elif case_id == "Q36":
        cl8 = claims.get("cl8")
        correctness = cr.get("answer_correctness", {})
        candidates = correctness.get("candidates", [])
        base = candidates[0].get("value") if len(candidates) > 0 else None
        variant = candidates[1].get("value") if len(candidates) > 1 else None
        checks = [
            _check(
                "cl8 factual/conflict/supported",
                cl8 is not None
                and cl8.claim_type == FACTUAL
                and cl8.claim_subtype == "conflict"
                and cl8.support_status == "supported",
            ),
            _check("cl8 not contradictory", cl8 is not None and cl8.is_contradictory is False),
            _check(
                "cl8 two-sided evidence",
                cl8 is not None and len(cl8.evidence_refs) >= 2,
                f"evidence={len(cl8.evidence_refs) if cl8 else 0}",
            ),
            _check("base C 0.5-0.6", base is not None and 0.5 <= base <= 0.6, f"C={base}"),
            _check(
                "base C not 0.0-0.2",
                base is not None and not (0.0 <= base <= 0.2),
                f"C={base}",
            ),
            _check(
                "variant C 0.9-1.0",
                variant is not None and 0.9 <= variant <= 1.0,
                f"C={variant}",
            ),
            _check("wrong_facts empty for real quote", None, "requires Judge output"),
            _check("no forced canonical rule", None, "requires answer semantics"),
        ]
    elif case_id == "Q21#3":
        cl4 = claims.get("cl4")
        cl5 = claims.get("cl5")
        single = None
        if cl4 is not None:
            single = 1.0 if cl4.support_status == "supported" else 0.0
        checks = [
            _check(
                "cl4 insufficient",
                cl4 is not None and cl4.support_status == "insufficient_evidence",
            ),
            _check(
                "cl4 not unsupported",
                cl4 is not None and cl4.support_status != "unsupported",
            ),
            _check(
                "cl5 insufficient",
                cl5 is not None and cl5.support_status == "insufficient_evidence",
            ),
            _check(
                "F != 1.0",
                f["status"] == "evaluated" and f["score"] != 1.0,
                f"F={f['score']}",
            ),
            _check("single Q21#3 claim score=0.0", single == 0.0, f"score={single}"),
        ]
    elif case_id == "Q11":
        cl4 = claims.get("cl4")
        checks = [
            _check(
                "cl4 factual/policy",
                cl4 is not None
                and cl4.claim_type == FACTUAL
                and cl4.claim_subtype == "policy",
            ),
            _check(
                "cl4 insufficient",
                cl4 is not None and cl4.support_status == "insufficient_evidence",
            ),
            _check(
                "cl4 not excluded as non_factual",
                cl4 is not None and cl4.claim_type != NON_FACTUAL,
            ),
            _check(
                "F != 1.0",
                f["status"] == "evaluated" and f["score"] != 1.0,
                f"F={f['score']}",
            ),
            _check(
                "F >= 0.5",
                f["status"] == "evaluated" and f["score"] is not None and f["score"] >= 0.5,
                f"F={f['score']}",
            ),
        ]
    elif case_id == "Q29":
        relevancy = cr.get("answer_relevancy", {})
        r_value = relevancy.get("candidates", [{}])[0].get("value")
        checks = [
            _check("F skipped", f["status"] == "skipped", f"status={f['status']}"),
            _check(
                "skip reason no_scorable_claims",
                f["skip_reason"] == "no_scorable_claims",
                f"reason={f['skip_reason']}",
            ),
            _check("R >= 0.8", r_value is not None and r_value >= 0.8, f"R={r_value}"),
            _check("wrong refusal absent", None, "requires Judge output"),
        ]
    return checks


def check_labels(output: FaithfulnessOutput, case_id: str) -> list[str]:
    claims = {claim.claim_id: claim for claim in output.claims if claim.claim_id}
    errors: list[str] = []
    for claim_id, expected in LABEL_ASSERTIONS.get(case_id, {}).items():
        claim = claims.get(claim_id)
        if claim is None:
            errors.append(f"{case_id}/{claim_id}: missing claim")
            continue
        for field, value in expected.items():
            if field == "evidence_count_min":
                if len(claim.evidence_refs) < value:
                    errors.append(
                        f"{case_id}/{claim_id}: evidence count "
                        f"{len(claim.evidence_refs)} < {value}"
                    )
                continue
            actual = getattr(claim, field)
            if actual != value:
                errors.append(
                    f"{case_id}/{claim_id}: {field} expected {value!r}, got {actual!r}"
                )
    return errors


def check_input(case: dict[str, Any], fixture: dict[str, Any]) -> dict[str, Any]:
    contexts = [item["content"] for item in fixture["answer_contexts"]]
    errors: list[str] = []
    checks = [
        _check(
            "judge_context_source=answer_contexts",
            fixture.get("judge_context_source") == "answer_contexts",
        ),
        _check("answer_contexts count=2", len(contexts) == 2, f"count={len(contexts)}"),
        _check(
            "retrieval_contexts not mixed",
            len(contexts) == len(fixture["answer_contexts"]),
            f"retrieval={len(fixture.get('retrieval_contexts') or [])}",
        ),
    ]
    try:
        parsed = RagJudgeInput(
            query=fixture["query"],
            answer=fixture["answer"],
            contexts=contexts,
            gold_answer=fixture.get("gold_answer"),
        )
        checks.append(_check("RagJudgeInput v1 parse", True, f"contexts={len(parsed.contexts)}"))
    except ValidationError as exc:
        errors.append(f"input schema: {exc}")
        checks.append(_check("RagJudgeInput v1 parse", False))
    for check in checks:
        if check["ok"] is False and check["detail"]:
            errors.append(f"input: {check['name']}")
    return {"checks": checks, "errors": errors}


def evaluate_case(
    case: dict[str, Any],
    fixture: dict[str, Any],
    mutate: Callable[[list[dict[str, Any]]], None] | None = None,
    check_extra: bool = True,
) -> dict[str, Any]:
    cid = case["id"]
    payload = build_payload(case, mutate)
    parsed, schema_errors = parse_output(payload)
    if parsed is None:
        return {
            "case_id": cid,
            "schema_ok": False,
            "errors": schema_errors,
            "evidence_checks": [],
            "checks": [],
            "passed": False,
        }
    f, evidence_checks, semantic_errors = score_with_service(payload, fixture)
    target = check_f_target(f, case)
    cr = simulate_cr(case)
    label_errors = check_labels(parsed, cid) if check_extra else []
    constraints = check_constraints(cid, parsed, f, cr) if check_extra else []

    cr_errors: list[str] = []
    for metric, item in cr.items():
        cr_errors.extend(f"{metric}: {error}" for error in item.get("errors", []))
    constraint_errors = [
        f"constraint: {check['name']} ({check['detail']})"
        for check in constraints
        if check["ok"] is False
    ]
    errors = (
        schema_errors
        + semantic_errors
        + label_errors
        + target["errors"]
        + cr_errors
        + constraint_errors
    )
    matrix_claims = {item["claim_id"]: item for item in case["expected_claims"]}
    return {
        "case_id": cid,
        "schema_ok": True,
        "claims": [
            {
                "claim_id": claim.claim_id,
                "claim": claim.claim,
                "claim_type": claim.claim_type,
                "claim_subtype": claim.claim_subtype,
                "support_status": claim.support_status,
                "is_contradictory": claim.is_contradictory,
                "contradiction_with": claim.contradiction_with,
                "evidence_count": len(claim.evidence_refs),
                "required": matrix_claims.get(claim.claim_id, {}).get("required"),
                "variant_only": matrix_claims.get(claim.claim_id, {}).get("variant_only"),
            }
            for claim in parsed.claims
        ],
        "faithfulness": f,
        "target": target,
        "correctness_relevancy": cr,
        "evidence_checks": evidence_checks,
        "labels": LABEL_ASSERTIONS.get(cid, {}),
        "label_errors": label_errors,
        "constraints": constraints,
        "errors": errors,
        "passed": not errors,
    }


def _by_id(claims: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {claim["claim_id"]: claim for claim in claims}


def neg_q35_wrong_context(claims: list[dict[str, Any]]) -> None:
    claim = _by_id(claims)["cl6"]
    claim["evidence_refs"] = [
        {"context_id": "C2", "quote": claim["evidence_refs"][0]["quote"]}
    ]


def neg_q23_cl1_non_factual(claims: list[dict[str, Any]]) -> None:
    _by_id(claims)["cl1"].update(
        {
            "claim_type": NON_FACTUAL,
            "claim_subtype": "meta",
            "support_status": None,
            "is_contradictory": False,
            "contradiction_with": [],
            "evidence_refs": [],
        }
    )


def neg_q21_cl4_supported_no_evidence(claims: list[dict[str, Any]]) -> None:
    claim = _by_id(claims)["cl4"]
    claim["support_status"] = "supported"
    claim["evidence_refs"] = []


def neg_q21_all_supported(claims: list[dict[str, Any]]) -> None:
    by_id = _by_id(claims)
    by_id["cl4"].update(
        {
            "support_status": "supported",
            "evidence_refs": [
                {
                    "context_id": "C1",
                    "quote": "质量问题需在签收后 24 小时内拍照反馈。",
                }
            ],
        }
    )
    by_id["cl5"].update(
        {
            "support_status": "supported",
            "evidence_refs": [
                {
                    "context_id": "C1",
                    "quote": "电子产品自签收之日起保修 12 个月，配件保修 3 个月。",
                }
            ],
        }
    )


def neg_q29_fabricated(claims: list[dict[str, Any]]) -> None:
    claims.append(
        {
            "claim_id": "cl4",
            "claim": "支持货到付款",
            "claim_type": FACTUAL,
            "claim_subtype": "policy",
            "support_status": "supported",
            "is_contradictory": False,
            "contradiction_with": [],
            "evidence_refs": [
                {
                    "context_id": "C1",
                    "quote": "订单签收后 7 天内可申请无理由退款。",
                }
            ],
            "reason": "fabricated for negative test",
        }
    )


def neg_q36_cl8_contradictory(claims: list[dict[str, Any]]) -> None:
    claim = _by_id(claims)["cl8"]
    claim["is_contradictory"] = True
    claim["contradiction_with"] = ["cl1"]


def neg_q23_no_pair(claims: list[dict[str, Any]]) -> None:
    _by_id(claims)["cl1"]["contradiction_with"] = []


def neg_q21_alt_split(claims: list[dict[str, Any]]) -> None:
    keep = {"cl1", "cl2", "cl4", "cl6"}
    claims[:] = [claim for claim in claims if claim["claim_id"] in keep]


def neg_q36_single_evidence(claims: list[dict[str, Any]]) -> None:
    claim = _by_id(claims)["cl8"]
    claim["evidence_refs"] = claim["evidence_refs"][:1]


def neg_q11_cl4_non_factual(claims: list[dict[str, Any]]) -> None:
    _by_id(claims)["cl4"].update(
        {
            "claim_type": NON_FACTUAL,
            "claim_subtype": "absence",
            "support_status": None,
            "evidence_refs": [],
        }
    )


def neg_q35_cl5_supported(claims: list[dict[str, Any]]) -> None:
    _by_id(claims)["cl5"]["support_status"] = "supported"


def variant_q36_without_cl8(claims: list[dict[str, Any]]) -> None:
    """Base v1.0.0 answer does not disclose the §1/§12 conflict."""
    claims[:] = [claim for claim in claims if claim["claim_id"] != "cl8"]


# (name, case_id, mutate, expected_error_substring, expect_pass, range_only)
# expect_pass=True means a boundary case that must still pass.
# range_only=True skips label/constraint assertions so the score guard is isolated.
NEGATIVE_TESTS: list[
    tuple[str, str, Callable[[list[dict[str, Any]]], None], str | None, bool, bool]
] = [
    (
        "Q35 cl6 evidence points to C2",
        "Q35",
        neg_q35_wrong_context,
        "not a verbatim substring",
        False,
        False,
    ),
    (
        "Q23 cl1 demoted to non_factual",
        "Q23",
        neg_q23_cl1_non_factual,
        "Q23/cl1",
        False,
        False,
    ),
    (
        "Q21 cl4 supported without evidence",
        "Q21#3",
        neg_q21_cl4_supported_no_evidence,
        "supported claim requires at least one evidence_ref",
        False,
        False,
    ),
    (
        "Q21 all claims supported -> F=1.0",
        "Q21#3",
        neg_q21_all_supported,
        "target_range",
        False,
        True,
    ),
    (
        "Q29 fabricated supported policy claim",
        "Q29",
        neg_q29_fabricated,
        "expected skipped",
        False,
        False,
    ),
    (
        "Q36 cl8 marked contradictory",
        "Q36",
        neg_q36_cl8_contradictory,
        "document conflict must not be answer-internal contradiction",
        False,
        False,
    ),
    (
        "Q23 cl1 contradictory without pair",
        "Q23",
        neg_q23_no_pair,
        "is_contradictory requires contradiction_with",
        False,
        False,
    ),
    (
        "Q36 cl8 single-sided evidence",
        "Q36",
        neg_q36_single_evidence,
        "conflict claim needs two-sided evidence",
        False,
        False,
    ),
    (
        "Q11 cl4 excluded as non_factual",
        "Q11",
        neg_q11_cl4_non_factual,
        "Q11/cl4",
        False,
        False,
    ),
    (
        "Q35 cl5 marked supported",
        "Q35",
        neg_q35_cl5_supported,
        "non_factual claim must not have support_status",
        False,
        False,
    ),
    (
        "Q21 alternative split 2/3=0.667",
        "Q21#3",
        neg_q21_alt_split,
        None,
        True,
        True,
    ),
    (
        "Q36 base answer without cl8 (7/7=1.0)",
        "Q36",
        variant_q36_without_cl8,
        None,
        True,
        True,
    ),
]


def run_negative_tests(
    matrix: dict[str, Any], fixtures: dict[str, Any]
) -> list[dict[str, Any]]:
    cases = {case["id"]: case for case in matrix["cases"]}
    results: list[dict[str, Any]] = []
    for name, case_id, mutate, expected_substring, expect_pass, range_only in NEGATIVE_TESTS:
        case = cases[case_id]
        fixture = fixtures[case["fixture_ref"]]
        result = evaluate_case(
            case,
            fixture,
            mutate=mutate,
            check_extra=not (expect_pass or range_only),
        )
        if expect_pass:
            score = (result.get("faithfulness") or {}).get("score")
            score_text = "skipped" if score is None else f"{score:.3f}"
            target_range = (result.get("target") or {}).get("target_range")
            target_text = (
                "skipped"
                if target_range is None
                else f"{target_range[0]:.1f}-{target_range[1]:.1f}"
            )
            observed = (
                f"F={score_text}, target={target_text} "
                f"{'PASS' if result['passed'] else 'FAIL'}"
            )
            as_expected = result["passed"]
        else:
            matched_errors = [
                error
                for error in result["errors"]
                if expected_substring and expected_substring in error
            ]
            as_expected = bool(matched_errors)
            observed = (
                matched_errors[0]
                if matched_errors
                else (result["errors"][0] if result["errors"] else "no error (not caught)")
            )
        results.append(
            {
                "name": name,
                "case_id": case_id,
                "expected": (
                    "PASS (range-only)"
                    if expect_pass
                    else f"FAIL containing {expected_substring!r}"
                ),
                "observed": observed,
                "faithfulness": result.get("faithfulness"),
                "target": result.get("target"),
                "errors": result["errors"],
                "as_expected": as_expected,
            }
        )
    return results


def fmt_score(value: float | None) -> str:
    return "skipped" if value is None else f"{value:.3f}"


def render_report(result: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Phase 3E Prompt v1.1.1 六案例 Dry-run 报告")
    lines.append("")
    lines.append(
        "> **这是 dry-run，不是 Judge 分数。** 未调用 LLM/Judge、未访问网络、"
        "未写数据库、未激活 v1.1.1。"
    )
    lines.append(">")
    lines.append(
        "> 输入：fixture `answer_contexts`（C1–C2）；`retrieval_contexts`（R1–R4）未混入。"
    )
    lines.append(
        "> 合成输出：用矩阵 `expected_claims` 构造 v1.1.1 输出（不是 Judge 生成），"
        "用生产 Schema/Service 解析与计分；只验证 Schema/计分/证据规则能否接受矩阵预期，"
        "不代表 Prompt 的真实模型表现。"
    )
    lines.append(
        f"> 生成：{result['meta']['generated_on']}；脚本：`docs/repair/phase3e/dry_run_prompt_v1.1.1.py`。"
    )
    lines.append("")
    lines.append("## 结论")
    lines.append("")
    summary = result["summary"]
    lines.append(
        f"**{'PASS' if summary['passed'] else 'FAIL'}** — "
        f"{summary['passed_cases']}/{summary['cases']} 案例通过；"
        f"负向/边界测试 {summary['negative_caught']}/{summary['negative_tests']} 符合预期；"
        f"未运行 Judge。"
    )
    lines.append("")
    lines.append(
        "| # | Case | F（计算） | F target | C（模拟） | R（模拟） | 证据 | 结果 |"
    )
    lines.append("|---|---|---|---|---|---|---|---|")
    for index, case in enumerate(result["cases"], 1):
        f = case["faithfulness"]
        target = case["target"]
        c_values = [
            item["value"]
            for item in case["correctness_relevancy"]
            .get("answer_correctness", {})
            .get("candidates", [])
        ]
        r_values = [
            item["value"]
            for item in case["correctness_relevancy"]
            .get("answer_relevancy", {})
            .get("candidates", [])
        ]
        target_text = (
            "skipped"
            if target["target_range"] is None
            else f"{target['target_range'][0]:.1f}–{target['target_range'][1]:.1f}"
        )
        evidence_total = len(case["evidence_checks"])
        evidence_bad = sum(1 for item in case["evidence_checks"] if not item["ok"])
        c_text = ", ".join(f"{value:.2f}" for value in c_values) or "n/a"
        r_text = ", ".join(f"{value:.2f}" for value in r_values) or "n/a"
        lines.append(
            f"| {index} | {case['case_id']} | {fmt_score(f['score'])} | {target_text} | "
            f"{c_text} | {r_text} | {evidence_total - evidence_bad}/{evidence_total} | "
            f"{'PASS' if case['passed'] else 'FAIL'} |"
        )
    lines.append("")
    lines.append(
        "> C/R 是矩阵区间内的模拟候选值，不是模型输出；F 由 claim `support_status` 计算。"
    )
    lines.append("")

    for case in result["cases"]:
        cid = case["case_id"]
        lines.append(f"## {cid}")
        lines.append("")
        lines.append(f"- Schema: {'PASS' if case['schema_ok'] else 'FAIL'}")
        f = case["faithfulness"]
        target = case["target"]
        if f["status"] == "skipped":
            lines.append("- F: `skipped(no_scorable_claims)`")
        else:
            lines.append(
                f"- F: `{f['supported_claim_count']}/{f['scorable_claim_count']} = "
                f"{fmt_score(f['score'])}`；target "
                f"`{target['target_range'][0]:.1f}–{target['target_range'][1]:.1f}` → "
                f"{'PASS' if target['in_range'] else 'FAIL'}"
            )
        lines.append(
            f"- Counts: scorable={f['scorable_claim_count']}, "
            f"supported={f['supported_claim_count']}, "
            f"unsupported={f['unsupported_claim_count']}, "
            f"insufficient={f['insufficient_evidence_count']}, "
            f"non_factual={f['non_factual_count']}, "
            f"absence={f['absence_count']}, "
            f"document_conflict={f['document_conflict_count']}, "
            f"contradiction={f['contradiction_count']}"
        )
        lines.append("")
        lines.append(
            "| claim_id | type/subtype | support_status | contradictory | evidence | required | variant |"
        )
        lines.append("|---|---|---|---|---|---|---|")
        for claim in case["claims"]:
            contradictory = "yes" if claim["is_contradictory"] else "no"
            lines.append(
                f"| {claim['claim_id']} | {claim['claim_type']}/{claim['claim_subtype']} | "
                f"{claim['support_status']} | {contradictory} | {claim['evidence_count']} | "
                f"{claim.get('required')} | {claim.get('variant_only')} |"
            )
        lines.append("")
        lines.append(
            f"证据校验：{len(case['evidence_checks'])} 条，"
            f"失败 {sum(1 for item in case['evidence_checks'] if not item['ok'])} 条。"
        )
        lines.append("")
        lines.append("| 检查 | 结果 | 说明 |")
        lines.append("|---|---|---|")
        for check in case["constraints"]:
            if check["ok"] is None:
                mark = "manual"
            else:
                mark = "PASS" if check["ok"] else "FAIL"
            lines.append(f"| {check['name']} | {mark} | {check['detail']} |")
        lines.append("")
        cr = case["correctness_relevancy"]
        for metric in ("answer_correctness", "answer_relevancy"):
            item = cr.get(metric, {})
            if item.get("status") == "not_applicable":
                lines.append(f"- {metric}: n/a（矩阵未给该案例目标）")
                continue
            values = ", ".join(
                f"{entry['label']}={entry['value']:.2f} "
                f"({'in' if entry['in_range'] else 'OUT'} "
                f"{entry['target_range'][0]:.1f}–{entry['target_range'][1]:.1f})"
                for entry in item.get("candidates", [])
            )
            probe = item.get("negative_probe", {})
            lines.append(
                f"- {metric}: {values}；negative probe {probe.get('value')} "
                f"{'rejected' if probe.get('rejected') else 'ACCEPTED'}"
            )
        lines.append("")
        if case["errors"]:
            lines.append("错误：")
            for error in case["errors"]:
                lines.append(f"- {error}")
            lines.append("")

    lines.append("## 负向与边界测试")
    lines.append("")
    lines.append("| 测试 | 预期 | 实际 | 结果 |")
    lines.append("|---|---|---|---|")
    for test in result["negative_tests"]:
        lines.append(
            f"| {test['name']} | {test['expected']} | {test['observed']} | "
            f"{'PASS' if test['as_expected'] else 'FAIL'} |"
        )
    lines.append("")
    lines.append("## 边界声明")
    lines.append("")
    lines.append("- 未调用 LLM/Judge，未访问网络，未写数据库；")
    lines.append("- 未生成真实 Judge 结果；C/R 仅为区间模拟候选；")
    lines.append("- v1.1.1 仍为 `design_draft` / `active=false`；")
    lines.append("- 未运行 10 条/40 条，未进入 Phase 4；")
    lines.append("- 未修改 Human Gold、v1.0.0/v1.1.0 Prompt、Agent/Service/Schema/DB。")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    matrix, fixtures = load_inputs()
    cases = {case["id"]: case for case in matrix["cases"]}
    results = []
    for cid in CASE_ORDER:
        case = cases[cid]
        fixture = fixtures[case["fixture_ref"]]
        result = evaluate_case(case, fixture)
        result["input"] = check_input(case, fixture)
        if result["input"]["errors"]:
            result["errors"].extend(result["input"]["errors"])
            result["passed"] = False
        results.append(result)

    negative_tests = run_negative_tests(matrix, fixtures)
    summary = {
        "passed": all(case["passed"] for case in results)
        and all(test["as_expected"] for test in negative_tests),
        "cases": len(results),
        "passed_cases": sum(1 for case in results if case["passed"]),
        "negative_tests": len(negative_tests),
        "negative_caught": sum(1 for test in negative_tests if test["as_expected"]),
        "judge_invoked": False,
        "llm_invoked": False,
        "network_used": False,
        "db_written": False,
    }
    payload = {
        "meta": {
            "name": "phase3e-prompt-v1.1.1-dry-run",
            "kind": "dry_run",
            "judge_invoked": False,
            "llm_invoked": False,
            "network_used": False,
            "db_written": False,
            "prompt_version": "v1.1.1",
            "prompt_status": "design_draft",
            "active": False,
            "generated_on": date.today().isoformat(),
            "matrix": str(MATRIX.relative_to(REPO_ROOT)).replace("\\", "/"),
            "fixtures": str(FIXTURES.relative_to(REPO_ROOT)).replace("\\", "/"),
            "context_source": "fixture.answer_contexts",
            "claim_source": "matrix.expected_claims (synthetic, not Judge output)",
            "schema_source": "production app.schemas.agents.rag_judge + app.services.rag_judge_service",
            "note": "dry-run only; F computed by production Service; C/R simulated; NOT Judge scores",
        },
        "summary": summary,
        "cases": results,
        "negative_tests": negative_tests,
    }
    RESULTS.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    REPORT.write_text(render_report(payload), encoding="utf-8", newline="\n")

    print(
        f"cases: {summary['passed_cases']}/{summary['cases']} passed; "
        f"negative/boundary tests: {summary['negative_caught']}/{summary['negative_tests']} as expected"
    )
    for case in results:
        f = case["faithfulness"]
        target = case["target"]
        print(
            f" - {case['case_id']}: schema={'ok' if case['schema_ok'] else 'FAIL'}, "
            f"F={fmt_score(f['score'])} "
            f"target={target['target_range']} in_range={target['in_range']}, "
            f"evidence={len(case['evidence_checks']) - sum(1 for e in case['evidence_checks'] if not e['ok'])}/"
            f"{len(case['evidence_checks'])}, errors={len(case['errors'])}"
        )
    for test in negative_tests:
        print(
            f" - negative {test['name']}: "
            f"{'PASS' if test['as_expected'] else 'FAIL'} ({test['observed']})"
        )
    print(f"report: {REPORT.relative_to(REPO_ROOT)}")
    print(f"results: {RESULTS.relative_to(REPO_ROOT)}")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
