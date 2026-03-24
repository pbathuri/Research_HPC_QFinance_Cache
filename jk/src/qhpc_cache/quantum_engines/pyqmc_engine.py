"""PyQMC Variational Monte Carlo engine for real quantum-chemistry workloads.

This engine is **not** a financial pricer.  It runs a genuine VMC calculation
on a small molecule (H2) via PySCF + PyQMC to exercise cache infrastructure
under a computationally expensive QMC workload.  The VMC total energy is mapped
to a pseudo-"price" via ``price = abs(energy) * scale_factor`` -- clearly
labeled as a research analogy.
"""

from __future__ import annotations

import math
from typing import Optional

from qhpc_cache.quantum_engines.base_engine import SimulationEngine, SimulationResult


_DEFAULT_SCALE = 10.0


class PyQMCEngine(SimulationEngine):
    """Wraps PyQMC's VMC with a Slater-Jastrow wavefunction on H2."""

    def __init__(self, nsteps: int = 200, scale_factor: float = _DEFAULT_SCALE) -> None:
        self._nsteps = nsteps
        self._scale_factor = scale_factor

    @property
    def name(self) -> str:
        return "PyQMC-VMC"

    @property
    def engine_type(self) -> str:
        return "pyqmc_vmc"

    @classmethod
    def available(cls) -> bool:
        try:
            import pyqmc.api  # noqa: F401
            import pyscf  # noqa: F401
            return True
        except ImportError:
            return False

    # ------------------------------------------------------------------

    def price(
        self,
        S0: float,
        K: float,
        r: float,
        sigma: float,
        T: float,
        num_paths: int,
        seed: Optional[int] = None,
    ) -> SimulationResult:
        """Run VMC on H2 and map the energy to a pseudo-price.

        The financial parameters (S0, K, ...) are stored in the cache key and
        metadata for bookkeeping but do **not** influence the QMC physics.
        ``num_paths`` is used as a proxy for total VMC steps if it exceeds the
        constructor default.
        """
        t0 = self._start_timer()
        try:
            import numpy as np
            import pyscf.gto
            import pyscf.scf
            import pyqmc.api as api

            total_steps = max(self._nsteps, num_paths // 50)
            nblocks = max(1, total_steps // 10)
            nsteps_per_block = max(1, total_steps // nblocks)

            mol = pyscf.gto.M(
                atom="H 0 0 0; H 0 0 1.4",
                basis="sto-3g",
                unit="bohr",
            )
            mf = pyscf.scf.RHF(mol)
            mf.verbose = 0
            mf.kernel()

            wf, _to_opt = api.generate_wf(mol, mf)
            configs = api.initial_guess(mol, nconfig=100)

            if seed is not None:
                np.random.seed(seed)

            data, _configs = api.vmc(
                wf,
                configs,
                nblocks=nblocks,
                nsteps_per_block=nsteps_per_block,
                accumulators={"energy": api.EnergyAccumulator(mol)},
                verbose=False,
            )

            energies = np.array(data["energytotal"])
            mean_energy = float(np.mean(energies))
            std_energy = float(np.std(energies, ddof=1) / math.sqrt(len(energies)))
            acceptance = float(np.mean(data["acceptance"]))

            pseudo_price = abs(mean_energy) * self._scale_factor
            pseudo_error = std_energy * self._scale_factor

            wall_ms = self._elapsed_ms(t0)
            return self._make_result(
                price=pseudo_price,
                std_error=pseudo_error,
                paths_used=nblocks * nsteps_per_block,
                wall_clock_ms=wall_ms,
                S0=S0, K=K, r=r, sigma=sigma, T=T, num_paths=num_paths,
                metadata={
                    "note": "RESEARCH ANALOGY -- not a financial price",
                    "molecule": "H2",
                    "basis": "sto-3g",
                    "vmc_energy": mean_energy,
                    "vmc_energy_error": std_energy,
                    "acceptance_ratio": acceptance,
                    "nblocks": nblocks,
                    "nsteps_per_block": nsteps_per_block,
                    "nconfig": 100,
                    "scale_factor": self._scale_factor,
                },
            )
        except Exception as exc:
            return self._error_result(
                str(exc), S0, K, r, sigma, T, num_paths, self._elapsed_ms(t0)
            )


if __name__ == "__main__":
    engine = PyQMCEngine(nsteps=50, scale_factor=10.0)
    print(f"PyQMC available: {engine.available()}")

    result = engine.price(
        S0=100.0, K=105.0, r=0.05, sigma=0.2, T=1.0,
        num_paths=100, seed=7,
    )
    print(f"Pseudo-price: {result.price:.4f}  (std_error={result.std_error:.4f})")
    print(f"Wall time   : {result.wall_clock_ms:.1f} ms")
    print(f"Metadata    : {result.metadata}")
    print("pyqmc_engine self-test passed.")
