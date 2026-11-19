"""Draperjev seštevalnik na osnovi kvantne Fourierjeve transformacije (Draper 2000).

Avtor: Janez Koprivec.

Ideja: register b prestavimo s QFT v Fourierjevo bazo, kjer je število zapisano v fazah
kubitov. Prištevanje a je tam samo zasuk faz, ki ga krmilijo biti a. Na koncu z inverzno
QFT vrnemo b v računsko bazo, kjer je zdaj zapisana vsota a + b.
"""

from math import pi

from qiskit import QuantumCircuit, QuantumRegister


def qft(qc: QuantumCircuit, reg: QuantumRegister) -> None:
    """QFT na registru reg, brez končnih zamenjav (SWAP).

    Po njej kubit k nosi fazo exp(2*pi*i * x / 2**(k+1)), kjer je x število v registru.
    Zamenjave izpustimo, ker bi se pri QFT in inverzni QFT izničile in samo dodale vrata.
    """
    m = len(reg)
    for k in reversed(range(m)):
        qc.h(reg[k])
        for j in reversed(range(k)):
            qc.cp(pi / 2 ** (k - j), reg[j], reg[k])


def iqft(qc: QuantumCircuit, reg: QuantumRegister) -> None:
    """Inverzna QFT: vrata funkcije qft v obratnem vrstnem redu z nasprotnimi koti."""
    m = len(reg)
    for k in range(m):
        for j in range(k):
            qc.cp(-pi / 2 ** (k - j), reg[j], reg[k])
        qc.h(reg[k])


def add_in_fourier(qc: QuantumCircuit, a: QuantumRegister, b: QuantumRegister) -> None:
    """Prišteje a k registru b, ki je v Fourierjevi bazi.

    Kubit b[k] potrebuje dodatno fazo 2*pi * a / 2**(k+1) = vsota po j od a_j * pi / 2**(k-j).
    Za j > k je kot večkratnik 2*pi, zato ta vrata izpustimo.
    """
    for k in range(len(b)):
        for j in range(min(k + 1, len(a))):
            qc.cp(pi / 2 ** (k - j), a[j], b[k])


def build_adder(n: int) -> QuantumCircuit:
    """Vrne vezje, ki v register b zapiše a + b (glej dogovor v README).

    Registri: a (n kubitov), b (n+1 kubitov, zgornji je izhodni prenos). Pomožnih kubitov ni.
    """
    if n < 1:
        raise ValueError("n mora biti vsaj 1")
    a = QuantumRegister(n, "a")
    b = QuantumRegister(n + 1, "b")
    qc = QuantumCircuit(a, b, name=f"draper_{n}")
    qft(qc, b)
    add_in_fourier(qc, a, b)
    iqft(qc, b)
    return qc
