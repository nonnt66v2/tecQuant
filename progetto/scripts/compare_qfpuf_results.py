from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _dominant_measurement(counts: Dict[str, Any]) -> str:
    if not counts:
        return ""
    return max(counts, key=counts.get)


def _compare_entries(
    enrollment: Dict[str, Any], verification: Dict[str, Any]
) -> List[Dict[str, Any]]:
    enrollment_entries = enrollment.get("entries", [])
    verification_entries = verification.get("results", [])
    if len(enrollment_entries) != len(verification_entries):
        raise ValueError(
            "Enrollment entries and verification results must have the same length"
        )

    report_entries: List[Dict[str, Any]] = []
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

        expected_response = verification_entry.get("expected_response", "")
        received_response = verification_entry.get("received_response", "")
        enrollment_response = enrollment_entry.get("response", "")
        report_entries.append(
            {
                "index": index,
                "challenge": enrollment_challenge,
                "enrollment_response": enrollment_response,
                "verification_expected_response": expected_response,
                "verification_received_response": received_response,
                "match": (
                    enrollment_response == expected_response == received_response
                ),
                "fidelity": float(verification_entry.get("fidelity", 0.0)),
                "qber": float(verification_entry.get("qber", 0.0)),
                "enrollment_dominant_measurement": _dominant_measurement(
                    enrollment_entry.get("counts", {})
                ),
                "verification_dominant_measurement": _dominant_measurement(
                    verification_entry.get("counts", {})
                ),
            }
        )
    return report_entries


def build_report(enrollment: Dict[str, Any], verification: Dict[str, Any]) -> Dict[str, Any]:
    entries = _compare_entries(enrollment, verification)
    return {
        "report_type": "qfpuf_result_comparison",
        "source_files": {
            "enrollment": "qfpuf_enrollment.json",
            "verification": "qfpuf_verification.json",
        },
        "summary": {
            "total_entries": len(entries),
            "matching_challenges": len(entries),
            "matching_responses": sum(1 for entry in entries if entry["match"]),
            "mismatched_responses": sum(1 for entry in entries if not entry["match"]),
            "average_fidelity": (
                sum(entry["fidelity"] for entry in entries) / len(entries)
                if entries
                else 0.0
            ),
            "average_qber": (
                sum(entry["qber"] for entry in entries) / len(entries)
                if entries
                else 0.0
            ),
            "accepted": bool(verification.get("accepted", False)),
            "thresholds": verification.get("thresholds", {}),
        },
        "entries": entries,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a JSON comparison report for QFPUF enrollment and verification"
    )
    parser.add_argument(
        "--enrollment",
        type=Path,
        default=Path("progetto/risultati/qpuf/qfpuf_enrollment.json"),
        help="Path to qfpuf_enrollment.json",
    )
    parser.add_argument(
        "--verification",
        type=Path,
        default=Path("progetto/risultati/qpuf/qfpuf_verification.json"),
        help="Path to qfpuf_verification.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("progetto/risultati/qpuf/qfpuf_comparison_report.json"),
        help="Path for the generated comparison JSON report",
    )
    args = parser.parse_args()

    enrollment = _load_json(args.enrollment)
    verification = _load_json(args.verification)
    report = build_report(enrollment, verification)
    report_text = json.dumps(report, indent=2)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report_text + "\n", encoding="utf-8")
    sys.stdout.write(report_text + "\n")


if __name__ == "__main__":
    main()
