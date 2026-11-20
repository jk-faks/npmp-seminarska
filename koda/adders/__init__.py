"""Kvantna seštevalnika. Vsak modul izvozi build_adder(n) po dogovoru v README.

ADDERS zbere vse seštevalnike na enem mestu, da lahko skupna koda in testi gredo
čez vse z eno zanko: for ime, build in ADDERS.items(): ...
"""

from . import cdkm, draper

ADDERS = {
    "cdkm": cdkm.build_adder,
    "draper": draper.build_adder,
}
