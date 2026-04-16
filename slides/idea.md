# Proposta di 3 idee ORIGINALI per progetto magistrale
## Idea 1
### Titolo tecnico: Ottimizzazione di circuiti di Uncomputation per attacchi Grover-aware su cifrari a blocchi lightweight.
#### Abstract: 
La tesi affronta il "Trash Problem" nell'implementazione dell'algoritmo di Grover per la cryptanalysis. Si analizzeranno cifrari simmetrici progettati per IoT (es. Simon o Speck) e si progetteranno oracoli quantistici ottimizzati. L'obiettivo è minimizzare la profondità del circuito di Uncomputation per bilanciare l'efficacia del diffusore di Grover e la vulnerabilità al rumore nei dispositivi NISQ.
Problema di ricerca: Come ridurre l'overhead computazionale della pulizia dei registri di lavoro (Uncomputation) senza degradare l'interferenza quantistica necessaria per Grover?
Contributo innovativo: Proposta di una strategia di Uncomputation parziale basata sulla sensibilità dei bit della chiave, riducendo il numero di porte Toffoli necessarie rispetto alle tecniche standard
.
Approccio metodologico: Modellazione dell'oracolo in Qiskit; test di circuiti con diverse profondità di Uncomputation; simulazione di attacchi chiave su piccoli spazi di ricerca (3-6 bit)
.
Valutazione sperimentale prevista: Confronto della probabilità di successo con e senza Uncomputation parziale; metriche di profondità del circuito e gate count; utilizzo di AerSimulator con modelli di rumore specifici
.
Fattibilità pratica: Alta. Richiede competenze medie di Qiskit e crittografia simmetrica, risorse IBM Quantum accessibili via cloud
.
Possibili sviluppi futuri: Estensione a cifrari a chiave pubblica PQC basati su codici.
## Idea 2
### Titolo tecnico: Analisi della resilienza di Variational Quantum Classifiers (VQC) per l'Anomaly Detection sotto attacchi di adversarial noise.
#### Abstract: 
Il progetto esplora l'intersezione tra Quantum Machine Learning e sicurezza. Utilizzando PennyLane, si addestrerà un classificatore variazionale per rilevare anomalie di rete. La ricerca valuterà come il rumore depolarizzante e gli errori di misura (readout errors) possano essere sfruttati da un attaccante per bypassare il rilevamento o se il modello quantistico offra una naturale robustezza superiore ai modelli classici.
Problema di ricerca: Il rumore hardware intrinseco dei dispositivi NISQ agisce come una difesa o come una vulnerabilità per i classificatori quantistici?
Contributo innovativo: Prima mappatura degli effetti dei "noisy fake backends" di IBM sulla precisione di un sistema IDS quantistico (Intrusion Detection System)
.
Approccio metodologico: Utilizzo di PennyLane per l'integrazione con PyTorch; definizione di un ansatz parametrizzato e layer di entanglement; mappatura di dataset classici (es. NSL-KDD) tramite zz_feature_map
.
Valutazione sperimentale prevista: Confronto dell'accuratezza e della F1-score tra simulatore ideale e simulatore con rumore; test di robustezza iniettando errori di fase arbitrari
.
Fattibilità pratica: Media. Richiede familiarità con QML e pipeline di Machine Learning classico
.
Possibili sviluppi futuri: Implementazione di tecniche di mitigazione degli errori per migliorare la detection.
## Idea 3
### Titolo tecnico: Risoluzione di problemi di ottimizzazione del posizionamento di sensori di sicurezza tramite QAOA: impatto dell'ansatz sulla convergenza.
#### Abstract:
Il progetto trasforma un problema di sicurezza fisica (posizionamento ottimale di sensori per coprire un'area critica) in un problema QUBO (Quadratic Unconstrained Binary Optimization). Verrà applicato l'algoritmo QAOA per trovare la soluzione ottimale, confrontando diversi "mixer Hamiltonians" per migliorare la velocità di convergenza verso lo stato fondamentale del sistema.
Problema di ricerca: In che modo la struttura dei mixer non commutativi in QAOA influisce sulla capacità di superare minimi locali in problemi di sicurezza con vincoli multipli?
Contributo innovativo: Introduzione di un ansatz personalizzato per QAOA che codifica vincoli di sicurezza direttamente nell'Hamiltoniana di mixer, invece di penalizzazioni nella funzione di costo
.
Approccio metodologico: Trasformazione del problema di copertura in matrice di adiacenza (Max-Cut generalizzato); implementazione QAOA con Qiskit Runtime; ottimizzazione dei parametri γ e β tramite COBYLA
.
Valutazione sperimentale prevista: Calcolo dell'approximation ratio (rapporto tra valore trovato e ottimo teorico); scalabilità al variare del numero di qubit; metriche di "shot noise"
.
Fattibilità pratica: Alta. Sfrutta le primitive Estimator e Sampler di Qiskit per ottimizzare l'esecuzione
.
Possibili sviluppi futuri: Applicazione a problemi di routing sicuro in reti quantistiche (Quantum Internet).
