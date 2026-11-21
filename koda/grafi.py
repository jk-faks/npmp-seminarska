"""Grafi za poročilo iz datotek v results/. Zaganjaj iz korena repozitorija:

    uv run python -m koda.grafi

Zapiše PDF-je v porocilo/img/.
"""

import csv
from collections import defaultdict
from pathlib import Path
from statistics import mean

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

REZULTATI = Path("results")
IZHOD = Path("porocilo/img")
BARVE = {"cdkm": "#1f77b4", "draper": "#d62728"}
IMENA = {"cdkm": "CDKM", "draper": "Draper"}


def preberi(ime: str) -> list[dict]:
    pot = REZULTATI / f"{ime}.csv"
    return list(csv.DictReader(pot.open())) if pot.exists() else []


def povprecja(vrstice: list[dict]) -> dict[str, tuple[list[int], list[float]]]:
    skupine = defaultdict(list)
    for v in vrstice:
        skupine[(v["sestevalnik"], int(v["n"]))].append(float(v["p_pravilne"]))
    out = {}
    for ime in IMENA:
        ns = sorted(n for (s, n) in skupine if s == ime)
        out[ime] = (ns, [mean(skupine[(ime, n)]) for n in ns])
    return out


def graf_uspesnost(poskusi: list[tuple[str, str, str]], datoteka: str, naslov: str) -> None:
    """poskusi: (ime datoteke v results/, oznaka v legendi, slog črte)."""
    fig, ax = plt.subplots(figsize=(6, 4))
    vse_n = set()
    for ime, oznaka, slog in poskusi:
        vrstice = preberi(ime)
        if not vrstice:
            continue
        for sest, (ns, ps) in povprecja(vrstice).items():
            vse_n |= set(ns)
            ax.plot(ns, ps, slog, color=BARVE[sest], marker="o", label=f"{IMENA[sest]}, {oznaka}")
    ns = sorted(vse_n)
    ax.plot(ns, [1 / 2 ** (n + 1) for n in ns], ":", color="gray", label="naključni izid")
    ax.set_xlabel("število bitov $n$")
    ax.set_ylabel("verjetnost pravilne vsote")
    ax.set_ylim(0, 1.02)
    ax.set_xticks(ns)
    ax.set_title(naslov)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(IZHOD / datoteka)
    plt.close(fig)


def graf_esp(ime: str, datoteka: str, naslov: str) -> None:
    vrstice = preberi(f"{ime}_analiza")
    if not vrstice:
        return
    fig, ax = plt.subplots(figsize=(4.5, 4.5))
    for sest in IMENA:
        vs = [v for v in vrstice if v["sestevalnik"] == sest]
        ax.scatter([float(v["esp"]) for v in vs], [float(v["p_pravilne"]) for v in vs],
                   s=12, color=BARVE[sest], label=IMENA[sest], alpha=0.7)
    ax.plot([0, 1], [0, 1], "--", color="gray", label="izmerjeno = ESP")
    ax.set_xlabel("ESP iz kalibracije")
    ax.set_ylabel("izmerjena verjetnost pravilne vsote")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_title(naslov)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(IZHOD / datoteka)
    plt.close(fig)


def main() -> None:
    IZHOD.mkdir(parents=True, exist_ok=True)
    graf_uspesnost([("ideal_aer_simulator", "idealno", "-"),
                    ("sum_fake_fez", "šumni simulator FakeFez", "--"),
                    ("ibm_ibm_fez", "ibm_fez", "-")],
                   "uspesnost_fez.pdf", "Simulator in procesor ibm_fez (brez DD)")
    graf_uspesnost([("ibm_ponovitev_ibm_fez", "brez DD", "-"),
                    ("ibm_dd_ibm_fez", "z DD", "--")],
                   "dd_fez.pdf", "Vpliv dinamičnega razklapljanja (ibm_fez)")
    graf_uspesnost([("ibm_n8_ibm_kingston", "brez DD", "-"),
                    ("ibm_dd_n8_ibm_kingston", "z DD", "--")],
                   "kingston_n8.pdf", "ibm_kingston, $n$ = 1 do 8")
    graf_esp("ibm_ponovitev_ibm_fez", "esp_brez_dd.pdf", "ibm_fez, brez DD")
    graf_esp("ibm_dd_ibm_fez", "esp_dd.pdf", "ibm_fez, z DD")
    print("Grafi so v", IZHOD)


if __name__ == "__main__":
    main()
