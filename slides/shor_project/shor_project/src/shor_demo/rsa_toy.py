from math import gcd

from .shor15 import nontrivial_factors_from_order


def egcd(a: int, b: int):
    if a == 0:
        return b, 0, 1
    g, y, x = egcd(b % a, a)
    return g, x - (b // a) * y, y


def mod_inverse(a: int, m: int) -> int:
    g, x, _ = egcd(a, m)
    if g != 1:
        raise ValueError("Inverso modulare non esistente")
    return x % m


def rsa_encrypt(message: int, e: int, n: int) -> int:
    return pow(message, e, n)


def rsa_decrypt(ciphertext: int, d: int, n: int) -> int:
    return pow(ciphertext, d, n)


def recover_private_key_from_factors(p: int, q: int, e: int) -> int:
    phi = (p - 1) * (q - 1)
    return mod_inverse(e, phi)


def run_rsa_toy_demo() -> None:
    """
    Esempio didattico: piccolo RSA con N=15.
    Qui simuliamo l'idea: se Shor fattorizza N, possiamo ricostruire d.
    """
    p, q = 3, 5
    n = p * q
    e = 3

    if gcd(e, (p - 1) * (q - 1)) != 1:
        raise ValueError("e non e' coprimo con phi(N)")

    d = recover_private_key_from_factors(p, q, e)
    message = 7
    ciphertext = rsa_encrypt(message, e, n)

    print("=== RSA toy demo ===")
    print(f"Chiave pubblica: (e={e}, n={n})")
    print(f"Messaggio in chiaro: {message}")
    print(f"Ciphertext: {ciphertext}")
    print(f"Chiave privata reale d: {d}")

    # Parte 'attacco': immaginiamo di aver ottenuto l'ordine r=4 da Shor con a=7 mod 15
    # e ricaviamo i fattori da r.
    recovered = nontrivial_factors_from_order(a=7, N=15, r=4)
    if recovered is None:
        print("Impossibile ricavare i fattori dal periodo.")
        return

    rp, rq = recovered
    recovered_d = recover_private_key_from_factors(rp, rq, e)
    recovered_message = rsa_decrypt(ciphertext, recovered_d, n)

    print("\n=== Simulazione dell'effetto di Shor ===")
    print(f"Fattori recuperati: p={rp}, q={rq}")
    print(f"Chiave privata ricostruita: d={recovered_d}")
    print(f"Messaggio decifrato dall'attaccante: {recovered_message}")
