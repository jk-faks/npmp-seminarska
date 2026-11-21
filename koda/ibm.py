"""Povezava s IBM Quantum in varovalke za porabo časa na procesorju.

Ključ API prebere iz okolja (IBM_API_KEY) ali iz datoteke .env v korenu repozitorija.
Datoteka .env je v .gitignore; ključa nikoli ne izpisujemo.
"""

import os
from pathlib import Path

from qiskit_ibm_runtime import QiskitRuntimeService

KANAL = "ibm_quantum_platform"


def _preberi_env(pot: Path = Path(".env")) -> None:
    """Vrstice KLJUC=vrednost iz .env doda v okolje (že nastavljenih ne prepiše)."""
    if not pot.exists():
        return
    for vrstica in pot.read_text().splitlines():
        vrstica = vrstica.strip()
        if not vrstica or vrstica.startswith("#") or "=" not in vrstica:
            continue
        kljuc, vrednost = vrstica.split("=", 1)
        os.environ.setdefault(kljuc.strip(), vrednost.strip().strip("'\""))


def storitev() -> QiskitRuntimeService:
    _preberi_env()
    kljuc = os.environ.get("IBM_API_KEY")
    if not kljuc:
        raise SystemExit("Manjka IBM_API_KEY (v okolju ali v datoteki .env).")
    return QiskitRuntimeService(channel=KANAL, token=kljuc, instance="auto")


def preostanek_sekund(service: QiskitRuntimeService) -> float:
    """Preostali čas na procesorju v trenutnem obdobju (Open Plan: 600 s na 28 dni)."""
    return float(service.usage()["usage_remaining_seconds"])
