"""Preveri, da je okolje pravilno nameščeno."""

from qiskit_aer import AerSimulator
from qiskit_ibm_runtime.fake_provider import FakeTorino


def test_lazni_procesor_in_sumni_simulator():
    backend = FakeTorino()
    assert backend.num_qubits > 12
    AerSimulator.from_backend(backend)
