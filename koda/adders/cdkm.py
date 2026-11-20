"""Seštevalnik CDKM z zaporednim prenosom (Cuccaro et al. 2004). Avtor: Jurij Anžič.

Ideja: prenos (carry) potuje od najnižjega bita navzgor, a ga ne hranimo v svojih kubitih.
Blok MAJ (večina) zapiše prenos c_{i+1} = MAJ(c_i, a_i, b_i) kar na mesto a_i. Ko pridemo
do vrha, zgornji prenos prepišemo v izhodni kubit. Nato bloki UMA (UnMajority and Add) gredo
nazaj navzdol: vsak razveljavi svoj MAJ, vrne a_i v prvotno stanje in v b_i zapiše
s_i = a_i XOR b_i XOR c_i. Potrebujemo samo en pomožni kubit (vhodni prenos c_0 = 0).

Vezje ima 2n Toffolijevih vrat in 4n + 1 vrat CNOT ter globino, ki raste linearno z n.
"""

from qiskit import QuantumCircuit, QuantumRegister
from qiskit.circuit import Qubit


def maj(qc: QuantumCircuit, c: Qubit, b: Qubit, a: Qubit) -> None:
    """Blok MAJ: c, b, a -> c XOR a, b XOR a, MAJ(a, b, c).

    Po njem kubit a nosi izhodni prenos tega bita.
    """
    qc.cx(a, b)
    qc.cx(a, c)
    qc.ccx(c, b, a)


def uma(qc: QuantumCircuit, c: Qubit, b: Qubit, a: Qubit) -> None:
    """Blok UMA (različica z 2 CNOT): razveljavi MAJ in v b zapiše bit vsote.

    Iz stanja po MAJ vrne c in a v prvotni stanji, b pa postane a XOR b XOR c.
    """
    qc.ccx(c, b, a)
    qc.cx(a, c)
    qc.cx(c, b)


def build_adder(n: int) -> QuantumCircuit:
    """Vrne vezje, ki v register b zapiše a + b (glej dogovor v README).

    Registri: a (n kubitov), b (n+1 kubitov, zgornji je izhodni prenos) in anc (1 kubit,
    vhodni prenos c_0, ki se začne in konča v stanju 0).
    """
    if n < 1:
        raise ValueError("n mora biti vsaj 1")
    a = QuantumRegister(n, "a")
    b = QuantumRegister(n + 1, "b")
    anc = QuantumRegister(1, "anc")
    qc = QuantumCircuit(a, b, anc, name=f"cdkm_{n}")

    # Prenos, ki pride v bit i: za i = 0 je to anc, sicer a[i-1] (tja ga je zapisal MAJ).
    def carry_in(i: int) -> Qubit:
        return anc[0] if i == 0 else a[i - 1]

    for i in range(n):
        maj(qc, carry_in(i), b[i], a[i])
    qc.cx(a[n - 1], b[n])  # izhodni prenos
    for i in reversed(range(n)):
        uma(qc, carry_in(i), b[i], a[i])
    return qc
