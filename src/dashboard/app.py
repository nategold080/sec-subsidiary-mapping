"""Streamlit dashboard for SEC Subsidiary Mapping.

Dark theme with 7+ interactive sections. Run with:
    streamlit run src/dashboard/app.py
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


@st.cache_resource
def get_db():
    """Get database connection."""
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def main():
    st.title("SEC Corporate Subsidiary & Ownership Mapping")
    st.caption("Structured database of corporate subsidiary relationships from SEC EDGAR Exhibit 21 filings")

    conn = get_db()

    # Check if database exists and has data
    try:
        stats = _get_stats(conn)
    except Exception:
        st.error("Database not found. Run the pipeline first: `python -m src.cli pipeline`")
        return

    if stats["parent_count"] == 0:
        st.warning("No data in database. Run the pipeline first.")
        return

    # Sidebar navigation
    page = st.sidebar.selectbox(
        "Navigate",
        [
            "Overview",
            "Subsidiary Explorer",
            "Company Deep Dive",
            "Jurisdiction Analysis",
            "Tax Haven Dashboard",
            "Year-over-Year Changes",
            "Industry Comparison",
            "Data Quality",
        ],
    )

    if page == "Overview":
        _page_overview(conn, stats)
    elif page == "Subsidiary Explorer":
        _page_explorer(conn)
    elif page == "Company Deep Dive":
        _page_company_deep_dive(conn)
    elif page == "Jurisdiction Analysis":
        _page_jurisdiction_analysis(conn)
    elif page == "Tax Haven Dashboard":
        _page_tax_havens(conn)
    elif page == "Year-over-Year Changes":
        _page_yoy_changes(conn)
    elif page == "Industry Comparison":
        _page_industry_comparison(conn)
    elif page == "Data Quality":
        _page_data_quality(conn)

    # Footer
    st.markdown("---")
    st.markdown(
        "**Built by Nathan Goldberg** | "
        "nathanmauricegoldberg@gmail.com | "
        "[LinkedIn](https://www.linkedin.com/in/nathanmauricegoldberg/)"
    )


def _get_stats(conn) -> dict:
    """Get summary statistics."""
    stats = {}
    stats["parent_count"] = conn.execute("SELECT COUNT(*) FROM parents").fetchone()[0]
    stats["filing_count"] = conn.execute("SELECT COUNT(*) FROM filings").fetchone()[0]
    stats["subsidiary_count"] = conn.execute("SELECT COUNT(*) FROM subsidiaries").fetchone()[0]
    stats["link_count"] = conn.execute("SELECT COUNT(*) FROM ownership_links").fetchone()[0]
    stats["tax_haven_count"] = conn.execute(
        "SELECT COUNT(*) FROM subsidiaries WHERE is_tax_haven = 1"
    ).fetchone()[0]
    stats["jurisdiction_count"] = conn.execute(
        "SELECT COUNT(DISTINCT jurisdiction_code) FROM subsidiaries WHERE jurisdiction_code != ''"
    ).fetchone()[0]
    row = conn.execute(
        "SELECT AVG(quality_score) FROM ownership_links WHERE quality_score IS NOT NULL"
    ).fetchone()
    stats["avg_quality"] = round(row[0], 3) if row and row[0] else 0
    return stats


def _page_overview(conn, stats):
    """Overview with KPI cards and summary charts."""
    st.header("Corporate Universe Overview")

    # KPI cards
    cols = st.columns(4)
    cols[0].metric("Parent Companies", f"{stats['parent_count']:,}")
    cols[1].metric("Unique Subsidiaries", f"{stats['subsidiary_count']:,}")
    cols[2].metric("Tax Haven Entities", f"{stats['tax_haven_count']:,}")
    cols[3].metric("Jurisdictions", f"{stats['jurisdiction_count']:,}")

    cols2 = st.columns(4)
    cols2[0].metric("Ownership Links", f"{stats['link_count']:,}")
    cols2[1].metric("Filings Parsed", f"{stats['filing_count']:,}")
    cols2[2].metric("Avg Quality", f"{stats['avg_quality']:.3f}")
    haven_pct = (
        stats["tax_haven_count"] / max(stats["subsidiary_count"], 1) * 100
    )
    cols2[3].metric("Tax Haven %", f"{haven_pct:.1f}%")

    # Top jurisdictions chart
    st.subheader("Top 15 Jurisdictions")
    df = pd.read_sql_query("""
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
    df = pd.read_sql_query("""
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

    df = pd.read_sql_query(f"""
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
    """Individual company deep dive."""
    st.header("Company Deep Dive")

    companies = pd.read_sql_query("""
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

    # Subsidiaries list
    st.subheader("Subsidiaries")
    df = pd.read_sql_query("""
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

    df = pd.read_sql_query("""
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

    # US vs International split
    us_count = df[df["jurisdiction_country"] == "US"]["subsidiary_count"].sum()
    intl_count = df[df["jurisdiction_country"] != "US"]["subsidiary_count"].sum()

    cols = st.columns(3)
    cols[0].metric("US Subsidiaries", f"{us_count:,}")
    cols[1].metric("International", f"{intl_count:,}")
    cols[2].metric("Unique Jurisdictions", f"{len(df):,}")

    # Top jurisdictions table
    st.subheader("All Jurisdictions")
    st.dataframe(df, use_container_width=True, hide_index=True)


def _page_tax_havens(conn):
    """Tax haven analysis."""
    st.header("Tax Haven Dashboard")

    df = pd.read_sql_query("""
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
    haven_df = pd.read_sql_query("""
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


def _page_yoy_changes(conn):
    """Year-over-year subsidiary changes."""
    st.header("Year-over-Year Changes")

    df = pd.read_sql_query("""
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

    df = pd.read_sql_query("""
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


def _page_data_quality(conn):
    """Data quality analysis."""
    st.header("Data Quality")

    # Quality score distribution
    df = pd.read_sql_query("""
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
    method_df = pd.read_sql_query("""
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
    norm_df = pd.read_sql_query("""
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


def _get_jurisdictions(conn) -> list[str]:
    """Get list of jurisdiction codes."""
    rows = conn.execute("""
        SELECT DISTINCT jurisdiction_code
        FROM subsidiaries
        WHERE jurisdiction_code != ''
        ORDER BY jurisdiction_code
    """).fetchall()
    return [r[0] for r in rows]


if __name__ == "__main__":
    main()
