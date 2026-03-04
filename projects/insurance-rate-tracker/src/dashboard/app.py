"""Streamlit dashboard for Insurance Rate Filing Tracker.

Sections:
1. National Overview — KPI cards
2. Filing Explorer — Search/filter
3. Insurer Profile — Company deep-dive
4. Rate Change Analysis — Trends
5. State Comparison — Cross-state metrics
6. Line of Business Analysis — By insurance type
7. Consumer Impact — Largest increases
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

PROJECT_ROOT = Path(__file__).parent.parent.parent
DB_PATH = PROJECT_ROOT / "data" / "insurance_rate_filings.db"


@st.cache_resource
def get_db():
    if not DB_PATH.exists():
        st.error("Database not found. Run the pipeline first: `python -m src.cli pipeline`")
        st.stop()
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


@st.cache_data(ttl=300)
def load_filings():
    conn = get_db()
    df = pd.read_sql("SELECT * FROM rate_filings", conn)
    return df


@st.cache_data(ttl=300)
def load_insurers():
    conn = get_db()
    df = pd.read_sql("SELECT * FROM insurers", conn)
    return df


def main():
    st.set_page_config(
        page_title="Insurance Rate Filing Tracker",
        page_icon="📊",
        layout="wide",
    )

    st.title("Insurance Rate Filing Tracker")
    st.caption("Cross-state database of insurance rate filing data from state departments of insurance")

    try:
        df = load_filings()
    except Exception as e:
        st.error(f"Error loading data: {e}")
        st.info("Run the pipeline first: `python -m src.cli pipeline`")
        st.stop()
        return

    if df.empty:
        st.warning("No data in database. Run the pipeline first.")
        st.stop()
        return

    # Sidebar navigation
    section = st.sidebar.radio(
        "Navigate",
        ["National Overview", "Filing Explorer", "Insurer Profile",
         "Rate Change Analysis", "State Comparison",
         "Line of Business", "Consumer Impact"],
    )

    if section == "National Overview":
        _national_overview(df)
    elif section == "Filing Explorer":
        _filing_explorer(df)
    elif section == "Insurer Profile":
        _insurer_profile(df)
    elif section == "Rate Change Analysis":
        _rate_change_analysis(df)
    elif section == "State Comparison":
        _state_comparison(df)
    elif section == "Line of Business":
        _line_of_business(df)
    elif section == "Consumer Impact":
        _consumer_impact(df)

    # Footer
    st.markdown("---")
    st.markdown(
        "Built by **Nathan Goldberg** | "
        "[nathanmauricegoldberg@gmail.com](mailto:nathanmauricegoldberg@gmail.com) | "
        "[LinkedIn](https://www.linkedin.com/in/nathan-goldberg-62a44522a/)"
    )


def _national_overview(df: pd.DataFrame):
    """KPI cards and high-level metrics."""
    st.header("National Overview")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Filings", f"{len(df):,}")
    with col2:
        st.metric("States Covered", df["state"].nunique())
    with col3:
        rate_df = df[df["requested_rate_change_pct"].notna()]
        avg_rate = rate_df["requested_rate_change_pct"].mean() if not rate_df.empty else 0
        st.metric("Avg Rate Change", f"{avg_rate:.1f}%")
    with col4:
        approved = df[df["status"] == "approved"]
        rate = len(approved) / len(df) * 100 if len(df) > 0 else 0
        st.metric("Approval Rate", f"{rate:.0f}%")

    col5, col6, col7, col8 = st.columns(4)
    with col5:
        st.metric("Unique Companies", df["company_name"].nunique())
    with col6:
        st.metric("Data Sources", df["source"].nunique())
    with col7:
        quality_df = df[df["quality_score"].notna()]
        avg_q = quality_df["quality_score"].mean() if not quality_df.empty else 0
        st.metric("Avg Quality Score", f"{avg_q:.2f}")
    with col8:
        increases = df[df["filing_type"] == "rate_increase"]
        st.metric("Rate Increases", f"{len(increases):,}")

    # Filings by state
    st.subheader("Filings by State")
    state_counts = df["state"].value_counts().reset_index()
    state_counts.columns = ["State", "Count"]
    fig = px.bar(state_counts, x="State", y="Count",
                 color="Count", color_continuous_scale="Blues")
    fig.update_layout(template="plotly_dark", paper_bgcolor="#0E1117", plot_bgcolor="#0E1117")
    st.plotly_chart(fig, use_container_width=True)

    # Filings by source
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("By Data Source")
        source_counts = df["source"].value_counts().reset_index()
        source_counts.columns = ["Source", "Count"]
        fig2 = px.pie(source_counts, values="Count", names="Source", hole=0.4)
        fig2.update_layout(template="plotly_dark", paper_bgcolor="#0E1117")
        st.plotly_chart(fig2, use_container_width=True)

    with col_b:
        st.subheader("By Status")
        status_counts = df["status"].value_counts().reset_index()
        status_counts.columns = ["Status", "Count"]
        fig3 = px.pie(status_counts, values="Count", names="Status", hole=0.4)
        fig3.update_layout(template="plotly_dark", paper_bgcolor="#0E1117")
        st.plotly_chart(fig3, use_container_width=True)


def _filing_explorer(df: pd.DataFrame):
    """Search and filter filings."""
    st.header("Filing Explorer")

    col1, col2, col3 = st.columns(3)
    with col1:
        states = ["All"] + sorted(df["state"].dropna().unique().tolist())
        sel_state = st.selectbox("State", states)
    with col2:
        lines = ["All"] + sorted(df["line_of_business"].dropna().unique().tolist())
        sel_line = st.selectbox("Line of Business", lines)
    with col3:
        statuses = ["All"] + sorted(df["status"].dropna().unique().tolist())
        sel_status = st.selectbox("Status", statuses)

    col4, col5 = st.columns(2)
    with col4:
        search = st.text_input("Company Search", "")
    with col5:
        sources = ["All"] + sorted(df["source"].dropna().unique().tolist())
        sel_source = st.selectbox("Source", sources)

    filtered = df.copy()
    if sel_state != "All":
        filtered = filtered[filtered["state"] == sel_state]
    if sel_line != "All":
        filtered = filtered[filtered["line_of_business"] == sel_line]
    if sel_status != "All":
        filtered = filtered[filtered["status"] == sel_status]
    if sel_source != "All":
        filtered = filtered[filtered["source"] == sel_source]
    if search:
        mask = (
            filtered["company_name"].str.contains(search, case=False, na=False) |
            filtered["canonical_company_name"].str.contains(search, case=False, na=False)
        )
        filtered = filtered[mask]

    st.write(f"**{len(filtered):,} filings** matching filters")

    display_cols = [
        "filing_id", "company_name", "state", "line_of_business",
        "filing_type", "status", "requested_rate_change_pct",
        "approved_rate_change_pct", "filing_date", "effective_date",
        "quality_score",
    ]
    available = [c for c in display_cols if c in filtered.columns]
    st.dataframe(filtered[available].head(500), use_container_width=True, height=500)


def _insurer_profile(df: pd.DataFrame):
    """Deep-dive into a specific insurer."""
    st.header("Insurer Profile")

    # Use canonical name if available, fall back to company name
    name_col = "canonical_company_name" if "canonical_company_name" in df.columns else "company_name"
    companies = sorted(df[name_col].dropna().unique().tolist())
    if not companies:
        companies = sorted(df["company_name"].dropna().unique().tolist())

    selected = st.selectbox("Select Company", companies)
    if not selected:
        return

    mask = (df[name_col] == selected) | (df["company_name"] == selected)
    company_df = df[mask]

    if company_df.empty:
        st.warning("No filings found for this company")
        return

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Filings", len(company_df))
    with col2:
        st.metric("States", company_df["state"].nunique())
    with col3:
        rate_df = company_df[company_df["requested_rate_change_pct"].notna()]
        avg = rate_df["requested_rate_change_pct"].mean() if not rate_df.empty else 0
        st.metric("Avg Rate Change", f"{avg:.1f}%")
    with col4:
        approved = company_df[company_df["status"] == "approved"]
        rate = len(approved) / len(company_df) * 100 if len(company_df) > 0 else 0
        st.metric("Approval Rate", f"{rate:.0f}%")

    # Filings by state
    st.subheader("Filings by State")
    state_counts = company_df["state"].value_counts().reset_index()
    state_counts.columns = ["State", "Count"]
    fig = px.bar(state_counts, x="State", y="Count")
    fig.update_layout(template="plotly_dark", paper_bgcolor="#0E1117", plot_bgcolor="#0E1117")
    st.plotly_chart(fig, use_container_width=True)

    # Filing history
    st.subheader("Filing History")
    display_cols = [
        "filing_id", "state", "line_of_business", "filing_type", "status",
        "requested_rate_change_pct", "approved_rate_change_pct",
        "filing_date", "effective_date",
    ]
    available = [c for c in display_cols if c in company_df.columns]
    st.dataframe(company_df[available], use_container_width=True)


def _rate_change_analysis(df: pd.DataFrame):
    """Rate change trends and distributions."""
    st.header("Rate Change Analysis")

    rate_df = df[df["requested_rate_change_pct"].notna()].copy()
    if rate_df.empty:
        st.warning("No rate change data available")
        return

    # Distribution of rate changes
    st.subheader("Distribution of Requested Rate Changes")
    fig = px.histogram(
        rate_df, x="requested_rate_change_pct", nbins=50,
        labels={"requested_rate_change_pct": "Rate Change %"},
        color_discrete_sequence=["#0984E3"],
    )
    fig.update_layout(template="plotly_dark", paper_bgcolor="#0E1117", plot_bgcolor="#0E1117")
    st.plotly_chart(fig, use_container_width=True)

    # Requested vs Approved
    both_df = rate_df[rate_df["approved_rate_change_pct"].notna()]
    if not both_df.empty:
        st.subheader("Requested vs Approved Rate Changes")
        fig2 = px.scatter(
            both_df, x="requested_rate_change_pct", y="approved_rate_change_pct",
            color="state", hover_data=["company_name", "line_of_business"],
            labels={
                "requested_rate_change_pct": "Requested %",
                "approved_rate_change_pct": "Approved %",
            },
        )
        fig2.add_shape(type="line", x0=-50, y0=-50, x1=100, y1=100,
                       line=dict(color="gray", dash="dash"))
        fig2.update_layout(template="plotly_dark", paper_bgcolor="#0E1117", plot_bgcolor="#0E1117")
        st.plotly_chart(fig2, use_container_width=True)

    # Rate changes by line of business
    st.subheader("Average Rate Change by Line of Business")
    lob_avg = rate_df.groupby("line_of_business")["requested_rate_change_pct"].agg(["mean", "count"]).reset_index()
    lob_avg.columns = ["Line of Business", "Avg Change %", "Count"]
    lob_avg = lob_avg[lob_avg["Count"] >= 5].sort_values("Avg Change %", ascending=False)
    fig3 = px.bar(lob_avg, x="Line of Business", y="Avg Change %",
                  color="Avg Change %", color_continuous_scale="RdYlGn_r")
    fig3.update_layout(template="plotly_dark", paper_bgcolor="#0E1117", plot_bgcolor="#0E1117")
    st.plotly_chart(fig3, use_container_width=True)


def _state_comparison(df: pd.DataFrame):
    """Cross-state comparison metrics."""
    st.header("State Comparison")

    # Average rate change by state
    rate_df = df[df["requested_rate_change_pct"].notna()]
    if not rate_df.empty:
        state_avg = rate_df.groupby("state").agg(
            avg_requested=("requested_rate_change_pct", "mean"),
            count=("filing_id", "count"),
        ).reset_index()
        state_avg = state_avg[state_avg["count"] >= 3]

        st.subheader("Average Requested Rate Change by State")
        fig = px.bar(
            state_avg.sort_values("avg_requested", ascending=False),
            x="state", y="avg_requested",
            color="avg_requested", color_continuous_scale="RdYlGn_r",
            labels={"avg_requested": "Avg Rate Change %", "state": "State"},
        )
        fig.update_layout(template="plotly_dark", paper_bgcolor="#0E1117", plot_bgcolor="#0E1117")
        st.plotly_chart(fig, use_container_width=True)

    # Approval rates by state
    st.subheader("Filing Status by State")
    status_by_state = df.groupby(["state", "status"]).size().reset_index(name="count")
    fig2 = px.bar(status_by_state, x="state", y="count", color="status", barmode="stack")
    fig2.update_layout(template="plotly_dark", paper_bgcolor="#0E1117", plot_bgcolor="#0E1117")
    st.plotly_chart(fig2, use_container_width=True)

    # Filing volume by state
    st.subheader("Filing Volume by State")
    state_counts = df["state"].value_counts().reset_index()
    state_counts.columns = ["State", "Count"]
    fig3 = px.bar(state_counts, x="State", y="Count",
                  color="Count", color_continuous_scale="Blues")
    fig3.update_layout(template="plotly_dark", paper_bgcolor="#0E1117", plot_bgcolor="#0E1117")
    st.plotly_chart(fig3, use_container_width=True)


def _line_of_business(df: pd.DataFrame):
    """Analysis by line of business."""
    st.header("Line of Business Analysis")

    lob_counts = df["line_of_business"].value_counts().reset_index()
    lob_counts.columns = ["Line", "Count"]

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Filing Volume by Line")
        fig = px.bar(lob_counts, x="Line", y="Count",
                     color="Count", color_continuous_scale="Blues")
        fig.update_layout(template="plotly_dark", paper_bgcolor="#0E1117", plot_bgcolor="#0E1117")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Distribution")
        fig2 = px.pie(lob_counts, values="Count", names="Line", hole=0.4)
        fig2.update_layout(template="plotly_dark", paper_bgcolor="#0E1117")
        st.plotly_chart(fig2, use_container_width=True)

    # Rate changes by line
    rate_df = df[df["requested_rate_change_pct"].notna()]
    if not rate_df.empty:
        st.subheader("Rate Change Distribution by Line")
        fig3 = px.box(
            rate_df, x="line_of_business", y="requested_rate_change_pct",
            labels={"requested_rate_change_pct": "Rate Change %", "line_of_business": "Line"},
        )
        fig3.update_layout(template="plotly_dark", paper_bgcolor="#0E1117", plot_bgcolor="#0E1117")
        st.plotly_chart(fig3, use_container_width=True)

    # Top companies per line
    st.subheader("Top Companies by Filing Volume")
    sel_line = st.selectbox("Select Line", sorted(df["line_of_business"].dropna().unique()))
    line_df = df[df["line_of_business"] == sel_line]
    top = line_df["company_name"].value_counts().head(15).reset_index()
    top.columns = ["Company", "Filings"]
    fig4 = px.bar(top, x="Filings", y="Company", orientation="h")
    fig4.update_layout(template="plotly_dark", paper_bgcolor="#0E1117", plot_bgcolor="#0E1117", yaxis=dict(autorange="reversed"))
    st.plotly_chart(fig4, use_container_width=True)


def _consumer_impact(df: pd.DataFrame):
    """Highlight largest rate increases and consumer impact."""
    st.header("Consumer Impact")

    rate_df = df[df["requested_rate_change_pct"].notna()].copy()
    if rate_df.empty:
        st.warning("No rate change data available")
        return

    # Top 20 largest rate increase requests
    st.subheader("Largest Rate Increase Requests")
    increases = rate_df[rate_df["requested_rate_change_pct"] > 0].sort_values(
        "requested_rate_change_pct", ascending=False
    ).head(20)
    display_cols = [
        "company_name", "state", "line_of_business",
        "requested_rate_change_pct", "approved_rate_change_pct",
        "status", "filing_date",
    ]
    available = [c for c in display_cols if c in increases.columns]
    st.dataframe(increases[available], use_container_width=True)

    # Companies with most rate increases
    st.subheader("Companies with Most Rate Increase Filings")
    increase_df = rate_df[rate_df["filing_type"] == "rate_increase"]
    if not increase_df.empty:
        top_companies = increase_df["company_name"].value_counts().head(15).reset_index()
        top_companies.columns = ["Company", "Increase Filings"]
        fig = px.bar(top_companies, x="Increase Filings", y="Company", orientation="h",
                     color="Increase Filings", color_continuous_scale="Reds")
        fig.update_layout(template="plotly_dark", paper_bgcolor="#0E1117", plot_bgcolor="#0E1117",
                          yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig, use_container_width=True)

    # Rate increase vs decrease ratio by state
    st.subheader("Rate Increase vs Decrease Ratio by State")
    increases_by_state = rate_df[rate_df["requested_rate_change_pct"] > 0].groupby("state").size()
    decreases_by_state = rate_df[rate_df["requested_rate_change_pct"] < 0].groupby("state").size()
    ratio_df = pd.DataFrame({
        "Increases": increases_by_state,
        "Decreases": decreases_by_state,
    }).fillna(0).reset_index()
    ratio_df.columns = ["State", "Increases", "Decreases"]
    fig2 = px.bar(ratio_df, x="State", y=["Increases", "Decreases"], barmode="group")
    fig2.update_layout(template="plotly_dark", paper_bgcolor="#0E1117", plot_bgcolor="#0E1117")
    st.plotly_chart(fig2, use_container_width=True)


if __name__ == "__main__":
    main()
