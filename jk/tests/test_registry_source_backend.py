"""Registry entry round-trip including source_backend."""

import unittest

from qhpc_cache.data_models import DatasetRegistryEntry


class TestRegistrySourceBackend(unittest.TestCase):
    def test_to_dict_from_dict_source_backend(self):
        entry = DatasetRegistryEntry(
            registry_key="k1",
            provider="test",
            dataset_kind="daily_ohlcv",
            date_range_start="2020-01-01",
            date_range_end="2020-12-31",
            symbol_coverage="SPY",
            schema_label="ohlcv",
            row_count=10,
            local_paths=["/tmp/x.parquet"],
            completion_status="complete",
            estimated_disk_usage_bytes=100,
            realized_disk_usage_bytes=100,
            ingestion_runtime_seconds=1.0,
            checkpoint_label="broad_universe_complete",
            batch_identifier="b0",
            parent_dataset_label="u",
            source_backend="databento_http",
            notes="",
        )
        restored = DatasetRegistryEntry.from_dict(entry.to_dict())
        self.assertEqual(restored.source_backend, "databento_http")


if __name__ == "__main__":
    unittest.main()
