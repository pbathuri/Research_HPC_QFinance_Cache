import wrds
import pandas as pd
from pprint import pprint

db = wrds.Connection(wrds_username="pbathuri")

print("\n==============================")
print("1. LIBRARY DISCOVERY")
print("==============================")
libraries = sorted(db.list_libraries())
candidate_libraries = [
    library_name for library_name in libraries
    if any(keyword in library_name.lower() for keyword in [
        "crsp", "taq", "link", "ff", "fama", "factors", "frb", "fed", "djones"
    ])
]
pprint(candidate_libraries)

print("\n==============================")
print("2. TABLE DISCOVERY BY LIBRARY")
print("==============================")
library_table_map = {}

for library_name in candidate_libraries:
    try:
        table_names = sorted(db.list_tables(library=library_name))
        filtered_table_names = [
            table_name for table_name in table_names
            if any(keyword in table_name.lower() for keyword in [
                "treas", "infl", "stock", "secur", "name", "event",
                "delist", "dist", "link", "taq", "daily", "index"
            ])
        ]
        library_table_map[library_name] = filtered_table_names[:200]
        print(f"\n--- {library_name} ---")
        pprint(filtered_table_names[:200])
    except Exception as error_message:
        print(f"\n--- {library_name} ---")
        print(f"ERROR: {error_message}")

print("\n==============================")
print("3. DESCRIBE MOST LIKELY TABLES")
print("==============================")

likely_targets = [
    ("crsp", "stocknames"),
    ("crsp", "dsf"),
    ("crsp", "dse"),
    ("crsp", "msf"),
    ("crsp", "mse"),
    ("crsp", "treasuries"),
    ("crsp", "tfz_dly"),
    ("crsp", "tfz_mth"),
    ("taq", "ctm_2019"),   # placeholder; may fail
    ("taq", "cq_2019"),    # placeholder; may fail
]

for library_name, table_name in likely_targets:
    try:
        print(f"\n--- DESCRIBE {library_name}.{table_name} ---")
        description_frame = db.describe_table(library=library_name, table=table_name)
        print(description_frame.head(20))
    except Exception as error_message:
        print(f"\n--- DESCRIBE {library_name}.{table_name} FAILED ---")
        print(error_message)

print("\n==============================")
print("4. FIRST VERIFIED PULLS")
print("==============================")

queries = {
    "crsp_stock_security_sample": """
        SELECT *
        FROM crsp.stocknames
        LIMIT 10
    """,
    "crsp_daily_stock_file_sample": """
        SELECT *
        FROM crsp.dsf
        LIMIT 10
    """,
    "crsp_stock_events_sample": """
        SELECT *
        FROM crsp.dse
        LIMIT 10
    """,
    "crsp_monthly_stock_file_sample": """
        SELECT *
        FROM crsp.msf
        LIMIT 10
    """,
    "crsp_monthly_stock_events_sample": """
        SELECT *
        FROM crsp.mse
        LIMIT 10
    """
}

for query_name, query_text in queries.items():
    print(f"\n--- QUERY: {query_name} ---")
    try:
        result_frame = db.raw_sql(query_text)
        print(result_frame.head(10))
        print("ROWS RETURNED:", len(result_frame))
        print("COLUMNS:", list(result_frame.columns))
    except Exception as error_message:
        print(f"FAILED: {error_message}")

print("\n==============================")
print("5. DATE RANGE CHECKS")
print("==============================")

date_range_queries = {
    "crsp_dsf_range": """
        SELECT MIN(date) AS min_date, MAX(date) AS max_date, COUNT(*) AS row_count
        FROM crsp.dsf
    """,
    "crsp_stocknames_range": """
        SELECT MIN(namedt) AS min_namedt, MAX(nameenddt) AS max_nameenddt, COUNT(*) AS row_count
        FROM crsp.stocknames
    """,
    "crsp_dse_range": """
        SELECT MIN(date) AS min_date, MAX(date) AS max_date, COUNT(*) AS row_count
        FROM crsp.dse
    """
}

for query_name, query_text in date_range_queries.items():
    print(f"\n--- RANGE: {query_name} ---")
    try:
        result_frame = db.raw_sql(query_text)
        print(result_frame)
    except Exception as error_message:
        print(f"FAILED: {error_message}")

print("\n==============================")
print("6. SEARCH FOR TREASURY / INFLATION TABLE CANDIDATES")
print("==============================")

crsp_tables = library_table_map.get("crsp", [])
treasury_candidates = [
    table_name for table_name in crsp_tables
    if any(keyword in table_name.lower() for keyword in ["treas", "tfz", "infl"])
]
pprint(treasury_candidates)

for table_name in treasury_candidates[:10]:
    try:
        print(f"\n--- DESCRIBE crsp.{table_name} ---")
        description_frame = db.describe_table(library="crsp", table=table_name)
        print(description_frame.head(20))
    except Exception as error_message:
        print(f"FAILED: {error_message}")

print("\n==============================")
print("7. SEARCH FOR TAQ-CRSP LINK CANDIDATES")
print("==============================")

for library_name, table_names in library_table_map.items():
    matching_table_names = [
        table_name for table_name in table_names
        if "link" in table_name.lower() or ("taq" in table_name.lower() and "crsp" in table_name.lower())
    ]
    if matching_table_names:
        print(f"\n--- LINK CANDIDATES IN {library_name} ---")
        pprint(matching_table_names[:50])

print("\n==============================")
print("8. OPTIONAL DOW JONES SANITY CHECK")
print("==============================")

try:
    dji_frame = db.raw_sql("""
        SELECT date, dji
        FROM djones.djdaily
        ORDER BY date DESC
        LIMIT 10
    """)
    print(dji_frame)
except Exception as error_message:
    print(f"FAILED: {error_message}")

db.close()
