import wrds
import pandas as pd

db = wrds.Connection(wrds_username="pbathuri")

print("\n==============================")
print("1. CRSP TREASURY DAILY SAMPLE")
print("==============================")
treasury_daily = db.raw_sql("""
    SELECT
        caldt,
        kytreasno,
        kycrspid,
        tdnomprc,
        tdyld,
        tdduratn,
        tdidxratio,
        tdretnua
    FROM crsp.tfz_dly
    ORDER BY caldt DESC
    LIMIT 20
""")
print(treasury_daily)
print("COLUMNS:", list(treasury_daily.columns))

print("\n==============================")
print("2. CRSP TREASURY MONTHLY SAMPLE")
print("==============================")
treasury_monthly = db.raw_sql("""
    SELECT
        mcaldt,
        kytreasno,
        kycrspid,
        tmnomprc,
        tmyld,
        tmduratn,
        tmidxratio,
        tmretnua,
        tmretnxs
    FROM crsp.tfz_mth
    ORDER BY mcaldt DESC
    LIMIT 20
""")
print(treasury_monthly)
print("COLUMNS:", list(treasury_monthly.columns))

print("\n==============================")
print("3. SECURITY MASTER SAMPLE (COMMON STOCKS)")
print("==============================")
security_master = db.raw_sql("""
    SELECT
        permno,
        permco,
        ticker,
        comnam,
        shrcd,
        exchcd,
        siccd,
        ncusip,
        namedt,
        nameenddt
    FROM crsp.stocknames
    WHERE shrcd IN (10, 11)
      AND exchcd IN (1, 2, 3)
    ORDER BY permno
    LIMIT 30
""")
print(security_master)
print("COLUMNS:", list(security_master.columns))

print("\n==============================")
print("4. DAILY STOCK FILE SAMPLE (RECENT)")
print("==============================")
daily_stock_sample = db.raw_sql("""
    SELECT
        permno,
        permco,
        date,
        prc,
        ret,
        retx,
        vol,
        shrout,
        cfacpr,
        cfacshr
    FROM crsp.dsf
    WHERE date >= '2024-01-01'
    ORDER BY date DESC, permno
    LIMIT 30
""")
print(daily_stock_sample)
print("COLUMNS:", list(daily_stock_sample.columns))

print("\n==============================")
print("5. EVENT CODE DISTRIBUTION")
print("==============================")
event_counts = db.raw_sql("""
    SELECT
        event,
        COUNT(*) AS event_count
    FROM crsp.dse
    GROUP BY event
    ORDER BY event_count DESC
    LIMIT 30
""")
print(event_counts)

print("\n==============================")
print("6. STOCK EVENTS SAMPLE")
print("==============================")
event_sample = db.raw_sql("""
    SELECT
        permno,
        date,
        event,
        ticker,
        comnam,
        dlstcd,
        distcd,
        divamt,
        facpr,
        facshr,
        dlret,
        dlretx
    FROM crsp.dse
    ORDER BY date DESC
    LIMIT 30
""")
print(event_sample)
print("COLUMNS:", list(event_sample.columns))

print("\n==============================")
print("7. TAQ-CRSP LINK TABLE DESCRIBE + SAMPLE")
print("==============================")

for library_name, table_name in [
    ("wrdsapps_link_crsp_taq", "tclink"),
    ("wrdsapps_link_crsp_taqm", "taqmclink"),
    ("wrdsapps_link_crsp_taqm", "taqmclink_cusip_2010"),
]:
    print(f"\n--- DESCRIBE {library_name}.{table_name} ---")
    try:
        description = db.describe_table(library=library_name, table=table_name)
        print(description.head(30))
    except Exception as error_message:
        print("DESCRIBE FAILED:", error_message)

    print(f"\n--- SAMPLE {library_name}.{table_name} ---")
    try:
        sample = db.raw_sql(f"SELECT * FROM {library_name}.{table_name} LIMIT 20")
        print(sample)
        print("COLUMNS:", list(sample.columns))
    except Exception as error_message:
        print("SAMPLE FAILED:", error_message)

print("\n==============================")
print("8. COMMON-STOCK UNIVERSE SIZE CHECK")
print("==============================")
universe_size = db.raw_sql("""
    SELECT COUNT(DISTINCT permno) AS distinct_permnos
    FROM crsp.stocknames
    WHERE shrcd IN (10, 11)
      AND exchcd IN (1, 2, 3)
""")
print(universe_size)

print("\n==============================")
print("9. RECENT DAILY COVERAGE CHECK")
print("==============================")
coverage_check = db.raw_sql("""
    SELECT
        MIN(date) AS min_date,
        MAX(date) AS max_date,
        COUNT(*) AS row_count
    FROM crsp.dsf
    WHERE date >= '2018-01-01'
""")
print(coverage_check)

db.close()
