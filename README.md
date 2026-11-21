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
uv run python -m koda.run metrike   # kubiti, globina, dvokubitna vrata (FakeTorino), ~15 s
uv run python -m koda.run ideal     # idealni simulator, nekaj sekund
uv run python -m koda.run sum       # šumni simulator z modelom FakeTorino, ~8 minut
uv run python -m koda.run metrike --lazni fake_fez   # isto za drug lažni procesor
uv run python -m koda.run sum --lazni fake_fez       # (fake_fez, fake_kingston, fake_marrakesh)
```

Metrike vsebujejo vrata, kot so v vezju (`dvokubitna_pred`, `trokubitna_pred`), in število CX po
razgradnji na CX in enokubitna vrata (`cx_razgrajeno`, `globina_razgrajeno`). Le slednje je
primerljivo med seštevalnikoma: Toffolijeva vrata stanejo 6 CX, kontrolirana fazna 2 CX.
Prevajanje na ravni 3 je naključno, zato je poleg `dvokubitna_po` (seme `SEED`) zapisan še razpon
čez `SEED` in semena 0–4 (`dvokubitna_po_min`, `dvokubitna_po_max`).

Vsak zagon odda vsa vezja obeh seštevalnikov (n = 1 do 5, isti pari vhodov, skupaj 136
vezij) v enem poslu. V `results/` zapiše `<ime>_naloga.json` (kaj je bilo oddano),
`<ime>_counts.json` (surovi izidi) in `<ime>.csv` (verjetnost pravilne vsote za vsako vezje).
Ponovni zagon datoteke prepiše.

## Zagon na procesorju IBM

Ključ API za IBM Quantum (Open Plan) zapiši v datoteko `.env` v korenu repozitorija kot
`IBM_API_KEY=...`. Datoteka je v `.gitignore` in ne sme v repozitorij.

Čas na procesorju je omejen (600 s na 28 dni), zato ima način `ibm` varovalke:

```sh
uv run python -m koda.run ibm --backend ibm_fez --pilot            # samo izpiše, kaj bi oddal
uv run python -m koda.run ibm --backend ibm_fez --pilot --potrdi   # poskusni posel: n = 1, 8 vezij
uv run python -m koda.run ibm --backend ibm_fez --potrdi           # vsa vezja (136)
uv run python -m koda.run prevzemi <job_id>                        # rezultati oddanega posla
```

- Brez `--potrdi` se nič ne odda.
- Celoten posel se odda samo, če obstaja izmerjena poraba poskusnega posla na istem procesorju.
  Iz nje se oceni poraba celotnega posla; če presega `--najvec-sekund` (privzeto 120 s) ali
  preostanek proračuna, se posel ne odda.
- Job ID in čas oddaje se zapišeta v `results/ibm_<procesor>_naloga.json` takoj ob oddaji, poraba
  pa, ko je posel končan. Če zagon prekineš, rezultate prevzameš z ukazom `prevzemi`.
- Brez blaženja napak (dinamično razklapljanje in twirling sta izklopljena), da so rezultati
  primerljivi s simulatorji.

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
uv run pytest                       # 40 passed
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

Šumni simulator z modelom FakeFez (Heron r2, isti tip kot procesorji, ki so na voljo v Open Plan;
`results/sum_fake_fez.csv`), povprečna verjetnost pravilne vsote:

| n | CDKM | Draper | naključno |
|---|---|---|---|
| 1 | 0,947 | 0,967 | 0,250 |
| 2 | 0,891 | 0,913 | 0,125 |
| 3 | 0,804 | 0,799 | 0,062 |
| 4 | 0,765 | 0,664 | 0,031 |
| 5 | 0,687 | 0,544 | 0,016 |

## Poskusi na procesorjih IBM

Vsi posli: 1000 ponovitev na vezje, isti pari vhodov kot na simulatorjih, raven prevajanja 3,
seme 2026, brez twirlinga. Datoteke so v `results/<ime>_*`.

| ime v results/ | procesor | n | DD | job ID | oddano (UTC) | poraba |
|---|---|---|---|---|---|---|
| `ibm_pilot_ibm_fez` | ibm_fez | 1 | ne | `dc0r00ls2omc7389ndn0` | 2026-11-21 14:51 | 4 s |
| `ibm_ibm_fez` | ibm_fez | 1–5 | ne | `dc0rbg5hdvas73bjutd0` | 2026-11-21 15:16 | 39 s |
| `ibm_dd_ibm_fez` | ibm_fez | 1–5 | da | `dc0rgfmq4uuc73a32e8g` | 2026-11-21 15:26 | 39 s |
| `ibm_ponovitev_ibm_fez` | ibm_fez | 1–5 | ne | `dc0rh8ls2omc7389oddg` | 2026-11-21 15:28 | 39 s |
| `ibm_pilot_ibm_kingston` | ibm_kingston | 1 | ne | `dc0rifmq4uuc73a32hp0` | 2026-11-21 15:31 | 4 s |
| `ibm_n8_ibm_kingston` | ibm_kingston | 1–8 | ne | `dc0riplhdvas73bjvamg` | 2026-11-21 15:31 | 66 s |
| `ibm_dd_n8_ibm_kingston` | ibm_kingston | 1–8 | da | `dc0rjn2nj2vs73defojg` | 2026-11-21 15:33 | 66 s |

DD = dinamično razklapljanje (zaporedje XpXm). Skupna poraba 257 s od 600 s.

Povprečna verjetnost pravilne vsote (CDKM / Draper):

| n | fez brez DD | fez ponovitev | fez z DD | kingston brez DD | kingston z DD | 2q po prevajanju |
|---|---|---|---|---|---|---|
| 1 | 0,894 / 0,937 | 0,896 / 0,935 | 0,892 / 0,941 | 0,914 / 0,966 | 0,919 / 0,966 | 22 / 10 |
| 2 | 0,581 / 0,847 | 0,613 / 0,842 | 0,732 / 0,831 | 0,844 / 0,823 | 0,830 / 0,756 | 46 / 29 |
| 3 | 0,584 / 0,629 | 0,607 / 0,603 | 0,629 / 0,612 | 0,713 / 0,776 | 0,706 / 0,744 | 70 / 70 |
| 4 | 0,426 / 0,452 | 0,408 / 0,445 | 0,504 / 0,458 | 0,026 / 0,667 | 0,609 / 0,571 | 94 / 139 |
| 5 | 0,266 / 0,272 | 0,248 / 0,268 | 0,337 / 0,244 | 0,418 / 0,440 | 0,463 / 0,409 | 124 / 195 |
| 6 | | | | 0,287 / 0,269 | 0,344 / 0,214 | 154 / 286 |
| 7 | | | | 0,118 / 0,260 | 0,250 / 0,165 | 177 / 386 |
| 8 | | | | 0,056 / 0,171 | 0,212 / 0,080 | 198 / 478 |

(Število dvokubitnih vrat je za ibm_fez; na ibm_kingston je enako.)

### Analiza

```sh
uv run python -m koda.analiza ibm_ibm_fez   # za katerikoli posel; prvič prenese vezja in kalibracijo
uv run python -m koda.grafi                 # grafi v porocilo/img/
```

`koda/analiza.py` iz IBM prenese natanko oddana vezja (s fizičnimi kubiti) in kalibracijo v času
posla ter ju shrani (`<ime>_vezja.qpy.gz`, `<ime>_kalibracija.json`). Za vsako vezje izračuna oceno
uspešnosti iz napak vrat in meritev (ESP), trajanje in čas mirovanja kubitov ter kateri biti so
napačni. Rezultat je `<ime>_analiza.csv`.

Korelacija ESP z izmerjeno uspešnostjo (vsa vezja posla): fez brez DD +0,86 in +0,87 (ponovitev),
fez z DD +0,97, kingston brez DD +0,68, kingston z DD +0,95.

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
