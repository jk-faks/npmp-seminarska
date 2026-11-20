"""Pravilnost seštevalnika CDKM na idealnem simulatorju, za vse pare vhodov."""

import pytest
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

from koda.adders.cdkm import build_adder


def run_ideal(n: int, a_val: int, b_val: int) -> dict[str, float]:
    """Pripravi vhoda, izvede seštevalnik in vrne verjetnosti izidov."""
    adder = build_adder(n)
    qc = QuantumCircuit(*adder.qregs)
    a, b = adder.qregs[0], adder.qregs[1]
    for i in range(n):
        if a_val >> i & 1:
            qc.x(a[i])
        if b_val >> i & 1:
            qc.x(b[i])
    qc.compose(adder, inplace=True)
    return Statevector(qc).probabilities_dict(decimals=10)


def test_registri_po_dogovoru():
    qc = build_adder(3)
    assert [(r.name, r.size) for r in qc.qregs] == [("a", 3), ("b", 4), ("anc", 1)]
    assert qc.num_clbits == 0


def test_stevilo_vrat():
    for n in range(1, 6):
        ops = build_adder(n).count_ops()
        assert ops["ccx"] == 2 * n
        assert ops["cx"] == 4 * n + 1


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5])
def test_vsi_pari(n):
    for a_val in range(2**n):
        for b_val in range(2**n):
            probs = run_ideal(n, a_val, b_val)
            # Bitni niz je anc (zgornji kubit), nato b (n+1 kubitov), nato a (n), little-endian.
            # anc mora biti spet 0 in a nespremenjen.
            expected = "0" + format(a_val + b_val, f"0{n + 1}b") + format(a_val, f"0{n}b")
            assert probs.get(expected, 0) == pytest.approx(1, abs=1e-8), (a_val, b_val)
