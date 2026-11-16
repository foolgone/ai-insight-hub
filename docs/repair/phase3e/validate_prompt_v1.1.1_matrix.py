"""Static validation for Phase 3E Prompt v1.1.1 acceptance matrix.

Read-only: loads the matrix + fixtures, checks types/IDs/subtypes/evidence/score
consistency. Does NOT call an LLM, Judge, or the network.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MATRIX = ROOT / "prompt-v1.1.1-acceptance-matrix.json"
FIXTURES = ROOT / "prompt-v1.1.1-fixtures.json"

EXPECTED_F = {
    "Q23": 0.5,
    "Q35": 1.0,
    "Q36": 1.0,
    "Q21#3": 0.6,
    "Q11": 0.6,
    "Q29": None,
}
SUBTYPES = {"policy", "absence", "conflict", "advice", "meta"}


def main() -> int:
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    fixtures = {
        c["case_id"]: c
        for c in json.loads(FIXTURES.read_text(encoding="utf-8"))["cases"]
    }
    errors: list[str] = []

    for case in matrix["cases"]:
        cid = case["id"]
        ref = case.get("fixture_ref")
        if ref not in fixtures:
            errors.append(f"{cid}: fixture_ref missing")
            continue
        if not isinstance(case.get("human_gold"), bool):
            errors.append(f"{cid}: human_gold must be boolean")
        hc = case.get("human_gold_claim")
        if hc is not None and not isinstance(hc, dict):
            errors.append(f"{cid}: human_gold_claim must be object/null")
        if "required" in case:
            errors.append(f"{cid}: 'required' must be per-claim, not per-case")

        context_contents = {
            c["context_id"]: (c.get("content") or "")
            for c in fixtures[ref]["answer_contexts"]
        }
        contexts = set(context_contents)
        claim_ids = [c["claim_id"] for c in case["expected_claims"]]
        if len(claim_ids) != len(set(claim_ids)):
            errors.append(f"{cid}: duplicate claim_id")

        for claim in case["expected_claims"]:
            if not isinstance(claim.get("required"), bool):
                errors.append(f"{cid}/{claim.get('claim_id')}: required not boolean")
            if not isinstance(claim.get("variant_only"), bool):
                errors.append(f"{cid}/{claim.get('claim_id')}: variant_only not boolean")
            subtype = claim.get("claim_subtype")
            if subtype not in SUBTYPES:
                errors.append(f"{cid}/{claim.get('claim_id')}: bad subtype {subtype}")
            if claim.get("claim_type") == "factual_claim" and subtype not in {"policy", "conflict"}:
                errors.append(f"{cid}/{claim.get('claim_id')}: factual with {subtype}")
            if claim.get("claim_type") == "non_factual" and subtype not in {"absence", "advice", "meta"}:
                errors.append(f"{cid}/{claim.get('claim_id')}: non_factual with {subtype}")
            for other in claim.get("contradiction_with") or []:
                if other not in claim_ids:
                    errors.append(f"{cid}/{claim.get('claim_id')}: contradiction_with {other}")
            evidence_refs = claim.get("evidence_refs") or []
            if (
                claim.get("claim_type") == "factual_claim"
                and claim.get("support_status") == "supported"
                and not evidence_refs
            ):
                errors.append(f"{cid}/{claim.get('claim_id')}: supported without evidence_refs")
            for evidence in evidence_refs:
                context_id = evidence.get("context_id")
                if context_id not in contexts:
                    errors.append(f"{cid}/{claim.get('claim_id')}: evidence context {context_id}")
                    continue
                quote = (evidence.get("quote") or "").strip()
                if not quote:
                    errors.append(f"{cid}/{claim.get('claim_id')}: empty evidence quote")
                elif quote not in context_contents[context_id].strip():
                    errors.append(
                        f"{cid}/{claim.get('claim_id')}: quote not verbatim in {context_id}"
                    )

        scorable = [c for c in case["expected_claims"] if c["claim_type"] == "factual_claim"]
        supported = [c for c in scorable if c.get("support_status") == "supported"]
        expected = EXPECTED_F.get(cid)
        actual = (len(supported) / len(scorable)) if scorable else None
        if expected is None:
            if scorable or "skipped" not in case["expected_scores"].get("faithfulness", ""):
                errors.append(f"{cid}: expected skipped/no_scorable")
        elif actual is None or abs(actual - expected) > 1e-9:
            errors.append(f"{cid}: supported/scorable={actual}, expected {expected}")

        if cid == "Q23":
            if case["expected_claims"][0].get("contradiction_with") != ["cl2"]:
                errors.append("Q23: contradiction_with must be ['cl2']")
            if fixtures[ref].get("answer_generated_with") != "query_original":
                errors.append("Q23: answer_generated_with must be query_original")
        if cid == "Q36":
            conflict = next((c for c in case["expected_claims"] if c["claim_id"] == "cl8"), None)
            if conflict is None or len(conflict.get("evidence_refs") or []) < 2:
                errors.append("Q36: cl8 needs two-sided evidence_refs")
        if cid == "Q21#3" and not isinstance(case.get("human_gold_claim"), dict):
            errors.append("Q21#3: human_gold_claim must be structured")

    for cid, fixture in fixtures.items():
        if len(fixture.get("retrieval_contexts") or []) != 4:
            errors.append(f"{cid}: expected 4 retrieval_contexts")
        if len(fixture.get("answer_contexts") or []) != 2:
            errors.append(f"{cid}: expected 2 answer_contexts")
        if fixture.get("judge_context_source") != "answer_contexts":
            errors.append(f"{cid}: judge_context_source must be answer_contexts")

    print(f"matrix cases: {len(matrix['cases'])}; fixtures: {len(fixtures)}")
    print("checks: types, IDs, subtypes, evidence refs, score consistency, 4R/2C")
    if errors:
        print("FAIL")
        for error in errors:
            print(" -", error)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
