"""Build a compact deploy database with pre-aggregated summary tables.

Creates data/nursing_homes_deploy.db (~50-100MB) from the full 420MB database
by trimming large tables and pre-computing heavy dashboard queries.
"""

import shutil
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
FULL_DB = PROJECT_ROOT / "data" / "nursing_homes.db"
DEPLOY_DB = PROJECT_ROOT / "data" / "nursing_homes_deploy.db"


def build_deploy_db():
    if not FULL_DB.exists():
        print(f"ERROR: Full database not found at {FULL_DB}")
        return

    # Remove old deploy DB if it exists
    if DEPLOY_DB.exists():
        DEPLOY_DB.unlink()

    print(f"Building deploy DB from {FULL_DB} ...")

    # Copy full DB as starting point, then trim
    shutil.copy2(FULL_DB, DEPLOY_DB)

    conn = sqlite3.connect(str(DEPLOY_DB))
    conn.execute("PRAGMA journal_mode=WAL")

    # ── Drop unused tables ──
    drop_tables = [
        "hcris_capital_costs",
        "hcris_revenue_by_payer",
        "oig_exclusions",
        "survey_summary",
        "pipeline_runs",
        "sqlite_sequence",
        "quality_measures",  # Only used in Deep Dive; providers has quality_measure_rating
    ]
    for table in drop_tables:
        try:
            conn.execute(f"DROP TABLE IF EXISTS [{table}]")
            print(f"  Dropped {table}")
        except Exception as e:
            print(f"  Warning dropping {table}: {e}")

    conn.commit()

    # ── Trim health_deficiencies to last 1 year ──
    try:
        conn.execute("""
            DELETE FROM health_deficiencies
            WHERE survey_date < date('now', '-1 year')
        """)
        remaining = conn.execute("SELECT COUNT(*) FROM health_deficiencies").fetchone()[0]
        print(f"  Trimmed health_deficiencies to {remaining:,} rows (last 1 year)")
    except Exception as e:
        print(f"  Warning trimming health_deficiencies: {e}")

    # ── Trim fire_safety_deficiencies to last 1 year ──
    try:
        conn.execute("""
            DELETE FROM fire_safety_deficiencies
            WHERE survey_date < date('now', '-1 year')
        """)
        remaining = conn.execute("SELECT COUNT(*) FROM fire_safety_deficiencies").fetchone()[0]
        print(f"  Trimmed fire_safety_deficiencies to {remaining:,} rows (last 1 year)")
    except Exception as e:
        print(f"  Warning trimming fire_safety_deficiencies: {e}")

    # ── Trim cost_reports to latest fiscal year per facility ──
    try:
        conn.execute("""
            DELETE FROM cost_reports
            WHERE rowid NOT IN (
                SELECT rowid FROM (
                    SELECT rowid, ROW_NUMBER() OVER (
                        PARTITION BY federal_provider_number
                        ORDER BY fiscal_year DESC
                    ) as rn
                    FROM cost_reports
                ) WHERE rn <= 1
            )
        """)
        remaining = conn.execute("SELECT COUNT(*) FROM cost_reports").fetchone()[0]
        print(f"  Trimmed cost_reports to {remaining:,} rows (latest year per facility)")
    except Exception as e:
        print(f"  Warning trimming cost_reports: {e}")

    # ── Trim related_party_transactions to top 3 per facility (by amount) ──
    try:
        conn.execute("""
            DELETE FROM related_party_transactions
            WHERE rowid NOT IN (
                SELECT rowid FROM (
                    SELECT rowid, ROW_NUMBER() OVER (
                        PARTITION BY federal_provider_number
                        ORDER BY amount DESC
                    ) as rn
                    FROM related_party_transactions
                ) WHERE rn <= 3
            )
        """)
        remaining = conn.execute("SELECT COUNT(*) FROM related_party_transactions").fetchone()[0]
        print(f"  Trimmed related_party_transactions to {remaining:,} rows (top 3 per facility)")
    except Exception as e:
        print(f"  Warning trimming related_party_transactions: {e}")

    # ── Trim snf_all_owners: keep only providers that exist in providers table ──
    try:
        conn.execute("""
            DELETE FROM snf_all_owners
            WHERE federal_provider_number NOT IN (
                SELECT federal_provider_number FROM providers
            )
        """)
        remaining = conn.execute("SELECT COUNT(*) FROM snf_all_owners").fetchone()[0]
        print(f"  Trimmed snf_all_owners to {remaining:,} rows (matched providers only)")
    except Exception as e:
        print(f"  Warning trimming snf_all_owners: {e}")

    # ── Trim owner_profiles to top 5000 by facility count ──
    try:
        conn.execute("""
            DELETE FROM owner_profiles
            WHERE rowid NOT IN (
                SELECT rowid FROM owner_profiles ORDER BY facility_count DESC LIMIT 5000
            )
        """)
        remaining = conn.execute("SELECT COUNT(*) FROM owner_profiles").fetchone()[0]
        print(f"  Trimmed owner_profiles to {remaining:,} rows (top 5000)")
    except Exception as e:
        print(f"  Warning trimming owner_profiles: {e}")

    # ── Trim snf_all_owners: keep max 3 owners per facility ──
    try:
        conn.execute("""
            DELETE FROM snf_all_owners
            WHERE rowid NOT IN (
                SELECT rowid FROM (
                    SELECT rowid, ROW_NUMBER() OVER (
                        PARTITION BY federal_provider_number
                        ORDER BY ownership_pct DESC
                    ) as rn
                    FROM snf_all_owners
                ) WHERE rn <= 3
            )
        """)
        remaining = conn.execute("SELECT COUNT(*) FROM snf_all_owners").fetchone()[0]
        print(f"  Trimmed snf_all_owners to {remaining:,} rows (top 3 per facility)")
    except Exception as e:
        print(f"  Warning trimming snf_all_owners: {e}")

    # ── Trim ownership: keep max 3 per facility ──
    try:
        conn.execute("""
            DELETE FROM ownership
            WHERE rowid NOT IN (
                SELECT rowid FROM (
                    SELECT rowid, ROW_NUMBER() OVER (
                        PARTITION BY federal_provider_number
                        ORDER BY owner_percentage DESC
                    ) as rn
                    FROM ownership
                ) WHERE rn <= 3
            )
        """)
        remaining = conn.execute("SELECT COUNT(*) FROM ownership").fetchone()[0]
        print(f"  Trimmed ownership to {remaining:,} rows (top 3 per facility)")
    except Exception as e:
        print(f"  Warning trimming ownership: {e}")

    conn.commit()

    # ── Create pre-aggregated summary tables ──
    print("\nBuilding summary tables...")

    # 1. Dashboard KPI stats
    try:
        conn.execute("DROP TABLE IF EXISTS dashboard_kpi_stats")
        conn.execute("""
            CREATE TABLE dashboard_kpi_stats AS
            SELECT
                COUNT(*) as total_facilities,
                AVG(overall_rating) as avg_overall_rating,
                SUM(CASE WHEN owner_classification = 'private_equity' THEN 1 ELSE 0 END) as pe_count,
                SUM(CASE WHEN owner_classification = 'reit' THEN 1 ELSE 0 END) as reit_count
            FROM providers
        """)

        # Add total fines
        conn.execute("""
            CREATE TABLE IF NOT EXISTS _tmp_fines AS
            SELECT SUM(fine_amount) as total_fines FROM penalties
        """)

        # Add total deficiencies
        conn.execute("""
            CREATE TABLE IF NOT EXISTS _tmp_defs AS
            SELECT COUNT(*) as total_deficiencies FROM health_deficiencies
        """)

        # Merge into single KPI table
        conn.execute("DROP TABLE IF EXISTS dashboard_kpi_stats")
        conn.execute("""
            CREATE TABLE dashboard_kpi_stats AS
            SELECT
                p.total_facilities,
                p.avg_overall_rating,
                p.pe_count,
                p.reit_count,
                COALESCE(f.total_fines, 0) as total_fines,
                COALESCE(d.total_deficiencies, 0) as total_deficiencies
            FROM (
                SELECT
                    COUNT(*) as total_facilities,
                    AVG(overall_rating) as avg_overall_rating,
                    SUM(CASE WHEN owner_classification = 'private_equity' THEN 1 ELSE 0 END) as pe_count,
                    SUM(CASE WHEN owner_classification = 'reit' THEN 1 ELSE 0 END) as reit_count
                FROM providers
            ) p,
            (SELECT SUM(fine_amount) as total_fines FROM penalties) f,
            (SELECT COUNT(*) as total_deficiencies FROM health_deficiencies) d
        """)
        conn.execute("DROP TABLE IF EXISTS _tmp_fines")
        conn.execute("DROP TABLE IF EXISTS _tmp_defs")
        print("  Created dashboard_kpi_stats")
    except Exception as e:
        print(f"  Warning creating dashboard_kpi_stats: {e}")

    # 2. Deficiency severity summary
    try:
        conn.execute("DROP TABLE IF EXISTS deficiency_severity_summary")
        conn.execute("""
            CREATE TABLE deficiency_severity_summary AS
            SELECT
                d.provider_state,
                d.scope_severity_code,
                COUNT(*) as count
            FROM health_deficiencies d
            WHERE d.scope_severity_code IS NOT NULL
            GROUP BY d.provider_state, d.scope_severity_code
        """)
        print("  Created deficiency_severity_summary")
    except Exception as e:
        print(f"  Warning: {e}")

    # 3. Deficiency tag summary
    try:
        conn.execute("DROP TABLE IF EXISTS deficiency_tag_summary")
        conn.execute("""
            CREATE TABLE deficiency_tag_summary AS
            SELECT
                d.deficiency_tag_number as tag,
                d.deficiency_description as description,
                d.provider_state,
                COUNT(*) as count
            FROM health_deficiencies d
            WHERE d.deficiency_tag_number IS NOT NULL
            GROUP BY d.deficiency_tag_number, d.deficiency_description, d.provider_state
        """)
        print("  Created deficiency_tag_summary")
    except Exception as e:
        print(f"  Warning: {e}")

    # 4. Cost report by ownership type (latest year per facility)
    try:
        conn.execute("DROP TABLE IF EXISTS cost_report_by_ownership")
        conn.execute("""
            CREATE TABLE cost_report_by_ownership AS
            SELECT p.owner_classification,
                   COUNT(*) as facilities,
                   AVG(cr.total_revenue) as avg_revenue,
                   AVG(cr.total_expenses) as avg_expenses,
                   AVG(cr.net_income) as avg_net_income,
                   AVG(cr.cost_per_patient_day) as avg_cost_per_day,
                   AVG(CASE WHEN cr.total_revenue > 100000
                       THEN 100.0 * (cr.total_revenue - cr.total_expenses) / cr.total_revenue
                       ELSE NULL END) as avg_margin
            FROM cost_reports cr
            INNER JOIN (
                SELECT federal_provider_number, MAX(fiscal_year) as max_fy
                FROM cost_reports GROUP BY federal_provider_number
            ) latest ON cr.federal_provider_number = latest.federal_provider_number
                   AND cr.fiscal_year = latest.max_fy
            JOIN providers p ON cr.federal_provider_number = p.federal_provider_number
            WHERE p.owner_classification IS NOT NULL AND cr.total_revenue > 100000
            GROUP BY p.owner_classification
        """)
        print("  Created cost_report_by_ownership")
    except Exception as e:
        print(f"  Warning: {e}")

    # 6. Ownership quality summary
    try:
        conn.execute("DROP TABLE IF EXISTS ownership_quality_summary")
        conn.execute("""
            CREATE TABLE ownership_quality_summary AS
            SELECT owner_classification,
                   COUNT(*) as facilities,
                   AVG(overall_rating) as avg_rating,
                   AVG(quality_score) as avg_quality_score,
                   AVG(health_inspection_rating) as avg_health,
                   AVG(staffing_rating) as avg_staffing,
                   AVG(quality_measure_rating) as avg_quality,
                   AVG(reported_total_nurse_staffing_hours) as avg_total_hours,
                   AVG(reported_rn_staffing_hours) as avg_rn_hours,
                   AVG(reported_nurse_aide_staffing_hours) as avg_cna_hours,
                   AVG(reported_lpn_staffing_hours) as avg_lpn_hours,
                   AVG(total_nursing_staff_turnover) as avg_turnover,
                   AVG(rn_turnover) as avg_rn_turnover
            FROM providers
            WHERE owner_classification IS NOT NULL
            GROUP BY owner_classification
        """)
        print("  Created ownership_quality_summary")
    except Exception as e:
        print(f"  Warning: {e}")

    # 7. State summary
    try:
        conn.execute("DROP TABLE IF EXISTS state_summary")
        conn.execute("""
            CREATE TABLE state_summary AS
            SELECT provider_state,
                   COUNT(*) as facility_count,
                   AVG(overall_rating) as avg_rating,
                   SUM(CASE WHEN owner_classification = 'private_equity' THEN 1 ELSE 0 END) as pe_count,
                   COUNT(*) as total_count
            FROM providers
            WHERE provider_state IS NOT NULL
            GROUP BY provider_state
        """)
        print("  Created state_summary")
    except Exception as e:
        print(f"  Warning: {e}")

    # 8. Penalty summary by state
    try:
        conn.execute("DROP TABLE IF EXISTS penalty_state_summary")
        conn.execute("""
            CREATE TABLE penalty_state_summary AS
            SELECT p.provider_state as state,
                   SUM(pen.fine_amount) as total_fines,
                   COUNT(*) as penalty_count
            FROM penalties pen
            JOIN providers p ON pen.federal_provider_number = p.federal_provider_number
            GROUP BY p.provider_state
        """)
        print("  Created penalty_state_summary")
    except Exception as e:
        print(f"  Warning: {e}")

    conn.commit()

    # ── Recreate indexes ──
    print("\nRecreating indexes...")
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_hd_fpn ON health_deficiencies(federal_provider_number)",
        "CREATE INDEX IF NOT EXISTS idx_hd_state ON health_deficiencies(provider_state)",
        "CREATE INDEX IF NOT EXISTS idx_hd_severity ON health_deficiencies(scope_severity_code)",
        "CREATE INDEX IF NOT EXISTS idx_hd_survey ON health_deficiencies(survey_date)",
        "CREATE INDEX IF NOT EXISTS idx_pen_fpn ON penalties(federal_provider_number)",
        "CREATE INDEX IF NOT EXISTS idx_own_fpn ON ownership(federal_provider_number)",
        "CREATE INDEX IF NOT EXISTS idx_own_name ON ownership(normalized_owner_name)",
        "CREATE INDEX IF NOT EXISTS idx_prov_state ON providers(provider_state)",
        "CREATE INDEX IF NOT EXISTS idx_prov_class ON providers(owner_classification)",
        "CREATE INDEX IF NOT EXISTS idx_cr_fpn ON cost_reports(federal_provider_number)",
        "CREATE INDEX IF NOT EXISTS idx_cr_fy ON cost_reports(fiscal_year)",
        "CREATE INDEX IF NOT EXISTS idx_rpt_fpn ON related_party_transactions(federal_provider_number)",
        "CREATE INDEX IF NOT EXISTS idx_fsd_fpn ON fire_safety_deficiencies(federal_provider_number)",
        "CREATE INDEX IF NOT EXISTS idx_qm_fpn ON quality_measures(federal_provider_number)",
        "CREATE INDEX IF NOT EXISTS idx_snf_fpn ON snf_all_owners(federal_provider_number)",
        "CREATE INDEX IF NOT EXISTS idx_oc_fpn ON ownership_changes(federal_provider_number)",
        "CREATE INDEX IF NOT EXISTS idx_cahcai_fpn ON ca_hcai_financials(federal_provider_number)",
    ]
    for idx_sql in indexes:
        try:
            conn.execute(idx_sql)
        except Exception:
            pass

    conn.commit()

    # ── VACUUM ──
    print("Running VACUUM...")
    conn.execute("VACUUM")
    conn.close()

    size_mb = DEPLOY_DB.stat().st_size / (1024 * 1024)
    print(f"\nDeploy DB created: {DEPLOY_DB}")
    print(f"Size: {size_mb:.1f} MB")

    # Show table counts
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
