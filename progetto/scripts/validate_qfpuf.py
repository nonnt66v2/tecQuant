from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _format_float(value: Any, digits: int) -> str:
    if not isinstance(value, (int, float)):
        raise TypeError(f"Expected numeric value, got {type(value).__name__}")
    return f"{float(value):.{digits}f}"


def _format_angles(angles: Any) -> str:
    if not isinstance(angles, list):
        raise TypeError("Challenge angles must be a list")
    return ", ".join(_format_float(angle, 3) for angle in angles)


def _render_html(report: Dict[str, Any]) -> str:
    summary = report["summary"]
    entries: List[Dict[str, Any]] = report["entries"]
    thresholds = summary.get("thresholds", {})
    accepted = bool(summary["accepted"])
    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")

    mismatch_indices = [str(entry["index"]) for entry in entries if not entry["match"]]
    mismatch_text = ", ".join(mismatch_indices) if mismatch_indices else "Nessun mismatch"

    row_html: List[str] = []
    for entry in entries:
        challenge = entry["challenge"]
        row_class = "match-false" if not entry["match"] else "match-true"
        row_html.append(
            "<tr class='{row_class}'>"
            "<td>{index}</td>"
            "<td>{bitstring}</td>"
            "<td>{angles}</td>"
            "<td>{enrollment_response}</td>"
            "<td>{expected_response}</td>"
            "<td>{received_response}</td>"
            "<td>{match}</td>"
            "<td>{fidelity}</td>"
            "<td>{qber}</td>"
            "<td>{enrollment_dom}</td>"
            "<td>{verification_dom}</td>"
            "</tr>".format(
                row_class=row_class,
                index=escape(str(entry["index"])),
                bitstring=escape(str(challenge.get("bitstring", ""))),
                angles=escape(_format_angles(challenge.get("angles", []))),
                enrollment_response=escape(str(entry["enrollment_response"])),
                expected_response=escape(str(entry["verification_expected_response"])),
                received_response=escape(str(entry["verification_received_response"])),
                match=escape("SI" if entry["match"] else "NO"),
                fidelity=escape(_format_float(entry["fidelity"], 4)),
                qber=escape(_format_float(entry["qber"], 4)),
                enrollment_dom=escape(str(entry["enrollment_dominant_measurement"])),
                verification_dom=escape(str(entry["verification_dominant_measurement"])),
            )
        )

    accepted_label = "ACCETTATO" if accepted else "RIFIUTATO"
    accepted_class = "accepted" if accepted else "rejected"

    return f"""<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>QFPUF - Report confronto</title>
      <style>
      :root {{
  --primary: #2563eb;
  --primary-light: #eff6ff;
  --success: #16a34a;
  --success-bg: #dcfce7;
  --danger: #dc2626;
  --danger-bg: #fee2e2;
  --text: #1e293b;
  --muted: #64748b;
  --border: #e2e8f0;
  --surface: #ffffff;
  --background: #f8fafc;
  --shadow: 0 10px 25px rgba(15, 23, 42, 0.08);
  --radius: 16px;
}}

* {{
  box-sizing: border-box;
}}

body {{
  font-family: Inter, "Segoe UI", sans-serif;
  margin: 0;
  padding: 40px;
  color: var(--text);
  background: var(--background);
  line-height: 1.5;
}}

.header {{
  background: linear-gradient(
    135deg,
    #2563eb 0%,
    #1d4ed8 100%
  );
  color: white;
  padding: 32px;
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  margin-bottom: 28px;
}}

.section {{
  background: var(--surface);
  border-radius: var(--radius);
  padding: 24px;
  box-shadow: var(--shadow);
  margin-bottom: 24px;
}}

.badge {{
  display: inline-flex;
  align-items: center;
  padding: 8px 14px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 700;
}}

.accepted {{
  background: var(--success-bg);
  color: var(--success);
}}

.rejected {{
  background: var(--danger-bg);
  color: var(--danger);
}}

table {{
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  border-radius: 12px;
  overflow: hidden;
}}

th {{
  background: #f1f5f9;
  padding: 14px;
  font-size: 12px;
  text-transform: uppercase;
}}

td {{
  padding: 12px 14px;
  border-bottom: 1px solid var(--border);
}}

tbody tr:nth-child(even) {{
  background: #fafcff;
}}

tbody tr:hover {{
  background: #f8fbff;
}}

.match-true {{
  background: #f0fdf4 !important;
}}

.match-false {{
  background: #fef2f2 !important;
}}

@media (max-width: 1200px) {{
  body {{
    padding: 20px;
  }}

  table {{
    font-size: 13px;
  }}

  th,
  td {{
    padding: 10px;
  }}
}}
    </style>
</head>
<body>
    <div class="header">
      <h1>QFPUF - Report confronto risultati</h1>
      <p class="subtitle">Generato il {escape(generated_at)}</p>
    </div>

  <div class="section">
    <span class="badge {accepted_class}">{accepted_label}</span>
    <table class="summary-table">
      <tr><th>Totale entry</th><td>{escape(str(summary["total_entries"]))}</td></tr>
      <tr><th>Risposte match</th><td>{escape(str(summary["matching_responses"]))}</td></tr>
      <tr><th>Risposte mismatch</th><td>{escape(str(summary["mismatched_responses"]))}</td></tr>
      <tr><th>Fidelity media</th><td>{escape(_format_float(summary["average_fidelity"], 4))}</td></tr>
      <tr><th>QBER medio</th><td>{escape(_format_float(summary["average_qber"], 4))}</td></tr>
      <tr><th>Soglia fidelity</th><td>{escape(str(thresholds.get("fidelity", "N/D")))}</td></tr>
      <tr><th>Soglia QBER</th><td>{escape(str(thresholds.get("qber", "N/D")))}</td></tr>
      <tr><th>Mismatch</th><td>{escape(mismatch_text)}</td></tr>
    </table>
  </div>

  <div class="section">
    <h2>Dettaglio per challenge</h2>
    <p class="note">Le righe rosse indicano mismatch tra expected e received.</p>
    <table>
      <tr>
        <th>#</th>
        <th>Bitstring</th>
        <th>Angoli</th>
        <th>Risposta enrollment</th>
        <th>Risposta expected</th>
        <th>Risposta received</th>
        <th>Match</th>
        <th>Fidelity</th>
        <th>QBER</th>
        <th>Dominant (enroll)</th>
        <th>Dominant (verify)</th>
      </tr>
      {''.join(row_html)}
    </table>
  </div>
</body>
</html>
"""


def _display_html(html: str) -> None:
    try:
        from IPython.display import HTML, display
    except ImportError as exc:
        raise RuntimeError(
            "IPython non è disponibile: installalo oppure apri manualmente il file HTML."
        ) from exc
    display(HTML(html))


def render_qfpuf_report(
    report_path: Path, output_path: Path, show: bool = False
) -> Path:
    report = _load_json(report_path)
    html = _render_html(report)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    if show:
        _display_html(html)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render the QFPUF comparison JSON report as a readable HTML file."
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path(
            "/kaggle/working/tecQuant/progetto/risultati/qpuf/qfpuf_comparison_report.json"
        ),
        help="Path to qfpuf_comparison_report.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "/kaggle/working/tecQuant/progetto/risultati/qpuf/qfpuf_comparison_report.html"
        ),
        help="Output path for the HTML report",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Mostra il report inline quando si esegue in un notebook.",
    )
    args = parser.parse_args()

    output_path = render_qfpuf_report(args.report, args.output, args.show)
    print(f"Report HTML scritto in: {output_path}")


if __name__ == "__main__":
    main()

