"""Sanity checks for shared defaults (demo and pricing)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from qhpc_cache.config import (
    get_default_config,
    get_demo_run_defaults,
)


class TestConfig(unittest.TestCase):
    def test_pricing_config_positive_spot(self):
        cfg = get_default_config()
        self.assertGreater(cfg.S0, 0.0)
        self.assertGreaterEqual(cfg.T, 0.0)

    def test_demo_defaults_sensible_path_counts(self):
        demo = get_demo_run_defaults()
        self.assertGreaterEqual(demo.european_call_paths, 1)
        self.assertGreaterEqual(demo.antithetic_paths, 1)
        self.assertGreater(demo.asian_time_steps, 0)


if __name__ == "__main__":
    unittest.main()
