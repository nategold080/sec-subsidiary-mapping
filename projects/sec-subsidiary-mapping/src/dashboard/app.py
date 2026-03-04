"""Streamlit dashboard for SEC Subsidiary Mapping.

Dark theme with 11 interactive sections including enrichment tabs.
Run with: streamlit run src/dashboard/app.py
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

PROJECT_ROOT = Path(__file__).parent.parent.parent
DB_PATH = PROJECT_ROOT / "data" / "sec_subsidiaries.db"

# Page config
st.set_page_config(
    page_title="SEC Corporate Subsidiary Mapping",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _table_exists(conn, name):
    """Check if a table exists in the database."""
    try:
        r = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
        return r is not None
    except Exception:
        return False


def _safe_query(sql, conn, params=()):
    """Run a SQL query and return a DataFrame, returning empty on error."""
    try:
        return pd.read_sql_query(sql, conn, params=params if params else None)
    except Exception:
        return pd.DataFrame()


def _safe_fetchone(conn, sql, params=(), default=0):
    """Execute SQL and return first column of first row, or default on error."""
    try:
        row = conn.execute(sql, params).fetchone()
        return row[0] if row else default
    except Exception:
        return default


@st.cache_resource
def get_db():
    """Get database connection. Creates empty DB file if it doesn't exist."""
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except Exception:
        pass
    return conn


def _has_column(conn, table, column):
    """Check if a column exists in a table."""
    try:
        conn.execute(f"SELECT {column} FROM {table} LIMIT 1")
        return True
    except Exception:
        return False


def main():
    st.title("SEC Corporate Subsidiary & Ownership Mapping")
    st.caption("Structured database of corporate subsidiary relationships from SEC EDGAR Exhibit 21 filings")

    conn = get_db()

    # Check if core tables exist and have data
    stats = _get_stats(conn)

    # Sidebar navigation
    pages = [
        "Overview",
        "Subsidiary Explorer",
        "Company Deep Dive",
        "Jurisdiction Analysis",
        "Tax Haven Dashboard",
        "Financial Profiles",
        "Tax Haven Financial Analysis",
        "Institutional Ownership",
        "Year-over-Year Changes",
        "Industry Comparison",
        "Data Quality",
    ]

    page = st.sidebar.selectbox("Navigate", pages)

    page_map = {
        "Overview": lambda: _page_overview(conn, stats),
        "Subsidiary Explorer": lambda: _page_explorer(conn),
        "Company Deep Dive": lambda: _page_company_deep_dive(conn),
        "Jurisdiction Analysis": lambda: _page_jurisdiction_analysis(conn),
        "Tax Haven Dashboard": lambda: _page_tax_havens(conn),
        "Financial Profiles": lambda: _page_financial_profiles(conn),
        "Tax Haven Financial Analysis": lambda: _page_tax_haven_financials(conn),
        "Institutional Ownership": lambda: _page_institutional_ownership(conn),
        "Year-over-Year Changes": lambda: _page_yoy_changes(conn),
        "Industry Comparison": lambda: _page_industry_comparison(conn),
        "Data Quality": lambda: _page_data_quality(conn, stats),
    }

    page_map[page]()

    # Footer
    st.markdown("---")
    st.markdown(
        "**Built by Nathan Goldberg** | "
        "nathanmauricegoldberg@gmail.com | "
        "[LinkedIn](https://www.linkedin.com/in/nathanmauricegoldberg/)"
    )


def _get_stats(conn) -> dict:
    """Get summary statistics, returning zeros for any missing tables."""
    stats = {}
    stats["parent_count"] = _safe_fetchone(conn, "SELECT COUNT(*) FROM parents")
    stats["filing_count"] = _safe_fetchone(conn, "SELECT COUNT(*) FROM filings")
    stats["subsidiary_count"] = _safe_fetchone(conn, "SELECT COUNT(*) FROM subsidiaries")
    stats["link_count"] = _safe_fetchone(conn, "SELECT COUNT(*) FROM ownership_links")
    stats["tax_haven_count"] = _safe_fetchone(
        conn, "SELECT COUNT(*) FROM subsidiaries WHERE is_tax_haven = 1"
    )
    stats["jurisdiction_count"] = _safe_fetchone(
        conn, "SELECT COUNT(DISTINCT jurisdiction_code) FROM subsidiaries WHERE jurisdiction_code != ''"
    )
    avg_q = _safe_fetchone(
        conn, "SELECT AVG(quality_score) FROM ownership_links WHERE quality_score IS NOT NULL", default=None
    )
    stats["avg_quality"] = round(avg_q, 3) if avg_q else 0

    # Financial stats
    stats["financial_count"] = _safe_fetchone(conn, "SELECT COUNT(*) FROM financials")
    stats["companies_with_financials"] = _safe_fetchone(
        conn, "SELECT COUNT(DISTINCT cik) FROM financials WHERE revenue IS NOT NULL OR total_assets IS NOT NULL"
    )
    stats["total_revenue"] = _safe_fetchone(
        conn, "SELECT SUM(revenue) FROM financials f WHERE fiscal_year = (SELECT MAX(fiscal_year) FROM financials f2 WHERE f2.cik = f.cik)"
    ) or 0

    # Institutional stats
    stats["institutional_holders"] = _safe_fetchone(
        conn, "SELECT COUNT(DISTINCT holder_cik) FROM institutional_holders"
    )

    return stats


def _fmt_currency(val):
    """Format currency value for display."""
    if val is None or val == 0:
        return "N/A"
    if abs(val) >= 1e12:
        return f"${val/1e12:.1f}T"
    if abs(val) >= 1e9:
        return f"${val/1e9:.1f}B"
    if abs(val) >= 1e6:
        return f"${val/1e6:.0f}M"
    return f"${val:,.0f}"


def _page_overview(conn, stats):
    """Overview with KPI cards and summary charts."""
    st.header("Corporate Universe Overview")

    if not _table_exists(conn, "parents") or not _table_exists(conn, "subsidiaries"):
        st.warning("No data loaded. Run the pipeline first: `python -m src.cli pipeline`")
        return

    # KPI cards row 1
    cols = st.columns(4)
    cols[0].metric("Parent Companies", f"{stats['parent_count']:,}")
    cols[1].metric("Unique Subsidiaries", f"{stats['subsidiary_count']:,}")
    cols[2].metric("Tax Haven Entities", f"{stats['tax_haven_count']:,}")
    cols[3].metric("Jurisdictions", f"{stats['jurisdiction_count']:,}")

    # KPI cards row 2
    cols2 = st.columns(4)
    cols2[0].metric("Ownership Links", f"{stats['link_count']:,}")
    cols2[1].metric("Filings Parsed", f"{stats['filing_count']:,}")
    cols2[2].metric("With Financials", f"{stats['companies_with_financials']:,}")
    haven_pct = stats["tax_haven_count"] / max(stats["subsidiary_count"], 1) * 100
    cols2[3].metric("Tax Haven %", f"{haven_pct:.1f}%")

    # KPI cards row 3 — financial overview
    if stats["total_revenue"] > 0:
        cols3 = st.columns(4)
        cols3[0].metric("Total Revenue Tracked", _fmt_currency(stats["total_revenue"]))
        cols3[1].metric("Financial Records", f"{stats['financial_count']:,}")
        cols3[2].metric("Institutional Holders", f"{stats['institutional_holders']:,}")
        avg_subs = stats["subsidiary_count"] / max(stats["parent_count"], 1)
        cols3[3].metric("Avg Subs/Company", f"{avg_subs:.1f}")

    # Top jurisdictions chart
    st.subheader("Top 15 Jurisdictions")
    df = _safe_query("""
        SELECT jurisdiction_name, jurisdiction_code, COUNT(*) as count,
               SUM(CASE WHEN is_tax_haven = 1 THEN 1 ELSE 0 END) as tax_haven_count
        FROM subsidiaries
        WHERE jurisdiction_code != ''
        GROUP BY jurisdiction_code
        ORDER BY count DESC
        LIMIT 15
    """, conn)

    if not df.empty:
        fig = px.bar(
            df, x="jurisdiction_name", y="count",
            color="tax_haven_count",
            color_continuous_scale=["#0984E3", "#E74C3C"],
            title="Subsidiary Count by Jurisdiction",
        )
        fig.update_layout(
            template="plotly_dark",
            plot_bgcolor="#0E1117",
            paper_bgcolor="#0E1117",
        )
        st.plotly_chart(fig, use_container_width=True)

    # Top companies
    st.subheader("Top 20 Companies by Subsidiary Count")
    df = _safe_query("""
        SELECT p.company_name, p.ticker, COUNT(DISTINCT ol.subsidiary_id) as sub_count,
               SUM(CASE WHEN s.is_tax_haven = 1 THEN 1 ELSE 0 END) as haven_count
        FROM ownership_links ol
        JOIN parents p ON p.cik = ol.parent_cik
        JOIN subsidiaries s ON s.id = ol.subsidiary_id
        GROUP BY ol.parent_cik
        ORDER BY sub_count DESC
        LIMIT 20
    """, conn)

    if not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)


def _page_explorer(conn):
    """Search and filter subsidiaries."""
    st.header("Subsidiary Explorer")

    if not _table_exists(conn, "ownership_links") or not _table_exists(conn, "subsidiaries"):
        st.warning("No data loaded. Run the pipeline first: `python -m src.cli pipeline`")
        return

    col1, col2 = st.columns(2)
    search = col1.text_input("Search subsidiary name", "")
    jurisdiction = col2.selectbox(
        "Filter by jurisdiction",
        ["All"] + _get_jurisdictions(conn),
    )

    col3, col4 = st.columns(2)
    tax_haven_only = col3.checkbox("Tax haven entities only")
    limit = col4.number_input("Max results", value=100, min_value=10, max_value=1000)

    where_clauses = []
    params = []

    if search:
        where_clauses.append("s.name LIKE ?")
        params.append(f"%{search}%")
    if jurisdiction != "All":
        where_clauses.append("s.jurisdiction_code = ?")
        params.append(jurisdiction)
    if tax_haven_only:
        where_clauses.append("s.is_tax_haven = 1")

    where = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    df = _safe_query(f"""
        SELECT p.company_name AS parent, p.ticker,
               s.name AS subsidiary, s.jurisdiction_name AS jurisdiction,
               s.jurisdiction_code, s.is_tax_haven,
               ol.ownership_pct, ol.filing_date, ol.quality_score
        FROM ownership_links ol
        JOIN parents p ON p.cik = ol.parent_cik
        JOIN subsidiaries s ON s.id = ol.subsidiary_id
        {where}
        ORDER BY p.company_name, s.name
        LIMIT ?
    """, conn, params=params + [limit])

    st.write(f"Showing {len(df):,} results")
    st.dataframe(df, use_container_width=True, hide_index=True)


def _page_company_deep_dive(conn):
    """Individual company deep dive with financial context."""
    st.header("Company Deep Dive")

    if not _table_exists(conn, "parents"):
        st.warning("No data loaded. Run the pipeline first: `python -m src.cli pipeline`")
        return

    companies = _safe_query("""
        SELECT p.cik, p.company_name || CASE WHEN p.ticker != '' THEN ' (' || p.ticker || ')' ELSE '' END as label,
               COUNT(DISTINCT ol.subsidiary_id) as sub_count
        FROM parents p
        LEFT JOIN ownership_links ol ON ol.parent_cik = p.cik
        GROUP BY p.cik
        ORDER BY sub_count DESC
    """, conn)

    if companies.empty:
        st.info("No companies in database.")
        return

    selected = st.selectbox("Select company", companies["label"].tolist())
    if not selected:
        return

    idx = companies[companies["label"] == selected].index[0]
    cik = companies.loc[idx, "cik"]

    # Company info
    info = conn.execute("SELECT * FROM parents WHERE cik = ?", (cik,)).fetchone()
    if info:
        cols = st.columns(4)
        cols[0].metric("CIK", info["cik"])
        cols[1].metric("Ticker", info["ticker"] or "N/A")
        cols[2].metric("SIC", info["sic_code"] or "N/A")
        cols[3].metric("Subsidiaries", companies.loc[idx, "sub_count"])

    # Financial info
    fin = None
    if _table_exists(conn, "financials"):
        try:
            fin = conn.execute("""
                SELECT fiscal_year, revenue, total_assets, net_income, employees
                FROM financials WHERE cik = ? ORDER BY fiscal_year DESC LIMIT 1
            """, (cik,)).fetchone()
        except Exception:
            pass

    if fin:
        st.subheader("Financial Profile")
        fcols = st.columns(4)
        fcols[0].metric("Revenue", _fmt_currency(fin["revenue"]))
        fcols[1].metric("Total Assets", _fmt_currency(fin["total_assets"]))
        fcols[2].metric("Net Income", _fmt_currency(fin["net_income"]))
        fcols[3].metric("Employees", f"{fin['employees']:,}" if fin["employees"] else "N/A")

    # Institutional holders for this company
    holders = pd.DataFrame()
    if _table_exists(conn, "institutional_holders"):
        holders = _safe_query("""
            SELECT holder_name, shares_held, value_usd, filing_date
            FROM institutional_holders
            WHERE held_cik = ?
            ORDER BY value_usd DESC
            LIMIT 10
        """, conn, params=[cik])

    if not holders.empty:
        st.subheader("Top Institutional Holders")
        st.dataframe(holders, use_container_width=True, hide_index=True)

    # Subsidiaries list
    st.subheader("Subsidiaries")
    df = _safe_query("""
        SELECT s.name AS subsidiary, s.jurisdiction_name AS jurisdiction,
               s.jurisdiction_code, s.is_tax_haven,
               ol.ownership_pct, ol.filing_date
        FROM ownership_links ol
        JOIN subsidiaries s ON s.id = ol.subsidiary_id
        WHERE ol.parent_cik = ?
        ORDER BY s.name
    """, conn, params=[cik])

    if not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Jurisdiction breakdown
        st.subheader("Jurisdiction Breakdown")
        juris = df["jurisdiction"].value_counts().head(15)
        fig = px.pie(
            values=juris.values, names=juris.index,
            title=f"Subsidiary Jurisdictions for {selected}",
        )
        fig.update_layout(template="plotly_dark", plot_bgcolor="#0E1117", paper_bgcolor="#0E1117")
        st.plotly_chart(fig, use_container_width=True)


def _page_jurisdiction_analysis(conn):
    """Jurisdiction analysis."""
    st.header("Jurisdiction Analysis")

    if not _table_exists(conn, "subsidiaries"):
        st.warning("No data loaded. Run the pipeline first: `python -m src.cli pipeline`")
        return

    df = _safe_query("""
        SELECT jurisdiction_name, jurisdiction_code, jurisdiction_country,
               COUNT(*) as subsidiary_count,
               SUM(CASE WHEN is_tax_haven = 1 THEN 1 ELSE 0 END) as is_haven,
               COUNT(DISTINCT id) as unique_entities
        FROM subsidiaries
        WHERE jurisdiction_code != ''
        GROUP BY jurisdiction_code
        ORDER BY subsidiary_count DESC
    """, conn)

    if df.empty:
        st.info("No jurisdiction data.")
        return

    us_count = df[df["jurisdiction_country"] == "US"]["subsidiary_count"].sum()
    intl_count = df[df["jurisdiction_country"] != "US"]["subsidiary_count"].sum()

    cols = st.columns(3)
    cols[0].metric("US Subsidiaries", f"{us_count:,}")
    cols[1].metric("International", f"{intl_count:,}")
    cols[2].metric("Unique Jurisdictions", f"{len(df):,}")

    st.subheader("All Jurisdictions")
    st.dataframe(df, use_container_width=True, hide_index=True)


def _page_tax_havens(conn):
    """Tax haven analysis."""
    st.header("Tax Haven Dashboard")

    if not _table_exists(conn, "ownership_links") or not _table_exists(conn, "subsidiaries"):
        st.warning("No data loaded. Run the pipeline first: `python -m src.cli pipeline`")
        return

    df = _safe_query("""
        SELECT p.company_name, p.ticker,
               COUNT(CASE WHEN s.is_tax_haven = 1 THEN 1 END) as haven_subs,
               COUNT(*) as total_subs,
               ROUND(100.0 * COUNT(CASE WHEN s.is_tax_haven = 1 THEN 1 END) / COUNT(*), 1) as haven_pct
        FROM ownership_links ol
        JOIN parents p ON p.cik = ol.parent_cik
        JOIN subsidiaries s ON s.id = ol.subsidiary_id
        GROUP BY ol.parent_cik
        HAVING haven_subs > 0
        ORDER BY haven_subs DESC
    """, conn)

    if df.empty:
        st.info("No tax haven data.")
        return

    cols = st.columns(3)
    cols[0].metric("Companies with Tax Haven Subs", f"{len(df):,}")
    cols[1].metric("Total Tax Haven Entities", f"{df['haven_subs'].sum():,}")
    cols[2].metric("Avg Haven %", f"{df['haven_pct'].mean():.1f}%")

    st.subheader("Companies with Most Tax Haven Subsidiaries")
    st.dataframe(df.head(30), use_container_width=True, hide_index=True)

    # Tax haven jurisdiction breakdown
    st.subheader("Tax Haven Jurisdiction Breakdown")
    haven_df = _safe_query("""
        SELECT jurisdiction_name, jurisdiction_code, COUNT(*) as count
        FROM subsidiaries
        WHERE is_tax_haven = 1
        GROUP BY jurisdiction_code
        ORDER BY count DESC
    """, conn)

    if not haven_df.empty:
        fig = px.bar(
            haven_df, x="jurisdiction_name", y="count",
            title="Tax Haven Subsidiary Count by Jurisdiction",
            color_discrete_sequence=["#E74C3C"],
        )
        fig.update_layout(template="plotly_dark", plot_bgcolor="#0E1117", paper_bgcolor="#0E1117")
        st.plotly_chart(fig, use_container_width=True)


def _page_financial_profiles(conn):
    """Financial profiles for parent companies."""
    st.header("Financial Profiles")

    if not _table_exists(conn, "financials"):
        st.info("No financial data. Run: `python -m src.cli enrich-financials`")
        return

    fin_count = _safe_fetchone(conn, "SELECT COUNT(*) FROM financials")
    if fin_count == 0:
        st.info("No financial data. Run: `python -m src.cli enrich-financials`")
        return

    # Summary metrics
    summary = _safe_query("""
        SELECT COUNT(DISTINCT cik) as companies,
               SUM(revenue) as total_revenue,
               SUM(total_assets) as total_assets,
               SUM(employees) as total_employees
        FROM financials f
        WHERE fiscal_year = (SELECT MAX(fiscal_year) FROM financials f2 WHERE f2.cik = f.cik)
    """, conn)

    if not summary.empty:
        cols = st.columns(4)
        cols[0].metric("Companies with Financials", f"{int(summary['companies'].iloc[0]):,}")
        cols[1].metric("Total Revenue", _fmt_currency(summary['total_revenue'].iloc[0]))
        cols[2].metric("Total Assets", _fmt_currency(summary['total_assets'].iloc[0]))
        emp = summary['total_employees'].iloc[0]
        cols[3].metric("Total Employees", f"{int(emp):,}" if emp else "N/A")

    # Revenue vs Subsidiary count scatter
    st.subheader("Revenue vs. Subsidiary Count")
    scatter_df = _safe_query("""
        SELECT p.company_name, p.ticker, f.revenue,
               COUNT(DISTINCT ol.subsidiary_id) as sub_count,
               SUM(CASE WHEN s.is_tax_haven = 1 THEN 1 ELSE 0 END) as haven_count
        FROM parents p
        JOIN financials f ON f.cik = p.cik
        JOIN ownership_links ol ON ol.parent_cik = p.cik
        JOIN subsidiaries s ON s.id = ol.subsidiary_id
        WHERE f.fiscal_year = (SELECT MAX(fiscal_year) FROM financials f2 WHERE f2.cik = f.cik)
            AND f.revenue IS NOT NULL AND f.revenue > 0
        GROUP BY p.cik
        ORDER BY f.revenue DESC
    """, conn)

    if not scatter_df.empty:
        fig = px.scatter(
            scatter_df, x="revenue", y="sub_count",
            hover_name="company_name",
            color="haven_count",
            color_continuous_scale=["#0984E3", "#E74C3C"],
            title="Revenue vs. Subsidiary Count",
            labels={"revenue": "Revenue (USD)", "sub_count": "Subsidiary Count"},
        )
        fig.update_layout(template="plotly_dark", plot_bgcolor="#0E1117", paper_bgcolor="#0E1117")
        fig.update_xaxes(type="log")
        st.plotly_chart(fig, use_container_width=True)

    # Financial metrics table
    st.subheader("Financial Metrics by Company")
    sort_by = st.selectbox("Sort by", ["Revenue", "Total Assets", "Subsidiaries", "Employees"])
    sort_map = {
        "Revenue": "f.revenue DESC",
        "Total Assets": "f.total_assets DESC",
        "Subsidiaries": "sub_count DESC",
        "Employees": "f.employees DESC",
    }

    table_df = _safe_query(f"""
        SELECT p.company_name, p.ticker, f.fiscal_year,
               f.revenue, f.total_assets, f.net_income, f.employees,
               COUNT(DISTINCT ol.subsidiary_id) as sub_count,
               SUM(CASE WHEN s.is_tax_haven = 1 THEN 1 ELSE 0 END) as haven_count
        FROM parents p
        JOIN financials f ON f.cik = p.cik
        JOIN ownership_links ol ON ol.parent_cik = p.cik
        JOIN subsidiaries s ON s.id = ol.subsidiary_id
        WHERE f.fiscal_year = (SELECT MAX(fiscal_year) FROM financials f2 WHERE f2.cik = f.cik)
        GROUP BY p.cik
        ORDER BY {sort_map[sort_by]}
        LIMIT 50
    """, conn)

    if not table_df.empty:
        st.dataframe(table_df, use_container_width=True, hide_index=True)


def _page_tax_haven_financials(conn):
    """Tax haven analysis with financial context."""
    st.header("Tax Haven Financial Analysis")

    if not _table_exists(conn, "financials"):
        st.info("No financial data. Run: `python -m src.cli enrich-financials`")
        return

    fin_count = _safe_fetchone(conn, "SELECT COUNT(*) FROM financials")
    if fin_count == 0:
        st.info("No financial data. Run: `python -m src.cli enrich-financials`")
        return

    # Revenue-weighted tax haven usage
    df = _safe_query("""
        SELECT p.company_name, p.ticker, p.sic_code, p.sic_description,
               f.revenue, f.total_assets,
               COUNT(DISTINCT ol.subsidiary_id) as total_subs,
               SUM(CASE WHEN s.is_tax_haven = 1 THEN 1 ELSE 0 END) as haven_subs,
               ROUND(100.0 * SUM(CASE WHEN s.is_tax_haven = 1 THEN 1 ELSE 0 END) / COUNT(DISTINCT ol.subsidiary_id), 1) as haven_pct
        FROM parents p
        JOIN financials f ON f.cik = p.cik
        JOIN ownership_links ol ON ol.parent_cik = p.cik
        JOIN subsidiaries s ON s.id = ol.subsidiary_id
        WHERE f.fiscal_year = (SELECT MAX(fiscal_year) FROM financials f2 WHERE f2.cik = f.cik)
            AND f.revenue IS NOT NULL AND f.revenue > 0
        GROUP BY p.cik
        HAVING haven_subs > 0
        ORDER BY haven_subs DESC
    """, conn)

    if df.empty:
        st.info("No companies with both financial data and tax haven subsidiaries.")
        return

    # Summary
    cols = st.columns(4)
    cols[0].metric("Companies", f"{len(df):,}")
    cols[1].metric("Total Revenue", _fmt_currency(df["revenue"].sum()))
    cols[2].metric("Total Haven Subs", f"{df['haven_subs'].sum():,}")
    cols[3].metric("Avg Haven %", f"{df['haven_pct'].mean():.1f}%")

    # Revenue per haven subsidiary
    st.subheader("Revenue per Tax Haven Subsidiary")
    df["rev_per_haven"] = df["revenue"] / df["haven_subs"]
    top = df.nlargest(20, "revenue")

    fig = px.bar(
        top, x="company_name", y="haven_pct",
        hover_data=["revenue", "haven_subs", "total_subs"],
        title="Tax Haven % — Top 20 by Revenue",
        color="haven_pct",
        color_continuous_scale=["#2ECC71", "#E74C3C"],
    )
    fig.update_layout(template="plotly_dark", plot_bgcolor="#0E1117", paper_bgcolor="#0E1117")
    st.plotly_chart(fig, use_container_width=True)

    # Industry peer comparison
    st.subheader("Industry Peer Comparison")
    industry_df = _safe_query("""
        SELECT p.sic_description as industry,
               COUNT(DISTINCT p.cik) as companies,
               AVG(ROUND(100.0 * SUM(CASE WHEN s.is_tax_haven = 1 THEN 1 ELSE 0 END) / COUNT(DISTINCT ol.subsidiary_id), 1)) as avg_haven_pct,
               SUM(f.revenue) as total_revenue,
               SUM(CASE WHEN s.is_tax_haven = 1 THEN 1 ELSE 0 END) as total_haven_subs
        FROM parents p
        JOIN financials f ON f.cik = p.cik
        JOIN ownership_links ol ON ol.parent_cik = p.cik
        JOIN subsidiaries s ON s.id = ol.subsidiary_id
        WHERE f.fiscal_year = (SELECT MAX(fiscal_year) FROM financials f2 WHERE f2.cik = f.cik)
            AND p.sic_description IS NOT NULL AND p.sic_description != ''
        GROUP BY p.sic_description
        HAVING companies >= 2
        ORDER BY total_haven_subs DESC
        LIMIT 15
    """, conn)

    if not industry_df.empty:
        st.dataframe(industry_df, use_container_width=True, hide_index=True)

    # Full table
    st.subheader("All Companies with Financial + Tax Haven Data")
    st.dataframe(df[["company_name", "ticker", "revenue", "total_assets", "total_subs", "haven_subs", "haven_pct"]].head(50),
                 use_container_width=True, hide_index=True)


def _page_institutional_ownership(conn):
    """Institutional ownership analysis."""
    st.header("Institutional Ownership")

    if not _table_exists(conn, "institutional_holders"):
        st.info("No institutional data. Run: `python -m src.cli enrich-13f`")
        return

    inst_count = _safe_fetchone(conn, "SELECT COUNT(*) FROM institutional_holders")
    if inst_count == 0:
        st.info("No institutional data. Run: `python -m src.cli enrich-13f`")
        return

    # Top holders across our universe
    st.subheader("Top Institutional Holders")
    holders = _safe_query("""
        SELECT ip.holder_name,
               ip.total_positions,
               ip.total_value
        FROM institutional_profiles ip
        ORDER BY ip.total_value DESC
    """, conn)

    if not holders.empty:
        cols = st.columns(3)
        cols[0].metric("Institutional Holders", f"{len(holders):,}")
        cols[1].metric("Total Positions", f"{holders['total_positions'].sum():,}")
        cols[2].metric("Total Value", _fmt_currency(holders['total_value'].sum()))

        fig = px.bar(
            holders.head(15), x="holder_name", y="total_value",
            title="Top Institutional Holders by Portfolio Value",
            color_discrete_sequence=["#0984E3"],
        )
        fig.update_layout(template="plotly_dark", plot_bgcolor="#0E1117", paper_bgcolor="#0E1117")
        st.plotly_chart(fig, use_container_width=True)

    # Company-level ownership
    st.subheader("Most Widely Held Companies")
    held = _safe_query("""
        SELECT p.company_name, p.ticker,
               COUNT(DISTINCT ih.holder_cik) as num_holders,
               SUM(ih.value_usd) as total_value_held
        FROM institutional_holders ih
        JOIN parents p ON p.cik = ih.held_cik
        GROUP BY ih.held_cik
        ORDER BY num_holders DESC
        LIMIT 30
    """, conn)

    if not held.empty:
        st.dataframe(held, use_container_width=True, hide_index=True)

    # Common ownership analysis
    st.subheader("Common Ownership Network")
    st.write("Companies sharing the same top institutional investors")
    common = _safe_query("""
        SELECT ih.holder_name,
               COUNT(DISTINCT ih.held_cik) as companies_held,
               SUM(ih.value_usd) as total_portfolio_value
        FROM institutional_holders ih
        GROUP BY ih.holder_cik
        ORDER BY companies_held DESC
        LIMIT 20
    """, conn)

    if not common.empty:
        st.dataframe(common, use_container_width=True, hide_index=True)


def _page_yoy_changes(conn):
    """Year-over-year subsidiary changes."""
    st.header("Year-over-Year Changes")

    if not _table_exists(conn, "ownership_links"):
        st.warning("No data loaded. Run the pipeline first: `python -m src.cli pipeline`")
        return

    df = _safe_query("""
        SELECT SUBSTR(filing_date, 1, 4) as year,
               COUNT(DISTINCT parent_cik) as companies,
               COUNT(DISTINCT subsidiary_id) as subsidiaries,
               SUM(CASE WHEN quality_score >= 0.4 THEN 1 ELSE 0 END) as above_threshold
        FROM ownership_links
        WHERE filing_date != ''
        GROUP BY year
        ORDER BY year
    """, conn)

    if df.empty:
        st.info("No filing date data available.")
        return

    fig = px.bar(
        df, x="year", y="subsidiaries",
        title="Subsidiaries by Filing Year",
        color_discrete_sequence=["#0984E3"],
    )
    fig.update_layout(template="plotly_dark", plot_bgcolor="#0E1117", paper_bgcolor="#0E1117")
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(df, use_container_width=True, hide_index=True)


def _page_industry_comparison(conn):
    """Industry sector comparison."""
    st.header("Industry Comparison")

    if not _table_exists(conn, "parents") or not _table_exists(conn, "ownership_links"):
        st.warning("No data loaded. Run the pipeline first: `python -m src.cli pipeline`")
        return

    df = _safe_query("""
        SELECT p.sic_code, p.sic_description,
               COUNT(DISTINCT p.cik) as companies,
               COUNT(DISTINCT ol.subsidiary_id) as subsidiaries,
               ROUND(AVG(
                   (SELECT COUNT(*) FROM ownership_links ol2 WHERE ol2.parent_cik = p.cik)
               ), 1) as avg_subs_per_company,
               SUM(CASE WHEN s.is_tax_haven = 1 THEN 1 ELSE 0 END) as haven_count
        FROM parents p
        JOIN ownership_links ol ON ol.parent_cik = p.cik
        JOIN subsidiaries s ON s.id = ol.subsidiary_id
        WHERE p.sic_code != '' AND p.sic_code IS NOT NULL
        GROUP BY p.sic_code
        ORDER BY subsidiaries DESC
        LIMIT 20
    """, conn)

    if df.empty:
        st.info("No SIC code data available. Run pipeline with company info enrichment.")
        return

    st.dataframe(df, use_container_width=True, hide_index=True)


def _page_data_quality(conn, stats):
    """Data quality analysis with enrichment coverage."""
    st.header("Data Quality")

    if not _table_exists(conn, "ownership_links"):
        st.warning("No data loaded. Run the pipeline first: `python -m src.cli pipeline`")
        return

    # Quality score distribution
    df = _safe_query("""
        SELECT quality_score,
               COUNT(*) as count
        FROM ownership_links
        WHERE quality_score IS NOT NULL
        GROUP BY ROUND(quality_score, 1)
        ORDER BY quality_score
    """, conn)

    if not df.empty:
        fig = px.bar(
            df, x="quality_score", y="count",
            title="Quality Score Distribution",
            color_discrete_sequence=["#0984E3"],
        )
        fig.update_layout(template="plotly_dark", plot_bgcolor="#0E1117", paper_bgcolor="#0E1117")
        st.plotly_chart(fig, use_container_width=True)

    # Parse method breakdown
    method_df = _safe_query("""
        SELECT parse_method, COUNT(*) as count,
               SUM(subsidiary_count) as total_subs,
               ROUND(AVG(subsidiary_count), 1) as avg_subs
        FROM filings
        WHERE parse_method IS NOT NULL
        GROUP BY parse_method
    """, conn)

    st.subheader("Parse Method Breakdown")
    st.dataframe(method_df, use_container_width=True, hide_index=True)

    # Jurisdiction normalization rate
    norm_df = _safe_query("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN jurisdiction_code != '' THEN 1 ELSE 0 END) as normalized,
            ROUND(100.0 * SUM(CASE WHEN jurisdiction_code != '' THEN 1 ELSE 0 END) / COUNT(*), 1) as pct
        FROM subsidiaries
    """, conn)

    if not norm_df.empty and norm_df['total'].iloc[0] > 0:
        st.subheader("Jurisdiction Normalization")
        cols = st.columns(3)
        total = int(norm_df['total'].iloc[0])
        normalized = int(norm_df['normalized'].iloc[0])
        pct = norm_df['pct'].iloc[0]
        cols[0].metric("Total Subsidiaries", f"{total:,}")
        cols[1].metric("Normalized", f"{normalized:,}")
        cols[2].metric("Rate", f"{pct}%")

    # Enrichment coverage
    st.subheader("Enrichment Coverage")
    ecols = st.columns(4)

    fin_coverage = stats.get("companies_with_financials", 0)
    ecols[0].metric("Financial Coverage",
                     f"{fin_coverage}/{stats['parent_count']}",
                     f"{fin_coverage/max(stats['parent_count'],1)*100:.0f}%")

    # Ownership % coverage
    try:
        pct_row = conn.execute(
            "SELECT COUNT(*) as total, SUM(CASE WHEN ownership_pct IS NOT NULL THEN 1 ELSE 0 END) as with_pct FROM ownership_links"
        ).fetchone()
        pct_coverage = pct_row["with_pct"] if pct_row else 0
        total_links = pct_row["total"] if pct_row else 0
        ecols[1].metric("Ownership % Coverage",
                         f"{pct_coverage}/{total_links}",
                         f"{pct_coverage/max(total_links,1)*100:.0f}%")
    except Exception:
        ecols[1].metric("Ownership % Coverage", "N/A")

    inst_holders = stats.get("institutional_holders", 0)
    ecols[2].metric("Institutional Holders", f"{inst_holders}")

    ecols[3].metric("Avg Quality Score", f"{stats['avg_quality']:.3f}")


def _get_jurisdictions(conn) -> list[str]:
    """Get list of jurisdiction codes."""
    try:
        rows = conn.execute("""
            SELECT DISTINCT jurisdiction_code
            FROM subsidiaries
            WHERE jurisdiction_code != ''
            ORDER BY jurisdiction_code
        """).fetchall()
        return [r[0] for r in rows]
    except Exception:
        return []


if __name__ == "__main__":
    main()
