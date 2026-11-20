"""Skupni del: vhodi, priprava vezij, prevajanje, metrike in vrednotenje.

Vse nastavitve, ki morajo biti enake za oba seštevalnika (pari vhodov, nastavitve
prevajanja, število ponovitev), so tu na enem mestu.
"""

import random

from qiskit import ClassicalRegister, QuantumCircuit
from qiskit.transpiler import generate_preset_pass_manager

from koda.adders import ADDERS

N_VREDNOSTI = range(1, 6)  # n = 1 do 5 (prijava teme)
STEVILO_NAKLJUCNIH = 16  # pri n > 2 toliko naključnih parov (prijava teme)
OPTIMIZATION_LEVEL = 3  # enaka raven prevajanja za oba seštevalnika
SEED = 2026  # seme za naključne pare in za prevajanje, da so rezultati ponovljivi
SHOTS = 1000  # privzeto število ponovitev vsakega vezja


def pari_vhodov(n: int) -> list[tuple[int, int]]:
    """Pari (a, b) za dani n: vsi pari pri n <= 2, sicer 16 različnih naključnih.

    Seme je fiksno, zato vsak zagon (in oba seštevalnika) dobi iste pare.
    """
    m = 2**n
    if n <= 2:
        return [(a, b) for a in range(m) for b in range(m)]
    rng = random.Random(SEED * 100 + n)
    return [divmod(k, m) for k in sorted(rng.sample(range(m * m), STEVILO_NAKLJUCNIH))]


def pripravi_vezje(ime: str, n: int, a_val: int, b_val: int) -> QuantumCircuit:
    """Celotno vezje za en poskus: vrata X za vhode, seštevalnik, meritev b v register 'sum'."""
    adder = ADDERS[ime](n)
    regs = {r.name: r for r in adder.qregs}
    vsota = ClassicalRegister(n + 1, "sum")
    qc = QuantumCircuit(*adder.qregs, vsota, name=f"{ime}_n{n}_{a_val}+{b_val}")
    for i in range(n):
        if a_val >> i & 1:
            qc.x(regs["a"][i])
        if b_val >> i & 1:
            qc.x(regs["b"][i])
    qc.compose(adder, inplace=True)
    qc.measure(regs["b"], vsota)
    return qc


def pass_manager(backend):
    """Prevajalnik z enakimi nastavitvami za oba seštevalnika."""
    return generate_preset_pass_manager(
        optimization_level=OPTIMIZATION_LEVEL, backend=backend, seed_transpiler=SEED
    )


def st_vrat(qc: QuantumCircuit, st_kubitov: int) -> int:
    """Število vrat, ki delujejo na natanko st_kubitov kubitov (brez pregrad)."""
    return sum(
        1
        for inst in qc.data
        if inst.operation.num_qubits == st_kubitov and inst.operation.name != "barrier"
    )


def metrike(ime: str, n: int, backend) -> dict:
    """Lastnosti samega seštevalnika (brez vhodov in meritev) pred prevajanjem in po njem.

    Pred prevajanjem CDKM vsebuje Toffolijeva vrata (3 kubiti), zato jih štejemo posebej.
    Po prevajanju so vsa večkubitna vrata dvokubitna (na IBM Heron so to vrata CZ).
    """
    qc = ADDERS[ime](n)
    t = pass_manager(backend).run(qc)
    return {
        "sestevalnik": ime,
        "n": n,
        "backend": backend.name,
        "kubiti": qc.num_qubits,
        "globina_pred": qc.depth(),
        "dvokubitna_pred": st_vrat(qc, 2),
        "trokubitna_pred": st_vrat(qc, 3),
        "globina_po": t.depth(),
        "dvokubitna_po": st_vrat(t, 2),
    }


def verjetnost_pravilne(counts: dict[str, int], a_val: int, b_val: int) -> float:
    """Delež meritev, pri katerih je register 'sum' enak a + b."""
    shots = sum(counts.values())
    pravilne = sum(c for izid, c in counts.items() if int(izid, 2) == a_val + b_val)
    return pravilne / shots


def nakljucni_izid(n: int) -> float:
    """Verjetnost pravilne vsote, če bi bil izid povsem naključen: 1 / 2**(n+1)."""
    return 1 / 2 ** (n + 1)
