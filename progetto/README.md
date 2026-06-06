# TEC QUANTISTICHE 
### composto da:
#### 2 MILESTONES
- 1° MILESTONE: fine aprile
- 2° MILESTONE: fine maggio
- ORALE

#### voto finale: 1+2+orale

## QFPUF (Qiskit + NetSquid)
La pipeline QFPUF usa Qiskit per generare challenge esplicite (bitstring + angoli)
e un noise model Aer per simulare istanze PUF rumorose. La configurazione è
riproducibile tramite seed.

### Dipendenze
```bash
pip install -r requirements.txt
```

NetSquid è distribuito separatamente: installare il pacchetto vendor e
verificare con `requirements-netsquid.txt`.

### Esecuzione rapida
```bash
python progetto/scripts/run_qfpuf_pipeline.py --config progetto/qfpuf_config.json --mode full
python progetto/scripts/run_qfpuf_pipeline.py --config progetto/qfpuf_config.json --mode enroll
python progetto/scripts/run_qfpuf_pipeline.py --config progetto/qfpuf_config.json --mode verify
python progetto/scripts/validate_qfpuf.py
python progetto/scripts/compare_results.py --enrollment progetto/risultati/qpuf/qfpuf_enrollment.json --verification progetto/risultati/qpuf/qfpuf_verification.json
python progetto/scripts/visualize_qfpuf_results.py --report progetto/risultati/qpuf/qfpuf_comparison_report.json --output progetto/risultati/qpuf/qfpuf_comparison_report.html
```

Output: `progetto/risultati/qfpuf/` con database di enrollment e report di verifica.

In un notebook (Kaggle/Jupyter) puoi eseguire inline:
```python
from progetto.scripts.visualize_qfpuf_results import render_qfpuf_report
render_qfpuf_report(
    "progetto/risultati/qpuf/qfpuf_comparison_report.json",
    "progetto/risultati/qpuf/qfpuf_comparison_report.html",
    show=True,
)
```
