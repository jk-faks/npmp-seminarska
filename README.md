# Seminarska naloga NPMP 2026/27, skupina 08

**Primerjava kvantnih seštevalnikov CDKM in Draper (QFT) na šumnem kvantnem procesorju IBM**

Jurij Anžič, Janez Koprivec. Predmet: Nekonvencionalne platforme in metode procesiranja.

## Vsebina

- `predlog/` — prijava teme (LaTeX in PDF)
- `koda/adders/cdkm.py` — seštevalnik CDKM (Jurij)
- `koda/adders/draper.py` — Draperjev seštevalnik (Janez)
- `koda/adders/__init__.py` — `ADDERS`: seznam vseh seštevalnikov
- `koda/common.py` — skupni del: vhodi, priprava vezij, prevajanje, metrike
- `koda/run.py` — poganjanje poskusov (glej spodaj)
- `tests/` — testi (pytest)
- `results/` — izmerjeni rezultati

## Namestitev

Potreben je [uv](https://docs.astral.sh/uv/). Ta sam namesti Python 3.12 in točne različice paketov iz `uv.lock`:

```sh
uv sync
uv run pytest
```

Žeton za IBM Quantum shrani samo lokalno (`QiskitRuntimeService.save_account(...)`), nikoli v repozitorij.

## Poganjanje poskusov

Iz korena repozitorija:

```sh
uv run python -m koda.run metrike   # kubiti, globina, dvokubitna vrata (FakeTorino), ~2 s
uv run python -m koda.run ideal     # idealni simulator, nekaj sekund
uv run python -m koda.run sum       # šumni simulator z modelom FakeTorino, ~8 minut
```

Vsak zagon odda vsa vezja obeh seštevalnikov (n = 1 do 5, isti pari vhodov, skupaj 136
vezij) v enem poslu. V `results/` zapiše `<ime>_naloga.json` (kaj je bilo oddano),
`<ime>_counts.json` (surovi izidi) in `<ime>.csv` (verjetnost pravilne vsote za vsako vezje).
Ponovni zagon datoteke prepiše.

Zagon na procesorju IBM še ni dodan.

## Ponovljivost rezultatov

Rezultati v `results/` so ponovljivi bit za bitom, če so izpolnjeni trije pogoji:

1. **Iste različice paketov.** `uv sync` namesti točno tiste iz `uv.lock` (Python 3.12,
   qiskit 2.6.2, qiskit-aer 0.18.4, qiskit-ibm-runtime 0.52.1). Šumni model in topologija
   FakeTorino sta posnetek, ki je del paketa qiskit-ibm-runtime, zato sta s tem določena tudi ona.
2. **Iste nastavitve v `koda/common.py`.** `SEED = 2026` določa naključne pare vhodov,
   prevajanje (`seed_transpiler`) in šumni simulator (`seed_simulator`). Poleg tega
   `OPTIMIZATION_LEVEL = 3`, `SHOTS = 1000` in `STEVILO_NAKLJUCNIH = 16`.
3. **Isti ukazi**, zgoraj, iz korena repozitorija.

Postopek:

```sh
uv sync
uv run pytest                       # 39 passed
uv run python -m koda.run metrike
uv run python -m koda.run ideal
uv run python -m koda.run sum
git diff --stat results/            # prazno = enaki rezultati
```

Pričakovan povzetek (povprečna verjetnost pravilne vsote):

| n | ideal CDKM | ideal Draper | šum CDKM | šum Draper | naključno |
|---|---|---|---|---|---|
| 1 | 1,000 | 1,000 | 0,933 | 0,952 | 0,250 |
| 2 | 1,000 | 1,000 | 0,856 | 0,882 | 0,125 |
| 3 | 1,000 | 1,000 | 0,774 | 0,715 | 0,062 |
| 4 | 1,000 | 1,000 | 0,712 | 0,554 | 0,031 |
| 5 | 1,000 | 1,000 | 0,630 | 0,463 | 0,016 |

Število dvokubitnih vrat po prevajanju za FakeTorino (`results/metrike_fake_torino.csv`):

| n | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| CDKM | 22 | 43 | 70 | 94 | 130 |
| Draper | 10 | 29 | 72 | 139 | 181 |

## Dogovor o vmesniku seštevalnika

Vsak seštevalnik je modul v `koda/adders/` s funkcijo:

```python
def build_adder(n: int) -> QuantumCircuit
```

- Vrne **samo seštevalnik**: brez priprave vhodov in brez meritev. Število vrat, globino in
  kubite merimo na tem vezju, zato vhodi ne vplivajo na metrike.
- Registri (`QuantumRegister`) z natanko temi imeni:
  - `a`: n kubitov, prvi sumand; po seštevanju ostane nespremenjen,
  - `b`: n+1 kubitov; na začetku drugi sumand (zgornji kubit je 0), na koncu vsota a + b
    (zgornji kubit je izhodni prenos),
  - po potrebi `anc`: pomožni kubiti, ki se začnejo in končajo v stanju 0 (CDKM: vhodni prenos).
- Vrstni red bitov je Qiskitov (little-endian): kubit 0 registra je najmanj pomemben bit.
- Skupna koda doda vrata X za vhodna števila in izmeri register `b` v klasični register `sum`.
