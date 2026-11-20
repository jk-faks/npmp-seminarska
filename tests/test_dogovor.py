"""Preveri, da vsi seštevalniki v ADDERS spoštujejo dogovor iz README.

Vhode in izhode bere po imenih registrov (ne po vrstnem redu), tako kot jih bo brala
skupna koda. Če kdo doda nov seštevalnik v ADDERS, ga ti testi preverijo samodejno.
"""

import random

import pytest
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

from koda.adders import ADDERS

IMENA = sorted(ADDERS)


def simuliraj(ime: str, n: int, a_val: int, b_val: int) -> dict[str, int]:
    """Izvede seštevalnik na idealnem simulatorju in vrne vrednost vsakega registra."""
    adder = ADDERS[ime](n)
    qc = QuantumCircuit(*adder.qregs)
    regs = {r.name: r for r in adder.qregs}
    for i in range(n):
        if a_val >> i & 1:
            qc.x(regs["a"][i])
        if b_val >> i & 1:
            qc.x(regs["b"][i])
    qc.compose(adder, inplace=True)

    probs = Statevector(qc).probabilities_dict(decimals=10)
    izid, p = max(probs.items(), key=lambda kv: kv[1])
    assert p == pytest.approx(1, abs=1e-8), "izid ni deterministicen"

    # Bitni niz je big-endian: znak -1-k pripada kubitu k.
    def vrednost(reg) -> int:
        return sum(int(izid[-1 - qc.find_bit(q).index]) << i for i, q in enumerate(reg))

    return {r.name: vrednost(r) for r in adder.qregs}


def pari(n: int) -> list[tuple[int, int]]:
    """Vsi pari pri n <= 3, sicer robni primeri in 20 naključnih (s fiksnim semenom)."""
    m = 2**n - 1
    if n <= 3:
        return [(x, y) for x in range(m + 1) for y in range(m + 1)]
    rng = random.Random(n)
    return [(0, 0), (m, m), (m, 0), (0, m)] + [
        (rng.randint(0, m), rng.randint(0, m)) for _ in range(20)
    ]


@pytest.mark.parametrize("ime", IMENA)
@pytest.mark.parametrize("n", [1, 2, 5])
def test_registri(ime, n):
    qc = ADDERS[ime](n)
    regs = {r.name: r.size for r in qc.qregs}
    assert regs["a"] == n
    assert regs["b"] == n + 1
    assert set(regs) <= {"a", "b", "anc"}, "dovoljeni so samo registri a, b in anc"
    assert qc.num_clbits == 0
    assert not {"measure", "reset"} & set(qc.count_ops()), "vezje ne sme meriti"


@pytest.mark.parametrize("ime", IMENA)
def test_n_manjsi_od_1(ime):
    with pytest.raises(ValueError):
        ADDERS[ime](0)


@pytest.mark.parametrize("ime", IMENA)
@pytest.mark.parametrize("n", [1, 2, 3, 4, 5])
def test_sesteje(ime, n):
    for a_val, b_val in pari(n):
        r = simuliraj(ime, n, a_val, b_val)
        assert r["b"] == a_val + b_val, (a_val, b_val)
        assert r["a"] == a_val, (a_val, b_val)
        assert r.get("anc", 0) == 0, (a_val, b_val)
