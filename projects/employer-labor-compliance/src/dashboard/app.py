"""Streamlit dashboard for Employer Labor Compliance Tracker."""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.storage.database import get_connection, init_db, get_stats

_NO_DATA_MSG = "No data loaded yet. Run the pipeline first: `python -m src.cli pipeline`"

CASE_TYPE_LABELS = {
    "CA": "Employer Unfair Labor Practice",
    "CB": "Union Unfair Labor Practice",
    "CC": "Union Unfair Labor Practice (secondary)",
    "CD": "Jurisdictional Dispute",
    "CE": "Employer ULP (dues/fees)",
    "CG": "Union ULP (dues/fees)",
    "CP": "Union Picketing",
    "RC": "Union Representation Petition",
    "RD": "Decertification Petition",
    "RM": "Employer-Filed Election Petition",
    "UC": "Unit Clarification",
    "UD": "Deauthorization Petition",
    "WH": "Wage/Hour Related",
    "AC": "Amendment of Certification",
}

US_STATES = {
    'AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL','IN','IA',
    'KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ',
    'NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT',
    'VA','WA','WV','WI','WY','DC','PR',
}

_DARK = dict(template="plotly_dark", paper_bgcolor="#0E1117", plot_bgcolor="#0E1117")

# SQL fragment to merge well-known employer name variants
# Uses prefix matching for large brands with many location suffixes
_EMPLOYER_MERGE = """
    CASE
        WHEN name_normalized IN ('U S POSTAL SERVICE','US POSTAL SERVICE','USPS')
             OR name_normalized LIKE 'UNITED STATES POSTAL SERVICE%'
             THEN 'UNITED STATES POSTAL SERVICE'
        WHEN name_normalized = 'UPS' OR name_normalized LIKE 'UNITED PARCEL SERVICE%'
             THEN 'UNITED PARCEL SERVICE'
        WHEN name_normalized LIKE 'WALMART%' OR name_normalized LIKE 'WAL MART%'
             THEN 'WALMART'
        WHEN name_normalized LIKE 'AMAZON%' OR name_normalized LIKE 'AMAZONCOM%'
             THEN 'AMAZON'
        WHEN name_normalized LIKE 'STARBUCKS%' THEN 'STARBUCKS'
        WHEN name_normalized LIKE 'MCDONALD%' THEN 'MCDONALDS'
        WHEN name_normalized LIKE 'TARGET%' AND LENGTH(name_normalized) <= 20
             THEN 'TARGET'
        WHEN name_normalized IN ('AT T','ATT','AT AND T') OR name_normalized LIKE 'AT AND T %'
             OR name_normalized LIKE 'AT T %' THEN 'AT AND T'
        WHEN name_normalized LIKE 'FEDEX%' OR name_normalized LIKE 'FEDERAL EXPRESS%'
             THEN 'FEDEX'
        WHEN name_normalized LIKE 'HOME DEPOT%' THEN 'HOME DEPOT'
        WHEN name_normalized LIKE 'KROGER%' THEN 'KROGER'
        WHEN name_normalized LIKE 'DOLLAR GENERAL%' THEN 'DOLLAR GENERAL'
        WHEN name_normalized LIKE 'DOLLAR TREE%' THEN 'DOLLAR TREE'
        ELSE name_normalized
    END
"""


def _safe_query(sql, conn, params=()):
    try:
        return pd.read_sql_query(sql, conn, params=params if params else None)
    except Exception:
        return pd.DataFrame()


def _table_exists(conn, name):
    try:
        r = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
        return r is not None
    except Exception:
        return False


def _safe_fetchone(conn, sql, params=(), default=0):
    try:
        row = conn.execute(sql, params).fetchone()
        return row[0] if row and row[0] is not None else default
    except Exception:
        return default


def get_db():
    conn = get_connection()
    init_db(conn)
    return conn


def _safe_get_stats(conn):
    try:
        return get_stats(conn)
    except Exception:
        return {
            "whd_count": 0, "osha_count": 0, "nlrb_count": 0,
            "employer_count": 0, "cross_link_count": 0,
            "total_back_wages": 0, "total_whd_penalties": 0,
            "total_osha_penalties": 0, "total_fatalities": 0,
            "employees_affected": 0,
            "avg_quality": {"whd": 0, "osha": 0, "nlrb": 0},
            "top_states": [],
        }


def main():
    st.set_page_config(
        page_title="Employer Labor Compliance Tracker",
        page_icon="⚖️",
        layout="wide",
    )

    st.title("⚖️ Employer Labor Compliance Tracker")
    st.markdown("*Cross-agency employer labor enforcement database — NLRB + WHD + OSHA*")

    conn = get_db()

    page = st.sidebar.radio("Navigate", [
        "Overview",
        "Geographic Distribution",
        "Multi-Agency Offenders",
        "Top Employers",
        "Temporal Trends",
        "WHD Wage Theft",
        "OSHA Inspections",
        "NLRB Labor Relations",
        "Employer Search",
    ])

    pages = {
        "Overview": show_overview,
        "Geographic Distribution": show_geographic,
        "Multi-Agency Offenders": show_multi_agency,
        "Top Employers": show_top_employers,
        "Temporal Trends": show_trends,
        "WHD Wage Theft": show_whd,
        "OSHA Inspections": show_osha,
        "NLRB Labor Relations": show_nlrb,
        "Employer Search": show_employer_search,
    }
    pages[page](conn)

    st.divider()
    st.markdown(
        """
        <div style='text-align: center; color: #888; padding: 20px;'>
            Built by Nathan Goldberg |
            <a href='mailto:nathanmauricegoldberg@gmail.com'>nathanmauricegoldberg@gmail.com</a> |
            <a href='https://www.linkedin.com/in/nathan-goldberg-62a44522a/'>LinkedIn</a><br>
            Data sourced from NLRB, DOL Wage & Hour Division, and OSHA public records.
        </div>
        """,
        unsafe_allow_html=True,
    )


# --- OVERVIEW ---

def show_overview(conn):
    st.header("Overview")

    nlrb = _safe_fetchone(conn, "SELECT COUNT(*) FROM nlrb_cases")
    whd = _safe_fetchone(conn, "SELECT COUNT(*) FROM whd_cases")
    osha = _safe_fetchone(conn, "SELECT COUNT(*) FROM osha_inspections")
    employers = _safe_fetchone(conn, "SELECT COUNT(*) FROM employers")

    if nlrb + whd + osha == 0:
        st.warning(_NO_DATA_MSG)
        return

    # Row 1: Record counts
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("NLRB Cases", f"{nlrb:,}")
    c2.metric("WHD Cases", f"{whd:,}")
    c3.metric("OSHA Inspections", f"{osha:,}")
    c4.metric("Unique Employers", f"{employers:,}")

    # Row 2: Financial & impact (only non-zero metrics)
    back_wages = _safe_fetchone(conn, "SELECT COALESCE(SUM(back_wages_owed),0) FROM whd_cases")
    whd_penalties = _safe_fetchone(conn, "SELECT COALESCE(SUM(civil_penalties),0) FROM whd_cases")
    employees = _safe_fetchone(conn, "SELECT COALESCE(SUM(employees_affected),0) FROM whd_cases")
    multi_agency = _safe_fetchone(conn, """
        SELECT COUNT(*) FROM employers
        WHERE (CASE WHEN whd_case_count > 0 THEN 1 ELSE 0 END +
               CASE WHEN osha_inspection_count > 0 THEN 1 ELSE 0 END +
               CASE WHEN nlrb_case_count > 0 THEN 1 ELSE 0 END) >= 2
    """)
    open_nlrb = _safe_fetchone(conn, "SELECT COUNT(*) FROM nlrb_cases WHERE status = 'Open'")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Total Back Wages", f"${back_wages:,.0f}")
    c6.metric("WHD Civil Penalties", f"${whd_penalties:,.0f}")
    c7.metric("Workers Affected", f"{employees:,}")
    c8.metric("Multi-Agency Offenders", f"{multi_agency:,}")

    three_agency = _safe_fetchone(conn, """
        SELECT COUNT(*) FROM employers
        WHERE whd_case_count > 0 AND osha_inspection_count > 0 AND nlrb_case_count > 0
    """)
    c9, c10, c11, c12 = st.columns(4)
    c9.metric("NLRB Open Cases", f"{open_nlrb:,}")
    c10.metric("All 3 Agencies", f"{three_agency:,}")
    c11.metric("Total Records", f"{nlrb + whd + osha:,}")
    c12.metric("Federal Laws Tracked", "6")

    st.markdown("---")

    # Source breakdown chart
    left, right = st.columns(2)
    with left:
        df_sources = pd.DataFrame({
            "Source": ["NLRB (Labor Relations)", "WHD (Wage & Hour)", "OSHA (Safety)"],
            "Records": [nlrb, whd, osha],
        })
        fig = px.bar(df_sources, x="Source", y="Records", title="Records by Federal Agency",
                     color="Source", color_discrete_sequence=["#3498db", "#e74c3c", "#f39c12"])
        fig.update_layout(**_DARK, height=400, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with right:
        # WHD violation types
        df_viol = _safe_query("""
            SELECT
                SUM(flsa_violated) as FLSA,
                SUM(mspa_violated) as MSPA,
                SUM(h1b_violated) as "H-1B",
                SUM(fmla_violated) as FMLA,
                SUM(sca_violated) as SCA,
                SUM(dba_violated) as DBA
            FROM whd_cases
        """, conn)
        if not df_viol.empty:
            viol_data = df_viol.iloc[0].to_dict()
            df_v = pd.DataFrame([(k, int(v)) for k, v in viol_data.items() if v and v > 0],
                                columns=["Law", "Cases"])
            if not df_v.empty:
                fig = px.pie(df_v, values="Cases", names="Law", title="WHD Violations by Federal Law",
                             color_discrete_sequence=px.colors.qualitative.Set2)
                fig.update_layout(**_DARK, height=400)
                st.plotly_chart(fig, use_container_width=True)


# --- GEOGRAPHIC ---

def show_geographic(conn):
    st.header("Geographic Distribution")

    # Combine all three sources by state
    df = _safe_query("""
        SELECT state,
               SUM(nlrb) as nlrb_cases, SUM(whd) as whd_cases, SUM(osha) as osha_inspections,
               SUM(nlrb + whd + osha) as total,
               SUM(bw) as back_wages, SUM(pen) as penalties
        FROM (
            SELECT state, COUNT(*) as nlrb, 0 as whd, 0 as osha, 0 as bw, 0 as pen
            FROM nlrb_cases WHERE state != '' GROUP BY state
            UNION ALL
            SELECT state, 0, COUNT(*), 0, SUM(COALESCE(back_wages_owed,0)), SUM(COALESCE(civil_penalties,0))
            FROM whd_cases WHERE state != '' GROUP BY state
            UNION ALL
            SELECT site_state, 0, 0, COUNT(*), 0, SUM(COALESCE(total_current_penalty,0))
            FROM osha_inspections WHERE site_state != '' GROUP BY site_state
        ) GROUP BY state
        HAVING LENGTH(state) = 2
        ORDER BY total DESC
    """, conn)

    if df.empty:
        st.info("No geographic data.")
        return

    # Filter to valid US states
    df = df[df["state"].isin(US_STATES)]

    metric = st.selectbox("Color map by:", [
        "All Enforcement Actions", "NLRB Cases", "WHD Wage Theft Cases",
        "OSHA Inspections", "Total Back Wages",
    ])
    col_map = {
        "All Enforcement Actions": "total",
        "NLRB Cases": "nlrb_cases",
        "WHD Wage Theft Cases": "whd_cases",
        "OSHA Inspections": "osha_inspections",
        "Total Back Wages": "back_wages",
    }
    color_col = col_map[metric]

    # Use log scale for better color distribution
    df["_color"] = np.log1p(df[color_col].astype(float))

    fig = px.choropleth(
        df, locations="state", locationmode="USA-states",
        color="_color", scope="usa",
        color_continuous_scale="YlOrRd",
        title=f"{metric} by State",
        hover_data={
            "_color": False,
            "nlrb_cases": ":,",
            "whd_cases": ":,",
            "osha_inspections": ":,",
            "back_wages": ":$,.0f",
        },
    )
    fig.update_layout(**_DARK, height=500)
    fig.update_coloraxes(showscale=False)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("State Breakdown")
    df_display = df[["state", "total", "nlrb_cases", "whd_cases", "osha_inspections", "back_wages"]].copy()
    df_display.columns = ["State", "Total", "NLRB", "WHD", "OSHA", "Back Wages"]
    st.dataframe(
        df_display.style.format({"Back Wages": "${:,.0f}"}),
        use_container_width=True, height=400,
    )


# --- MULTI-AGENCY OFFENDERS ---

def show_multi_agency(conn):
    st.header("Multi-Agency Offenders")
    st.markdown("*Employers flagged across 2+ federal agencies — the highest-risk employers.*")

    multi_count = _safe_fetchone(conn, """
        SELECT COUNT(*) FROM employers
        WHERE (CASE WHEN whd_case_count > 0 THEN 1 ELSE 0 END +
               CASE WHEN osha_inspection_count > 0 THEN 1 ELSE 0 END +
               CASE WHEN nlrb_case_count > 0 THEN 1 ELSE 0 END) >= 2
    """)
    three_agency = _safe_fetchone(conn, """
        SELECT COUNT(*) FROM employers
        WHERE whd_case_count > 0 AND osha_inspection_count > 0 AND nlrb_case_count > 0
    """)

    c1, c2 = st.columns(2)
    c1.metric("2+ Agency Offenders", f"{multi_count:,}")
    c2.metric("All 3 Agencies", f"{three_agency:,}")

    # Top multi-agency offenders — merge name variants, filter UNKNOWN
    df = _safe_query(f"""
        SELECT merged_name as employer,
               SUM(whd_case_count) as whd,
               SUM(osha_inspection_count) as osha,
               SUM(nlrb_case_count) as nlrb,
               SUM(whd_case_count + osha_inspection_count + nlrb_case_count) as total,
               SUM(total_back_wages) as total_back_wages
        FROM (
            SELECT {_EMPLOYER_MERGE} as merged_name,
                   whd_case_count, osha_inspection_count, nlrb_case_count,
                   total_back_wages
            FROM employers
            WHERE (CASE WHEN whd_case_count > 0 THEN 1 ELSE 0 END +
                   CASE WHEN osha_inspection_count > 0 THEN 1 ELSE 0 END +
                   CASE WHEN nlrb_case_count > 0 THEN 1 ELSE 0 END) >= 2
              AND name_normalized NOT IN ('UNKNOWN', '', 'NONE', 'N A')
        )
        GROUP BY merged_name
        HAVING merged_name NOT IN ('UNKNOWN', '', 'NONE', 'N A')
        ORDER BY total DESC
        LIMIT 100
    """, conn)

    if df.empty:
        st.info("No multi-agency offenders found.")
        return

    st.subheader("Top 100 Multi-Agency Offenders")
    st.dataframe(
        df.style.format({
            "total_back_wages": "${:,.0f}",
        }),
        use_container_width=True, height=500,
    )

    # Chart: top 20 by total actions
    fig = px.bar(
        df.head(20), x="total", y="employer", orientation="h",
        title="Top 20 Multi-Agency Offenders (Total Actions Across Agencies)",
        color="total", color_continuous_scale="OrRd",
    )
    fig.update_layout(**_DARK, height=600, yaxis=dict(autorange="reversed"), showlegend=False)
    st.plotly_chart(fig, use_container_width=True)


# --- TOP EMPLOYERS ---

def show_top_employers(conn):
    st.header("Top Employers")

    sort_by = st.selectbox("Rank by:", [
        "Total Actions (All Agencies)", "NLRB Cases", "WHD Cases",
        "OSHA Inspections", "Total Back Wages",
    ])
    sort_col = {
        "Total Actions (All Agencies)": "total",
        "NLRB Cases": "nlrb",
        "WHD Cases": "whd",
        "OSHA Inspections": "osha",
        "Total Back Wages": "total_back_wages",
    }

    df = _safe_query(f"""
        SELECT merged_name as employer,
               SUM(nlrb_case_count) as nlrb,
               SUM(whd_case_count) as whd,
               SUM(osha_inspection_count) as osha,
               SUM(whd_case_count + osha_inspection_count + nlrb_case_count) as total,
               SUM(total_back_wages) as total_back_wages
        FROM (
            SELECT {_EMPLOYER_MERGE} as merged_name,
                   whd_case_count, osha_inspection_count, nlrb_case_count,
                   total_back_wages
            FROM employers
            WHERE name_normalized NOT IN ('UNKNOWN', '', 'NONE', 'N A')
        )
        GROUP BY merged_name
        HAVING merged_name NOT IN ('UNKNOWN', '', 'NONE', 'N A')
        ORDER BY {sort_col[sort_by]} DESC
        LIMIT 50
    """, conn)

    if df.empty:
        st.info("No employer data.")
        return

    fig = px.bar(
        df.head(25), x="total", y="employer", orientation="h",
        title=f"Top 25 Employers by {sort_by}",
        color="total", color_continuous_scale="Reds",
    )
    fig.update_layout(**_DARK, height=700, yaxis=dict(autorange="reversed"), showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        df.style.format({"total_back_wages": "${:,.0f}"}),
        use_container_width=True, height=400,
    )


# --- TEMPORAL TRENDS ---

def show_trends(conn):
    st.header("Temporal Trends")

    # Show each agency separately with its actual date range
    # NLRB: 2015-present, WHD: 2015-2018, OSHA: 2005-2017

    tab1, tab2, tab3 = st.tabs(["NLRB (2015-Present)", "OSHA (2005-2017)", "WHD (2015-2018)"])

    with tab1:
        df_nlrb = _safe_query("""
            SELECT substr(date_filed,1,4) as year, COUNT(*) as cases
            FROM nlrb_cases WHERE date_filed >= '2015' AND date_filed != ''
            GROUP BY year ORDER BY year
        """, conn)
        if not df_nlrb.empty:
            fig = px.bar(df_nlrb, x="year", y="cases",
                         title="NLRB Cases Filed Per Year",
                         color_discrete_sequence=["#3498db"])
            fig.update_layout(**_DARK, height=400)
            st.plotly_chart(fig, use_container_width=True)

    with tab2:
        df_osha = _safe_query("""
            SELECT substr(open_date,1,4) as year, COUNT(*) as inspections
            FROM osha_inspections WHERE open_date >= '2005' AND open_date != ''
            GROUP BY year ORDER BY year
        """, conn)
        if not df_osha.empty:
            fig = px.bar(df_osha, x="year", y="inspections",
                         title="OSHA Inspections Per Year",
                         color_discrete_sequence=["#f39c12"])
            fig.update_layout(**_DARK, height=400)
            st.plotly_chart(fig, use_container_width=True)

    with tab3:
        df_whd = _safe_query("""
            SELECT substr(findings_start_date,1,4) as year, COUNT(*) as cases,
                   SUM(COALESCE(back_wages_owed,0)) as back_wages
            FROM whd_cases WHERE findings_start_date >= '2005' AND findings_start_date != ''
            GROUP BY year ORDER BY year
        """, conn)
        if not df_whd.empty:
            fig = px.bar(df_whd, x="year", y="cases",
                         title="WHD Wage Theft Cases Per Year",
                         color_discrete_sequence=["#e74c3c"])
            fig.update_layout(**_DARK, height=400)
            st.plotly_chart(fig, use_container_width=True)

    # Combined annual comparison for overlapping years only
    st.subheader("Combined View (Overlapping Years)")
    df_annual = _safe_query("""
        SELECT year, SUM(nlrb) as NLRB, SUM(whd) as WHD, SUM(osha) as OSHA FROM (
            SELECT substr(date_filed,1,4) as year, COUNT(*) as nlrb, 0 as whd, 0 as osha
            FROM nlrb_cases WHERE date_filed >= '2015' AND date_filed != '' GROUP BY year
            UNION ALL
            SELECT substr(findings_start_date,1,4), 0, COUNT(*), 0
            FROM whd_cases WHERE findings_start_date >= '2015' AND findings_start_date != '' GROUP BY 1
            UNION ALL
            SELECT substr(open_date,1,4), 0, 0, COUNT(*)
            FROM osha_inspections WHERE open_date >= '2015' AND open_date != '' GROUP BY 1
        ) GROUP BY year
        HAVING year >= '2015' AND year <= '2018'
        ORDER BY year
    """, conn)
    if not df_annual.empty and len(df_annual) > 0:
        fig2 = px.bar(df_annual, x="year", y=["NLRB", "WHD", "OSHA"],
                       title="Annual Enforcement Actions — All 3 Agencies (2015-2018)",
                       barmode="group",
                       color_discrete_sequence=["#3498db", "#e74c3c", "#f39c12"])
        fig2.update_layout(**_DARK, height=400)
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No overlapping year data available.")


# --- WHD WAGE THEFT ---

def show_whd(conn):
    st.header("WHD Wage & Hour Division")

    whd_count = _safe_fetchone(conn, "SELECT COUNT(*) FROM whd_cases")
    if whd_count == 0:
        st.info("No WHD data loaded.")
        return

    back_wages = _safe_fetchone(conn, "SELECT COALESCE(SUM(back_wages_owed),0) FROM whd_cases")
    penalties = _safe_fetchone(conn, "SELECT COALESCE(SUM(civil_penalties),0) FROM whd_cases")
    employees = _safe_fetchone(conn, "SELECT COALESCE(SUM(employees_affected),0) FROM whd_cases")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("WHD Cases", f"{whd_count:,}")
    c2.metric("Back Wages Recovered", f"${back_wages:,.0f}")
    c3.metric("Civil Penalties", f"${penalties:,.0f}")
    c4.metric("Workers Affected", f"{employees:,}")

    left, right = st.columns(2)

    with left:
        # Violation types pie
        df_viol = _safe_query("""
            SELECT
                SUM(flsa_violated) as FLSA,
                SUM(mspa_violated) as MSPA,
                SUM(h1b_violated) as "H-1B",
                SUM(fmla_violated) as FMLA,
                SUM(sca_violated) as "SCA/CWHSSA",
                SUM(dba_violated) as "Davis-Bacon"
            FROM whd_cases
        """, conn)
        if not df_viol.empty:
            viol_data = df_viol.iloc[0].to_dict()
            df_v = pd.DataFrame([(k, int(v)) for k, v in viol_data.items() if v and v > 0],
                                columns=["Law", "Cases"])
            if not df_v.empty:
                fig = px.pie(df_v, values="Cases", names="Law", title="Violations by Federal Law")
                fig.update_layout(**_DARK, height=400)
                st.plotly_chart(fig, use_container_width=True)

    with right:
        # Top states by back wages
        df_states = _safe_query("""
            SELECT state, COUNT(*) as cases, SUM(COALESCE(back_wages_owed,0)) as back_wages,
                   SUM(COALESCE(employees_affected,0)) as employees
            FROM whd_cases WHERE state != '' AND LENGTH(state) = 2
            GROUP BY state ORDER BY back_wages DESC LIMIT 15
        """, conn)
        if not df_states.empty:
            fig = px.bar(df_states, x="state", y="back_wages",
                         title="Top 15 States by Back Wages Owed",
                         color="back_wages", color_continuous_scale="Reds")
            fig.update_layout(**_DARK, height=400, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

    # Top industries
    st.subheader("Top Industries by WHD Cases")
    df_ind = _safe_query("""
        SELECT naics_description as industry, COUNT(*) as cases,
               SUM(COALESCE(back_wages_owed,0)) as back_wages,
               SUM(COALESCE(employees_affected,0)) as employees
        FROM whd_cases WHERE naics_description != ''
        GROUP BY naics_description ORDER BY cases DESC LIMIT 20
    """, conn)
    if not df_ind.empty:
        fig = px.bar(df_ind, x="cases", y="industry", orientation="h",
                     title="Top 20 Industries by WHD Cases",
                     color="back_wages", color_continuous_scale="OrRd")
        fig.update_layout(**_DARK, height=600, yaxis=dict(autorange="reversed"), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    # Top employers by back wages
    st.subheader("Top Employers by Back Wages")
    df_emp = _safe_query("""
        SELECT employer_normalized as employer, state, COUNT(*) as cases,
               SUM(COALESCE(back_wages_owed,0)) as back_wages,
               SUM(COALESCE(civil_penalties,0)) as penalties,
               SUM(COALESCE(employees_affected,0)) as employees
        FROM whd_cases WHERE employer_normalized != ''
        GROUP BY employer_normalized ORDER BY back_wages DESC LIMIT 25
    """, conn)
    if not df_emp.empty:
        st.dataframe(
            df_emp.style.format({"back_wages": "${:,.0f}", "penalties": "${:,.0f}"}),
            use_container_width=True,
        )


# --- OSHA INSPECTIONS ---

def show_osha(conn):
    st.header("OSHA Workplace Safety Inspections")

    osha_count = _safe_fetchone(conn, "SELECT COUNT(*) FROM osha_inspections")
    if osha_count == 0:
        st.info("No OSHA data loaded.")
        return

    # Only show KPIs that have data — inspection counts, not violation details
    states_covered = _safe_fetchone(conn, "SELECT COUNT(DISTINCT site_state) FROM osha_inspections WHERE site_state != ''")
    employers_inspected = _safe_fetchone(conn, "SELECT COUNT(DISTINCT employer_normalized) FROM osha_inspections WHERE employer_normalized != ''")
    date_range = _safe_fetchone(conn, "SELECT MIN(open_date) || ' — ' || MAX(open_date) FROM osha_inspections WHERE open_date != ''", default="N/A")

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Inspections", f"{osha_count:,}")
    c2.metric("States/Territories", f"{states_covered:,}")
    c3.metric("Employers Inspected", f"{employers_inspected:,}")

    st.caption(f"Coverage period: {date_range}")

    left, right = st.columns(2)

    with left:
        # Top states
        df_states = _safe_query("""
            SELECT site_state as state, COUNT(*) as inspections
            FROM osha_inspections WHERE site_state != '' AND LENGTH(site_state) = 2
            GROUP BY site_state ORDER BY inspections DESC LIMIT 15
        """, conn)
        if not df_states.empty:
            fig = px.bar(df_states, x="state", y="inspections",
                         title="Top 15 States by Inspections",
                         color="inspections", color_continuous_scale="YlOrRd")
            fig.update_layout(**_DARK, height=400, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

    with right:
        # Inspection types
        df_types = _safe_query("""
            SELECT inspection_type as type, COUNT(*) as count
            FROM osha_inspections WHERE inspection_type != ''
            GROUP BY inspection_type ORDER BY count DESC
        """, conn)
        if not df_types.empty:
            type_labels = {"A": "Accident", "B": "Complaint", "C": "Referral", "D": "Monitoring",
                           "E": "Variance", "F": "Follow-up", "G": "Unprog Related", "H": "Planned",
                           "I": "Unprog Other", "J": "Programmed Related", "K": "Programmed Other",
                           "L": "Fatality/Catastrophe"}
            df_types["label"] = df_types["type"].map(lambda x: type_labels.get(x, x))
            fig = px.bar(df_types, x="count", y="label", orientation="h",
                         title="Inspections by Type", color="count", color_continuous_scale="Blues")
            fig.update_layout(**_DARK, height=400, yaxis=dict(autorange="reversed"), showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

    # Top employers by inspection count
    st.subheader("Most Frequently Inspected Employers")
    df_emp = _safe_query(f"""
        SELECT merged_name as employer,
               MAX(site_state) as state,
               SUM(cnt) as inspections
        FROM (
            SELECT
                CASE employer_normalized
                    WHEN 'U S POSTAL SERVICE' THEN 'UNITED STATES POSTAL SERVICE'
                    WHEN 'US POSTAL SERVICE' THEN 'UNITED STATES POSTAL SERVICE'
                    WHEN 'USPS' THEN 'UNITED STATES POSTAL SERVICE'
                    WHEN 'UPS' THEN 'UNITED PARCEL SERVICE'
                    ELSE employer_normalized
                END as merged_name,
                site_state,
                COUNT(*) as cnt
            FROM osha_inspections
            WHERE employer_normalized != ''
              AND employer_normalized NOT IN ('UNKNOWN', 'NONE', 'N A')
            GROUP BY employer_normalized, site_state
        )
        GROUP BY merged_name
        HAVING merged_name NOT IN ('UNKNOWN', 'NONE', 'N A')
        ORDER BY inspections DESC
        LIMIT 25
    """, conn)
    if not df_emp.empty:
        st.dataframe(df_emp, use_container_width=True)


# --- NLRB LABOR RELATIONS ---

def show_nlrb(conn):
    st.header("NLRB Labor Relations")

    nlrb_count = _safe_fetchone(conn, "SELECT COUNT(*) FROM nlrb_cases")
    if nlrb_count == 0:
        st.info("No NLRB data loaded.")
        return

    employer_ulp = _safe_fetchone(conn, "SELECT COUNT(*) FROM nlrb_cases WHERE case_type IN ('CA','CE')")
    union_ulp = _safe_fetchone(conn, "SELECT COUNT(*) FROM nlrb_cases WHERE case_type IN ('CB','CC','CG','CP')")
    rep_cases = _safe_fetchone(conn, "SELECT COUNT(*) FROM nlrb_cases WHERE case_type IN ('RC','RD','RM','UC','UD','AC')")
    open_cases = _safe_fetchone(conn, "SELECT COUNT(*) FROM nlrb_cases WHERE status = 'Open'")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total NLRB Cases", f"{nlrb_count:,}")
    c2.metric("Against Employers", f"{employer_ulp:,}")
    c3.metric("Against Unions", f"{union_ulp:,}")
    c4.metric("Open Cases", f"{open_cases:,}")

    left, right = st.columns(2)

    with left:
        # Case category pie
        df_cat = pd.DataFrame({
            "Category": ["Against Employers (CA/CE)", "Against Unions (CB/CC/CG/CP)", "Representation (RC/RD/RM/etc)"],
            "Count": [employer_ulp, union_ulp, rep_cases],
        })
        fig = px.pie(df_cat, values="Count", names="Category", title="Case Category Breakdown",
                     color_discrete_sequence=["#e74c3c", "#3498db", "#2ecc71"])
        fig.update_layout(**_DARK, height=400)
        st.plotly_chart(fig, use_container_width=True)

    with right:
        # Allegation categories
        df_allege = _safe_query("""
            SELECT
                CASE
                    WHEN allegation LIKE '%8(a)(5)%' THEN 'Refusal to Bargain [8(a)(5)]'
                    WHEN allegation LIKE '%8(a)(3)%' THEN 'Discrimination [8(a)(3)]'
                    WHEN allegation LIKE '%8(a)(1)%' THEN 'Interference [8(a)(1)]'
                    WHEN allegation LIKE '%8(b)(1)%' THEN 'Union Restraint [8(b)(1)]'
                    WHEN allegation LIKE '%8(b)(4)%' THEN 'Secondary Boycott [8(b)(4)]'
                    ELSE 'Other'
                END as category, COUNT(*) as cases
            FROM nlrb_cases WHERE allegation != ''
            GROUP BY category ORDER BY cases DESC
        """, conn)
        if not df_allege.empty:
            fig = px.bar(df_allege, x="cases", y="category", orientation="h",
                         title="Allegation Categories", color="cases", color_continuous_scale="Reds")
            fig.update_layout(**_DARK, height=400, yaxis=dict(autorange="reversed"), showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

    # Detailed case type table
    st.subheader("Case Types")
    df_types = _safe_query("""
        SELECT case_type, COUNT(*) as count FROM nlrb_cases GROUP BY case_type ORDER BY count DESC
    """, conn)
    if not df_types.empty:
        df_types["description"] = df_types["case_type"].map(
            lambda ct: CASE_TYPE_LABELS.get(ct, "Other")
        )
        st.dataframe(df_types.rename(columns={"case_type": "Type", "count": "Cases", "description": "Description"}),
                     use_container_width=True)


# --- EMPLOYER SEARCH ---

def show_employer_search(conn):
    st.header("Employer Search")

    search_term = st.text_input("Search for an employer:", placeholder="e.g., STARBUCKS, AMAZON, WALMART")

    if not search_term:
        return

    search_pattern = f"%{search_term.upper()}%"

    df_emp = _safe_query(f"""
        SELECT merged_name as employer,
               SUM(nlrb_case_count) as nlrb,
               SUM(whd_case_count) as whd,
               SUM(osha_inspection_count) as osha,
               SUM(whd_case_count + osha_inspection_count + nlrb_case_count) as total,
               SUM(total_back_wages) as total_back_wages
        FROM (
            SELECT {_EMPLOYER_MERGE} as merged_name,
                   nlrb_case_count, whd_case_count, osha_inspection_count,
                   total_back_wages
            FROM employers
            WHERE name_normalized LIKE ?
              AND name_normalized NOT IN ('UNKNOWN', '', 'NONE', 'N A')
        )
        GROUP BY merged_name
        HAVING merged_name NOT IN ('UNKNOWN', '', 'NONE', 'N A')
        ORDER BY total DESC
        LIMIT 50
    """, conn, params=(search_pattern,))

    if df_emp.empty:
        st.warning(f"No employers found matching '{search_term}'")
        return

    st.subheader(f"Found {len(df_emp)} employer(s)")
    st.dataframe(
        df_emp.style.format({"total_back_wages": "${:,.0f}"}),
        use_container_width=True,
    )

    emp_name = df_emp.iloc[0]["employer"]
    st.markdown("---")
    st.subheader(f"Detail: {emp_name}")

    # Find all original names that map to this merged name for detail queries
    emp_like = f"%{emp_name}%"

    # Agency breakdown
    c1, c2, c3, c4 = st.columns(4)
    row = df_emp.iloc[0]
    c1.metric("NLRB Cases", f"{int(row['nlrb']):,}")
    c2.metric("WHD Cases", f"{int(row['whd']):,}")
    c3.metric("OSHA Inspections", f"{int(row['osha']):,}")
    c4.metric("Back Wages", f"${float(row['total_back_wages']):,.0f}")

    # NLRB detail
    if row["nlrb"] > 0:
        with st.expander(f"NLRB Cases ({int(row['nlrb']):,})", expanded=True):
            df_nlrb = _safe_query("""
                SELECT case_number, case_name, date_filed, status, case_type, allegation, city, state
                FROM nlrb_cases WHERE employer_normalized LIKE ?
                ORDER BY date_filed DESC LIMIT 25
            """, conn, params=(emp_like,))
            if not df_nlrb.empty:
                st.dataframe(df_nlrb, use_container_width=True)

    # WHD detail
    if row["whd"] > 0:
        with st.expander(f"WHD Wage & Hour Cases ({int(row['whd']):,})", expanded=True):
            df_whd = _safe_query("""
                SELECT trade_name, city, state, findings_start_date as date,
                       back_wages_owed as back_wages, civil_penalties as penalties,
                       employees_affected as employees, naics_description as industry
                FROM whd_cases WHERE employer_normalized LIKE ?
                ORDER BY findings_start_date DESC LIMIT 25
            """, conn, params=(emp_like,))
            if not df_whd.empty:
                st.dataframe(
                    df_whd.style.format({"back_wages": "${:,.0f}", "penalties": "${:,.0f}"}),
                    use_container_width=True,
                )

    # OSHA detail
    if row["osha"] > 0:
        with st.expander(f"OSHA Inspections ({int(row['osha']):,})", expanded=True):
            df_osha = _safe_query("""
                SELECT establishment_name, site_city, site_state, open_date,
                       inspection_type
                FROM osha_inspections WHERE employer_normalized LIKE ?
                ORDER BY open_date DESC LIMIT 25
            """, conn, params=(emp_like,))
            if not df_osha.empty:
                st.dataframe(df_osha, use_container_width=True)

    # Timeline across agencies
    df_time = _safe_query("""
        SELECT month, SUM(nlrb) as NLRB, SUM(whd) as WHD, SUM(osha) as OSHA FROM (
            SELECT substr(date_filed,1,7) as month, COUNT(*) as nlrb, 0 as whd, 0 as osha
            FROM nlrb_cases WHERE employer_normalized LIKE ? AND date_filed != '' GROUP BY 1
            UNION ALL
            SELECT substr(findings_start_date,1,7), 0, COUNT(*), 0
            FROM whd_cases WHERE employer_normalized LIKE ? AND findings_start_date != '' GROUP BY 1
            UNION ALL
            SELECT substr(open_date,1,7), 0, 0, COUNT(*)
            FROM osha_inspections WHERE employer_normalized LIKE ? AND open_date != '' GROUP BY 1
        ) GROUP BY month ORDER BY month
    """, conn, params=(emp_like, emp_like, emp_like))
    if not df_time.empty and len(df_time) > 2:
        fig = px.line(df_time, x="month", y=["NLRB", "WHD", "OSHA"],
                      title=f"Enforcement Actions Over Time — {emp_name.title()}",
                      color_discrete_sequence=["#3498db", "#e74c3c", "#f39c12"])
        fig.update_layout(**_DARK, height=350)
        st.plotly_chart(fig, use_container_width=True)


if __name__ == "__main__":
    main()
