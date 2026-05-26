"""
Struttura della simulazione:
  1. Preparazione qubit da parte di Alice
  2. (Opzionale) Intercettazione da parte di Eve
  3. Misura da parte di Bob
  4. Sifting: confronto delle basi
  5. Stima del QBER (Quantum Bit Error Rate)
"""


import random
import netsquid as ns
import netsquid.qubits as qapi


NUM_QUBITS = 100      #Numero totale di qubit che Alice invia a Bob
EVE_PRESENT = True   #Se True, Eve intercetta e ri-invia ogni qubit
SEED = 42             #Seme per riproducibilità dei risultati casuali

#Impostiamo il seme globale di NetSquid (influenza anche le misure quantistiche)
ns.set_qstate_formalism(ns.QFormalism.DM)   #Usiamo la matrice densità (Density Matrix)
                                             #più realistica di ket state puro
ns.set_random_state(seed=SEED)              #Seme per RNG interno di NetSquid
random.seed(SEED)                           #Seme per RNG classico Python



def prepara_qubit(bit: int, base: int):
    """
    Crea un qubit e lo prepara nello stato scelto da Alice.

    Basi:
      0 → base Z (computazionale):  |0⟩ per bit=0,  |1⟩ per bit=1
      1 → base X (di Hadamard):     |+⟩ per bit=0,  |−⟩ per bit=1

    Tabella degli stati:
      bit=0, base=Z  →  |0⟩
      bit=1, base=Z  →  |1⟩  (porta X su |0⟩)
      bit=0, base=X  →  |+⟩  (porta H su |0⟩)
      bit=1, base=X  →  |−⟩  (porta X poi H su |0⟩)
    """
    #create_qubits(1) restituisce una lista; prendiamo il primo (e unico) qubit
    [qubit] = qapi.create_qubits(1)

    #Ogni qubit nasce nello stato |0⟩ per default

    if bit == 1:
        #Porta X (NOT quantistico): |0⟩ → |1⟩
        qapi.operate(qubit, ns.X)

    if base == 1:
        #Porta H (Hadamard): converte tra base Z e base X
        #|0⟩ → |+⟩ = (|0⟩+|1⟩)/√2
        #|1⟩ → |−⟩ = (|0⟩−|1⟩)/√2
        qapi.operate(qubit, ns.H)

    return qubit   # Restituiamo il qubit preparato


def misura_qubit(qubit, base: int) -> int:
    """
    Bob (o Eve) misura il qubit nella base scelta.

    Se la base è X, applichiamo prima H per "ruotare" nella base Z,
    poi eseguiamo la misura standard nella base computazionale.
    Questo è equivalente a misurare nella base X.

    Restituisce il risultato della misura: 0 o 1.
    """
    if base == 1:
        #Ruotiamo dalla base X alla base Z con Hadamard
        #Così la misura successiva è equivalente a misurare in base X
        qapi.operate(qubit, ns.H)

    #measure() restituisce (risultato, probabilità)
    #risultato è 0 o 1 (proiezione su |0⟩ o |1⟩)
    risultato, _ = qapi.measure(qubit, discard=True)
    #discard=True: dopo la misura il qubit viene scartato (liberato dalla memoria)

    return int(risultato)   # Convertiamo da bool a int (0/1)


def intercetta_eve(qubit, base_eve: int):
    """
    Eve intercetta il qubit, lo misura in una base casuale, poi prepara
    e invia un nuovo qubit con il valore che ha misurato.

    Se la base di Eve ≠ base di Alice, il qubit ri-inviato è sbagliato:
    questo introduce errori rilevabili nel QBER.
    """
    #Eve misura il qubit originale nella sua base casuale
    bit_eve = misura_qubit(qubit, base_eve)
    #La misura ha collassato lo stato originale: Eve non sa se ha indovinato la base

    #Eve prepara un nuovo qubit con il bit che ha misurato nella sua base
    nuovo_qubit = prepara_qubit(bit_eve, base_eve)
    #Bob riceverà questo qubit "falsificato" → fonte di errori

    return nuovo_qubit


#Fase 1: Alice genera bit e basi casuali

#Lista di NUM_QUBITS bit casuali (0 o 1): il messaggio segreto di Alice
alice_bits  = [random.randint(0, 1) for _ in range(NUM_QUBITS)]

#Lista di basi casuali di Alice: 0=Z (standard), 1=X (Hadamard)
alice_basi  = [random.randint(0, 1) for _ in range(NUM_QUBITS)]


#Fase 2: Bob genera le sue basi casuali

#Bob sceglie indipendentemente in quale base misurare ogni qubit
bob_basi    = [random.randint(0, 1) for _ in range(NUM_QUBITS)]

#Lista dove salveremo i risultati delle misure di Bob
bob_risultati = []


#Fase 3: Simulazione del canale quantistico

print("=" * 60)
print("  Simulazione BB84 con NetSquid")
print("=" * 60)
print(f"  Numero di qubit:    {NUM_QUBITS}")
print(f"  Eve presente:       {EVE_PRESENT}")
print()

for i in range(NUM_QUBITS):

    #Alice prepara il qubit i-esimo
    qubit = prepara_qubit(alice_bits[i], alice_basi[i])
    #Il qubit è ora pronto per essere "inviato" sul canale quantistico

    #(Opzionale) Eve intercetta
    if EVE_PRESENT:
        base_eve = random.randint(0, 1)  # Eve sceglie una base a caso
        qubit = intercetta_eve(qubit, base_eve)
        #qubit ora è il qubit ri-preparato da Eve, non quello originale di Alice

    #Bob misura il qubit
    risultato = misura_qubit(qubit, bob_basi[i])
    bob_risultati.append(risultato)
    #Se alice_basi[i] == bob_basi[i] e non c'è Eve, risultato == alice_bits[i]


#Fase 4: Sifting (confronto delle basi via canale classico)
#Alice e Bob si comunicano pubblicamente LE BASI USATE (non i bit!)
#Tengono solo i bit dove le basi coincidono.

alice_key = []   #Raw key di Alice dopo il sifting
bob_key   = []   #Raw key di Bob dopo il sifting
posizioni_ok = []  #Indici dove le basi coincidono

for i in range(NUM_QUBITS):
    if alice_basi[i] == bob_basi[i]:
        #Le basi coincidono → il bit è valido
        alice_key.append(alice_bits[i])
        bob_key.append(bob_risultati[i])
        posizioni_ok.append(i)

#Il sifting scarta in media il 50% dei qubit (basi discordanti)


#Fase 5: Stima del QBER
'''
QBER = Quantum Bit Error Rate = frazione di bit diversi nella raw key
In assenza di Eve (e senza rumore): QBER ≈ 0%
Con Eve che misura sempre in base casuale: QBER ≈ 25%
(Eve sbaglia base il 50% delle volte; quando sbaglia, introduce
un errore con probabilità 50% → 0.5 × 0.5 = 0.25)
'''
errori = sum(a != b for a, b in zip(alice_key, bob_key))
#Contiamo le posizioni dove il bit di Alice ≠ bit di Bob

lunghezza_key = len(alice_key)   # Lunghezza della raw key dopo sifting

qber = errori / lunghezza_key if lunghezza_key > 0 else 0.0
#QBER: valore tra 0.0 (nessun errore) e 1.0 (tutti errori)


#Risultati

print(f"Qubit inviati:              {NUM_QUBITS}")
print(f"Basi coincidenti (sifting): {lunghezza_key}  "
      f"({100*lunghezza_key/NUM_QUBITS:.1f}% del totale)")
print(f"Errori nella raw key:       {errori}")
print(f"QBER stimato:               {qber*100:.2f}%")
print()

#Mostriamo i primi 20 bit delle due chiavi per confronto visivo
preview = min(20, lunghezza_key)
print(f"Alice key (prime {preview}): {alice_key[:preview]}")
print(f"Bob   key (prime {preview}): {bob_key[:preview]}")
print()

#Soglia di sicurezza: se QBER > 11% il canale è considerato compromesso
SOGLIA_QBER = 0.11
if qber > SOGLIA_QBER:
    print("QBER troppo alto: canale compromesso (probabilmente c'è un intercettatore)!")
    print("Alice e Bob devono ABORTIRE la sessione e ricominciare.")
else:
    print("QBER accettabile: il canale sembra sicuro.")
    print("Alice e Bob possono procedere con privacy amplification e error correction.")
