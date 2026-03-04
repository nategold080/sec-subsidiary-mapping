"""Streamlit dashboard for SEC Subsidiary Mapping.

Consolidated 5-tab layout with improved data presentation.
Run with: streamlit run src/dashboard/app.py
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

PROJECT_ROOT = Path(__file__).parent.parent.parent
DB_PATH = os.environ.get("DATABASE_URL", str(PROJECT_ROOT / "data" / "sec_subsidiaries.db"))

st.set_page_config(
    page_title="SEC Corporate Subsidiary Mapping",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def _table_exists(conn, name):
    try:
        r = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
        return r is not None
    except Exception:
        return False


def _safe_query(sql, conn, params=()):
    try:
        return pd.read_sql_query(sql, conn, params=params if params else None)
    except Exception:
        return pd.DataFrame()


def _safe_fetchone(conn, sql, params=(), default=0):
    try:
        row = conn.execute(sql, params).fetchone()
        return row[0] if row else default
    except Exception:
        return default


@st.cache_resource
def get_db():
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except Exception:
        pass
    return conn


def _fmt_currency(val):
    if val is None or val == 0:
        return "N/A"
    if abs(val) >= 1e12:
        return f"${val/1e12:.1f}T"
    if abs(val) >= 1e9:
        return f"${val/1e9:.1f}B"
    if abs(val) >= 1e6:
        return f"${val/1e6:.0f}M"
    return f"${val:,.0f}"


def _fmt_number(val):
    if val is None or pd.isna(val):
        return "N/A"
    return f"{int(val):,}"


def _get_stats(conn) -> dict:
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
    stats["financial_count"] = _safe_fetchone(conn, "SELECT COUNT(*) FROM financials")
    stats["companies_with_financials"] = _safe_fetchone(
        conn, "SELECT COUNT(DISTINCT cik) FROM financials WHERE revenue IS NOT NULL OR total_assets IS NOT NULL"
    )
    stats["total_revenue"] = _safe_fetchone(
        conn, "SELECT SUM(revenue) FROM financials f WHERE fiscal_year = (SELECT MAX(fiscal_year) FROM financials f2 WHERE f2.cik = f.cik)"
    ) or 0
    stats["institutional_holders"] = _safe_fetchone(
        conn, "SELECT COUNT(DISTINCT holder_cik) FROM institutional_holders"
    )
    return stats


def _dark_layout(fig):
    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor="#0E1117",
        paper_bgcolor="#0E1117",
        margin=dict(l=40, r=40, t=50, b=40),
    )
    return fig


def _get_jurisdictions(conn) -> list[str]:
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


# ---------------------------------------------------------------------------
# Tab 1: Overview
# ---------------------------------------------------------------------------
def _tab_overview(conn, stats):
    if not _table_exists(conn, "parents") or not _table_exists(conn, "subsidiaries"):
        st.warning("No data loaded. Run the pipeline first: `python -m src.cli pipeline`")
        return

    # KPI row 1 — core counts
    c = st.columns(5)
    c[0].metric("Parent Companies", f"{stats['parent_count']:,}")
    c[1].metric("Subsidiaries", f"{stats['subsidiary_count']:,}")
    c[2].metric("Filings Parsed", f"{stats['filing_count']:,}")
    c[3].metric("Jurisdictions", f"{stats['jurisdiction_count']:,}")
    haven_pct = stats["tax_haven_count"] / max(stats["subsidiary_count"], 1) * 100
    c[4].metric("Tax Haven %", f"{haven_pct:.1f}%")

    # KPI row 2 — financials (only if data exists)
    if stats["total_revenue"] > 0:
        c2 = st.columns(5)
        c2[0].metric("Total Revenue Tracked", _fmt_currency(stats["total_revenue"]))
        c2[1].metric("Companies with Financials", f"{stats['companies_with_financials']:,}")
        c2[2].metric("Tax Haven Entities", f"{stats['tax_haven_count']:,}")
        c2[3].metric("Institutional Holders", f"{stats['institutional_holders']:,}")
        avg_subs = stats["subsidiary_count"] / max(stats["parent_count"], 1)
        c2[4].metric("Avg Subs/Company", f"{avg_subs:.1f}")

    st.markdown("")

    # Two-column layout: jurisdiction chart + top companies
    left, right = st.columns([3, 2])

    with left:
        st.subheader("Top 15 Jurisdictions")
        jdf = _safe_query("""
            SELECT jurisdiction_name, COUNT(*) as count,
                   SUM(CASE WHEN is_tax_haven = 1 THEN 1 ELSE 0 END) as tax_haven
            FROM subsidiaries WHERE jurisdiction_code != ''
            GROUP BY jurisdiction_code ORDER BY count DESC LIMIT 15
        """, conn)
        if not jdf.empty:
            jdf["type"] = jdf.apply(
                lambda r: "Tax Haven" if r["tax_haven"] > 0 else "Standard", axis=1
            )
            fig = px.bar(
                jdf, x="jurisdiction_name", y="count",
                color="type",
                color_discrete_map={"Standard": "#0984E3", "Tax Haven": "#E74C3C"},
                labels={"jurisdiction_name": "Jurisdiction", "count": "Subsidiaries"},
            )
            fig.update_layout(showlegend=True, legend_title_text="")
            _dark_layout(fig)
            st.plotly_chart(fig, width="stretch")

    with right:
        st.subheader("Top 15 Companies")
        tdf = _safe_query("""
            SELECT p.company_name AS Company, p.ticker AS Ticker,
                   COUNT(DISTINCT ol.subsidiary_id) as Subsidiaries,
                   SUM(CASE WHEN s.is_tax_haven = 1 THEN 1 ELSE 0 END) as "Tax Haven"
            FROM ownership_links ol
            JOIN parents p ON p.cik = ol.parent_cik
            JOIN subsidiaries s ON s.id = ol.subsidiary_id
            GROUP BY ol.parent_cik ORDER BY Subsidiaries DESC LIMIT 15
        """, conn)
        if not tdf.empty:
            st.dataframe(tdf, width="stretch", hide_index=True, height=490)

    # Revenue vs Subsidiary Count scatter (if financial data exists)
    if stats["total_revenue"] > 0:
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
            GROUP BY p.cik ORDER BY f.revenue DESC
        """, conn)
        if not scatter_df.empty:
            fig = px.scatter(
                scatter_df, x="revenue", y="sub_count",
                hover_name="company_name",
                color="haven_count",
                color_continuous_scale=["#0984E3", "#E74C3C"],
                labels={"revenue": "Revenue (USD)", "sub_count": "Subsidiary Count", "haven_count": "Tax Haven Subs"},
                size_max=12,
            )
            fig.update_xaxes(type="log")
            _dark_layout(fig)
            st.plotly_chart(fig, width="stretch")

    # Year-over-year summary (compact)
    yoy = _safe_query("""
        SELECT SUBSTR(filing_date, 1, 4) as Year,
               COUNT(DISTINCT parent_cik) as Companies,
               COUNT(DISTINCT subsidiary_id) as Subsidiaries
        FROM ownership_links WHERE filing_date != ''
        GROUP BY Year ORDER BY Year
    """, conn)
    if not yoy.empty and len(yoy) > 1:
        st.subheader("Filing Year Coverage")
        fig = px.bar(yoy, x="Year", y="Subsidiaries", text="Companies",
                     color_discrete_sequence=["#0984E3"])
        fig.update_traces(texttemplate="%{text} cos", textposition="outside")
        _dark_layout(fig)
        st.plotly_chart(fig, width="stretch")


# ---------------------------------------------------------------------------
# Tab 2: Company Lookup
# ---------------------------------------------------------------------------
def _tab_company_lookup(conn):
    if not _table_exists(conn, "parents"):
        st.warning("No data loaded. Run the pipeline first.")
        return

    companies = _safe_query("""
        SELECT p.cik, p.company_name || CASE WHEN p.ticker != '' THEN ' (' || p.ticker || ')' ELSE '' END as label,
               COUNT(DISTINCT ol.subsidiary_id) as sub_count
        FROM parents p
        LEFT JOIN ownership_links ol ON ol.parent_cik = p.cik
        GROUP BY p.cik ORDER BY sub_count DESC
    """, conn)

    if companies.empty:
        st.info("No companies in database.")
        return

    selected = st.selectbox("Search or select a company", companies["label"].tolist())
    if not selected:
        return

    idx = companies[companies["label"] == selected].index[0]
    cik = companies.loc[idx, "cik"]
    sub_count = companies.loc[idx, "sub_count"]

    info = conn.execute("SELECT * FROM parents WHERE cik = ?", (cik,)).fetchone()

    # Company header
    cols = st.columns(4)
    cols[0].metric("CIK", info["cik"] if info else "N/A")
    cols[1].metric("Ticker", (info["ticker"] or "N/A") if info else "N/A")
    sic_label = info["sic_description"] or info["sic_code"] or "N/A" if info else "N/A"
    cols[2].metric("Industry (SIC)", sic_label)
    cols[3].metric("Subsidiaries", f"{sub_count:,}")

    # Financial profile
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
        fc = st.columns(4)
        fc[0].metric("Revenue", _fmt_currency(fin["revenue"]))
        fc[1].metric("Total Assets", _fmt_currency(fin["total_assets"]))
        fc[2].metric("Net Income", _fmt_currency(fin["net_income"]))
        fc[3].metric("Employees", _fmt_number(fin["employees"]))

    # Institutional holders
    if _table_exists(conn, "institutional_holders"):
        holders = _safe_query("""
            SELECT holder_name AS "Holder", shares_held AS "Shares",
                   value_usd AS "Value (USD)", filing_date AS "Filing Date"
            FROM institutional_holders WHERE held_cik = ?
            ORDER BY value_usd DESC LIMIT 10
        """, conn, params=[cik])
        if not holders.empty:
            st.subheader("Top Institutional Holders")
            holders["Value (USD)"] = holders["Value (USD)"].apply(
                lambda v: _fmt_currency(v) if v else "N/A"
            )
            holders["Shares"] = holders["Shares"].apply(
                lambda v: f"{int(v):,}" if pd.notna(v) else "N/A"
            )
            st.dataframe(holders, width="stretch", hide_index=True)

    st.markdown("---")

    # Subsidiaries — with dedup toggle
    latest_only = st.checkbox("Show latest filing only (deduplicate)", value=True)

    if latest_only:
        sub_sql = """
            SELECT s.name AS Subsidiary, s.jurisdiction_name AS Jurisdiction,
                   s.jurisdiction_code AS Code, s.is_tax_haven AS "Tax Haven",
                   ol.ownership_pct AS "Ownership %", MAX(ol.filing_date) AS "Filing Date"
            FROM ownership_links ol
            JOIN subsidiaries s ON s.id = ol.subsidiary_id
            WHERE ol.parent_cik = ?
            GROUP BY s.id
            ORDER BY s.name
        """
    else:
        sub_sql = """
            SELECT s.name AS Subsidiary, s.jurisdiction_name AS Jurisdiction,
                   s.jurisdiction_code AS Code, s.is_tax_haven AS "Tax Haven",
                   ol.ownership_pct AS "Ownership %", ol.filing_date AS "Filing Date"
            FROM ownership_links ol
            JOIN subsidiaries s ON s.id = ol.subsidiary_id
            WHERE ol.parent_cik = ?
            ORDER BY s.name, ol.filing_date DESC
        """

    sdf = _safe_query(sub_sql, conn, params=[cik])

    if not sdf.empty:
        st.subheader(f"Subsidiaries ({len(sdf):,})")
        st.dataframe(sdf, width="stretch", hide_index=True, height=400)

        # Jurisdiction breakdown — horizontal bar chart (not pie)
        juris = sdf["Jurisdiction"].value_counts().head(15).reset_index()
        juris.columns = ["Jurisdiction", "Count"]
        fig = px.bar(juris, x="Count", y="Jurisdiction", orientation="h",
                     color_discrete_sequence=["#0984E3"])
        fig.update_layout(yaxis=dict(autorange="reversed"))
        _dark_layout(fig)
        st.plotly_chart(fig, width="stretch")


# ---------------------------------------------------------------------------
# Tab 3: Subsidiary Explorer
# ---------------------------------------------------------------------------
def _tab_explorer(conn):
    if not _table_exists(conn, "ownership_links") or not _table_exists(conn, "subsidiaries"):
        st.warning("No data loaded. Run the pipeline first.")
        return

    c1, c2, c3 = st.columns([3, 2, 1])
    search = c1.text_input("Search subsidiary name", "")
    jurisdiction = c2.selectbox("Filter by jurisdiction", ["All"] + _get_jurisdictions(conn))
    tax_haven_only = c3.checkbox("Tax haven only")

    latest_only = st.checkbox("Latest filing per subsidiary (deduplicate)", value=True)
    limit = st.slider("Max results", 50, 1000, 200, 50)

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

    if latest_only:
        sql = f"""
            SELECT p.company_name AS Parent, p.ticker AS Ticker,
                   s.name AS Subsidiary, s.jurisdiction_name AS Jurisdiction,
                   s.jurisdiction_code AS Code, s.is_tax_haven AS "Tax Haven",
                   ol.ownership_pct AS "Ownership %",
                   MAX(ol.filing_date) AS "Filing Date",
                   MAX(ol.quality_score) AS "Quality"
            FROM ownership_links ol
            JOIN parents p ON p.cik = ol.parent_cik
            JOIN subsidiaries s ON s.id = ol.subsidiary_id
            {where}
            GROUP BY ol.parent_cik, s.id
            ORDER BY p.company_name, s.name
            LIMIT ?
        """
    else:
        sql = f"""
            SELECT p.company_name AS Parent, p.ticker AS Ticker,
                   s.name AS Subsidiary, s.jurisdiction_name AS Jurisdiction,
                   s.jurisdiction_code AS Code, s.is_tax_haven AS "Tax Haven",
                   ol.ownership_pct AS "Ownership %",
                   ol.filing_date AS "Filing Date",
                   ol.quality_score AS "Quality"
            FROM ownership_links ol
            JOIN parents p ON p.cik = ol.parent_cik
            JOIN subsidiaries s ON s.id = ol.subsidiary_id
            {where}
            ORDER BY p.company_name, s.name
            LIMIT ?
        """

    df = _safe_query(sql, conn, params=params + [limit])

    st.caption(f"Showing {len(df):,} results")
    st.dataframe(df, width="stretch", hide_index=True, height=500)


# ---------------------------------------------------------------------------
# Tab 4: Tax Havens (merged)
# ---------------------------------------------------------------------------
def _tab_tax_havens(conn):
    if not _table_exists(conn, "ownership_links") or not _table_exists(conn, "subsidiaries"):
        st.warning("No data loaded. Run the pipeline first.")
        return

    # Company-level tax haven stats
    df = _safe_query("""
        SELECT p.company_name, p.ticker,
               COUNT(CASE WHEN s.is_tax_haven = 1 THEN 1 END) as haven_subs,
               COUNT(*) as total_subs,
               ROUND(100.0 * COUNT(CASE WHEN s.is_tax_haven = 1 THEN 1 END) / COUNT(*), 1) as haven_pct
        FROM ownership_links ol
        JOIN parents p ON p.cik = ol.parent_cik
        JOIN subsidiaries s ON s.id = ol.subsidiary_id
        GROUP BY ol.parent_cik HAVING haven_subs > 0
        ORDER BY haven_subs DESC
    """, conn)

    if df.empty:
        st.info("No tax haven data.")
        return

    # KPI cards
    c = st.columns(4)
    c[0].metric("Companies with Tax Haven Subs", f"{len(df):,}")
    c[1].metric("Total Tax Haven Entities", f"{df['haven_subs'].sum():,}")
    c[2].metric("Avg Haven %", f"{df['haven_pct'].mean():.1f}%")
    top_company = df.iloc[0]
    c[3].metric("Most Haven Subs", f"{top_company['company_name']}", f"{int(top_company['haven_subs']):,}")

    # Two columns: company table + jurisdiction chart
    left, right = st.columns([3, 2])

    with left:
        st.subheader("Companies with Most Tax Haven Subsidiaries")
        display_df = df.head(25).copy()
        display_df.columns = ["Company", "Ticker", "Haven Subs", "Total Subs", "Haven %"]
        st.dataframe(display_df, width="stretch", hide_index=True, height=450)

    with right:
        st.subheader("Tax Haven Jurisdictions")
        haven_df = _safe_query("""
            SELECT jurisdiction_name AS Jurisdiction, COUNT(*) as Count
            FROM subsidiaries WHERE is_tax_haven = 1
            GROUP BY jurisdiction_code ORDER BY Count DESC
        """, conn)
        if not haven_df.empty:
            fig = px.bar(haven_df.head(15), x="Count", y="Jurisdiction",
                         orientation="h", color_discrete_sequence=["#E74C3C"])
            fig.update_layout(yaxis=dict(autorange="reversed"))
            _dark_layout(fig)
            st.plotly_chart(fig, width="stretch")

    # Financial context section (if financials available)
    if _table_exists(conn, "financials"):
        fin_df = _safe_query("""
            SELECT p.company_name, p.ticker, f.revenue, f.total_assets,
                   COUNT(DISTINCT ol.subsidiary_id) as total_subs,
                   SUM(CASE WHEN s.is_tax_haven = 1 THEN 1 ELSE 0 END) as haven_subs,
                   ROUND(100.0 * SUM(CASE WHEN s.is_tax_haven = 1 THEN 1 ELSE 0 END) / COUNT(DISTINCT ol.subsidiary_id), 1) as haven_pct
            FROM parents p
            JOIN financials f ON f.cik = p.cik
            JOIN ownership_links ol ON ol.parent_cik = p.cik
            JOIN subsidiaries s ON s.id = ol.subsidiary_id
            WHERE f.fiscal_year = (SELECT MAX(fiscal_year) FROM financials f2 WHERE f2.cik = f.cik)
                AND f.revenue IS NOT NULL AND f.revenue > 0
            GROUP BY p.cik HAVING haven_subs > 0
            ORDER BY f.revenue DESC
        """, conn)

        if not fin_df.empty:
            st.markdown("---")
            st.subheader("Tax Haven Usage by Top Revenue Companies")

            top20 = fin_df.head(20)
            fig = px.bar(
                top20, x="company_name", y="haven_pct",
                hover_data=["revenue", "haven_subs", "total_subs"],
                color="haven_pct",
                color_continuous_scale=["#2ECC71", "#E74C3C"],
                labels={"company_name": "Company", "haven_pct": "Haven %"},
            )
            fig.update_xaxes(tickangle=45)
            _dark_layout(fig)
            st.plotly_chart(fig, width="stretch")

            st.subheader("All Companies with Financial + Tax Haven Data")
            show_df = fin_df[["company_name", "ticker", "revenue", "total_assets", "total_subs", "haven_subs", "haven_pct"]].head(50).copy()
            show_df.columns = ["Company", "Ticker", "Revenue", "Assets", "Total Subs", "Haven Subs", "Haven %"]
            show_df["Revenue"] = show_df["Revenue"].apply(_fmt_currency)
            show_df["Assets"] = show_df["Assets"].apply(_fmt_currency)
            st.dataframe(show_df, width="stretch", hide_index=True)


# ---------------------------------------------------------------------------
# Tab 5: Data Quality
# ---------------------------------------------------------------------------
def _tab_data_quality(conn, stats):
    if not _table_exists(conn, "ownership_links"):
        st.warning("No data loaded. Run the pipeline first.")
        return

    # Top-level metrics
    c = st.columns(4)
    c[0].metric("Avg Quality Score", f"{stats['avg_quality']:.3f}")
    c[1].metric("Ownership Links", f"{stats['link_count']:,}")
    fin_coverage = stats.get("companies_with_financials", 0)
    c[2].metric("Financial Coverage", f"{fin_coverage}/{stats['parent_count']}")
    c[3].metric("Institutional Holders", f"{stats.get('institutional_holders', 0)}")

    # Quality score distribution
    qdf = _safe_query("""
        SELECT quality_score, COUNT(*) as count
        FROM ownership_links WHERE quality_score IS NOT NULL
        GROUP BY ROUND(quality_score, 2) ORDER BY quality_score
    """, conn)
    if not qdf.empty:
        fig = px.histogram(qdf, x="quality_score", y="count",
                           nbins=20, color_discrete_sequence=["#0984E3"],
                           labels={"quality_score": "Quality Score", "count": "Records"})
        _dark_layout(fig)
        st.plotly_chart(fig, width="stretch")

    left, right = st.columns(2)

    with left:
        # Parse method breakdown
        st.subheader("Parse Method Breakdown")
        method_df = _safe_query("""
            SELECT parse_method AS Method, COUNT(*) as Filings,
                   SUM(subsidiary_count) as "Total Subs",
                   ROUND(AVG(subsidiary_count), 1) as "Avg Subs"
            FROM filings WHERE parse_method IS NOT NULL
            GROUP BY parse_method ORDER BY Filings DESC
        """, conn)
        if not method_df.empty:
            st.dataframe(method_df, width="stretch", hide_index=True)

    with right:
        # Jurisdiction normalization
        st.subheader("Jurisdiction Normalization")
        norm_df = _safe_query("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN jurisdiction_code != '' THEN 1 ELSE 0 END) as normalized
            FROM subsidiaries
        """, conn)
        if not norm_df.empty and norm_df['total'].iloc[0] > 0:
            total = int(norm_df['total'].iloc[0])
            normalized = int(norm_df['normalized'].iloc[0])
            pct = normalized / total * 100
            nc = st.columns(3)
            nc[0].metric("Total", f"{total:,}")
            nc[1].metric("Normalized", f"{normalized:,}")
            nc[2].metric("Rate", f"{pct:.1f}%")

    # Enrichment coverage
    st.subheader("Enrichment Coverage")
    ec = st.columns(3)
    ec[0].metric(
        "Financial Coverage",
        f"{fin_coverage}/{stats['parent_count']}",
        f"{fin_coverage/max(stats['parent_count'],1)*100:.0f}%",
    )

    try:
        pct_row = conn.execute(
            "SELECT COUNT(*) as total, SUM(CASE WHEN ownership_pct IS NOT NULL THEN 1 ELSE 0 END) as with_pct FROM ownership_links"
        ).fetchone()
        pct_coverage = pct_row["with_pct"] if pct_row else 0
        total_links = pct_row["total"] if pct_row else 0
        ec[1].metric(
            "Ownership % Coverage",
            f"{pct_coverage}/{total_links}",
            f"{pct_coverage/max(total_links,1)*100:.0f}%",
        )
    except Exception:
        ec[1].metric("Ownership % Coverage", "N/A")

    ec[2].metric("Avg Quality Score", f"{stats['avg_quality']:.3f}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    st.title("SEC Corporate Subsidiary & Ownership Mapping")
    st.caption("Structured database of corporate subsidiary relationships from SEC EDGAR Exhibit 21 filings")

    conn = get_db()
    stats = _get_stats(conn)

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Overview",
        "Company Lookup",
        "Subsidiary Explorer",
        "Tax Havens",
        "Data Quality",
    ])

    with tab1:
        _tab_overview(conn, stats)
    with tab2:
        _tab_company_lookup(conn)
    with tab3:
        _tab_explorer(conn)
    with tab4:
        _tab_tax_havens(conn)
    with tab5:
        _tab_data_quality(conn, stats)

    # Footer
    st.markdown("---")
    st.markdown(
        "**Built by Nathan Goldberg** | "
        "nathanmauricegoldberg@gmail.com | "
        "[LinkedIn](https://www.linkedin.com/in/nathan-goldberg-62a44522a/)"
    )


if __name__ == "__main__":
    main()
