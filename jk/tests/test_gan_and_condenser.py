"""Tests for GAN data generator and feature condenser."""

import unittest
import numpy as np
from pathlib import Path
import tempfile


class TestFinancialGAN(unittest.TestCase):
    def test_available(self):
        from qhpc_cache.gan_data_generator import FinancialGAN
        gan = FinancialGAN()
        self.assertTrue(gan.available())

    def test_train_and_generate(self):
        from qhpc_cache.gan_data_generator import FinancialGAN, GANConfig
        cfg = GANConfig(epochs=2, seq_len=10, hidden_dim=16, batch_size=8)
        gan = FinancialGAN(cfg)

        rng = np.random.default_rng(0)
        data = rng.normal(100, 10, (200, 5)).astype(np.float32)
        result = gan.train(data, verbose=False)
        self.assertEqual(result.epochs_completed, 2)
        self.assertGreater(result.wall_clock_seconds, 0)

        generated = gan.generate(5)
        self.assertEqual(generated.ndim, 2)
        self.assertEqual(generated.shape[1], 5)

    def test_generate_dataframe(self):
        from qhpc_cache.gan_data_generator import FinancialGAN, GANConfig
        cfg = GANConfig(epochs=1, seq_len=5, hidden_dim=8, batch_size=4)
        gan = FinancialGAN(cfg)
        data = np.random.default_rng(0).normal(100, 10, (100, 5)).astype(np.float32)
        gan.train(data)
        df = gan.generate_dataframe(num_days=10, num_assets=3)
        self.assertEqual(len(df), 30)
        self.assertIn("close", df.columns)

    def test_save_csv(self):
        from qhpc_cache.gan_data_generator import FinancialGAN, GANConfig
        cfg = GANConfig(epochs=1, seq_len=5, hidden_dim=8, batch_size=4)
        gan = FinancialGAN(cfg)
        data = np.random.default_rng(0).normal(100, 10, (50, 5)).astype(np.float32)
        gan.train(data)
        df = gan.generate_dataframe(num_days=5, num_assets=2)
        with tempfile.TemporaryDirectory() as td:
            p = gan.save_generated_dataset(df, Path(td) / "out.csv")
            self.assertTrue(p.exists())


class TestFeatureCondenser(unittest.TestCase):
    def test_fit_transform(self):
        from qhpc_cache.feature_condenser import FeatureCondenser
        rng = np.random.default_rng(42)
        X = rng.normal(0, 1, (50, 5))
        fc = FeatureCondenser(n_components=3)
        fc.fit(X, feature_names=["S0", "K", "r", "sigma", "T"])
        reduced = fc.transform(X[0])
        self.assertEqual(len(reduced), 3)

    def test_condensed_key(self):
        from qhpc_cache.feature_condenser import FeatureCondenser
        rng = np.random.default_rng(42)
        X = rng.normal(0, 1, (50, 5))
        fc = FeatureCondenser(n_components=2)
        fc.fit(X)
        key1 = fc.condensed_cache_key(X[0])
        key2 = fc.condensed_cache_key(X[0])
        self.assertEqual(key1, key2)
        self.assertEqual(len(key1), 16)

    def test_collision_tracking(self):
        from qhpc_cache.feature_condenser import FeatureCondenser
        fc = FeatureCondenser(n_components=2)
        rng = np.random.default_rng(0)
        X = rng.normal(0, 1, (20, 3))
        fc.fit(X)
        for i in range(10):
            ckey = fc.condensed_cache_key(X[i])
            fc.track_key(f"orig_{i}", ckey)
        self.assertEqual(fc.total_keys, 10)

    def test_variance_explained(self):
        from qhpc_cache.feature_condenser import FeatureCondenser
        rng = np.random.default_rng(42)
        X = rng.normal(0, 1, (100, 5))
        fc = FeatureCondenser(n_components=5)
        fc.fit(X)
        self.assertAlmostEqual(fc.variance_explained_ratio(), 1.0, delta=0.01)

    def test_record_snapshot(self):
        from qhpc_cache.feature_condenser import FeatureCondenser
        fc = FeatureCondenser(n_components=2)
        X = np.random.default_rng(0).normal(0, 1, (30, 4))
        fc.fit(X, feature_names=["a", "b", "c", "d"])
        snap = fc.record_snapshot("test_phase")
        self.assertEqual(snap.phase, "test_phase")
        self.assertEqual(snap.original_dims, 4)
        self.assertEqual(snap.reduced_dims, 2)


if __name__ == "__main__":
    unittest.main()
