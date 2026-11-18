# Seminarska naloga NPMP 2026/27, skupina 08

**Primerjava kvantnih seštevalnikov CDKM in Draper (QFT) na šumnem kvantnem procesorju IBM**

Jurij Anžič, Janez Koprivec. Predmet: Nekonvencionalne platforme in metode procesiranja.

## Vsebina

- `predlog/` — prijava teme (LaTeX in PDF)
- `koda/adders/cdkm.py` — seštevalnik CDKM (Jurij)
- `koda/adders/draper.py` — Draperjev seštevalnik (Janez)
- `koda/common.py`, `koda/run.py` — skupni del: vhodi, metrike, poganjanje (sledi)
- `tests/` — testi (pytest)
- `results/` — izmerjeni rezultati

## Namestitev

Potreben je [uv](https://docs.astral.sh/uv/). Ta sam namesti Python 3.12 in točne različice paketov iz `uv.lock`:

```sh
uv sync
uv run pytest
```

Žeton za IBM Quantum shrani samo lokalno (`QiskitRuntimeService.save_account(...)`), nikoli v repozitorij.

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
