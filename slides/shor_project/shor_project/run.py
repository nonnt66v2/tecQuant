import sys
from src.shor_demo.qpe import run_qpe_demo
from src.shor_demo.shor15 import run_shor_16q_demo
from src.shor_demo.rsa_toy import run_rsa_toy_demo


def main() -> None:
    if len(sys.argv) < 2:
        print("Uso: python run.py [qpe|shor|shor16|rsa]")
        raise SystemExit(1)

    cmd = sys.argv[1].lower()
    if cmd == "qpe":
        run_qpe_demo()
    elif cmd == "shor16":
        run_shor_16q_demo()
    elif cmd == "rsa":
        run_rsa_toy_demo()
    else:
        print(f"Comando sconosciuto: {cmd}")
        print("Uso: python run.py [qpe|shor|shor16|rsa]")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
