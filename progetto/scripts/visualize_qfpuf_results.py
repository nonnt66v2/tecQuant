from __future__ import annotations

import argparse
import html
import json
import sys
import webbrowser
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text())


def _probabilities(entry: Dict[str, Any]) -> Dict[str, float]:
    probs = entry.get("probabilities")
    if probs:
        return {str(key): float(value) for key, value in probs.items()}

    counts = entry.get("counts", {})
    shots = float(entry.get("shots") or sum(counts.values()) or 1)
    return {str(key): float(value) / shots for key, value in counts.items()}


def _ordered_states(*distributions: Dict[str, float]) -> List[str]:
    states = set()
    for distribution in distributions:
        states.update(distribution)
    return sorted(states, key=lambda state: (-max(distribution.get(state, 0.0) for distribution in distributions), state))


def _fmt_float(value: float) -> str:
    return f"{value:.4f}"


def _fmt_angles(angles: Sequence[float]) -> str:
    return ", ".join(_fmt_float(angle) for angle in angles)


def _entry_label(index: int, entry: Dict[str, Any]) -> str:
    challenge = entry.get("challenge", {})
    bitstring = challenge.get("bitstring", "?")
    return f"#{index + 1} · {bitstring}"


def _compare_entries(enrollment: Dict[str, Any], verification: Dict[str, Any]) -> List[Dict[str, Any]]:
    enrollment_entries = enrollment.get("entries", [])
    verification_entries = verification.get("results", [])
    if len(enrollment_entries) != len(verification_entries):
        raise ValueError(
            "Enrollment entries and verification results must have the same length"
        )

    comparisons: List[Dict[str, Any]] = []
    for index, (enrollment_entry, verification_entry) in enumerate(
        zip(enrollment_entries, verification_entries)
    ):
        enrollment_challenge = enrollment_entry.get("challenge", {})
        verification_challenge = verification_entry.get("challenge", {})
        if enrollment_challenge != verification_challenge:
            raise ValueError(
                f"Challenge mismatch at index {index}: "
                f"{enrollment_challenge!r} != {verification_challenge!r}"
            )

        enrollment_probs = _probabilities(enrollment_entry)
        verification_probs = _probabilities(verification_entry)
        states = _ordered_states(enrollment_probs, verification_probs)
        match = enrollment_entry.get("response") == verification_entry.get(
            "received_response"
        )
        comparisons.append(
            {
                "index": index,
                "label": _entry_label(index, enrollment_entry),
                "challenge": enrollment_challenge,
                "enrollment_response": enrollment_entry.get("response", ""),
                "verification_response": verification_entry.get("received_response", ""),
                "match": match,
                "fidelity": float(verification_entry.get("fidelity", 0.0)),
                "qber": float(verification_entry.get("qber", 0.0)),
                "states": states,
                "enrollment_probs": enrollment_probs,
                "verification_probs": verification_probs,
                "enrollment_counts": enrollment_entry.get("counts", {}),
                "verification_counts": verification_entry.get("counts", {}),
                "enrollment_angles": enrollment_challenge.get("angles", []),
            }
        )
    return comparisons


def _summary_stats(comparisons: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    if not comparisons:
        return {
            "entries": 0,
            "matches": 0,
            "average_fidelity": 0.0,
            "average_qber": 0.0,
            "average_distribution_drift": 0.0,
        }

    drift_values = []
    match_count = 0
    fidelity_values = []
    qber_values = []
    for comparison in comparisons:
        states = comparison["states"]
        drift = sum(
            abs(comparison["enrollment_probs"].get(state, 0.0) - comparison["verification_probs"].get(state, 0.0))
            for state in states
        ) / len(states)
        drift_values.append(drift)
        fidelity_values.append(float(comparison["fidelity"]))
        qber_values.append(float(comparison["qber"]))
        match_count += 1 if comparison["match"] else 0

    return {
        "entries": len(comparisons),
        "matches": match_count,
        "average_fidelity": sum(fidelity_values) / len(fidelity_values),
        "average_qber": sum(qber_values) / len(qber_values),
        "average_distribution_drift": sum(drift_values) / len(drift_values),
    }


def _svg_bar_rows(
    comparison: Dict[str, Any],
    width: int = 920,
    row_height: int = 24,
) -> str:
    states = comparison["states"]
    left_label_x = 16
    bar_start_x = 220
    bar_width = width - bar_start_x - 110
    bar_height = 7
    gap = 3
    axis_y = 56
    chart_height = axis_y + len(states) * row_height + 18
    tick_positions = [0.0, 0.25, 0.5, 0.75, 1.0]

    parts = [
        f'<svg viewBox="0 0 {width} {chart_height}" width="100%" height="{chart_height}" role="img" aria-label="{html.escape(comparison["label"])}">',
        f'<rect x="0" y="0" width="{width}" height="{chart_height}" rx="12" fill="#ffffff" stroke="#d0d7de"/>',
        f'<text x="{left_label_x}" y="24" font-size="16" font-weight="700" fill="#111827">{html.escape(comparison["label"])}</text>',
        (
            f'<text x="{left_label_x}" y="42" font-size="11" fill="#6b7280">'
            f'challenge: {html.escape(str(comparison["challenge"].get("bitstring", "")))} · '
            f'angles: {html.escape(_fmt_angles(comparison["enrollment_angles"]))}'
            "</text>"
        ),
    ]

    for tick in tick_positions:
        x = bar_start_x + bar_width * tick
        parts.append(
            f'<line x1="{x:.1f}" y1="{axis_y - 10}" x2="{x:.1f}" y2="{chart_height - 14}" stroke="#e5e7eb" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{x:.1f}" y="{axis_y - 15}" font-size="10" text-anchor="middle" fill="#9ca3af">{int(tick * 100)}%</text>'
        )

    parts.extend(
        [
            f'<text x="{bar_start_x}" y="{axis_y - 2}" font-size="11" font-weight="600" fill="#2563eb">Enrollment</text>',
            f'<text x="{bar_start_x + bar_width / 2}" y="{axis_y - 2}" font-size="11" font-weight="600" fill="#f97316">Verification</text>',
            f'<line x1="{bar_start_x}" y1="{axis_y}" x2="{width - 18}" y2="{axis_y}" stroke="#cbd5e1" stroke-width="1"/>',
        ]
    )

    for row, state in enumerate(states):
        y = axis_y + 14 + row * row_height
        enrollment_value = float(comparison["enrollment_probs"].get(state, 0.0))
        verification_value = float(comparison["verification_probs"].get(state, 0.0))
        enrollment_width = bar_width * enrollment_value
        verification_width = bar_width * verification_value
        parts.append(
            f'<text x="{left_label_x}" y="{y}" font-size="12" fill="#111827">{html.escape(state)}</text>'
        )
        parts.append(
            f'<rect x="{bar_start_x}" y="{y - bar_height - gap}" width="{enrollment_width:.2f}" height="{bar_height}" rx="3" fill="#2563eb">'
            f'<title>Enrollment {state}: {comparison["enrollment_counts"].get(state, 0)} ({_fmt_float(enrollment_value)})</title></rect>'
        )
        parts.append(
            f'<rect x="{bar_start_x}" y="{y + gap}" width="{verification_width:.2f}" height="{bar_height}" rx="3" fill="#f97316">'
            f'<title>Verification {state}: {comparison["verification_counts"].get(state, 0)} ({_fmt_float(verification_value)})</title></rect>'
        )
        parts.append(
            f'<text x="{bar_start_x + enrollment_width + 6:.2f}" y="{y - 1}" font-size="10" fill="#1f2937">{_fmt_float(enrollment_value)}</text>'
        )
        parts.append(
            f'<text x="{bar_start_x + verification_width + 6:.2f}" y="{y + 11}" font-size="10" fill="#1f2937">{_fmt_float(verification_value)}</text>'
        )

    parts.append("</svg>")
    return "".join(parts)


def _metric_card(label: str, value: str, color: str) -> str:
    return (
        f'<div class="metric-card"><div class="metric-label">{html.escape(label)}</div>'
        f'<div class="metric-value" style="color:{color}">{html.escape(value)}</div></div>'
    )


def _render_report(
    comparisons: Sequence[Dict[str, Any]],
    summary: Dict[str, Any],
    enrollment_path: Path,
    verification_path: Path,
) -> str:
    rows = []
    for comparison in comparisons:
        rows.append(
            "<tr>"
            f"<td>{html.escape(comparison['label'])}</td>"
            f"<td>{html.escape(comparison['enrollment_response'])}</td>"
            f"<td>{html.escape(comparison['verification_response'])}</td>"
            f"<td>{'yes' if comparison['match'] else 'no'}</td>"
            f"<td>{_fmt_float(float(comparison['fidelity']))}</td>"
            f"<td>{_fmt_float(float(comparison['qber']))}</td>"
            "</tr>"
        )

    charts = "\n".join(_svg_bar_rows(comparison) for comparison in comparisons)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>QFPUF comparison report</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f8fafc;
      --card: #ffffff;
      --border: #d0d7de;
      --text: #111827;
      --muted: #6b7280;
    }}
    body {{
      margin: 0;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--text);
    }}
    .wrap {{
      max-width: 1280px;
      margin: 0 auto;
      padding: 24px;
    }}
    .panel {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 20px;
      margin-bottom: 20px;
      box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
    }}
    .meta {{
      color: var(--muted);
      font-size: 13px;
      line-height: 1.6;
    }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 12px;
      margin-top: 14px;
    }}
    .metric-card {{
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 12px;
      background: #fff;
    }}
    .metric-label {{
      font-size: 12px;
      color: var(--muted);
      margin-bottom: 4px;
    }}
    .metric-value {{
      font-size: 22px;
      font-weight: 700;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 12px;
      font-size: 13px;
    }}
    th, td {{
      border-bottom: 1px solid var(--border);
      padding: 8px 10px;
      text-align: left;
    }}
    th {{
      color: var(--muted);
      font-weight: 600;
      background: #f9fafb;
    }}
    .charts {{
      display: grid;
      gap: 16px;
    }}
    .section-title {{
      font-size: 18px;
      font-weight: 700;
      margin: 0 0 10px 0;
    }}
    .subtle {{
      color: var(--muted);
      font-size: 12px;
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="panel">
      <div class="section-title">QFPUF verification vs enrollment</div>
      <div class="meta">
        Enrollment: {html.escape(str(enrollment_path))}<br>
        Verification: {html.escape(str(verification_path))}
      </div>
      <div class="metrics">
        {_metric_card("Entries", str(summary["entries"]), "#111827")}
        {_metric_card("Exact matches", f'{summary["matches"]}/{summary["entries"]}', "#2563eb")}
        {_metric_card("Average fidelity", _fmt_float(float(summary["average_fidelity"])), "#2563eb")}
        {_metric_card("Average QBER", _fmt_float(float(summary["average_qber"])), "#f97316")}
        {_metric_card("Avg distribution drift", _fmt_float(float(summary["average_distribution_drift"])), "#7c3aed")}
      </div>
    </div>

    <div class="panel">
      <div class="section-title">Per-entry comparison</div>
      <div class="subtle">Blue = enrollment, orange = verification.</div>
      <table>
        <thead>
          <tr>
            <th>Entry</th>
            <th>Enrollment response</th>
            <th>Verification response</th>
            <th>Match</th>
            <th>Fidelity</th>
            <th>QBER</th>
          </tr>
        </thead>
        <tbody>
          {''.join(rows)}
        </tbody>
      </table>
    </div>

    <div class="charts">
      {charts}
    </div>
  </div>
</body>
</html>
"""


def _resolve_default_paths() -> Tuple[Path, Path, Path]:
    candidates = [
        ROOT / "progetto/risultati/qpuf/qfpuf_enrollment.json",
        ROOT / "progetto/risultati/qfpuf/qfpuf_enrollment.json",
    ]
    enrollment_path = next((path for path in candidates if path.exists()), candidates[0])

    verification_candidates = [
        ROOT / "progetto/risultati/qpuf/qfpuf_verification.json",
        ROOT / "progetto/risultati/qfpuf/qfpuf_verification.json",
    ]
    verification_path = next(
        (path for path in verification_candidates if path.exists()),
        verification_candidates[0],
    )

    output_candidates = [
        ROOT / "progetto/risultati/qpuf/qfpuf_comparison.html",
        ROOT / "progetto/risultati/qfpuf/qfpuf_comparison.html",
    ]
    output_path = output_candidates[0]
    return enrollment_path, verification_path, output_path


def main() -> None:
    default_enrollment, default_verification, default_output = _resolve_default_paths()

    parser = argparse.ArgumentParser(
        description="Visualize QFPUF verification results and compare them with enrollment"
    )
    parser.add_argument(
        "--enrollment",
        type=Path,
        default=default_enrollment,
        help="Path to qfpuf_enrollment.json",
    )
    parser.add_argument(
        "--verification",
        type=Path,
        default=default_verification,
        help="Path to qfpuf_verification.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=default_output,
        help="Path for the generated HTML report",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open the generated report in a browser",
    )
    args = parser.parse_args()

    enrollment = _load_json(args.enrollment)
    verification = _load_json(args.verification)
    comparisons = _compare_entries(enrollment, verification)
    summary = _summary_stats(comparisons)
    report = _render_report(comparisons, summary, args.enrollment, args.verification)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(f"Saved comparison report to {args.output}")

    if args.open:
        webbrowser.open(args.output.resolve().as_uri())


if __name__ == "__main__":
    main()
