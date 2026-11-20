"""Testi skupnega dela (koda/common.py)."""

import pytest
from qiskit_aer import AerSimulator
from qiskit_ibm_runtime.fake_provider import FakeTorino

from koda.adders import ADDERS
from koda.common import (
    STEVILO_NAKLJUCNIH,
    metrike,
    nakljucni_izid,
    pari_vhodov,
    pass_manager,
    pripravi_vezje,
    verjetnost_pravilne,
)


def test_pari_vhodov():
    assert len(pari_vhodov(1)) == 4
    assert len(pari_vhodov(2)) == 16
    for n in (3, 4, 5):
        pari = pari_vhodov(n)
        assert len(set(pari)) == STEVILO_NAKLJUCNIH, "pari se ne smejo ponavljati"
        assert all(0 <= a < 2**n and 0 <= b < 2**n for a, b in pari)
        assert pari == pari_vhodov(n), "pari morajo biti pri vsakem klicu enaki"


def test_verjetnost_pravilne():
    # n = 2, 3 + 2 = 5 = '101'
    assert verjetnost_pravilne({"101": 3, "000": 1}, 3, 2) == 0.75
    assert verjetnost_pravilne({"000": 10}, 3, 2) == 0
    assert nakljucni_izid(2) == 1 / 8


@pytest.mark.parametrize("ime", sorted(ADDERS))
def test_pripravljeno_vezje_na_idealnem_simulatorju(ime):
    """Celotno vezje (vhodi + seštevalnik + meritev) vrne pravilno vsoto."""
    sim = AerSimulator()
    n = 3
    vezja = [pripravi_vezje(ime, n, a, b) for a, b in pari_vhodov(n)]
    rezultat = sim.run(pass_manager(sim).run(vezja), shots=20).result()
    for (a, b), qc in zip(pari_vhodov(n), vezja):
        assert verjetnost_pravilne(rezultat.get_counts(qc.name), a, b) == 1, (a, b)


def test_pripravljeno_vezje_meri_samo_b():
    qc = pripravi_vezje("cdkm", 2, 1, 2)
    assert [c.name for c in qc.cregs] == ["sum"]
    assert qc.count_ops()["measure"] == 3


@pytest.mark.parametrize("ime", sorted(ADDERS))
def test_metrike(ime):
    m = metrike(ime, 2, FakeTorino())
    assert m["n"] == 2 and m["sestevalnik"] == ime
    assert m["dvokubitna_po"] > 0
    assert m["globina_po"] >= m["globina_pred"]
