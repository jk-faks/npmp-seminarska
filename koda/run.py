"""Poganjanje poskusov. Zaganjaj iz korena repozitorija:

    uv run python -m koda.run metrike   # lastnosti vezij pred in po prevajanju (FakeTorino)
    uv run python -m koda.run ideal     # idealni simulator
    uv run python -m koda.run sum       # šumni simulator (šumni model FakeTorino)
    uv run python -m koda.run sum --lazni fake_fez        # šumni model drugega procesorja
    uv run python -m koda.run ibm --backend ibm_fez --pilot --potrdi   # poskusni posel
    uv run python -m koda.run ibm --backend ibm_fez --potrdi           # vsa vezja
    uv run python -m koda.run prevzemi <job_id>   # rezultati posla, če zagon ni počakal

Vsak zagon odda vsa vezja (oba seštevalnika, n = 1 do 5) v enem poslu in v mapo
results/ zapiše:
    <ime>_naloga.json   kaj je bilo oddano (pari vhodov, vrata po prevajanju, job ID),
    <ime>_counts.json   surovi izidi meritev za vsako vezje,
    <ime>.csv           ena vrstica na vezje z verjetnostjo pravilne vsote.

Čas na procesorju IBM je omejen (Open Plan: 600 s na 28 dni), zato način ibm:
  - brez --potrdi ničesar ne odda, samo izpiše, kaj bi oddal,
  - z --pilot odda samo vezja za n = 1 (8 vezij × 1000 ponovitev) in izmeri porabo,
  - za celoten posel oceni porabo iz poskusnega posla in ga ne odda, če bi ocena
    presegla --najvec-sekund ali preostanek proračuna.
"""

import argparse
import csv
import json
from datetime import datetime, timezone
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


LAZNI = ("fake_torino", "fake_fez", "fake_kingston", "fake_marrakesh")


def izberi_backend(nacin: str, lazni: str = "fake_torino"):
    """Idealni simulator ali lažni procesor IBM (šumni model in topologija posnetka)."""
    if nacin == "ideal":
        from qiskit_aer import AerSimulator

        return AerSimulator()
    from qiskit_ibm_runtime import fake_provider

    razred = "Fake" + lazni.removeprefix("fake_").capitalize()
    return getattr(fake_provider, razred)()


def zapisi_csv(pot: Path, vrstice: list[dict]) -> None:
    with pot.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(vrstice[0]))
        w.writeheader()
        w.writerows(vrstice)


def ukaz_metrike(backend) -> None:
    vrstice = [metrike(ime, n, backend) for n in N_VREDNOSTI for ime in ADDERS]
    pot = REZULTATI / f"metrike_{backend.name}.csv"
    zapisi_csv(pot, vrstice)
    print(f"{'n':>2} {'seštevalnik':12} {'kubiti':>6} {'CX razgr.':>9} {'glob. razgr.':>12} "
          f"{'2q po':>6} {'2q po (razpon semen)':>21} {'globina po':>11}")
    for v in vrstice:
        razpon = f"{v['dvokubitna_po_min']}–{v['dvokubitna_po_max']}"
        print(f"{v['n']:>2} {v['sestevalnik']:12} {v['kubiti']:>6} {v['cx_razgrajeno']:>9} "
              f"{v['globina_razgrajeno']:>12} {v['dvokubitna_po']:>6} {razpon:>21} "
              f"{v['globina_po']:>11}")
    print(f"\nZapisano v {pot}")


def pripravi(backend, n_vrednosti=N_VREDNOSTI) -> tuple[list[dict], list]:
    """Naloge (seštevalnik, n, a, b) in prevedena vezja za vse v enem seznamu."""
    naloge = [
        {"sestevalnik": ime, "n": n, "a": a, "b": b}
        for ime in ADDERS
        for n in n_vrednosti
        for a, b in pari_vhodov(n)
    ]
    vezja = [pripravi_vezje(t["sestevalnik"], t["n"], t["a"], t["b"]) for t in naloge]
    print(f"Prevajam {len(vezja)} vezij za {backend.name} ...")
    prevedena = pass_manager(backend).run(vezja)
    for t, qc in zip(naloge, prevedena):
        t["dvokubitna_po"] = st_vrat(qc, 2)
        t["globina_po"] = qc.depth()
    return naloge, prevedena


def zazeni(nacin: str, backend, shots: int) -> None:
    """Pripravi, prevede in odda vsa vezja v enem poslu na simulatorju, nato shrani rezultate."""
    naloge, prevedena = pripravi(backend)

    # Seme simulatorja: isti zagon na istih različicah paketov da iste izide.
    sampler = Sampler(mode=backend, options={"simulator": {"seed_simulator": SEED}})
    meta = {"nacin": nacin, "backend": backend.name, "shots": shots, "naloge": naloge}
    osnova = REZULTATI / f"{nacin}_{backend.name}"
    Path(f"{osnova}_naloga.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False))
    print("Simuliram ...")
    rezultat = sampler.run(prevedena, shots=shots).result()
    shrani_rezultate(meta, rezultat, osnova)


def ocena_porabe(backend_ime: str, st_vezij: int, shots: int) -> float | None:
    """Ocena sekund za posel iz izmerjene porabe poskusnega posla na istem procesorju.

    Porabo poskusnega posla linearno preračunamo na skupno število ponovitev. Del porabe je
    stalen strošek posla, zato je ocena za večji posel prej previsoka kot prenizka.
    """
    pot = REZULTATI / f"ibm_pilot_{backend_ime}_naloga.json"
    if not pot.exists():
        return None
    pilot = json.loads(pot.read_text())
    if not pilot.get("poraba_s"):  # None ali 0: poraba še ni izmerjena
        return None
    pilot_ponovitve = len(pilot["naloge"]) * pilot["shots"]
    return pilot["poraba_s"] * st_vezij * shots / pilot_ponovitve


def zazeni_ibm(backend_ime: str, shots: int, pilot: bool, potrdi: bool, najvec_s: float,
               n_vrednosti=N_VREDNOSTI, dd: bool = False, oznaka: str = "",
               rezerva_s: float = 60) -> None:
    """Odda vezja na procesor IBM v enem poslu, z varovalkami za porabo časa.

    dd: vklopi dinamično razklapljanje (impulzi na kubitih med mirovanjem).
    oznaka: dodatek k imenu datotek v results/, da različni poskusi ne prepišejo drug drugega.
    rezerva_s: toliko sekund proračuna mora ostati tudi po tem poslu.
    """
    from koda.ibm import preostanek_sekund, storitev

    nacin = "ibm_pilot" if pilot else "ibm" + ("_dd" if dd else "") + (f"_{oznaka}" if oznaka else "")
    osnova = REZULTATI / f"{nacin}_{backend_ime}"
    if Path(f"{osnova}_naloga.json").exists():
        raise SystemExit(f"{osnova}_naloga.json že obstaja. Za nov poskus uporabi --oznaka.")

    service = storitev()
    backend = service.backend(backend_ime)
    if pilot:
        n_vrednosti = [1]
    naloge, prevedena = pripravi(backend, n_vrednosti)
    preostanek = preostanek_sekund(service)
    print(f"{nacin}: {len(prevedena)} vezij × {shots} ponovitev na {backend.name}, DD={dd}; "
          f"preostanek proračuna: {preostanek:.0f} s")
    if pilot and preostanek - 10 < rezerva_s:
        raise SystemExit("Premalo preostalega proračuna. Ničesar nisem oddal.")

    if not pilot:
        ocena = ocena_porabe(backend.name, len(prevedena), shots)
        if ocena is None:
            raise SystemExit("Ni izmerjene porabe poskusnega posla na tem procesorju. "
                             "Najprej poženi z --pilot.")
        print(f"Ocenjena poraba: {ocena:.0f} s (meja --najvec-sekund: {najvec_s:.0f} s)")
        if ocena > najvec_s or ocena > preostanek - rezerva_s:
            raise SystemExit("Ocena presega mejo ali preostanek proračuna. Ničesar nisem oddal.")
    if not potrdi:
        print("Brez --potrdi ničesar ne oddam.")
        return

    # Privzeto brez blaženja napak, da je primerljivo s simulatorji; DD samo z --dd.
    sampler = Sampler(mode=backend, options={
        "dynamical_decoupling": {"enable": dd, **({"sequence_type": "XpXm"} if dd else {})},
        "twirling": {"enable_gates": False, "enable_measure": False},
    })
    job = sampler.run(prevedena, shots=shots)
    meta = {
        "nacin": nacin,
        "backend": backend.name,
        "shots": shots,
        "dd": dd,
        "job_id": job.job_id(),
        "oddano": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "poraba_s": None,
        "naloge": naloge,
    }
    Path(f"{osnova}_naloga.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False))
    print(f"Oddano, job ID: {job.job_id()}. Čakam na rezultate (prekinitev je varna, "
          f"kasneje: uv run python -m koda.run prevzemi {job.job_id()}) ...")
    prevzemi(job.job_id(), service)


def prevzemi(job_id: str, service=None) -> None:
    """Počaka na posel IBM, shrani rezultate in izmerjeno porabo v <ime>_naloga.json."""
    if service is None:
        from koda.ibm import storitev

        service = storitev()
    job = service.job(job_id)
    rezultat = job.result()
    poti = [p for p in REZULTATI.glob("ibm*_naloga.json")
            if json.loads(p.read_text()).get("job_id") == job_id]
    if len(poti) != 1:
        raise SystemExit(f"V results/ ni natanko ene naloge s tem job ID ({len(poti)}).")
    pot = poti[0]
    meta = json.loads(pot.read_text())
    meta["poraba_s"] = izmerjena_poraba(job)
    pot.write_text(json.dumps(meta, indent=1, ensure_ascii=False))
    print(f"Poraba posla: {meta['poraba_s']} s" if meta["poraba_s"] else
          f"Poraba še ni izračunana; ponovi prevzemi {job_id} čez nekaj minut.")
    shrani_rezultate(meta, rezultat, Path(str(pot).removesuffix("_naloga.json")))


def izmerjena_poraba(job, poskusov: int = 12) -> float | None:
    """Poraba posla v sekundah. IBM jo izračuna z zamikom in do takrat vrne 0, zato nekaj
    časa počakamo. Vrne None, če je še ni; ocena_porabe takrat celotnega posla ne dovoli."""
    import time

    for _ in range(poskusov):
        poraba = job.usage()
        if poraba:
            return float(poraba)
        time.sleep(5)
    return None


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
    for n in sorted({v["n"] for v in vrstice}):
        p = [mean(v["p_pravilne"] for v in vrstice if v["n"] == n and v["sestevalnik"] == ime)
             for ime in ADDERS]
        print(f"{n:>2} " + " ".join(f"{x:>8.3f}" for x in p) + f" {nakljucni_izid(n):>10.3f}")


def main() -> None:
    p = argparse.ArgumentParser(description="Poskusi s seštevalnikoma CDKM in Draper.")
    p.add_argument("ukaz", choices=["metrike", "ideal", "sum", "ibm", "prevzemi"])
    p.add_argument("job_id", nargs="?", help="za prevzemi: job ID posla IBM")
    p.add_argument("--shots", type=int, default=SHOTS)
    p.add_argument("--lazni", choices=LAZNI, default="fake_torino",
                   help="za metrike in sum: lažni procesor (šumni model in topologija)")
    p.add_argument("--backend", help="za ibm: ime procesorja, npr. ibm_fez")
    p.add_argument("--pilot", action="store_true", help="za ibm: samo n = 1 (8 vezij)")
    p.add_argument("--potrdi", action="store_true", help="za ibm: res oddaj posel")
    p.add_argument("--najvec-sekund", type=float, default=120,
                   help="za ibm: največja ocenjena poraba celotnega posla (privzeto 120 s)")
    p.add_argument("--rezerva", type=float, default=60,
                   help="za ibm: toliko sekund proračuna mora ostati po poslu (privzeto 60 s)")
    p.add_argument("--n", default=None,
                   help="za ibm in sum: vrednosti n, npr. 1-8 (privzeto 1-5)")
    p.add_argument("--dd", action="store_true", help="za ibm: dinamično razklapljanje")
    p.add_argument("--oznaka", default="", help="za ibm: dodatek k imenu datotek v results/")
    args = p.parse_args()

    REZULTATI.mkdir(exist_ok=True)
    n_vrednosti = N_VREDNOSTI
    if args.n:
        od, _, do = args.n.partition("-")
        n_vrednosti = range(int(od), int(do or od) + 1)
    if args.ukaz == "ibm":
        if not args.backend:
            p.error("ibm potrebuje --backend")
        zazeni_ibm(args.backend, args.shots, args.pilot, args.potrdi, args.najvec_sekund,
                   n_vrednosti, args.dd, args.oznaka, args.rezerva)
    elif args.ukaz == "prevzemi":
        if not args.job_id:
            p.error("prevzemi potrebuje job_id")
        prevzemi(args.job_id)
    elif args.ukaz == "metrike":
        ukaz_metrike(izberi_backend("metrike", args.lazni))
    else:
        zazeni(args.ukaz, izberi_backend(args.ukaz, args.lazni), args.shots)


if __name__ == "__main__":
    main()
