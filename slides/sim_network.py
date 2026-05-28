import netsquid as ns
from netsquid.nodes import Node, Network
from netsquid.protocols.nodeprotocols import NodeProtocol
from netsquid.components import QuantumChannel, ClassicalChannel
from netsquid.components.qprocessor import QuantumProcessor
from netsquid.components.qsource import QSource
from netsquid.components.qsource import SourceStatus
from netsquid.components.qprogram import QuantumProgram
from netsquid.components.qprocessor import PhysicalInstruction
from netsquid.components.instructions import (
        INSTR_X,
        INSTR_Z,
        INSTR_H,
        INSTR_CNOT,
        INSTR_MEASURE,
        INSTR_MEASURE_BELL,
    )

from netsquid.components.models.delaymodels import FibreDelayModel, FixedDelayModel
from netsquid.components.models.qerrormodels import DepolarNoiseModel, FibreLossModel
from netsquid.qubits import StateSampler
from netsquid.qubits import ketstates as ks


b00 = ks.b00

#Per differenze nelle versioni
def obs_name(obs):
    try:
        return obs.name
    except Exception:
        return str(obs)


def build_processor(name, num_positions):
    phys_instr = [
        PhysicalInstruction(INSTR_X, duration=1, parallel=True),
        PhysicalInstruction(INSTR_Z, duration=1, parallel=True),
        PhysicalInstruction(INSTR_H, duration=1, parallel=True),
        PhysicalInstruction(INSTR_CNOT, duration=4, parallel=False),
        PhysicalInstruction(INSTR_MEASURE, duration=5, parallel=False),
        PhysicalInstruction(INSTR_MEASURE_BELL, duration=8, parallel=False),
    ]

    return QuantumProcessor(
        name=name,
        num_positions=num_positions,
        phys_instructions=phys_instr,
        fallback_to_nonphysical=True,
    )


def build_bell_source(name, period=40):
    return QSource(
        name=name,
        state_sampler=StateSampler([b00], [1.0]),
        num_ports=2,
        status=SourceStatus.EXTERNAL,
        models={"emission_delay_model": FixedDelayModel(delay=period)},
    )


def build_quantum_channel(name, length_km=10,
                          depolar_rate=0.0,
                          p_loss_init=0.0,
                          p_loss_length=0.0):
    return QuantumChannel(
        name=name,
        length=length_km,
        models={
            "delay_model": FibreDelayModel(),
            "quantum_noise_model": DepolarNoiseModel(depolar_rate=depolar_rate),
            "quantum_loss_model": FibreLossModel(
                p_loss_init=p_loss_init,
                p_loss_length=p_loss_length
            ),
        },
    )


def build_classical_channel(name, length_km=10):
    return ClassicalChannel(
        name=name,
        length=length_km,
        models={"delay_model": FibreDelayModel()},
    )


def print_topology(network):
    print("\n================ TOPOLOGIA ================")
    for node_name, node in network.nodes.items():
        print(f"Nodo {node_name}")
        print(f"  porte: {list(node.ports.keys())}")
        if getattr(node, "qmemory", None) is not None:
            print(f"  qmemory: {node.qmemory.name} | slots={node.qmemory.num_positions}")
            print(f"  qmemory ports: {list(node.qmemory.ports.keys())}")
        else:
            print("  qmemory: nessuna")
        if getattr(node, "subcomponents", None):
            print(f"  subcomponents: {list(node.subcomponents.keys())}")
    print("===========================================\n")


class BellMeasureProgram(QuantumProgram):
    default_num_qubits = 2

    def program(self):
        q1, q2 = self.get_qubit_indices(2)
        self.apply(INSTR_MEASURE_BELL, [q1, q2], output_key="bell_index")
        yield self.run()


class SourceNodeProtocol(NodeProtocol):
    """
    Protocollo per Alice o Bob:
    - triggera la QSource
    - il qubit remoto va al repeater
    - il qubit locale entra in qmemory slot 0
    - aspetta l'heralding del repeater
    - misura il qubit locale
    """
    def __init__(self, node, source_name, herald_port, role="Alice", rounds=6, interval=50):
        super().__init__(node=node)
        self.source_name = source_name
        self.herald_port = herald_port
        self.role = role
        self.rounds = rounds
        self.interval = interval
        self.round_id = 0

    def choose_basis(self):
        return ns.Z if self.round_id % 2 == 0 else ns.X

    def run(self):
        qsource = self.node.subcomponents[self.source_name]
        qin0 = self.node.qmemory.ports["qin0"]
        cin = self.node.ports[self.herald_port]

        for r in range(1, self.rounds + 1):
            print(f"[t={ns.sim_time():>6}] {self.role.upper():8}: trigger source round={r}")
            qsource.trigger()

            yield self.await_port_input(qin0)
            self.round_id += 1
            print(f"[t={ns.sim_time():>6}] {self.role.upper():8}: qubit locale arrivato in memoria")

            yield self.await_port_input(cin)
            herald_msg = cin.rx_input()
            if herald_msg is None or len(herald_msg.items) == 0:
                print(f"[t={ns.sim_time():>6}] {self.role.upper():8}: heralding mancante")
                continue

            herald = herald_msg.items[0]
            print(f"[t={ns.sim_time():>6}] {self.role.upper():8}: heralding -> {herald}")

            q = self.node.qmemory.pop(positions=[0])[0]
            if q is None:
                print(f"[t={ns.sim_time():>6}] {self.role.upper():8}: slot 0 vuoto")
                continue

            obs = self.choose_basis()
            outcome, _ = ns.qubits.measure(q, observable=obs)
            print(f"[t={ns.sim_time():>6}] {self.role.upper():8}: misura base={obs_name(obs)} outcome={outcome}")

            yield self.await_timer(self.interval)


class RepeaterProtocol(NodeProtocol):
    def __init__(self, node, qin_port_alice, qin_port_bob, herald_port_alice, herald_port_bob):
        super().__init__(node=node)
        self.qin_port_alice = qin_port_alice
        self.qin_port_bob = qin_port_bob
        self.herald_port_alice = herald_port_alice
        self.herald_port_bob = herald_port_bob
        self.round_id = 0

    def run(self):
        port_a = self.node.ports[self.qin_port_alice]
        port_b = self.node.ports[self.qin_port_bob]
        cout_alice = self.node.ports[self.herald_port_alice]
        cout_bob = self.node.ports[self.herald_port_bob]

        while True:
            # aspetta che arrivino entrambi i qubit del nuovo round
            yield self.await_port_input(port_a) & self.await_port_input(port_b)

            qa = self.node.qmemory.peek(positions=[0])[0]
            qb = self.node.qmemory.peek(positions=[1])[0]

            if qa is None or qb is None:
                print(f"[t={ns.sim_time():>8}] REPEATER : slot non pronti, skip")
                continue

            print(f"[t={ns.sim_time():>8}] REPEATER: qubit da Alice presente in slot 0")
            print(f"[t={ns.sim_time():>8}] REPEATER: qubit da Bob presente in slot 1")

            self.round_id += 1
            print(f"[t={ns.sim_time():>8}] REPEATER: avvio BSM round={self.round_id}")

            prog = BellMeasureProgram()
            self.node.qmemory.execute_program(prog, qubit_mapping=[0, 1])
            yield self.await_program(self.node.qmemory)

            try:
                bell_index = prog.output["bell_index"][0]
            except Exception:
                bell_index = prog.output["bell_index"]

            herald = {
                "type": "bsm_result",
                "round": self.round_id,
                "bell_index": str(bell_index),
                "time": ns.sim_time(),
            }

            print(f"[t={ns.sim_time():>8}] REPEATER : BSM -> {herald}")

            cout_alice.tx_output(herald)
            cout_bob.tx_output(herald)

            # pulizia esplicita degli slot del repeater
            for pos in [0, 1]:
                q = self.node.qmemory.peek(positions=[pos])[0]
                if q is not None:
                    self.node.qmemory.pop(positions=[pos])


def build_network():
    network = Network("RepeaterSwap116")

    alice = Node("Alice", qmemory=build_processor("alice_proc", 1))
    repeater = Node("Repeater", qmemory=build_processor("rep_proc", 2))
    bob = Node("Bob", qmemory=build_processor("bob_proc", 1))

    network.add_nodes([alice, repeater, bob])

    # Aggiungo le due sorgenti locali
    alice_source = build_bell_source("alice_source", period=20)
    bob_source = build_bell_source("bob_source", period=20)

    alice.add_subcomponent(alice_source, name="alice_source")
    bob.add_subcomponent(bob_source, name="bob_source")

    # Link quantistici Alice -> Repeater e Bob -> Repeater
    alice_qout, rep_qin_from_alice = network.add_connection(
        alice,
        repeater,
        channel_to=build_quantum_channel("q_alice_rep", length_km=10),
        label="q_alice_rep",
    )

    bob_qout, rep_qin_from_bob = network.add_connection(
        bob,
        repeater,
        channel_to=build_quantum_channel("q_bob_rep", length_km=10),
        label="q_bob_rep",
    )

    # Heralding classico Repeater -> Alice e Repeater -> Bob
    rep_to_alice, alice_herald_in = network.add_connection(
        repeater,
        alice,
        channel_to=build_classical_channel("c_rep_alice", length_km=10),
        label="c_rep_alice",
    )

    rep_to_bob, bob_herald_in = network.add_connection(
        repeater,
        bob,
        channel_to=build_classical_channel("c_rep_bob", length_km=10),
        label="c_rep_bob",
    )

    # Wiring QSource Alice:
    # qout0 -> rete verso repeater
    # qout1 -> memoria locale Alice
    alice.subcomponents["alice_source"].ports["qout0"].forward_output(alice.ports[alice_qout])
    alice.subcomponents["alice_source"].ports["qout1"].connect(alice.qmemory.ports["qin0"])

    # Wiring QSource Bob
    bob.subcomponents["bob_source"].ports["qout0"].forward_output(bob.ports[bob_qout])
    bob.subcomponents["bob_source"].ports["qout1"].connect(bob.qmemory.ports["qin0"])

    # Rete in ingresso -> qmemory del repeater
    repeater.ports[rep_qin_from_alice].forward_input(repeater.qmemory.ports["qin0"])
    repeater.ports[rep_qin_from_bob].forward_input(repeater.qmemory.ports["qin1"])

    protocols = [
        SourceNodeProtocol(
            alice,
            source_name="alice_source",
            herald_port=alice_herald_in,
            role="Alice",
            rounds=6,
            interval=40,
        ),
        SourceNodeProtocol(
            bob,
            source_name="bob_source",
            herald_port=bob_herald_in,
            role="Bob",
            rounds=6,
            interval=40,
        ),
        RepeaterProtocol(
            repeater,
            qin_port_alice=rep_qin_from_alice,
            qin_port_bob=rep_qin_from_bob,
            herald_port_alice=rep_to_alice,
            herald_port_bob=rep_to_bob,
        ),
    ]

    return network, protocols


def main():
    try:
        ns.sim_reset()
    except Exception:
        pass

    try:
        ns.set_qstate_formalism(ns.QFormalism.DM)
    except Exception:
        try:
            ns.set_qstate_formalism(ns.QFormalism.KET)
        except Exception:
            pass

    network, protocols = build_network()
    print_topology(network)

    for p in protocols:
        p.start()

    stats = ns.sim_run(duration=700_000)

    print("\nFINE SIMULAZIONE")
    print(stats)

if __name__ == "__main__":
    main()