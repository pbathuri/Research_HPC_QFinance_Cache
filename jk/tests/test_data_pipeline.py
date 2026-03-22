"""Tests for data ingestion layer (no live network)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools" / "pixel_agents_bridge"))

try:
    import pandas as pd
except ImportError:
    pd = None  # type: ignore

from qhpc_cache.data_models import DailyUniverseRequest, DatasetRegistryEntry, EventWindowRequest
from qhpc_cache.data_registry import initialize_dataset_registry, load_dataset_registry, register_dataset
from qhpc_cache.data_storage import build_storage_path
from qhpc_cache.data_ingestion import (
    validate_event_book,
    validate_universe_alignment,
    write_synthetic_daily_universe,
)
from qhpc_cache.event_book import (
    EventBookEntry,
    EventBookSummary,
    extract_event_windows_from_taq,
    save_event_book_manifest,
    summarize_event_book,
)
from qhpc_cache.data_sources import NyseTaqFileProvider
from qhpc_cache.historical_returns import compute_log_returns
from qhpc_cache.historical_risk import compute_historical_var, compute_event_window_drawdown
from qhpc_cache.workflow_events import WorkflowEvent, workflow_event_now, WorkflowStage

import pixel_mapping


@unittest.skipIf(pd is None, "pandas not installed")
class TestDataRegistry(unittest.TestCase):
    def test_register_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            initialize_dataset_registry(tmp)
            entry = DatasetRegistryEntry(
                registry_key="test::1",
                provider="test",
                dataset_kind="daily_ohlcv",
                date_range_start="2020-01-01",
                date_range_end="2020-12-31",
                symbol_coverage="AAPL",
                schema_label="ohlcv",
                row_count=10,
                local_paths=["/tmp/x.csv"],
                completion_status="complete",
                estimated_disk_usage_bytes=100,
                realized_disk_usage_bytes=100,
                ingestion_runtime_seconds=1.0,
                checkpoint_label="broad_universe_complete",
                batch_identifier="b0",
                parent_dataset_label="u",
            )
            register_dataset(tmp, entry)
            loaded = load_dataset_registry(tmp)
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0].registry_key, "test::1")


class TestStoragePath(unittest.TestCase):
    def test_build_storage_path_deterministic(self):
        path = build_storage_path(
            "/tmp/out",
            provider_name="p",
            dataset_label="d",
            batch_identifier="b1",
            date_start="2020-01-01",
            date_end="2020-02-01",
            extension="csv",
        )
        self.assertIn("p__d__b1__2020-01-01__2020-02-01.csv", str(path))


@unittest.skipIf(pd is None, "pandas not installed")
class TestEventBookHelpers(unittest.TestCase):
    def test_extract_from_sample_taq_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            taq = Path(tmp) / "taq"
            taq.mkdir()
            csv_path = taq / "sample.csv"
            csv_path.write_text(
                "timestamp,symbol,price\n"
                "2020-03-10T15:00:00+00:00,SPY,300.0\n"
                "2020-03-10T16:00:00+00:00,SPY,301.0\n",
                encoding="utf-8",
            )
            out = Path(tmp) / "ev"
            request = EventWindowRequest(
                event_identifier="test_evt",
                event_label="test",
                symbols=["SPY"],
                start_timestamp=datetime(2020, 3, 10, 14, 0, tzinfo=timezone.utc),
                end_timestamp=datetime(2020, 3, 10, 17, 0, tzinfo=timezone.utc),
                data_schema_label="taq",
                provider_name="nyse_taq_files",
                local_input_path=str(taq),
                local_output_directory=str(out),
            )
            summary = extract_event_windows_from_taq(
                [request],
                data_root=tmp,
                time_budget_seconds=60.0,
                disk_budget_bytes=10**9,
                register=False,
            )
            self.assertEqual(summary.completed_events, 1)
            self.assertGreater(summary.total_rows, 0)

    def test_summarize_event_book(self):
        summary = EventBookSummary(
            total_events=1,
            completed_events=0,
            pending_events=1,
            total_rows=0,
            total_disk_bytes=0,
            entries=[],
            deferred_identifiers=["a"],
        )
        blob = summarize_event_book(summary)
        self.assertEqual(blob["pending_events"], 1)


@unittest.skipIf(pd is None, "pandas not installed")
class TestReturnsAndRisk(unittest.TestCase):
    def test_log_returns_length(self):
        frame = pd.DataFrame(
            {
                "date": ["2020-01-01", "2020-01-02", "2020-01-01", "2020-01-02"],
                "symbol": ["A", "A", "B", "B"],
                "close": [100.0, 110.0, 50.0, 55.0],
            }
        )
        result = compute_log_returns(frame)
        self.assertEqual(len(result), 2)

    def test_historical_var_positive_tail(self):
        samples = [-0.05, -0.02, 0.01, 0.02, 0.03]
        var_loss = compute_historical_var(samples, confidence_level=0.8)
        self.assertGreaterEqual(var_loss, 0.0)

    def test_drawdown(self):
        dd = compute_event_window_drawdown([100.0, 110.0, 90.0, 95.0])
        self.assertGreater(dd, 0.0)


class TestWorkflowEventSerialization(unittest.TestCase):
    def test_to_dict_roundtrip(self):
        event = workflow_event_now(
            event_identifier="e1",
            stage=WorkflowStage.BROAD_UNIVERSE,
            event_type="broad_universe_download_started",
            active_module_name="m",
            summary="s",
        )
        data = event.to_dict()
        self.assertEqual(data["event_type"], "broad_universe_download_started")

    def test_pixel_mapping_shape(self):
        event = WorkflowEvent(
            event_identifier="x",
            stage_name="broad_universe",
            event_type="test",
            timestamp_label="t",
            active_module_name="m",
            active_dataset_label="d",
            active_symbol_batch="",
            summary="s",
            details="",
            status_label="ok",
        )
        row = pixel_mapping.workflow_event_to_pixel_row(event)
        self.assertEqual(row["type"], "assistant")
        self.assertIn("_qhpc_data_phase", row)


@unittest.skipIf(pd is None, "pandas not installed")
class TestValidateEventBookManifest(unittest.TestCase):
    def test_validate_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "m.json"
            path.write_text(
                json.dumps({"summary": {}, "entries": []}),
                encoding="utf-8",
            )
            ok, reason = validate_event_book(path)
            self.assertTrue(ok)
            self.assertEqual(reason, "ok")


@unittest.skipIf(pd is None, "pandas not installed")
class TestSyntheticUniverse(unittest.TestCase):
    def test_write_synthetic(self):
        with tempfile.TemporaryDirectory() as tmp:
            req = DailyUniverseRequest(
                universe_name="u_test",
                symbols=["A", "B"],
                start_date=date(2020, 1, 1),
                end_date=date(2020, 1, 10),
                adjusted_prices_required=True,
                include_reference_data=False,
                provider_name="synthetic",
                local_output_directory=str(Path(tmp) / "daily"),
            )
            result = write_synthetic_daily_universe(req, tmp)
            self.assertEqual(result["status"], "synthetic_fallback")
            entries = load_dataset_registry(tmp)
            self.assertTrue(any(entry.provider == "synthetic_demo" for entry in entries))


class TestNyseTaqProvider(unittest.TestCase):
    def test_discover_empty_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            provider = NyseTaqFileProvider()
            found = provider.discover_available_taq_files(tmp)
            self.assertEqual(found, [])


@unittest.skipIf(pd is None, "pandas not installed")
class TestUniverseAlignment(unittest.TestCase):
    def test_alignment_ok_for_synthetic_parent(self):
        entries = [
            DatasetRegistryEntry(
                registry_key="k",
                provider="synthetic_demo",
                dataset_kind="daily_ohlcv",
                date_range_start="2020-01-01",
                date_range_end="2020-01-02",
                symbol_coverage="A",
                schema_label="s",
                row_count=1,
                local_paths=["x"],
                completion_status="complete",
                estimated_disk_usage_bytes=1,
                realized_disk_usage_bytes=1,
                ingestion_runtime_seconds=0.0,
                checkpoint_label="c",
                batch_identifier="b",
                parent_dataset_label="u_test",
            )
        ]
        ok, issues = validate_universe_alignment(entries, expected_universe_name="u_test")
        self.assertTrue(ok)
        self.assertEqual(issues, [])


if __name__ == "__main__":
    unittest.main()
