# TEC QUANTISTICHE 
### composto da:
#### 2 MILESTONES
- 1° MILESTONE: fine aprile
- 2° MILESTONE: fine maggio
- ORALE

#### voto finale: 1+2+orale

## QFPUF (Qiskit + NetSquid)
La pipeline QFPUF usa Qiskit per generare le challenge circuit e NetSquid per
l'autenticazione/verification. La configurazione è riproducibile tramite seed.

### Dipendenze
```bash
pip install -r requirements.txt
```

NetSquid è distribuito separatamente: installare il pacchetto vendor e
verificare con `requirements-netsquid.txt`.

### Esecuzione rapida
```bash
python progetto/scripts/run_qfpuf_pipeline.py --config progetto/qfpuf_config.json
python progetto/scripts/validate_qfpuf.py
```

Output: `progetto/risultati/qfpuf/`.
