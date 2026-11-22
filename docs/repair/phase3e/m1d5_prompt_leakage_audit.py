"""Audit v1.2.3 Judge prompts for gate-case answer/gold/claim/evidence leakage.

Rule: after whitespace normalization, any >=12-character shared substring between
a prompt asset and a gate-case answer/gold/claim/evidence quote is a finding.
Contexts are intentionally excluded (contexts are passed to the Judge at runtime).
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[3]
PROMPT_ROOT = BASE / "backend/app/prompts/rag_judge"
VERSION = "v1.2.3"
FIXTURE_FILE = BASE / "docs/repair/phase3e/pilot-10-v1.1.5-gate.json"
M1D3_FILE = BASE / "docs/repair/phase3e/m1d3-judge-only-results.json"
M1D4_FILE = BASE / "docs/repair/phase3e/m1d4-single-case-results.json"
WHITELIST_FILE = Path(__file__).resolve().parent / "m1d5-prompt-leakage-whitelist.json"
OUT_JSON = Path(__file__).resolve().parent / "m1d5-prompt-leakage-audit.json"
OUT_MD = Path(__file__).resolve().parent / "m1d5-prompt-leakage-audit.md"
MIN_CHARS = 12


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", str(text or ""))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _strip_code_fence(text: str) -> str:
    value = str(text or "").strip()
    if value.startswith("```json"):
        value = value[len("```json") :].strip()
    elif value.startswith("```"):
        value = value[3:].strip()
    if value.endswith("```"):
        value = value[:-3].strip()
    return value


def _claims_from_raw(text: str | None) -> list[dict[str, Any]]:
    if not text:
        return []
    try:
        data = json.loads(_strip_code_fence(text))
    except json.JSONDecodeError:
        return []
    claims = data.get("claims") if isinstance(data, dict) else None
    return claims if isinstance(claims, list) else []


def _add_claim_sources(
    sources: list[dict[str, str]],
    *,
    case_id: str,
    claims: list[dict[str, Any]],
    source_prefix: str,
) -> None:
    for index, claim in enumerate(claims, 1):
        if not isinstance(claim, dict):
            continue
        text = str(claim.get("claim") or "").strip()
        if text:
            sources.append(
                {
                    "case_id": case_id,
                    "source": f"{source_prefix}:claim:{claim.get('claim_id') or index}",
                    "text": text,
                }
            )
        for ref in claim.get("evidence_refs") or []:
            if not isinstance(ref, dict):
                continue
            quote = str(ref.get("quote") or "").strip()
            if quote:
                sources.append(
                    {
                        "case_id": case_id,
                        "source": f"{source_prefix}:evidence:{claim.get('claim_id') or index}",
                        "text": quote,
                    }
                )


def collect_sources() -> list[dict[str, str]]:
    fixture = load_json(FIXTURE_FILE)
    sources: list[dict[str, str]] = []
    fixture_cases = {case["id"]: case for case in fixture["cases"]}
    for case_id, case in fixture_cases.items():
        for field in ("answer", "gold_answer"):
            text = str(case.get(field) or "").strip()
            if text:
                sources.append(
                    {
                        "case_id": case_id,
                        "source": field,
                        "text": text,
                    }
                )

    for path, prefix in ((M1D3_FILE, "m1d3"), (M1D4_FILE, "m1d4")):
        data = load_json(path)
        for case in data.get("cases", []):
            case_id = str(case.get("case_id") or "")
            if not case_id:
                continue
            outcomes: list[dict[str, Any]] = []
            for run in case.get("runs", []):
                outcomes.extend(run.get("outcomes", []))
            outcomes.extend(case.get("outcomes", []))
            for outcome in outcomes:
                if outcome.get("metric_name") != "faithfulness":
                    continue
                details = outcome.get("details") or {}
                _add_claim_sources(
                    sources,
                    case_id=case_id,
                    claims=details.get("claims") or [],
                    source_prefix=f"{prefix}:details",
                )
                for field in ("original_raw_output", "raw_output"):
                    _add_claim_sources(
                        sources,
                        case_id=case_id,
                        claims=_claims_from_raw(outcome.get(field)),
                        source_prefix=f"{prefix}:{field}",
                    )

    # Deduplicate identical (case, source, text) rows.
    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for source in sources:
        key = (source["case_id"], source["source"], source["text"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(source)
    return deduped


def _line_map(text: str) -> tuple[str, list[int]]:
    normalized_chars: list[str] = []
    line_map: list[int] = []
    line_number = 1
    for char in text:
        if char == "\n":
            line_number += 1
            continue
        if char.isspace():
            continue
        normalized_chars.append(char)
        line_map.append(line_number)
    return "".join(normalized_chars), line_map


def load_prompt_assets() -> list[dict[str, str]]:
    assets: list[dict[str, str]] = []
    for filename in ("faithfulness.txt", "answer_correctness.txt", "answer_relevancy.txt"):
        assets.append(
            {
                "file": filename,
                "text": (PROMPT_ROOT / VERSION / filename).read_text(encoding="utf-8"),
            }
        )
    sys.path.insert(0, str(BASE / "backend"))
    from app.agents.rag_judge_agent import RagJudgeAgent

    repair = (
        RagJudgeAgent("faithfulness", llm=object(), prompt_version=VERSION)._repair_example() or ""
    )
    assets.append({"file": "repair_example.json", "text": repair})
    return assets


def _load_whitelist() -> list[dict[str, str]]:
    if not WHITELIST_FILE.is_file():
        return []
    data = load_json(WHITELIST_FILE)
    return data if isinstance(data, list) else []


def _is_whitelisted(
    finding: dict[str, Any], whitelist: list[dict[str, str]]
) -> tuple[bool, str | None]:
    for entry in whitelist:
        if entry.get("prompt_file") != finding["prompt_file"]:
            continue
        if entry.get("text") != finding["text"]:
            continue
        return True, entry.get("reason")
    return False, None


def run_audit() -> dict[str, Any]:
    sources = collect_sources()
    assets = load_prompt_assets()
    whitelist = _load_whitelist()
    findings: list[dict[str, Any]] = []
    for asset in assets:
        prompt_norm, prompt_lines = _line_map(asset["text"])
        prompt_text_lines = asset["text"].splitlines()
        for source in sources:
            source_norm = normalize(source["text"])
            if len(source_norm) < MIN_CHARS:
                continue
            matcher = SequenceMatcher(None, source_norm, prompt_norm, autojunk=False)
            for block in matcher.get_matching_blocks():
                if block.size < MIN_CHARS:
                    continue
                matched = source_norm[block.b : block.b + block.size]
                line = prompt_lines[block.b]
                finding = {
                    "prompt_file": asset["file"],
                    "line": line,
                    "prompt_text": (
                        prompt_text_lines[line - 1].strip()
                        if 0 < line <= len(prompt_text_lines)
                        else ""
                    ),
                    "case_id": source["case_id"],
                    "source": source["source"],
                    "text": matched,
                    "length": block.size,
                }
                whitelisted, reason = _is_whitelisted(finding, whitelist)
                finding["whitelisted"] = whitelisted
                finding["whitelist_reason"] = reason
                findings.append(finding)
    # Deduplicate identical findings.
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for finding in findings:
        key = (
            finding["prompt_file"],
            finding["line"],
            finding["case_id"],
            finding["source"],
            finding["text"],
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(finding)
    deduped.sort(
        key=lambda item: (
            item["prompt_file"],
            item["line"],
            item["case_id"],
            item["source"],
            item["text"],
        )
    )
    by_prompt = Counter(item["prompt_file"] for item in deduped)
    by_case = Counter(item["case_id"] for item in deduped)
    non_whitelisted = [item for item in deduped if not item["whitelisted"]]
    return {
        "name": "m1d5-prompt-leakage-audit",
        "version": VERSION,
        "min_chars": MIN_CHARS,
        "initial_audit": {
            "finding_count": 113,
            "by_prompt": {
                "faithfulness.txt": 69,
                "answer_correctness.txt": 43,
                "answer_relevancy.txt": 1,
            },
            "by_case": {
                "Q01": 27,
                "Q11": 22,
                "Q17": 12,
                "Q21": 18,
                "Q23": 26,
                "Q31": 2,
                "Q35": 1,
                "Q36": 5,
            },
            "note": "去案例化前的首轮审计；用于记录泄漏范围，不是当前 findings。",
        },
        "source_files": [
            str(FIXTURE_FILE.relative_to(BASE)),
            str(M1D3_FILE.relative_to(BASE)),
            str(M1D4_FILE.relative_to(BASE)),
        ],
        "prompt_assets": [asset["file"] for asset in assets],
        "source_count": len(sources),
        "finding_count": len(deduped),
        "non_whitelisted_count": len(non_whitelisted),
        "by_prompt": dict(sorted(by_prompt.items())),
        "by_case": dict(sorted(by_case.items())),
        "findings": deduped,
        "status": "pass" if not non_whitelisted else "fail",
    }


def render_markdown(audit: dict[str, Any]) -> str:
    lines = [
        "# M1-D-5 v1.2.3 Prompt 泄漏审计",
        "",
        f"> 状态：`{audit['status']}`；最小匹配长度：{audit['min_chars']} 个归一化字符。",
        f"> 来源：{', '.join(audit['source_files'])}",
        f"> 审计对象：{', '.join(audit['prompt_assets'])}",
        f"> findings：{audit['finding_count']}；未 whitelist：{audit['non_whitelisted_count']}",
        f"> 首轮（去案例化前）：{audit['initial_audit']['finding_count']} findings；"
        f"by_prompt={audit['initial_audit']['by_prompt']}；"
        f"by_case={audit['initial_audit']['by_case']}",
        "",
        "## 按 Prompt",
        "",
        "| Prompt | findings |",
        "|---|---:|",
    ]
    for name, count in audit["by_prompt"].items():
        lines.append(f"| `{name}` | {count} |")
    lines.extend(["", "## 按 Case", "", "| Case | findings |", "|---|---:|"])
    for name, count in audit["by_case"].items():
        lines.append(f"| {name} | {count} |")
    lines.extend(
        [
            "",
            "## Findings",
            "",
            "| Prompt | 行 | Case | 来源 | 匹配文本 | 长度 | whitelist |",
            "|---|---:|---|---|---|---:|---|",
        ]
    )
    for finding in audit["findings"]:
        text = finding["text"].replace("|", "\\|")
        lines.append(
            f"| `{finding['prompt_file']}` | {finding['line']} | {finding['case_id']} | "
            f"{finding['source']} | {text} | {finding['length']} | "
            f"{'yes' if finding['whitelisted'] else 'no'} |"
        )
    if not audit["findings"]:
        lines.append("| — | — | — | — | 无 | 0 | — |")
    lines.extend(
        [
            "",
            "## 规则",
            "",
            "- contexts 全文不进 Prompt 审计（运行时本来会输入 contexts）。",
            "- answer、gold_answer、Judge claim、evidence quote 的 ≥12 字符共享子串必须为 0。",
            "- 任何 whitelist 必须逐条写明“不是任一 gate case 的 claim/evidence”。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    audit = run_audit()
    OUT_JSON.write_text(json.dumps(audit, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    OUT_MD.write_text(render_markdown(audit), encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "status": audit["status"],
                "finding_count": audit["finding_count"],
                "non_whitelisted_count": audit["non_whitelisted_count"],
                "by_prompt": audit["by_prompt"],
                "by_case": audit["by_case"],
            },
            ensure_ascii=False,
            indent=1,
        )
    )
    if audit["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
