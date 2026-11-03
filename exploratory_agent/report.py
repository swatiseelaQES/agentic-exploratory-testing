import json
import re
from datetime import datetime, timezone
from html import escape
from pathlib import Path


STATUS_RANK = {
    "suspicion": 0,
    "investigating": 1,
    "reproduced": 2,
}


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _finding_key(finding: dict) -> str:
    if finding.get("finding_key"):
        return finding["finding_key"]

    return re.sub(
        r"[^a-z0-9]+",
        "_",
        finding.get("title", "finding").lower(),
    ).strip("_")


def _merge_findings(history: list[dict]) -> dict[str, dict]:
    """
    Consolidate all updates that use the same finding_key.

    The most advanced lifecycle state becomes the primary record.
    Evidence steps and reproduction steps are accumulated.
    """
    merged: dict[str, dict] = {}

    for step_number, item in enumerate(history, 1):
        finding = item["decision"].get("finding")

        if not finding:
            continue

        finding = dict(finding)
        key = _finding_key(finding)

        finding.setdefault("evidence_steps", [])
        finding["evidence_steps"] = sorted(
            set(finding["evidence_steps"] + [step_number])
        )

        existing = merged.get(key)

        if existing is None:
            merged[key] = finding
            continue

        combined_evidence = sorted(
            set(
                existing.get("evidence_steps", [])
                + finding.get("evidence_steps", [])
            )
        )

        combined_reproduction = list(
            dict.fromkeys(
                existing.get("reproduction", [])
                + finding.get("reproduction", [])
            )
        )

        current_rank = STATUS_RANK.get(
            finding.get("status", "suspicion"),
            0,
        )
        existing_rank = STATUS_RANK.get(
            existing.get("status", "suspicion"),
            0,
        )

        if current_rank >= existing_rank:
            merged[key] = finding

        merged[key]["evidence_steps"] = combined_evidence
        merged[key]["reproduction"] = combined_reproduction

    return merged


def _collect_coverage(history: list[dict]) -> dict[str, dict]:
    """
    Return coverage keyed by normalized charter-area name.

    Each entry retains the model's displayed name and its supporting steps.
    """
    coverage: dict[str, dict] = {}

    for step_number, item in enumerate(history, 1):
        area = item["decision"].get("coverage_area")

        if not area:
            continue

        normalized = _normalize(area)

        if normalized not in coverage:
            coverage[normalized] = {
                "name": area,
                "steps": [],
            }

        coverage[normalized]["steps"].append(step_number)

    return coverage


def _depth_label(step_count: int) -> str:
    if step_count == 0:
        return "Not examined"

    if step_count < 3:
        return "Exercised"

    return "Repeated or varied"


def write_report(
    session_dir: Path,
    charter: str,
    charter_data: dict,
    history: list[dict],
) -> Path:
    report_path = session_dir / "report.md"
    raw_data_path = session_dir / "session.json"

    findings = _merge_findings(history)

    reproduced = [
        finding
        for finding in findings.values()
        if finding.get("status") == "reproduced"
    ]

    open_items = [
        finding
        for finding in findings.values()
        if finding.get("status") != "reproduced"
    ]

    review_items = open_items + [
        finding
        for finding in reproduced
        if finding.get("causal_status") == "inferred"
    ]

    coverage = _collect_coverage(history)

    focus_areas = [
        str(area)
        for area in charter_data.get("focus_areas", [])
    ]

    untested_areas = [
        area
        for area in focus_areas
        if _normalize(area) not in coverage
    ]

    generated = datetime.now(timezone.utc).isoformat()

    lines = [
        "# Exploratory testing report",
        "",
        f"Generated: {generated}",
        "",
        "## Decision summary",
        "",
        f"- **Mission:** {charter_data.get('mission', 'Not supplied')}",
        f"- **Actions performed:** {len(history)}",
        f"- **Unique reproduced findings:** {len(reproduced)}",
        f"- **Open suspicions:** {len(open_items)}",
        f"- **Items requiring human review:** {len(review_items)}",
        (
            f"- **Coverage areas exercised:** "
            f"{len(coverage)} of {len(focus_areas)} charter focus areas"
        ),
        "",
    ]

    lines.extend(
        _render_reproduced_findings(reproduced)
    )

    lines.extend(
        _render_human_review_queue(review_items)
    )

    lines.extend(
        _render_coverage(focus_areas, coverage)
    )

    lines.extend(
        _render_remaining_uncertainty(
            open_items,
            untested_areas,
        )
    )

    lines.extend(
        _render_regression_suggestions(reproduced)
    )

    lines.extend(
        _render_action_appendix(history)
    )

    lines.extend(
        [
            "## Raw session data",
            "",
            (
                "See `session.json` for the complete structured "
                "observations and decisions."
            ),
            "",
        ]
    )

    report_path.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    raw_data_path.write_text(
        json.dumps(history, indent=2),
        encoding="utf-8",
    )

    (session_dir / "report.html").write_text(
        _render_html(
            generated, charter_data.get("mission", "Not supplied"),
            reproduced, review_items, focus_areas, coverage, history,
        ),
        encoding="utf-8",
    )

    return report_path


def _render_reproduced_findings(
    reproduced: list[dict],
) -> list[str]:
    lines = [
        "## Reproduced findings",
        "",
    ]

    if not reproduced:
        lines.extend(
            [
                "No finding reached the reproduced threshold.",
                "",
            ]
        )
        return lines

    for index, finding in enumerate(reproduced, 1):
        evidence = ", ".join(
            f"step {step}"
            for step in finding.get("evidence_steps", [])
        )

        if not evidence:
            evidence = "Not linked"

        causal_status = finding.get(
            "causal_status",
            "not_claimed",
        ).replace("_", " ")

        lines.extend(
            [
                f"### F{index}: {finding['title']}",
                "",
                f"- **Confidence:** {finding['confidence']}",
                f"- **Causal status:** {causal_status}",
                f"- **Expected:** {finding['expected']}",
                f"- **Actual:** {finding['actual']}",
                f"- **Evidence:** {evidence}",
            ]
        )

        if finding.get("causal_explanation"):
            lines.append(
                "- **Causal explanation:** "
                + finding["causal_explanation"]
            )

        lines.extend(
            [
                "",
                "**Shortest reproduced path:**",
                "",
            ]
        )

        reproduction = finding.get("reproduction", [])

        if reproduction:
            lines.extend(
                f"{number}. {step}"
                for number, step in enumerate(
                    reproduction,
                    1,
                )
            )
        else:
            lines.append("Not recorded.")

        lines.append("")

    return lines


def _render_human_review_queue(
    review_items: list[dict],
) -> list[str]:
    lines = [
        "## Human review queue",
        "",
    ]

    if not review_items:
        lines.extend(
            [
                (
                    "No unresolved suspicion or inferred causal "
                    "claim requires review."
                ),
                "",
            ]
        )
        return lines

    for finding in review_items:
        if finding.get("status") != "reproduced":
            reason = "Finding has not been reproduced."
        else:
            reason = (
                "The behavior was reproduced, but its causal "
                "explanation remains inferred."
            )

        lines.append(
            f"- **{finding['title']}** — {reason}"
        )

    lines.append("")
    return lines


def _render_coverage(
    focus_areas: list[str],
    coverage: dict[str, dict],
) -> list[str]:
    lines = [
        "## Coverage and depth",
        "",
        "| Charter dimension | Evidence | Depth |",
        "|---|---|---|",
    ]

    for area in focus_areas:
        entry = coverage.get(
            _normalize(area),
            {"steps": []},
        )
        steps = entry["steps"]

        if steps:
            evidence = "Steps " + ", ".join(
                str(step)
                for step in steps
            )
        else:
            evidence = "—"

        lines.append(
            f"| {area} | {evidence} | "
            f"{_depth_label(len(steps))} |"
        )

    lines.append("")
    return lines


def _render_remaining_uncertainty(
    open_items: list[dict],
    untested_areas: list[str],
) -> list[str]:
    lines = [
        "## Remaining uncertainty",
        "",
    ]

    if open_items:
        for finding in open_items:
            lines.append(
                f"- **{finding['title']}:** "
                f"{finding.get('actual', 'Further investigation required.')}"
            )
    else:
        lines.append(
            "- No recorded suspicion remained open."
        )

    if untested_areas:
        lines.append(
            "- **Intentionally or operationally unexamined:** "
            + ", ".join(untested_areas)
            + "."
        )

    lines.append("")
    return lines


def _render_regression_suggestions(
    reproduced: list[dict],
) -> list[str]:
    lines = [
        "## Suggested regression checks",
        "",
    ]

    if not reproduced:
        lines.extend(
            [
                (
                    "- None proposed because no defect was "
                    "reproduced."
                ),
                "",
            ]
        )
        return lines

    for finding in reproduced:
        lines.append(
            "- After human confirmation, convert the shortest "
            f"reproduced path for **{finding['title']}** into "
            "a deterministic regression check."
        )

    lines.append("")
    return lines


def _render_action_appendix(
    history: list[dict],
) -> list[str]:
    lines = [
        "## Action trace (appendix)",
        "",
        "| Step | Action | Coverage area | What was learned |",
        "|---:|---|---|---|",
    ]

    for index, item in enumerate(history, 1):
        decision = item["decision"]

        learned = (
            decision.get("learned")
            or decision.get("reason")
            or ""
        )

        learned = (
            learned
            .replace("|", "\\|")
            .replace("\n", " ")
        )

        coverage_area = (
            decision.get("coverage_area")
            or "—"
        )

        lines.append(
            f"| {index} | {decision['action']} | "
            f"{coverage_area} | {learned} |"
        )

    lines.append("")
    return lines
def _render_html(generated, mission, findings, review, areas, coverage, history):
    def e(value):
        return escape(str(value or ""))

    def links(steps):
        return " ".join(
            f'<a href="#step-{step}">Step {step}</a>'
            for step in steps if isinstance(step, int) and 1 <= step <= len(history)
        ) or "No linked steps"

    exercised = sum(_normalize(area) in coverage for area in areas)
    metrics = [
        (len(history), "Trace entries"),
        (len(findings), "Reproduced findings"),
        (f"{exercised}/{len(areas)}", "Charter areas exercised"),
        (len(review), "Items for human review"),
    ]
    parts = ["""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Exploratory testing report</title>
<style>
* { box-sizing: border-box }
body { margin: 0; background: #f7f5ef; color: #183633; font: 1rem/1.55 system-ui, sans-serif }
header { background: #103f3e; color: #fff; padding: 2rem max(1rem, calc((100% - 68rem)/2)) }
main { max-width: 70rem; margin: auto; padding: 1rem 1rem 3rem }
h1, h2, h3, p { margin: 0 0 .6rem }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 15rem), 1fr)); gap: .75rem }
section { margin-top: 1.7rem }
article, .tile, .trace { background: white; border: 1px solid #d4dfdb; border-radius: .7rem; padding: 1rem; overflow-wrap: anywhere }
article, .trace { margin-bottom: .75rem }
.tile strong { display: block; font-size: 1.5rem }
.finding { border-left: .35rem solid #bc5948 }
.observed { background: #fff1eb; padding: .65rem; border-radius: .35rem }
summary { cursor: pointer; font-weight: 650 }
a { color: #075955 }
:target { outline: 3px solid #bc5948 }
.steps a { display: inline-block; margin-right: .45rem }
</style></head><body>""",
        f"<header><p>Session report · {e(generated)}</p><h1>Exploratory testing</h1>"
        f"<p>{e(mission)}</p></header><main><div class='grid'>",
    ]
    parts.extend(f'<div class="tile"><strong>{count}</strong>{label}</div>' for count, label in metrics)
    parts.append("</div><section><h2>Reproduced findings</h2>")
    if not findings:
        parts.append("<p>No finding reached the reproduced threshold.</p>")
    for index, finding in enumerate(findings, 1):
        reproduction = "".join(f"<li>{e(step)}</li>" for step in finding.get("reproduction", []))
        parts.append(
            f'<article class="finding"><h3>F{index} · {e(finding["title"])}</h3>'
            f'<div class="grid"><p><strong>Expected</strong><br>{e(finding["expected"])}</p>'
            f'<p class="observed"><strong>Observed</strong><br>{e(finding["actual"])}</p></div>'
            f'<p class="steps">{links(finding.get("evidence_steps", []))}</p>'
            f'<details><summary>Reproduction notes</summary>'
            f'<p>Confidence · {e(finding["confidence"])}</p>'
            + (f"<ol>{reproduction}</ol>" if reproduction else "<p>No steps recorded.</p>")
            + "</details></article>"
        )
    parts.append("</section><section><h2>Human review</h2>")
    if not review:
        parts.append("<p>No findings queued for review.</p>")
    for finding in review:
        reason = (
            "Causal explanation remains inferred."
            if finding.get("status") == "reproduced"
            else "Further reproduction needed."
        )
        parts.append(
            f'<article><h3>{e(finding["title"])}</h3><p>{reason}</p>'
            f'<p>{e(finding.get("causal_explanation") if finding.get("status") == "reproduced" else finding.get("actual"))}</p>'
            f'<p class="steps">{links(finding.get("evidence_steps", []))}</p></article>'
        )
    parts.append('</section><section><h2>Coverage and depth</h2><div class="grid">')
    if not areas:
        parts.append("<p>No charter areas supplied.</p>")
    for area in areas:
        steps = coverage.get(_normalize(area), {}).get("steps", [])
        parts.append(
            f'<article><h3>{e(area)}</h3><p>{_depth_label(len(steps))}</p>'
            f'<p class="steps">{links(steps)}</p></article>'
        )
    parts.append('</div></section><section><details><summary>Action trace</summary>')
    for index, item in enumerate(history, 1):
        decision = item["decision"]
        error = item.get("execution_error")
        parts.append(
            f'<article class="trace" id="step-{index}"><h3>Step {index} · {e(decision["action"])}</h3>'
            f'<p>{e(decision.get("coverage_area"))}</p>'
            f'<p>{e(decision.get("learned") or decision.get("reason"))}</p>'
            + (f'<p><strong>Execution error</strong> · {e(error)}</p>' if error else "")
            + "</article>"
        )
    parts.append(
        '</details></section><footer><a href="report.md">Markdown report</a> · '
        '<a href="session.json">Session data</a></footer></main>'
        """<script>
function revealStep() {
    const target = document.getElementById(location.hash.slice(1));
    const trace = target?.closest("details");
    if (trace) {
        trace.open = true;
        target.scrollIntoView();
    }
}
addEventListener("hashchange", revealStep);
revealStep();
</script></body></html>"""
    )
    return "\n".join(parts)

