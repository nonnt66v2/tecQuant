from __future__ import annotations

# Cross-verification matrix per QFPUF
# Obiettivo: dimostrare che ogni chip risponde in modo unico alle sfide.
# La diagonale della matrice (chip arruolato = chip esecutore) deve avere
# fidelity alta (chip legittimo); le celle fuori diagonale (spoofing)
# devono restare sotto la soglia e venire rifiutate.

import argparse
import dataclasses
import html
import json
import math
import sys
import webbrowser
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))

from progetto.qfpuf import QFPUFConfig, load_config, run_enrollment, run_verification
from progetto.qfpuf.challenge import Challenge
from progetto.qfpuf.config import NoiseConfig
from progetto.qfpuf.qiskit_circuit import build_challenge_circuit, simulate_challenge

# Soglia di default per la metrica cosine-deviation (vedi _cosine_deviation).
# Calibrata empiricamente: legit ~0.994, impostori <=0.961. 0.975 centra il
# margine (+~0.018 su entrambi i lati), robusta contro il rumore di campionamento.
DEFAULT_COSINE_THRESHOLD = 0.975
# Shot elevati per la distribuzione ideale di riferimento: deve essere il piu'
# possibile priva di rumore di campionamento, perche' funge da "zero" rispetto
# a cui si misura lo scostamento di ogni chip.
IDEAL_SHOTS = 16384


def _ideal_probabilities(config: QFPUFConfig, enrollment: Dict[str, Any]) -> List[Dict[str, float]]:
    # Distribuzione ideale (circuito SENZA rumore) per ogni challenge.
    # E' il riferimento rispetto a cui si calcola lo scostamento di ciascun chip:
    # la firma hardware non sta nella distribuzione grezza ma in COME il chip
    # devia dall'ideale.
    ideals: List[Dict[str, float]] = []
    for entry in enrollment["entries"]:
        challenge = Challenge.from_dict(entry["challenge"])
        circuit = build_challenge_circuit(config.num_qubits, config.depth, challenge)
        result = simulate_challenge(
            circuit, shots=IDEAL_SHOTS, seed=config.seed + 99991, noise_model=None
        )
        ideals.append(result.probabilities)
    return ideals


def _cosine_deviation(
    p: Dict[str, float], q: Dict[str, float], ideal: Dict[str, float]
) -> float:
    # Cosine similarity tra i vettori di SCOSTAMENTO dall'ideale (p-ideal, q-ideal).
    # La Bhattacharyya grezza non distingue i chip: due copie rumorose dello stesso
    # circuito restano quasi identiche (BC ~0.98) qualunque sia il rumore, perche'
    # condividono la struttura del circuito. Lo scostamento dall'ideale isola invece
    # la firma hardware. Stesso chip -> stessa direzione di scostamento (~0.99);
    # chip diverso -> pattern di errore per-qubit diverso -> direzione diversa (~0.95).
    keys = set(p) | set(q) | set(ideal)
    a = [p.get(k, 0.0) - ideal.get(k, 0.0) for k in keys]
    b = [q.get(k, 0.0) - ideal.get(k, 0.0) for k in keys]
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return sum(x * y for x, y in zip(a, b)) / (na * nb)


def _parse_chips(values: List[str]) -> Dict[str, Dict[str, Any]]:
    # Converte le specifiche CLI in un dizionario {nome: {seed, noise_overrides}}.
    # Formato atteso: NAME=SEED  oppure  NAME=SEED:key=val,key=val,...
    # Gli override rumore sono opzionali e sovrascrivono solo i parametri indicati.
    chips: Dict[str, Dict[str, Any]] = {}
    for item in values:
        noise_overrides: Dict[str, float] = {}
        if ":" in item:
            id_part, noise_part = item.split(":", 1)
            for kv in noise_part.split(","):
                if "=" not in kv:
                    continue
                k, v = kv.split("=", 1)
                noise_overrides[k.strip()] = float(v.strip())
        else:
            id_part = item

        if "=" not in id_part:
            raise ValueError(f"Invalid chip spec '{item}', expected NAME=SEED or NAME=SEED:key=val,...")
        name, seed = id_part.split("=", 1)
        name = name.strip()
        if not name:
            raise ValueError(f"Empty chip name in '{item}'")
        chips[name] = {"seed": int(seed), "noise_overrides": noise_overrides}
    return chips


def _chip_config(config: QFPUFConfig, chip: Dict[str, Any]) -> QFPUFConfig:
    # Costruisce la configurazione specifica del chip applicando i suoi override
    # di rumore al config base. Se non ci sono override, restituisce il config invariato.
    # Ogni chip simula hardware reale con caratteristiche di rumore diverse
    # (T1, T2, depolarizing_1q, depolarizing_2q).
    overrides = chip.get("noise_overrides", {})
    if overrides:
        noise_dict = dataclasses.asdict(config.noise)
        noise_dict.update(overrides)
        chip_noise = NoiseConfig(**noise_dict)
        return dataclasses.replace(config, noise=chip_noise)
    return config


def _enroll_chips(
    config: QFPUFConfig, chips: Dict[str, Dict[str, Any]]
) -> Dict[str, Dict[str, Any]]:
    # Fase di enrollment: per ogni chip genera il suo "fingerprint" quantistico.
    # Il fingerprint è il database delle risposte attese (distribuzioni di probabilità)
    # per ciascuna challenge, misurate con il noise model specifico del chip.
    enrollments: Dict[str, Dict[str, Any]] = {}
    for name, chip in chips.items():
        cfg = _chip_config(config, chip)
        cfg = dataclasses.replace(cfg, enrollment_instance_seed=chip["seed"])
        enrollments[name] = run_enrollment(cfg)
    return enrollments


def _cross_matrix(
    config: QFPUFConfig,
    chips: Dict[str, Dict[str, Any]],
    enrollments: Dict[str, Dict[str, Any]],
    threshold: float,
) -> List[Dict[str, Any]]:
    # Nucleo del cross-verification: per ogni coppia (chip_arruolato, chip_esecutore)
    # esegue le sfide del chip arruolato sul noise model del chip esecutore e
    # confronta le RISPOSTE tramite la metrica cosine-deviation dall'ideale.
    #
    # Perche' NON la Bhattacharyya grezza: due copie rumorose dello stesso circuito
    # restano quasi identiche (BC ~0.98) per qualunque livello di rumore, perche'
    # condividono la struttura del circuito -> la BC non distingue i chip. La firma
    # hardware emerge solo isolando lo SCOSTAMENTO dall'ideale (vedi _cosine_deviation):
    #   - Diagonale (stesso chip, stesso seed): stessa direzione di scostamento -> ~0.99 -> ACCEPT.
    #   - Fuori diagonale (chip diverso): pattern di errore per-qubit diverso -> ~0.95 -> REJECT.
    #
    # Le challenge sono identiche per tutti i chip (derivano dalla stessa config),
    # quindi la distribuzione ideale di riferimento si calcola una sola volta.
    ideals = _ideal_probabilities(config, next(iter(enrollments.values())))

    cells: List[Dict[str, Any]] = []
    for enrolled_name, enrolled_chip in chips.items():
        enrollment = enrollments[enrolled_name]
        enrolled_entries = enrollment["entries"]
        for executed_name, executed_chip in chips.items():
            cfg = _chip_config(config, executed_chip)
            cfg = dataclasses.replace(cfg, verification_instance_seed=executed_chip["seed"])
            report = run_verification(cfg, enrollment)

            cosine_values = [
                _cosine_deviation(
                    enrolled_entries[i].get("probabilities", {}),
                    result.get("probabilities", {}),
                    ideals[i],
                )
                for i, result in enumerate(report["results"])
            ]
            cosine = sum(cosine_values) / len(cosine_values) if cosine_values else 0.0
            cells.append(
                {
                    "enrolled": enrolled_name,
                    "executed": executed_name,
                    "legitimate": enrolled_name == executed_name,  # True solo sulla diagonale
                    "average_fidelity": cosine,  # ora: cosine-deviation fingerprint score
                    "average_qber": report["average_qber"],
                    "accepted": cosine >= threshold,
                }
            )
    return cells


def _matrix_lookup(cells: List[Dict[str, Any]]) -> Dict[Tuple[str, str], Dict[str, Any]]:
    # Indicizza le celle per coppia (enrolled, executed) per accesso O(1) durante il rendering.
    return {(cell["enrolled"], cell["executed"]): cell for cell in cells}


def _print_matrix(chips: Dict[str, Dict[str, Any]], cells: List[Dict[str, Any]]) -> None:
    # Stampa la matrice di fidelity e la matrice di accettazione (1=OK, 0=REJECT)
    # in formato testuale sulla console.
    lookup = _matrix_lookup(cells)
    names = list(chips)
    width = max((len(name) for name in names), default=4) + 2

    print("Fidelity matrix:")
    header = "enroll \\ exec".ljust(width) + "".join(name.ljust(width) for name in names)
    print(header)
    for enrolled in names:
        row = enrolled.ljust(width)
        for executed in names:
            cell = lookup[(enrolled, executed)]
            row += f"{cell['average_fidelity']:.3f}".ljust(width)
        print(row)

    print()
    print("Acceptance (1=OK, 0=REJECT):")
    print(header)
    for enrolled in names:
        row = enrolled.ljust(width)
        for executed in names:
            cell = lookup[(enrolled, executed)]
            row += ("1" if cell["accepted"] else "0").ljust(width)
        print(row)


def _summary(cells: List[Dict[str, Any]]) -> Dict[str, Any]:
    # Calcola le statistiche aggregate separando coppie legittime (diagonale)
    # da coppie impostori (fuori diagonale).
    # False accept: impostore accettato (fidelity alta nonostante chip sbagliato).
    # False reject: chip legittimo rifiutato (fidelity bassa nonostante chip corretto).
    legit = [c for c in cells if c["legitimate"]]
    impostor = [c for c in cells if not c["legitimate"]]

    def _avg(items: List[Dict[str, Any]], key: str) -> float:
        return sum(item[key] for item in items) / len(items) if items else 0.0

    return {
        "legitimate_pairs": len(legit),
        "impostor_pairs": len(impostor),
        "avg_fidelity_legitimate": _avg(legit, "average_fidelity"),
        "avg_fidelity_impostor": _avg(impostor, "average_fidelity"),
        "avg_qber_legitimate": _avg(legit, "average_qber"),
        "avg_qber_impostor": _avg(impostor, "average_qber"),
        "false_rejects": sum(1 for c in legit if not c["accepted"]),
        "false_accepts": sum(1 for c in impostor if c["accepted"]),
    }


def _heatmap_color(value: float, vmin: float, vmax: float) -> str:
    # Interpola il colore della cella HTML tra rosso (bassa fidelity) e verde (alta fidelity).
    # Usa una scala lineare tra vmin e vmax per normalizzare il valore.
    if vmax <= vmin:
        ratio = 0.0
    else:
        ratio = max(0.0, min(1.0, (value - vmin) / (vmax - vmin)))
    r = int(220 - ratio * (220 - 37))
    g = int(38 + ratio * (197 - 38))
    b = int(38 + ratio * (94 - 38))
    return f"rgb({r},{g},{b})"


def _render_html(
    chips: Dict[str, Dict[str, Any]],
    cells: List[Dict[str, Any]],
    summary: Dict[str, Any],
    threshold: float,
) -> str:
    # Genera un report HTML interattivo con heatmap colorata della matrice di fidelity.
    # Le celle diagonali (chip legittimo) hanno bordo spesso; le celle fuori diagonale
    # mostrano anche il QBER e il verdetto (OK/REJECT).
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
            qber = cell["average_qber"]
            row.append(
                f'<td style="background:{color};border:{border}">'
                f'<div class="val">{value:.3f}</div>'
                f'<div class="tag">QBER {qber:.2f} · {mark}</div></td>'
            )
        rows.append("<tr>" + "".join(row) + "</tr>")

    chip_profiles = ""
    for name, chip in chips.items():
        overrides = chip.get("noise_overrides", {})
        if overrides:
            items = ", ".join(f"{k}={v}" for k, v in overrides.items())
            chip_profiles += f"<li><b>{html.escape(name)}</b> (seed {chip['seed']}): {html.escape(items)}</li>"
        else:
            chip_profiles += f"<li><b>{html.escape(name)}</b> (seed {chip['seed']}): base config</li>"

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
    ul {{ font-size:12px; color:#6b7280; margin:8px 0 0 0; padding-left:18px; }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="panel">
      <div class="title">QFPUF cross-verification matrix</div>
      <div class="legend">
        Rows = enrolled chip (fingerprint owner), columns = executing chip.<br>
        Diagonal (bold border) = legitimate; off-diagonal = spoofing attempt.<br>
        Metric = cosine similarity of the deviation-from-ideal (hardware fingerprint).<br>
        Acceptance threshold: cosine-deviation &ge; {threshold:.3f}.
      </div>
      <ul>{chip_profiles}</ul>
      <div class="metrics">
        <div class="card"><div class="lbl">Avg cosine-dev legitimate</div><div class="num">{summary['avg_fidelity_legitimate']:.3f}</div></div>
        <div class="card"><div class="lbl">Avg cosine-dev impostor</div><div class="num">{summary['avg_fidelity_impostor']:.3f}</div></div>
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
    # Entry point: parsing degli argomenti, esecuzione enrollment + cross-verification,
    # stampa della matrice su console, salvataggio JSON e (opzionale) report HTML.
    parser = argparse.ArgumentParser(
        description="QFPUF cross-verification across multiple simulated chips"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("progetto/qfpuf_config.json"),
    )
    parser.add_argument(
        "--chip",
        action="append",
        default=None,
        metavar="NAME=SEED[:key=val,...]",
        help="Chip definition with optional per-chip noise overrides",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("progetto/risultati/qfpuf/qfpuf_cross_matrix.json"),
    )
    parser.add_argument("--html", type=Path, default=None)
    parser.add_argument("--open", action="store_true")
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_COSINE_THRESHOLD,
        help="Soglia di accettazione sulla metrica cosine-deviation (default %(default)s)",
    )
    args = parser.parse_args()

    config = load_config(args.config)

    # Chip di default: STESSO profilo hardware nominale (stessi T1/T2/depol/readout),
    # distinti SOLO dal seed. Il seed determina il profilo di rumore PER-QUBIT (vedi
    # noise.build_noise_model): ogni chip e' una diversa istanza fisica dello stesso
    # modello, con la propria firma spaziale irriproducibile. E' il punto centrale
    # della QPUF: non distinguiamo i chip per "quanto" rumore hanno (la BC mostra che
    # non basta), ma per "come" il rumore e' distribuito sui qubit, misurato come
    # scostamento dall'ideale. Il rumore e' deliberatamente alto per amplificare la
    # firma (depol_2q=0.10, readout=0.20, variation=0.8).
    _profile = "t1=40000,t2=30000,depolarizing_1q=0.01,depolarizing_2q=0.10,readout_error=0.20,variation=1.0"
    default_chips = [
        f"Samuele=42:{_profile}",
        f"Lorenzo=1337:{_profile}",
        f"Bob=2024:{_profile}",
    ]
    chip_specs = args.chip or default_chips
    chips = _parse_chips(chip_specs)
    if len(chips) < 2:
        raise SystemExit("Provide at least two chips to compare")

    enrollments = _enroll_chips(config, chips)
    cells = _cross_matrix(config, chips, enrollments, args.threshold)
    summary = _summary(cells)

    _print_matrix(chips, cells)
    print()
    print(
        f"Legitimate avg fidelity : {summary['avg_fidelity_legitimate']:.4f}\n"
        f"Impostor  avg fidelity  : {summary['avg_fidelity_impostor']:.4f}\n"
        f"False accepts : {summary['false_accepts']} | False rejects : {summary['false_rejects']}"
    )

    payload = {
        "chips": {name: {**chip, "noise_overrides": chip["noise_overrides"]} for name, chip in chips.items()},
        "metric": "cosine_deviation_from_ideal",
        "thresholds": {"cosine_deviation": args.threshold, "qber": config.qber_threshold},
        "matrix": cells,
        "summary": summary,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2))
    print(f"Saved cross-verification matrix to {args.output}")

    if args.html is not None:
        report = _render_html(chips, cells, summary, args.threshold)
        args.html.parent.mkdir(parents=True, exist_ok=True)
        args.html.write_text(report, encoding="utf-8")
        print(f"Saved heatmap to {args.html}")
        if args.open:
            webbrowser.open(args.html.resolve().as_uri())


if __name__ == "__main__":
    main()
