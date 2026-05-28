from __future__ import annotations

import argparse
import dataclasses
import html
import json
import sys
import webbrowser
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))

from progetto.qfpuf import QFPUFConfig, load_config, run_enrollment, run_verification


def _parse_chips(values: List[str]) -> Dict[str, int]:
    chips: Dict[str, int] = {}
    for item in values:
        if "=" not in item:
            raise ValueError(f"Invalid chip spec '{item}', expected NAME=SEED")
        name, seed = item.split("=", 1)
        name = name.strip()
        if not name:
            raise ValueError(f"Invalid chip name in '{item}'")
        chips[name] = int(seed)
    return chips


def _enroll_chips(
    config: QFPUFConfig, chips: Dict[str, int]
) -> Dict[str, Dict[str, Any]]:
    enrollments: Dict[str, Dict[str, Any]] = {}
    for name, seed in chips.items():
        chip_config = dataclasses.replace(config, enrollment_instance_seed=seed)
        enrollments[name] = run_enrollment(chip_config)
    return enrollments


def _cross_matrix(
    config: QFPUFConfig,
    chips: Dict[str, int],
    enrollments: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    cells: List[Dict[str, Any]] = []
    for enrolled_name in chips:
        enrollment = enrollments[enrolled_name]
        for executed_name, executed_seed in chips.items():
            verify_config = dataclasses.replace(
                config, verification_instance_seed=executed_seed
            )
            report = run_verification(verify_config, enrollment)
            cells.append(
                {
                    "enrolled": enrolled_name,
                    "executed": executed_name,
                    "legitimate": enrolled_name == executed_name,
                    "average_fidelity": report["average_fidelity"],
                    "average_qber": report["average_qber"],
                    "accepted": report["accepted"],
                }
            )
    return cells


def _matrix_lookup(cells: List[Dict[str, Any]]) -> Dict[Tuple[str, str], Dict[str, Any]]:
    return {(cell["enrolled"], cell["executed"]): cell for cell in cells}


def _print_matrix(chips: Dict[str, int], cells: List[Dict[str, Any]]) -> None:
    lookup = _matrix_lookup(cells)
    names = list(chips)
    width = max((len(name) for name in names), default=4) + 2
    header = "enroll \\ exec".ljust(width) + "".join(name.ljust(width) for name in names)
    print(header)
    for enrolled in names:
        row = enrolled.ljust(width)
        for executed in names:
            cell = lookup[(enrolled, executed)]
            row += f"{cell['average_fidelity']:.3f}".ljust(width)
        print(row)

    print()
    print("Acceptance (1 = authenticated):")
    header = "enroll \\ exec".ljust(width) + "".join(name.ljust(width) for name in names)
    print(header)
    for enrolled in names:
        row = enrolled.ljust(width)
        for executed in names:
            cell = lookup[(enrolled, executed)]
            row += ("1" if cell["accepted"] else "0").ljust(width)
        print(row)


def _summary(cells: List[Dict[str, Any]]) -> Dict[str, Any]:
    legit = [cell for cell in cells if cell["legitimate"]]
    impostor = [cell for cell in cells if not cell["legitimate"]]

    def _avg(items: List[Dict[str, Any]], key: str) -> float:
        return sum(item[key] for item in items) / len(items) if items else 0.0

    false_rejects = sum(1 for cell in legit if not cell["accepted"])
    false_accepts = sum(1 for cell in impostor if cell["accepted"])
    return {
        "legitimate_pairs": len(legit),
        "impostor_pairs": len(impostor),
        "avg_fidelity_legitimate": _avg(legit, "average_fidelity"),
        "avg_fidelity_impostor": _avg(impostor, "average_fidelity"),
        "avg_qber_legitimate": _avg(legit, "average_qber"),
        "avg_qber_impostor": _avg(impostor, "average_qber"),
        "false_rejects": false_rejects,
        "false_accepts": false_accepts,
    }


def _heatmap_color(value: float, vmin: float, vmax: float) -> str:
    if vmax <= vmin:
        ratio = 0.0
    else:
        ratio = max(0.0, min(1.0, (value - vmin) / (vmax - vmin)))
    red = int(220 - ratio * (220 - 37))
    green = int(38 + ratio * (197 - 38))
    blue = int(38 + ratio * (94 - 38))
    return f"rgb({red},{green},{blue})"


def _render_html(
    chips: Dict[str, int],
    cells: List[Dict[str, Any]],
    summary: Dict[str, Any],
    threshold: float,
) -> str:
    lookup = _matrix_lookup(cells)
    names = list(chips)
    fidelities = [cell["average_fidelity"] for cell in cells]
    vmin, vmax = min(fidelities), max(fidelities)

    head_cells = "".join(f"<th>{html.escape(name)}</th>" for name in names)
    rows = []
    for enrolled in names:
        row = [f"<th>{html.escape(enrolled)}</th>"]
        for executed in names:
            cell = lookup[(enrolled, executed)]
            value = cell["average_fidelity"]
            color = _heatmap_color(value, vmin, vmax)
            border = "3px solid #111827" if cell["legitimate"] else "1px solid #e5e7eb"
            mark = "OK" if cell["accepted"] else "REJECT"
            row.append(
                f'<td style="background:{color};border:{border}">'
                f'<div class="val">{value:.3f}</div>'
                f'<div class="tag">{mark}</div></td>'
            )
        rows.append("<tr>" + "".join(row) + "</tr>")

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>QFPUF cross-verification matrix</title>
  <style>
    body {{ font-family: system-ui, -apple-system, "Segoe UI", sans-serif; background:#f8fafc; color:#111827; margin:0; }}
    .wrap {{ max-width: 1000px; margin: 0 auto; padding: 24px; }}
    .panel {{ background:#fff; border:1px solid #d0d7de; border-radius:16px; padding:20px; margin-bottom:20px; }}
    .title {{ font-size:18px; font-weight:700; margin-bottom:10px; }}
    table {{ border-collapse:collapse; }}
    th, td {{ padding:10px 14px; text-align:center; }}
    td {{ color:#fff; }}
    .val {{ font-size:16px; font-weight:700; }}
    .tag {{ font-size:10px; opacity:0.9; }}
    .legend {{ font-size:13px; color:#6b7280; line-height:1.6; }}
    .metrics {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:12px; margin-top:12px; }}
    .card {{ border:1px solid #d0d7de; border-radius:12px; padding:12px; }}
    .card .lbl {{ font-size:12px; color:#6b7280; }}
    .card .num {{ font-size:22px; font-weight:700; }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="panel">
      <div class="title">QFPUF cross-verification matrix</div>
      <div class="legend">
        Rows = enrolled chip (fingerprint owner), columns = executing chip.<br>
        Diagonal (bold border) = legitimate; off-diagonal = spoofing attempt.<br>
        Acceptance threshold: fidelity &ge; {threshold:.3f}.
      </div>
      <div class="metrics">
        <div class="card"><div class="lbl">Avg fidelity legitimate</div><div class="num">{summary['avg_fidelity_legitimate']:.3f}</div></div>
        <div class="card"><div class="lbl">Avg fidelity impostor</div><div class="num">{summary['avg_fidelity_impostor']:.3f}</div></div>
        <div class="card"><div class="lbl">False accepts</div><div class="num">{summary['false_accepts']}</div></div>
        <div class="card"><div class="lbl">False rejects</div><div class="num">{summary['false_rejects']}</div></div>
      </div>
    </div>
    <div class="panel">
      <table>
        <thead><tr><th>enroll \\ exec</th>{head_cells}</tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </div>
  </div>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run QFPUF cross-verification across multiple simulated chips"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("progetto/qfpuf_config.json"),
        help="Path to QFPUF config JSON",
    )
    parser.add_argument(
        "--chip",
        action="append",
        default=None,
        metavar="NAME=SEED",
        help="Chip definition as NAME=SEED (repeatable)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("progetto/risultati/qpuf/qfpuf_cross_matrix.json"),
        help="Path for the cross-verification JSON result",
    )
    parser.add_argument(
        "--html",
        type=Path,
        default=None,
        help="Optional path for an HTML heatmap of the matrix",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open the generated HTML report in a browser",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    chip_specs = args.chip or ["ChipA=42", "ChipB=1337", "ChipC=2024"]
    chips = _parse_chips(chip_specs)
    if len(chips) < 2:
        raise SystemExit("Provide at least two chips to compare")

    enrollments = _enroll_chips(config, chips)
    cells = _cross_matrix(config, chips, enrollments)
    summary = _summary(cells)

    _print_matrix(chips, cells)
    print()
    print(
        f"Legitimate avg fidelity: {summary['avg_fidelity_legitimate']:.4f} | "
        f"Impostor avg fidelity: {summary['avg_fidelity_impostor']:.4f}"
    )
    print(
        f"False accepts: {summary['false_accepts']} | "
        f"False rejects: {summary['false_rejects']}"
    )

    payload = {
        "chips": chips,
        "thresholds": {
            "fidelity": config.fidelity_threshold,
            "qber": config.qber_threshold,
        },
        "matrix": cells,
        "summary": summary,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2))
    print(f"Saved cross-verification matrix to {args.output}")

    if args.html is not None:
        report = _render_html(chips, cells, summary, config.fidelity_threshold)
        args.html.parent.mkdir(parents=True, exist_ok=True)
        args.html.write_text(report, encoding="utf-8")
        print(f"Saved heatmap to {args.html}")
        if args.open:
            webbrowser.open(args.html.resolve().as_uri())


if __name__ == "__main__":
    main()
