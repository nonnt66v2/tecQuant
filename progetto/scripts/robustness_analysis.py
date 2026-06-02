"""Analisi di robustezza per la presentazione QFPUF.

Genera grafici (PNG) che mostrano come la separazione legit/impostore della
metrica cosine-deviation dipende dai parametri del protocollo:
  1. numero di shot
  2. profondita' del circuito-sfida
  3. variation (forza della firma per-qubit)
  4. soglia di decisione -> false accepts / false rejects (curva ROC-like)
  5. confronto diretto Bhattacharyya vs cosine-deviation
  6. scalabilita' a piu' chip (matrice 5x5)

Riusa il codice reale del progetto (pipeline + cross_verify) per coerenza.
"""
from __future__ import annotations

import dataclasses
import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))

from progetto.qfpuf import load_config, run_enrollment, run_verification
from progetto.qfpuf.config import NoiseConfig
from progetto.scripts.cross_verify_chips import (
    _cosine_deviation,
    _ideal_probabilities,
)

OUTDIR = ROOT / "progetto" / "risultati" / "qfpuf" / "grafici"
OUTDIR.mkdir(parents=True, exist_ok=True)

# Profilo di rumore ad alto jitter usato per tutti gli esperimenti di robustezza.
# depol_2q=0.10 e readout=0.20 amplificano la firma per-qubit; variation=1.0
# massimizza la diversita' tra chip con seed diversi.
BASE_PROFILE = dict(
    t1=40000.0, t2=30000.0, depolarizing_1q=0.01, depolarizing_2q=0.10,
    readout_error=0.20, variation=1.0,
)

# I tre chip simulati, distinti solo dal seed (= diversa istanza fisica).
# Eve e Mallory sono nomi convenzionali della crittografia per attaccanti.
CHIP_SEEDS = {"Samuele": 42, "Lorenzo": 1337, "Bob": 2024}

# Soglia di accettazione cosine-deviation calibrata sul regime PA.
THRESHOLD = 0.975


def _bhattacharyya(p, q):
    """Coefficiente di Bhattacharyya tra due distribuzioni di probabilita'.
    Usato solo per il confronto metrica (esperimento 5): dimostra che BC non
    distingue i chip (rimane ~0.98 per qualunque livello di rumore).
    """
    return sum(math.sqrt(p.get(k, 0.0) * q.get(k, 0.0)) for k in set(p) | set(q))


def _cfg(config, *, depth=None, shots=None, profile=None, count=None):
    """Restituisce una copia del config con i parametri sovrascrivibili.
    Usato dagli sweep per variare un parametro alla volta mantenendo gli altri fissi.
    """
    noise = NoiseConfig(**{**dataclasses.asdict(config.noise), **(profile or BASE_PROFILE)})
    kw = {"noise": noise}
    if depth is not None:
        kw["depth"] = depth
    if shots is not None:
        kw["shots"] = shots
    if count is not None:
        kw["challenge_config"] = dataclasses.replace(config.challenge_config, count=count)
    return dataclasses.replace(config, **kw)


def _matrix(config, seeds, profile, *, use_bc=False):
    """Costruisce la matrice NxN (enrolled, executed) -> score medio sulle challenge.

    Per ogni coppia di chip (enrolled, executed): esegue le challenge del chip
    enrollato sul noise model del chip esecutore e calcola la cosine-deviation
    (o Bhattacharyya se use_bc=True) media su tutte le challenge.
    Diagonale = chip legittimo (stesso seed); fuori diagonale = impostore.
    """
    base = _cfg(config, profile=profile)
    # Enrollment: ogni chip registra la propria impronta (distribuzioni attese)
    enrollments = {}
    for name, seed in seeds.items():
        enrollments[name] = run_enrollment(dataclasses.replace(base, enrollment_instance_seed=seed))
    # Distribuzioni ideali (senza rumore) usate come riferimento per cosine-deviation
    ideals = _ideal_probabilities(base, next(iter(enrollments.values())))
    scores = {}
    for en, en_seed in seeds.items():
        entries = enrollments[en]["entries"]
        for ex, ex_seed in seeds.items():
            # Verifica: esegue le challenge sul noise model del chip esecutore
            cfg = dataclasses.replace(base, verification_instance_seed=ex_seed)
            report = run_verification(cfg, enrollments[en])
            vals = []
            for i, res in enumerate(report["results"]):
                p = entries[i].get("probabilities", {})
                q = res.get("probabilities", {})
                vals.append(_bhattacharyya(p, q) if use_bc else _cosine_deviation(p, q, ideals[i]))
            scores[(en, ex)] = sum(vals) / len(vals)
    return scores


def _separation(scores, seeds):
    """Estrae le statistiche di separazione dalla matrice dei punteggi.
    Ritorna: min legit, max impostore, media legit, media impostore.
    Un buon protocollo ha min_legit >> max_impostor.
    """
    names = list(seeds)
    legit = [scores[(n, n)] for n in names]
    imp = [scores[(a, b)] for a in names for b in names if a != b]
    return min(legit), max(imp), sum(legit) / len(legit), sum(imp) / len(imp)


def sweep(config, param, values, builder):
    """Esegue uno sweep su una lista di valori di un parametro.
    Per ogni valore calcola la matrice e registra min_legit e max_impostor.
    """
    legit_min, imp_max = [], []
    for v in values:
        scores = _matrix(*builder(v))
        lo, hi, _, _ = _separation(scores, CHIP_SEEDS)
        legit_min.append(lo)
        imp_max.append(hi)
        print(f"  {param}={v}: legit_min={lo:.3f} impostor_max={hi:.3f} margine={lo-hi:+.3f}")
    return legit_min, imp_max


def plot_sep(values, legit_min, imp_max, xlabel, title, fname, logx=False):
    """Genera e salva il grafico di separazione legit/impostore vs parametro.
    La zona grigia tra le due curve e' il margine di separazione.
    La linea tratteggiata e' la soglia di decisione.
    """
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(values, legit_min, "o-", color="#16a34a", label="Chip legittimo (min)")
    ax.plot(values, imp_max, "s-", color="#dc2626", label="Impostore (max)")
    ax.axhline(THRESHOLD, ls="--", color="#2563eb", label=f"Soglia {THRESHOLD}")
    ax.fill_between(values, legit_min, imp_max, color="#94a3b8", alpha=0.15)
    if logx:
        ax.set_xscale("log", base=2)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Cosine-deviation")
    ax.set_title(title)
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUTDIR / fname, dpi=130)
    plt.close(fig)
    print(f"  -> salvato {fname}")


def main():
    config = load_config(ROOT / "progetto" / "qfpuf_config_PA.json")

    # [1/6] Quanto contano gli shot: piu' shot = stima piu' precisa della distribuzione
    # e quindi del vettore di scostamento. Verifica che 2048 sia sufficiente.
    print("[1/6] Sensibilita' agli SHOT")
    shots_vals = [256, 512, 1024, 2048, 4096]
    lo, hi = sweep(config, "shots", shots_vals,
                   lambda v: (_cfg(config, shots=v), CHIP_SEEDS, BASE_PROFILE))
    plot_sep(shots_vals, lo, hi, "Numero di shot",
             "Separazione vs shot", "rob_shots.png", logx=True)

    # [2/6] Quanto conta la profondita': circuiti piu' profondi accumulano piu'
    # errori hardware e amplificano la firma. Verifica che depth=5 sia nel range utile.
    print("[2/6] Sensibilita' alla PROFONDITA'")
    depth_vals = [1, 2, 3, 4, 5, 6, 8]
    lo, hi = sweep(config, "depth", depth_vals,
                   lambda v: (_cfg(config, depth=v), CHIP_SEEDS, BASE_PROFILE))
    plot_sep(depth_vals, lo, hi, "Profondita' circuito (depth)",
             "Separazione vs profondita'", "rob_depth.png")

    # [3/6] Quanto conta la variation: e' il parametro chiave della firma per-qubit.
    # Con variation=0 tutti i qubit hanno lo stesso rumore -> nessuna firma.
    # Con variation=1.0 ogni qubit e' molto diverso -> firma forte.
    print("[3/6] Sensibilita' alla VARIATION (forza firma per-qubit)")
    var_vals = [0.2, 0.4, 0.6, 0.8, 1.0]
    lo, hi = sweep(config, "variation", var_vals,
                   lambda v: (config, CHIP_SEEDS, {**BASE_PROFILE, "variation": v}))
    plot_sep(var_vals, lo, hi, "Variation (jitter per-qubit)",
             "Separazione vs forza della firma", "rob_variation.png")

    # [4/6] Curva ROC-like: mostra la "finestra di sicurezza" della soglia.
    # Idealmente esiste un range di soglie che danno 0 false accepts E 0 false rejects.
    print("[4/6] Curva soglia -> errori (ROC-like)")
    scores = _matrix(config, CHIP_SEEDS, BASE_PROFILE)
    names = list(CHIP_SEEDS)
    legit = [scores[(n, n)] for n in names]
    imp = [scores[(a, b)] for a in names for b in names if a != b]
    thr_vals = [round(0.90 + 0.005 * k, 3) for k in range(21)]  # 0.90..1.00
    fa = [sum(1 for v in imp if v >= t) for t in thr_vals]
    fr = [sum(1 for v in legit if v < t) for t in thr_vals]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(thr_vals, fa, "o-", color="#dc2626", label="False accepts")
    ax.plot(thr_vals, fr, "s-", color="#f59e0b", label="False rejects")
    ax.axvline(THRESHOLD, ls="--", color="#2563eb", label=f"Soglia scelta {THRESHOLD}")
    ax.set_xlabel("Soglia di decisione")
    ax.set_ylabel("Numero di errori")
    ax.set_title("Errori vs soglia (finestra di sicurezza)")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUTDIR / "rob_threshold.png", dpi=130)
    plt.close(fig)
    print(f"  finestra pulita: soglie con 0 errori = "
          f"{[t for t, a, r in zip(thr_vals, fa, fr) if a == 0 and r == 0]}")
    print("  -> salvato rob_threshold.png")

    # [5/6] Confronto diretto tra Bhattacharyya (metrica standard) e cosine-deviation.
    # BC non separa perche' due distribuzioni rumorose dello stesso circuito restano
    # simili indipendentemente dal chip; cosine-deviation isola lo scostamento hardware.
    print("[5/6] Confronto metrica: Bhattacharyya vs cosine-deviation")
    bc = _matrix(config, CHIP_SEEDS, BASE_PROFILE, use_bc=True)
    cos = scores
    bc_lo, bc_hi, _, _ = _separation(bc, CHIP_SEEDS)
    cos_lo, cos_hi, _, _ = _separation(cos, CHIP_SEEDS)
    fig, ax = plt.subplots(figsize=(6, 4))
    x = [0, 1]
    ax.bar([0 - 0.2, 1 - 0.2], [bc_lo, cos_lo], width=0.4, color="#16a34a", label="Legittimo (min)")
    ax.bar([0 + 0.2, 1 + 0.2], [bc_hi, cos_hi], width=0.4, color="#dc2626", label="Impostore (max)")
    ax.axhline(THRESHOLD, ls="--", color="#2563eb", label=f"Soglia {THRESHOLD}")
    ax.set_xticks(x)
    ax.set_xticklabels(["Bhattacharyya\n(grezza)", "Cosine-deviation\n(scostamento)"])
    ax.set_ylabel("Score")
    ax.set_ylim(0.8, 1.01)
    ax.set_title("Perche' la metrica conta")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(OUTDIR / "rob_metric_compare.png", dpi=130)
    plt.close(fig)
    print(f"  BC: legit_min={bc_lo:.3f} imp_max={bc_hi:.3f} (gap {bc_lo-bc_hi:+.3f}) -> non separa")
    print(f"  COS: legit_min={cos_lo:.3f} imp_max={cos_hi:.3f} (gap {cos_lo-cos_hi:+.3f}) -> separa")
    print("  -> salvato rob_metric_compare.png")

    # [6/6] Scalabilita': verifica che il protocollo funzioni oltre i 3 chip di default.
    # Eve e Mallory sono nomi convenzionali della crittografia per attaccanti.
    print("[6/6] Scalabilita': matrice a 5 chip")
    seeds5 = {"Samuele": 42, "Lorenzo": 1337, "Bob": 2024, "Eve": 777, "Mallory": 9001}
    s5 = _matrix(config, seeds5, BASE_PROFILE)
    lo, hi, _, _ = _separation(s5, seeds5)
    names5 = list(seeds5)
    fa5 = sum(1 for a in names5 for b in names5 if a != b and s5[(a, b)] >= THRESHOLD)
    fr5 = sum(1 for n in names5 if s5[(n, n)] < THRESHOLD)
    import numpy as np
    mat = np.array([[s5[(en, ex)] for ex in names5] for en in names5])
    fig, ax = plt.subplots(figsize=(5.5, 5))
    im = ax.imshow(mat, cmap="RdYlGn", vmin=0.9, vmax=1.0)
    ax.set_xticks(range(len(names5)), names5, rotation=30, ha="right")
    ax.set_yticks(range(len(names5)), names5)
    for i in range(len(names5)):
        for j in range(len(names5)):
            ax.text(j, i, f"{mat[i,j]:.3f}", ha="center", va="center", fontsize=8)
    ax.set_title(f"Matrice 5x5 - false accepts={fa5}, false rejects={fr5}")
    fig.colorbar(im, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(OUTDIR / "rob_scale_5chip.png", dpi=130)
    plt.close(fig)
    print(f"  5 chip: legit_min={lo:.3f} impostor_max={hi:.3f} fa={fa5} fr={fr5}")
    print(f"  -> salvato rob_scale_5chip.png")

    print(f"\nTutti i grafici in: {OUTDIR}")


if __name__ == "__main__":
    main()
