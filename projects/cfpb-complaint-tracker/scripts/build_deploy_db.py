"""Build a compact deploy database for Railway deployment.

Creates data/cfpb_tracker_deploy.db (~30-50MB) from the full 11.8GB database by:
- Skipping raw cfpb_complaints entirely (13.7M rows = 10GB+)
- Keeping ALL enrichment tables in full (financials, enforcement, HMDA, risk profiles)
- Pre-aggregating complaint data into summary tables for dashboard use
- Including institution-level complaint counts for cross-reference

Target: < 100MB deploy DB.
"""

import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
FULL_DB = PROJECT_ROOT / "data" / "cfpb_tracker.db"
DEPLOY_DB = PROJECT_ROOT / "data" / "cfpb_tracker_deploy.db"


def build_deploy_db():
    if not FULL_DB.exists():
        print(f"ERROR: Full database not found at {FULL_DB}")
        sys.exit(1)

    if DEPLOY_DB.exists():
        DEPLOY_DB.unlink()
        print("Removed old deploy DB")

    print(f"Building deploy DB from {FULL_DB} ...")
    print("Strategy: enrichment tables + pre-aggregated complaint summaries\n")

    deploy = sqlite3.connect(str(DEPLOY_DB))
    deploy.execute("PRAGMA journal_mode=WAL")
    deploy.execute(f"ATTACH DATABASE '{FULL_DB}' AS full_db")

    # ── 1. Copy all small tables in full ──
    small_tables = [
        ("financial_institutions", "Base institution data"),
        ("institution_financials", "FDIC Call Report financials"),
        ("regulatory_enforcement", "Multi-agency enforcement actions"),
        ("institution_risk_profiles", "Composite risk scores"),
        ("hmda_institution_summary", "HMDA mortgage lending"),
        ("enforcement_actions", "Legacy CFPB enforcement"),
        ("cra_ratings", "CRA ratings"),
        ("pipeline_runs", "Pipeline tracking"),
    ]

    for table, desc in small_tables:
        print(f"Copying {table} ({desc}) ...")
        try:
            deploy.execute(f"CREATE TABLE [{table}] AS SELECT * FROM full_db.[{table}]")
            count = deploy.execute(f"SELECT COUNT(*) FROM [{table}]").fetchone()[0]
            print(f"  {count:,} rows")
        except Exception as e:
            # Table might not exist — create empty
            print(f"  Warning: {e}")

    deploy.commit()

    # ── 2. Create pre-aggregated complaint summary tables ──
    print("\nBuilding pre-aggregated complaint summaries from full DB ...")

    # 2a. KPI totals (single row with all-time stats)
    deploy.execute("""
        CREATE TABLE kpi_totals AS
        SELECT
            (SELECT COUNT(*) FROM full_db.cfpb_complaints) AS total_complaints,
            (SELECT COUNT(*) FROM full_db.institution_complaints) AS total_cross_links,
            (SELECT AVG(match_confidence) FROM full_db.institution_complaints) AS avg_match_confidence,
            (SELECT COUNT(DISTINCT company) FROM full_db.cfpb_complaints) AS total_companies,
            (SELECT MIN(date_received) FROM full_db.cfpb_complaints) AS earliest_complaint,
            (SELECT MAX(date_received) FROM full_db.cfpb_complaints) AS latest_complaint,
            (SELECT SUM(penalty_amount) FROM full_db.enforcement_actions WHERE penalty_amount > 0) AS total_penalties
    """)
    print("  kpi_totals: 1 row")

    # 2b. Monthly complaint counts by product (for trends charts)
    deploy.execute("""
        CREATE TABLE complaint_monthly AS
        SELECT
            strftime('%Y-%m', date_received) AS month,
            product,
            COUNT(*) AS cnt
        FROM full_db.cfpb_complaints
        WHERE date_received IS NOT NULL
        GROUP BY strftime('%Y-%m', date_received), product
    """)
    count = deploy.execute("SELECT COUNT(*) FROM complaint_monthly").fetchone()[0]
    print(f"  complaint_monthly: {count:,} rows")

    # 2c. Complaint counts by state
    deploy.execute("""
        CREATE TABLE complaint_by_state AS
        SELECT
            state,
            COUNT(*) AS cnt,
            COUNT(DISTINCT company) AS companies
        FROM full_db.cfpb_complaints
        WHERE state IS NOT NULL AND state != ''
        GROUP BY state
    """)
    count = deploy.execute("SELECT COUNT(*) FROM complaint_by_state").fetchone()[0]
    print(f"  complaint_by_state: {count:,} rows")

    # 2d. Complaint counts by product/sub-product
    deploy.execute("""
        CREATE TABLE complaint_by_product AS
        SELECT
            product,
            sub_product,
            COUNT(*) AS cnt
        FROM full_db.cfpb_complaints
        GROUP BY product, sub_product
    """)
    count = deploy.execute("SELECT COUNT(*) FROM complaint_by_product").fetchone()[0]
    print(f"  complaint_by_product: {count:,} rows")

    # 2e. Complaint counts by issue
    deploy.execute("""
        CREATE TABLE complaint_by_issue AS
        SELECT
            product,
            issue,
            COUNT(*) AS cnt
        FROM full_db.cfpb_complaints
        WHERE issue IS NOT NULL
        GROUP BY product, issue
        HAVING COUNT(*) >= 5
    """)
    count = deploy.execute("SELECT COUNT(*) FROM complaint_by_issue").fetchone()[0]
    print(f"  complaint_by_issue: {count:,} rows")

    # 2f. Top companies by complaint count
    deploy.execute("""
        CREATE TABLE complaint_by_company AS
        SELECT
            company,
            COUNT(*) AS cnt,
            SUM(CASE WHEN timely_response = 'Yes' THEN 1 ELSE 0 END) AS timely_count,
            SUM(CASE WHEN consumer_disputed = 'Yes' THEN 1 ELSE 0 END) AS disputed_count
        FROM full_db.cfpb_complaints
        WHERE company IS NOT NULL
        GROUP BY company
        HAVING COUNT(*) >= 10
        ORDER BY cnt DESC
    """)
    count = deploy.execute("SELECT COUNT(*) FROM complaint_by_company").fetchone()[0]
    print(f"  complaint_by_company: {count:,} rows")

    # 2g. Company response breakdown
    deploy.execute("""
        CREATE TABLE complaint_by_response AS
        SELECT
            company_response,
            COUNT(*) AS cnt
        FROM full_db.cfpb_complaints
        WHERE company_response IS NOT NULL
        GROUP BY company_response
    """)
    count = deploy.execute("SELECT COUNT(*) FROM complaint_by_response").fetchone()[0]
    print(f"  complaint_by_response: {count:,} rows")

    # 2h. Submission channel breakdown
    deploy.execute("""
        CREATE TABLE complaint_by_channel AS
        SELECT
            submitted_via,
            COUNT(*) AS cnt
        FROM full_db.cfpb_complaints
        WHERE submitted_via IS NOT NULL
        GROUP BY submitted_via
    """)
    count = deploy.execute("SELECT COUNT(*) FROM complaint_by_channel").fetchone()[0]
    print(f"  complaint_by_channel: {count:,} rows")

    # 2i. Timeliness breakdown
    deploy.execute("""
        CREATE TABLE complaint_by_timeliness AS
        SELECT
            timely_response,
            COUNT(*) AS cnt
        FROM full_db.cfpb_complaints
        GROUP BY timely_response
    """)
    count = deploy.execute("SELECT COUNT(*) FROM complaint_by_timeliness").fetchone()[0]
    print(f"  complaint_by_timeliness: {count:,} rows")

    # 2j. Institution complaint counts (for institution explorer and cross-ref)
    deploy.execute("""
        CREATE TABLE institution_complaint_counts AS
        SELECT
            ic.cert_number,
            COUNT(*) AS complaint_count,
            AVG(ic.match_confidence) AS avg_confidence,
            COUNT(DISTINCT c.product) AS product_count
        FROM full_db.institution_complaints ic
        JOIN full_db.cfpb_complaints c ON ic.complaint_id = c.complaint_id
        GROUP BY ic.cert_number
    """)
    count = deploy.execute("SELECT COUNT(*) FROM institution_complaint_counts").fetchone()[0]
    print(f"  institution_complaint_counts: {count:,} rows")

    # 2k. Monthly total (for volume-over-time chart without product breakdown)
    deploy.execute("""
        CREATE TABLE complaint_monthly_total AS
        SELECT
            strftime('%Y-%m', date_received) AS month,
            COUNT(*) AS cnt
        FROM full_db.cfpb_complaints
        WHERE date_received IS NOT NULL
        GROUP BY strftime('%Y-%m', date_received)
    """)
    count = deploy.execute("SELECT COUNT(*) FROM complaint_monthly_total").fetchone()[0]
    print(f"  complaint_monthly_total: {count:,} rows")

    # 2l. State + product cross-tab (for geographic + product filter)
    deploy.execute("""
        CREATE TABLE complaint_state_product AS
        SELECT
            state,
            product,
            COUNT(*) AS cnt
        FROM full_db.cfpb_complaints
        WHERE state IS NOT NULL AND state != ''
        GROUP BY state, product
    """)
    count = deploy.execute("SELECT COUNT(*) FROM complaint_state_product").fetchone()[0]
    print(f"  complaint_state_product: {count:,} rows")

    # 2m. Day-of-week pattern
    deploy.execute("""
        CREATE TABLE complaint_by_weekday AS
        SELECT
            CASE CAST(strftime('%w', date_received) AS INTEGER)
                WHEN 0 THEN 'Sunday'
                WHEN 1 THEN 'Monday'
                WHEN 2 THEN 'Tuesday'
                WHEN 3 THEN 'Wednesday'
                WHEN 4 THEN 'Thursday'
                WHEN 5 THEN 'Friday'
                WHEN 6 THEN 'Saturday'
            END AS weekday,
            CAST(strftime('%w', date_received) AS INTEGER) AS day_num,
            COUNT(*) AS cnt
        FROM full_db.cfpb_complaints
        WHERE date_received IS NOT NULL
        GROUP BY strftime('%w', date_received)
    """)
    count = deploy.execute("SELECT COUNT(*) FROM complaint_by_weekday").fetchone()[0]
    print(f"  complaint_by_weekday: {count:,} rows")

    # 2n. CRA vs complaints cross-tab (for CRA section)
    deploy.execute("""
        CREATE TABLE cra_complaint_summary AS
        SELECT
            cr.cra_rating,
            COUNT(DISTINCT cr.cert_number) AS institution_count,
            COALESCE(SUM(icc.complaint_count), 0) AS total_complaints,
            COALESCE(AVG(icc.complaint_count), 0) AS avg_complaints
        FROM full_db.cra_ratings cr
        LEFT JOIN institution_complaint_counts icc ON cr.cert_number = icc.cert_number
        WHERE cr.cra_rating IS NOT NULL
        GROUP BY cr.cra_rating
    """)
    count = deploy.execute("SELECT COUNT(*) FROM cra_complaint_summary").fetchone()[0]
    print(f"  cra_complaint_summary: {count:,} rows")

    # 2o. Top companies with complaint details for institution explorer
    deploy.execute("""
        CREATE TABLE top_company_details AS
        SELECT
            c.company,
            c.product,
            COUNT(*) AS cnt,
            SUM(CASE WHEN c.timely_response = 'Yes' THEN 1 ELSE 0 END) AS timely,
            SUM(CASE WHEN c.consumer_disputed = 'Yes' THEN 1 ELSE 0 END) AS disputed
        FROM full_db.cfpb_complaints c
        WHERE c.company IN (
            SELECT company FROM full_db.cfpb_complaints
            GROUP BY company HAVING COUNT(*) >= 100
        )
        GROUP BY c.company, c.product
    """)
    count = deploy.execute("SELECT COUNT(*) FROM top_company_details").fetchone()[0]
    print(f"  top_company_details: {count:,} rows")

    deploy.commit()

    # ── 3. Create indexes ──
    print("\nCreating indexes ...")
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_fi_cert ON financial_institutions(cert_number)",
        "CREATE INDEX IF NOT EXISTS idx_fi_name ON financial_institutions(canonical_name)",
        "CREATE INDEX IF NOT EXISTS idx_if_cert ON institution_financials(cert_number)",
        "CREATE INDEX IF NOT EXISTS idx_re_agency ON regulatory_enforcement(agency)",
        "CREATE INDEX IF NOT EXISTS idx_re_cert ON regulatory_enforcement(cert_number)",
        "CREATE INDEX IF NOT EXISTS idx_rp_tier ON institution_risk_profiles(risk_tier)",
        "CREATE INDEX IF NOT EXISTS idx_rp_cert ON institution_risk_profiles(cert_number)",
        "CREATE INDEX IF NOT EXISTS idx_hmda_cert ON hmda_institution_summary(cert_number)",
        "CREATE INDEX IF NOT EXISTS idx_icc_cert ON institution_complaint_counts(cert_number)",
        "CREATE INDEX IF NOT EXISTS idx_cbc_company ON complaint_by_company(company)",
        "CREATE INDEX IF NOT EXISTS idx_cm_month ON complaint_monthly(month)",
    ]
    for idx_sql in indexes:
        try:
            deploy.execute(idx_sql)
        except Exception as e:
            print(f"  Warning: {e}")

    deploy.commit()

    # ── 4. Detach and VACUUM ──
    deploy.execute("DETACH DATABASE full_db")
    print("\nRunning VACUUM ...")
    deploy.execute("VACUUM")
    deploy.close()

    size_mb = DEPLOY_DB.stat().st_size / (1024 * 1024)
    print(f"\n{'='*60}")
    print(f"Deploy DB created: {DEPLOY_DB}")
    print(f"Size: {size_mb:.1f} MB")
    print(f"{'='*60}")

    # Show final table counts
    conn = sqlite3.connect(str(DEPLOY_DB))
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    print("\nTable row counts:")
    for (name,) in tables:
        count = conn.execute(f"SELECT COUNT(*) FROM [{name}]").fetchone()[0]
        print(f"  {name}: {count:,}")
    conn.close()


if __name__ == "__main__":
    build_deploy_db()
