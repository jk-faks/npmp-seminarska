"""Poganjanje poskusov na simulatorjih. Zaganjaj iz korena repozitorija:

    uv run python -m koda.run metrike   # lastnosti vezij pred in po prevajanju (FakeTorino)
    uv run python -m koda.run ideal     # idealni simulator
    uv run python -m koda.run sum       # šumni simulator (šumni model FakeTorino)

Vsak zagon odda vsa vezja (oba seštevalnika, n = 1 do 5) v enem poslu in v mapo
results/ zapiše:
    <ime>_naloga.json   kaj je bilo oddano (pari vhodov, vrata po prevajanju),
    <ime>_counts.json   surovi izidi meritev za vsako vezje,
    <ime>.csv           ena vrstica na vezje z verjetnostjo pravilne vsote.

Zagon na procesorju IBM še ni dodan (glej README).
"""

import argparse
import csv
import json
from pathlib import Path
from statistics import mean

from qiskit_ibm_runtime import SamplerV2 as Sampler

from koda.adders import ADDERS
from koda.common import (
    N_VREDNOSTI,
    SEED,
    SHOTS,
    metrike,
    nakljucni_izid,
    pari_vhodov,
    pass_manager,
    pripravi_vezje,
    st_vrat,
    verjetnost_pravilne,
)

REZULTATI = Path("results")


def izberi_backend(nacin: str):
    """Idealni simulator ali šumni simulator z modelom procesorja IBM Torino."""
    if nacin == "ideal":
        from qiskit_aer import AerSimulator

        return AerSimulator()
    from qiskit_ibm_runtime.fake_provider import FakeTorino

    return FakeTorino()


def zapisi_csv(pot: Path, vrstice: list[dict]) -> None:
    with pot.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(vrstice[0]))
        w.writeheader()
        w.writerows(vrstice)


def ukaz_metrike(backend) -> None:
    vrstice = [metrike(ime, n, backend) for n in N_VREDNOSTI for ime in ADDERS]
    pot = REZULTATI / f"metrike_{backend.name}.csv"
    zapisi_csv(pot, vrstice)
    print(f"{'n':>2} {'seštevalnik':12} {'kubiti':>6} {'2q pred':>8} {'3q pred':>8} "
          f"{'2q po':>6} {'globina po':>11}")
    for v in vrstice:
        print(f"{v['n']:>2} {v['sestevalnik']:12} {v['kubiti']:>6} {v['dvokubitna_pred']:>8} "
              f"{v['trokubitna_pred']:>8} {v['dvokubitna_po']:>6} {v['globina_po']:>11}")
    print(f"\nZapisano v {pot}")


def zazeni(nacin: str, backend, shots: int) -> None:
    """Pripravi, prevede in odda vsa vezja v enem poslu, nato shrani rezultate."""
    naloge = [
        {"sestevalnik": ime, "n": n, "a": a, "b": b}
        for ime in ADDERS
        for n in N_VREDNOSTI
        for a, b in pari_vhodov(n)
    ]
    vezja = [pripravi_vezje(t["sestevalnik"], t["n"], t["a"], t["b"]) for t in naloge]
    print(f"Prevajam {len(vezja)} vezij za {backend.name} ...")
    prevedena = pass_manager(backend).run(vezja)
    for t, qc in zip(naloge, prevedena):
        t["dvokubitna_po"] = st_vrat(qc, 2)
        t["globina_po"] = qc.depth()

    # Seme simulatorja: isti zagon na istih različicah paketov da iste izide.
    sampler = Sampler(mode=backend, options={"simulator": {"seed_simulator": SEED}})
    meta = {"nacin": nacin, "backend": backend.name, "shots": shots, "naloge": naloge}
    osnova = REZULTATI / f"{nacin}_{backend.name}"
    Path(f"{osnova}_naloga.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False))
    print("Simuliram ...")
    rezultat = sampler.run(prevedena, shots=shots).result()
    shrani_rezultate(meta, rezultat, osnova)


def shrani_rezultate(meta: dict, rezultat, osnova: Path) -> None:
    vrstice, surovi = [], []
    for t, pub in zip(meta["naloge"], rezultat, strict=True):
        counts = pub.data.sum.get_counts()
        vrstice.append({
            "nacin": meta["nacin"],
            "backend": meta["backend"],
            **t,
            "shots": meta["shots"],
            "p_pravilne": verjetnost_pravilne(counts, t["a"], t["b"]),
            "nakljucno": nakljucni_izid(t["n"]),
        })
        surovi.append({**t, "counts": counts})
    zapisi_csv(Path(f"{osnova}.csv"), vrstice)
    Path(f"{osnova}_counts.json").write_text(json.dumps(surovi, indent=1))
    povzetek(vrstice)
    print(f"\nZapisano v {osnova}.csv in {osnova}_counts.json")


def povzetek(vrstice: list[dict]) -> None:
    """Povprečna verjetnost pravilne vsote po seštevalniku in n."""
    print(f"\n{'n':>2} " + " ".join(f"{ime:>8}" for ime in ADDERS) + f" {'naključno':>10}")
    for n in N_VREDNOSTI:
        p = [mean(v["p_pravilne"] for v in vrstice if v["n"] == n and v["sestevalnik"] == ime)
             for ime in ADDERS]
        print(f"{n:>2} " + " ".join(f"{x:>8.3f}" for x in p) + f" {nakljucni_izid(n):>10.3f}")


def main() -> None:
    p = argparse.ArgumentParser(description="Poskusi s seštevalnikoma CDKM in Draper.")
    p.add_argument("ukaz", choices=["metrike", "ideal", "sum"])
    p.add_argument("--shots", type=int, default=SHOTS)
    args = p.parse_args()

    REZULTATI.mkdir(exist_ok=True)
    backend = izberi_backend(args.ukaz)
    if args.ukaz == "metrike":
        ukaz_metrike(backend)
    else:
        zazeni(args.ukaz, backend, args.shots)


if __name__ == "__main__":
    main()
