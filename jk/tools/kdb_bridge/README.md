# kdb-taq bridge (optional)

Python code in ``qhpc_cache.taq_kdb_adapter`` drives **your** local ``kdb-taq`` checkout. Nothing here vendors that repository.

## Contract

1. Set ``QHPC_KDB_TAQ_REPO`` to the root of ``kdb-taq`` (defaults try ``~/desktop/kdb-taq`` and ``~/Desktop/kdb-taq``).
2. Either:
   - set ``QHPC_KDB_EXTRACTION_COMMAND`` to a shell snippet with ``{spec_file}`` and ``{repo}``, **or**
   - add ``scripts/qhpc_export_window.q`` (or another name from ``_pick_extraction_script``) that:
     - reads the JSON spec (path passed as argv or ``QHPC_SPEC_FILE``),
     - loads NYSE TAQ from **your** kdb tables,
     - writes CSV to ``output_csv`` in the spec.

Spec JSON fields: ``event_identifier``, ``start_timestamp``, ``end_timestamp``, ``symbols``, ``output_csv``, ``repo_root``.

## q binary

Override with ``QHPC_KDB_Q_BINARY`` if ``q`` is not on ``PATH``.

## Outputs

CSV is ingested by pandas and saved under ``QHPC_DATA_ROOT/event_book/`` with registry metadata — same as flat-file TAQ fallback.
