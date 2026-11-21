"""Analiza poslov IBM: pričakovana uspešnost iz kalibracije in vrste napak.

    uv run python -m koda.analiza <ime>      # npr. ibm_ibm_fez (datoteke results/<ime>_*)

Za vsak posel:
  1. Iz IBM prenese natanko oddana (prevedena) vezja, s fizičnimi kubiti, in kalibracijo
     procesorja v času izvajanja posla. Oboje shrani v results/, da je analiza ponovljiva
     brez dostopa do IBM (<ime>_vezja.qpy.gz, <ime>_kalibracija.json).
  2. Za vsako vezje izračuna oceno verjetnosti uspeha (ESP, estimated success probability):
     zmnožek (1 - napaka) čez vsa vrata in meritve na dejanskih fizičnih kubitih in povezavah.
     ESP ne upošteva časa mirovanja (dekoherenca), presluha in koherentnih napak.
  3. Primerja, kako dobro izmerjeno uspešnost napovesta ESP in število dvokubitnih vrat.
  4. Opiše napačne izide: koliko bitov je napačnih in kateri.

Zapiše results/<ime>_analiza.csv (ena vrstica na vezje) in izpiše povzetek.
"""

import csv
import gzip
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from math import exp
from statistics import correlation, mean

from qiskit import QuantumCircuit, qpy

from koda.common import st_vrat

REZULTATI = Path("results")


def prenesi(osnova: Path, meta: dict) -> tuple[list[QuantumCircuit], dict]:
    """Oddana vezja in kalibracija (napake vrat in meritev) v času posla; lokalno predpomnjeno."""
    pot_vezja = Path(f"{osnova}_vezja.qpy.gz")
    pot_kal = Path(f"{osnova}_kalibracija.json")
    if pot_vezja.exists() and pot_kal.exists():
        with gzip.open(pot_vezja, "rb") as f:
            return qpy.load(f), json.loads(pot_kal.read_text())

    from koda.ibm import storitev

    service = storitev()
    job = service.job(meta["job_id"])
    vezja = [item.circuit for item in job.inputs["quantum_program"].items]
    zagon = job.metrics()["timestamps"]["running"]
    cas = datetime.fromisoformat(zagon.replace("Z", "+00:00"))
    target = service.backend(meta["backend"]).target_history(datetime=cas)
    napake, trajanja = {}, {}
    for ime_op in target.operation_names:
        for qargs, lastnosti in (target[ime_op] or {}).items():
            if qargs is None or lastnosti is None:
                continue
            kljuc = f"{ime_op}:{','.join(map(str, qargs))}"
            if lastnosti.error is not None:
                napake[kljuc] = lastnosti.error
            if lastnosti.duration is not None:
                trajanja[kljuc] = lastnosti.duration
    kubiti = {str(i): {"t1": qp.t1, "t2": qp.t2}
              for i, qp in enumerate(target.qubit_properties or []) if qp is not None}
    kal = {"backend": meta["backend"], "cas_kalibracije": cas.isoformat(), "napake": napake,
           "trajanja": trajanja, "kubiti": kubiti, "dt": target.dt}
    with gzip.open(pot_vezja, "wb") as f:
        qpy.dump(vezja, f)
    pot_kal.write_text(json.dumps(kal, indent=1))
    return vezja, kal


def fizicni_kubiti(qc: QuantumCircuit) -> list[int]:
    """Kubiti, ki jih vezje dejansko uporablja (dvokubitna vrata ali meritev).

    Pri DD IBM doda zakasnitve in impulze X tudi na vse ostale kubite procesorja; ti na
    rezultat ne vplivajo, zato jih izpustimo.
    """
    return sorted({qc.find_bit(q).index for inst in qc.data for q in inst.qubits
                   if inst.operation.name in ("cz", "measure")})


def esp(qc: QuantumCircuit, napake: dict) -> dict:
    """ESP in njeni deli: dvokubitna vrata, enokubitna vrata, meritve."""
    deli = {"2q": 1.0, "1q": 1.0, "meritve": 1.0}
    uporabljeni = set(fizicni_kubiti(qc))
    for inst in qc.data:
        op = inst.operation.name
        if op in ("barrier", "delay"):
            continue
        if not {qc.find_bit(q).index for q in inst.qubits} <= uporabljeni:
            continue
        qargs = ",".join(str(qc.find_bit(q).index) for q in inst.qubits)
        e = napake.get(f"{op}:{qargs}", 0.0)  # rz je navidezen (brez napake)
        del_ = "meritve" if op == "measure" else ("2q" if len(inst.qubits) == 2 else "1q")
        deli[del_] *= 1 - e
    return {"esp": deli["2q"] * deli["1q"] * deli["meritve"],
            "esp_2q": deli["2q"], "esp_1q": deli["1q"], "esp_meritve": deli["meritve"]}


def mirovanje(qc: QuantumCircuit, kal: dict) -> dict:
    """Razpored ASAP s trajanji iz kalibracije: trajanje vezja in čas mirovanja kubitov.

    Kubit miruje med svojimi prvimi in zadnjimi vrati, ko ne izvaja nobenih vrat (čaka na
    druge kubite). Pred prvimi vrati je v stanju 0 in mirovanje ne škodi. Iz T1 in T2 vrne
    faktorja exp(-t/T1) (relaksacija) in exp(-t/T2) (izguba faze), zmnožena čez kubite.
    """
    prost, zacetek, zasedenost = defaultdict(float), {}, defaultdict(float)
    uporabljeni = set(fizicni_kubiti(qc))
    for inst in qc.data:
        qs = [qc.find_bit(q).index for q in inst.qubits]
        if not set(qs) <= uporabljeni:
            continue
        if inst.operation.name == "delay":  # izrecno mirovanje (vstavi ga DD)
            op = inst.operation
            trajanje = op.duration * (kal["dt"] if op.unit == "dt" else 1.0)
            for q in qs:
                prost[q] += trajanje
            continue
        if inst.operation.name == "barrier":
            t = max(prost[q] for q in qs)
            for q in qs:
                prost[q] = t
            continue
        trajanje = kal["trajanja"].get(f"{inst.operation.name}:{','.join(map(str, qs))}", 0.0)
        t = max(prost[q] for q in qs)
        for q in qs:
            zacetek.setdefault(q, t)
            prost[q] = t + trajanje
            zasedenost[q] += trajanje
    f_t1 = f_t2 = 1.0
    skupno_mirovanje = 0.0
    for q in zacetek:
        t_mir = prost[q] - zacetek[q] - zasedenost[q]
        skupno_mirovanje += t_mir
        lastnosti = kal["kubiti"].get(str(q), {})
        if lastnosti.get("t1"):
            f_t1 *= exp(-t_mir / lastnosti["t1"])
        if lastnosti.get("t2"):
            f_t2 *= exp(-t_mir / lastnosti["t2"])
    return {"trajanje_us": max(prost.values()) * 1e6, "mirovanje_us": skupno_mirovanje * 1e6,
            "f_mirovanje_t1": f_t1, "f_mirovanje_t2": f_t2}


def napacni_biti(counts: dict[str, int], pravilno: int, st_bitov: int) -> dict:
    """Kateri biti so napačni pri napačnih izidih (utežno s številom ponovitev)."""
    po_bitih = [0] * st_bitov
    hamming, napacnih = 0, 0
    for izid, c in counts.items():
        razlika = int(izid, 2) ^ pravilno
        if not razlika:
            continue
        napacnih += c
        hamming += c * bin(razlika).count("1")
        for i in range(st_bitov):
            if razlika >> i & 1:
                po_bitih[i] += c
    return {"napacnih": napacnih, "povp_napacnih_bitov": hamming / napacnih if napacnih else 0,
            "po_bitih": po_bitih}


def analiziraj(ime: str) -> None:
    osnova = REZULTATI / ime
    meta = json.loads(Path(f"{osnova}_naloga.json").read_text())
    surovi = json.loads(Path(f"{osnova}_counts.json").read_text())
    vezja, kal = prenesi(osnova, meta)
    print(f"{ime}: {meta['backend']}, job {meta['job_id']}, kalibracija {kal['cas_kalibracije']}")

    vrstice = []
    for t, s, qc in zip(meta["naloge"], surovi, vezja, strict=True):
        assert (t["a"], t["b"], t["n"]) == (s["a"], s["b"], s["n"])
        counts = s["counts"]
        shots = sum(counts.values())
        pravilno = t["a"] + t["b"]
        nb = napacni_biti(counts, pravilno, t["n"] + 1)
        vrstice.append({
            "sestevalnik": t["sestevalnik"], "n": t["n"], "a": t["a"], "b": t["b"],
            "p_pravilne": counts.get(format(pravilno, f"0{t['n'] + 1}b"), 0) / shots,
            "dvokubitna_po": st_vrat(qc, 2), "globina_po": qc.depth(),
            **esp(qc, kal["napake"]),
            **mirovanje(qc, kal),
            "povp_napacnih_bitov": nb["povp_napacnih_bitov"],
            "napake_po_bitih": " ".join(f"{x / shots:.3f}" for x in nb["po_bitih"]),
            "fizicni_kubiti": " ".join(map(str, fizicni_kubiti(qc))),
        })
    with Path(f"{osnova}_analiza.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(vrstice[0]))
        w.writeheader()
        w.writerows(vrstice)
    povzetek(vrstice)
    print(f"\nZapisano v {osnova}_analiza.csv")


def povzetek(vrstice: list[dict]) -> None:
    skupine = defaultdict(list)
    for v in vrstice:
        skupine[(v["n"], v["sestevalnik"])].append(v)
    print(f"\n{'n':>2} {'seštevalnik':11} {'izmerjeno':>9} {'ESP':>6} {'ESP 2q':>7} "
          f"{'ESP 1q':>7} {'ESP mer.':>8} {'2q':>4} {'napačnih bitov':>15}  napake po bitih (0 = najnižji)")
    for (n, ime), vs in sorted(skupine.items()):
        po_bitih = [mean(float(v["napake_po_bitih"].split()[i]) for v in vs) for i in range(n + 1)]
        print(f"{n:>2} {ime:11} {mean(v['p_pravilne'] for v in vs):>9.3f} "
              f"{mean(v['esp'] for v in vs):>6.3f} {mean(v['esp_2q'] for v in vs):>7.3f} "
              f"{mean(v['esp_1q'] for v in vs):>7.3f} {mean(v['esp_meritve'] for v in vs):>8.3f} "
              f"{vs[0]['dvokubitna_po']:>4} {mean(v['povp_napacnih_bitov'] for v in vs):>15.2f}  "
              + " ".join(f"{x:.2f}" for x in po_bitih))

    print(f"\n{'n':>2} {'seštevalnik':11} {'izmerjeno':>9} {'trajanje µs':>11} "
          f"{'mirovanje µs':>12} {'ESP×T1':>7} {'ESP×T2':>7}")
    for (n, ime), vs in sorted(skupine.items()):
        print(f"{n:>2} {ime:11} {mean(v['p_pravilne'] for v in vs):>9.3f} "
              f"{mean(v['trajanje_us'] for v in vs):>11.1f} {mean(v['mirovanje_us'] for v in vs):>12.1f} "
              f"{mean(v['esp'] * v['f_mirovanje_t1'] for v in vs):>7.3f} "
              f"{mean(v['esp'] * v['f_mirovanje_t2'] for v in vs):>7.3f}")

    p = [v["p_pravilne"] for v in vrstice]
    print("\nKorelacija z izmerjeno uspešnostjo (Pearson, vsa vezja):")
    print(f"  ESP:                       {correlation(p, [v['esp'] for v in vrstice]):+.3f}")
    print(f"  število dvokubitnih vrat:  {correlation(p, [v['dvokubitna_po'] for v in vrstice]):+.3f}")
    print(f"  globina:                   {correlation(p, [v['globina_po'] for v in vrstice]):+.3f}")
    print(f"  trajanje vezja:            {correlation(p, [v['trajanje_us'] for v in vrstice]):+.3f}")
    print(f"  ESP × mirovanje (T1):      {correlation(p, [v['esp'] * v['f_mirovanje_t1'] for v in vrstice]):+.3f}")
    print(f"  ESP × mirovanje (T2):      {correlation(p, [v['esp'] * v['f_mirovanje_t2'] for v in vrstice]):+.3f}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    analiziraj(sys.argv[1])
