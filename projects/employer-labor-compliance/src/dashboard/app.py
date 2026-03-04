"""Streamlit dashboard for Employer Labor Compliance Tracker."""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.storage.database import get_connection, init_db, get_stats

_NO_DATA_MSG = "No data loaded yet. Run the pipeline first: `python -m src.cli pipeline`"


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


def get_db():
    conn = get_connection()
    init_db(conn)
    return conn


def _safe_get_stats(conn):
    """Get stats safely, returning zeroes if tables are empty or missing."""
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


def _has_data(stats):
    """Check if the database has any meaningful data."""
    return (stats["whd_count"] + stats["osha_count"] + stats["nlrb_count"]) > 0


def main():
    st.set_page_config(
        page_title="Employer Labor Compliance Tracker",
        page_icon="⚖️",
        layout="wide",
    )

    st.title("⚖️ Employer Labor Compliance Tracker")
    st.markdown("*Cross-agency employer violation database: WHD + OSHA + NLRB*")

    conn = get_db()

    # Sidebar navigation
    page = st.sidebar.radio("Navigate", [
        "Overview",
        "Geographic Distribution",
        "Multi-Agency Offenders",
        "Industry Analysis",
        "Temporal Trends",
        "Violation Analysis",
        "Employer Search",
        "Data Quality",
    ])

    if page == "Overview":
        show_overview(conn)
    elif page == "Geographic Distribution":
        show_geographic(conn)
    elif page == "Multi-Agency Offenders":
        show_multi_agency(conn)
    elif page == "Industry Analysis":
        show_industry(conn)
    elif page == "Temporal Trends":
        show_trends(conn)
    elif page == "Violation Analysis":
        show_violations(conn)
    elif page == "Employer Search":
        show_employer_search(conn)
    elif page == "Data Quality":
        show_quality(conn)

    # Footer
    st.divider()
    st.markdown(
        """
        <div style='text-align: center; color: #888; padding: 20px;'>
            Built by Nathan Goldberg |
            <a href='mailto:nathanmauricegoldberg@gmail.com'>nathanmauricegoldberg@gmail.com</a> |
            <a href='https://linkedin.com/in/nathangoldberg'>LinkedIn</a><br>
            Data sourced from DOL Wage & Hour Division, OSHA, and NLRB public records.
        </div>
        """,
        unsafe_allow_html=True,
    )


def show_overview(conn):
    """KPI overview section."""
    st.header("Overview")

    stats = _safe_get_stats(conn)

    if not _has_data(stats):
        st.warning(_NO_DATA_MSG)
        return

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("WHD Cases", f"{stats['whd_count']:,}")
    col2.metric("OSHA Inspections", f"{stats['osha_count']:,}")
    col3.metric("NLRB Cases", f"{stats['nlrb_count']:,}")
    col4.metric("Unique Employers", f"{stats['employer_count']:,}")
    col5.metric("Cross-Links", f"{stats['cross_link_count']:,}")

    col6, col7, col8, col9 = st.columns(4)
    col6.metric("Total Back Wages", f"${stats['total_back_wages']:,.0f}")
    col7.metric("WHD Penalties", f"${stats['total_whd_penalties']:,.0f}")
    col8.metric("OSHA Penalties", f"${stats['total_osha_penalties']:,.0f}")
    col9.metric("Workplace Fatalities", f"{stats['total_fatalities']:,}")


def show_geographic(conn):
    """Geographic distribution section."""
    st.header("Geographic Distribution")

    if not _table_exists(conn, "whd_cases") and not _table_exists(conn, "osha_inspections"):
        st.warning(_NO_DATA_MSG)
        return

    tab_geo1, tab_geo2 = st.tabs(["WHD Cases by State", "OSHA Inspections by State"])

    with tab_geo1:
        if not _table_exists(conn, "whd_cases"):
            st.info("No WHD data loaded.")
        else:
            df_states = _safe_query("""
                SELECT state, COUNT(*) as cases, SUM(back_wages_owed) as total_wages,
                       SUM(civil_penalties) as total_penalties, SUM(employees_affected) as employees
                FROM whd_cases WHERE state != ''
                GROUP BY state ORDER BY cases DESC
            """, conn)
            if not df_states.empty:
                fig = px.choropleth(
                    df_states, locations="state", locationmode="USA-states",
                    color="cases", scope="usa",
                    color_continuous_scale="Blues",
                    title="WHD Wage & Hour Cases by State",
                )
                fig.update_layout(template="plotly_dark", paper_bgcolor="#0E1117", plot_bgcolor="#0E1117")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No WHD geographic data available.")

    with tab_geo2:
        if not _table_exists(conn, "osha_inspections"):
            st.info("No OSHA data loaded.")
        else:
            df_osha_states = _safe_query("""
                SELECT site_state as state, COUNT(*) as inspections,
                       SUM(total_current_penalty) as total_penalties,
                       SUM(fatalities) as fatalities
                FROM osha_inspections WHERE site_state != ''
                GROUP BY site_state ORDER BY inspections DESC
            """, conn)
            if not df_osha_states.empty:
                fig = px.choropleth(
                    df_osha_states, locations="state", locationmode="USA-states",
                    color="inspections", scope="usa",
                    color_continuous_scale="Reds",
                    title="OSHA Safety Inspections by State",
                )
                fig.update_layout(template="plotly_dark", paper_bgcolor="#0E1117", plot_bgcolor="#0E1117")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No OSHA geographic data available.")


def show_multi_agency(conn):
    """Multi-agency offenders section."""
    st.header("Multi-Agency Offenders")
    st.markdown("*Employers flagged across 2+ federal agencies — the highest-risk employers.*")

    if not _table_exists(conn, "employers"):
        st.warning(_NO_DATA_MSG)
        return

    df_multi = _safe_query("""
        SELECT name_normalized as employer, primary_state as state,
               whd_case_count as whd, osha_inspection_count as osha,
               nlrb_case_count as nlrb,
               (whd_case_count + osha_inspection_count + nlrb_case_count) as total,
               total_back_wages, total_penalties, total_fatalities,
               compliance_score
        FROM employers
        WHERE (CASE WHEN whd_case_count > 0 THEN 1 ELSE 0 END +
               CASE WHEN osha_inspection_count > 0 THEN 1 ELSE 0 END +
               CASE WHEN nlrb_case_count > 0 THEN 1 ELSE 0 END) >= 2
        ORDER BY total DESC
        LIMIT 100
    """, conn)

    if not df_multi.empty:
        st.dataframe(
            df_multi.style.format({
                "total_back_wages": "${:,.0f}",
                "total_penalties": "${:,.0f}",
                "compliance_score": "{:.2f}",
            }),
            use_container_width=True,
            height=400,
        )
    else:
        st.info("No multi-agency offenders found. Run the pipeline with data from multiple sources.")


def show_industry(conn):
    """Industry analysis section."""
    st.header("Industry Analysis")

    if not _table_exists(conn, "whd_cases") and not _table_exists(conn, "osha_inspections"):
        st.warning(_NO_DATA_MSG)
        return

    tab_ind1, tab_ind2 = st.tabs(["Top Industries (WHD)", "Top Industries (OSHA)"])

    with tab_ind1:
        if not _table_exists(conn, "whd_cases"):
            st.info("No WHD data loaded.")
        else:
            df_industries = _safe_query("""
                SELECT naics_description as industry, COUNT(*) as cases,
                       SUM(back_wages_owed) as back_wages,
                       SUM(employees_affected) as employees
                FROM whd_cases WHERE naics_description != ''
                GROUP BY naics_description ORDER BY cases DESC LIMIT 20
            """, conn)
            if not df_industries.empty:
                fig = px.bar(
                    df_industries, x="cases", y="industry", orientation="h",
                    title="Top 20 Industries by WHD Cases",
                    color="back_wages",
                    color_continuous_scale="Blues",
                )
                fig.update_layout(template="plotly_dark", paper_bgcolor="#0E1117", plot_bgcolor="#0E1117", yaxis=dict(autorange="reversed"))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No WHD industry data available.")

    with tab_ind2:
        if not _table_exists(conn, "osha_inspections"):
            st.info("No OSHA data loaded.")
        else:
            df_osha_ind = _safe_query("""
                SELECT naics_code, COUNT(*) as inspections,
                       SUM(total_current_penalty) as penalties,
                       SUM(fatalities) as fatalities
                FROM osha_inspections WHERE naics_code != ''
                GROUP BY naics_code ORDER BY inspections DESC LIMIT 20
            """, conn)
            if not df_osha_ind.empty:
                fig = px.bar(
                    df_osha_ind, x="inspections", y="naics_code", orientation="h",
                    title="Top 20 NAICS Codes by OSHA Inspections",
                    color="penalties",
                    color_continuous_scale="Reds",
                )
                fig.update_layout(template="plotly_dark", paper_bgcolor="#0E1117", plot_bgcolor="#0E1117", yaxis=dict(autorange="reversed"))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No OSHA industry data available.")


def show_trends(conn):
    """Temporal trends section."""
    st.header("Temporal Trends")

    if not _table_exists(conn, "whd_cases") and not _table_exists(conn, "osha_inspections"):
        st.warning(_NO_DATA_MSG)
        return

    tab_t1, tab_t2 = st.tabs(["WHD Cases Over Time", "OSHA Inspections Over Time"])

    with tab_t1:
        if not _table_exists(conn, "whd_cases"):
            st.info("No WHD data loaded.")
        else:
            df_whd_time = _safe_query("""
                SELECT substr(findings_start_date, 1, 7) as month, COUNT(*) as cases,
                       SUM(back_wages_owed) as wages
                FROM whd_cases WHERE findings_start_date != ''
                GROUP BY month ORDER BY month
            """, conn)
            if not df_whd_time.empty:
                fig = px.line(df_whd_time, x="month", y="cases", title="WHD Cases by Month")
                fig.update_layout(template="plotly_dark", paper_bgcolor="#0E1117", plot_bgcolor="#0E1117")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No WHD temporal data available.")

    with tab_t2:
        if not _table_exists(conn, "osha_inspections"):
            st.info("No OSHA data loaded.")
        else:
            df_osha_time = _safe_query("""
                SELECT substr(open_date, 1, 7) as month, COUNT(*) as inspections,
                       SUM(total_current_penalty) as penalties
                FROM osha_inspections WHERE open_date != ''
                GROUP BY month ORDER BY month
            """, conn)
            if not df_osha_time.empty:
                fig = px.line(df_osha_time, x="month", y="inspections", title="OSHA Inspections by Month")
                fig.update_layout(template="plotly_dark", paper_bgcolor="#0E1117", plot_bgcolor="#0E1117")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No OSHA temporal data available.")


def show_violations(conn):
    """Violation analysis section."""
    st.header("Violation Analysis")

    if not _table_exists(conn, "whd_cases") and not _table_exists(conn, "osha_inspections"):
        st.warning(_NO_DATA_MSG)
        return

    tab_v1, tab_v2 = st.tabs(["WHD Violation Types", "OSHA Violation Severity"])

    with tab_v1:
        if not _table_exists(conn, "whd_cases"):
            st.info("No WHD data loaded.")
        else:
            violation_types = {
                "FLSA": _safe_fetchone(conn, "SELECT COUNT(*) FROM whd_cases WHERE flsa_violated = 1"),
                "MSPA": _safe_fetchone(conn, "SELECT COUNT(*) FROM whd_cases WHERE mspa_violated = 1"),
                "H-1B": _safe_fetchone(conn, "SELECT COUNT(*) FROM whd_cases WHERE h1b_violated = 1"),
                "FMLA": _safe_fetchone(conn, "SELECT COUNT(*) FROM whd_cases WHERE fmla_violated = 1"),
                "SCA": _safe_fetchone(conn, "SELECT COUNT(*) FROM whd_cases WHERE sca_violated = 1"),
                "DBA": _safe_fetchone(conn, "SELECT COUNT(*) FROM whd_cases WHERE dba_violated = 1"),
            }
            df_violations = pd.DataFrame(list(violation_types.items()), columns=["Law", "Cases"])
            df_violations = df_violations[df_violations["Cases"] > 0]
            if not df_violations.empty:
                fig = px.pie(df_violations, values="Cases", names="Law", title="WHD Violations by Federal Law")
                fig.update_layout(template="plotly_dark", paper_bgcolor="#0E1117", plot_bgcolor="#0E1117")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No WHD violation data available.")

    with tab_v2:
        if not _table_exists(conn, "osha_inspections"):
            st.info("No OSHA data loaded.")
        else:
            osha_severity = _safe_query("""
                SELECT
                    SUM(serious_violations) as serious,
                    SUM(willful_violations) as willful,
                    SUM(repeat_violations) as repeat_violations,
                    SUM(num_violations - serious_violations - willful_violations - repeat_violations) as other
                FROM osha_inspections
            """, conn)
            if not osha_severity.empty:
                severity_data = {
                    "Serious": int(osha_severity["serious"].iloc[0] or 0),
                    "Willful": int(osha_severity["willful"].iloc[0] or 0),
                    "Repeat": int(osha_severity["repeat_violations"].iloc[0] or 0),
                    "Other": max(0, int(osha_severity["other"].iloc[0] or 0)),
                }
                df_sev = pd.DataFrame(list(severity_data.items()), columns=["Type", "Count"])
                df_sev = df_sev[df_sev["Count"] > 0]
                if not df_sev.empty:
                    fig = px.pie(df_sev, values="Count", names="Type", title="OSHA Violations by Severity")
                    fig.update_layout(template="plotly_dark", paper_bgcolor="#0E1117", plot_bgcolor="#0E1117")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No OSHA violation severity data available.")
            else:
                st.info("No OSHA violation severity data available.")


def show_employer_search(conn):
    """Employer search section."""
    st.header("Employer Search")

    if not _table_exists(conn, "employers"):
        st.warning(_NO_DATA_MSG)
        return

    search_term = st.text_input("Search for an employer:", placeholder="e.g., WALMART, AMAZON, MCDONALDS")

    if search_term:
        search_pattern = f"%{search_term.upper()}%"

        df_emp = _safe_query("""
            SELECT name_normalized, primary_state, whd_case_count, osha_inspection_count,
                   nlrb_case_count, total_back_wages, total_penalties, total_fatalities,
                   compliance_score
            FROM employers
            WHERE name_normalized LIKE ?
            ORDER BY (whd_case_count + osha_inspection_count + nlrb_case_count) DESC
            LIMIT 50
        """, conn, params=(search_pattern,))

        if not df_emp.empty:
            st.subheader(f"Found {len(df_emp)} employer(s)")
            st.dataframe(
                df_emp.style.format({
                    "total_back_wages": "${:,.0f}",
                    "total_penalties": "${:,.0f}",
                    "compliance_score": "{:.2f}",
                }),
                use_container_width=True,
            )

            # Show individual cases for first employer
            emp_name = df_emp.iloc[0]["name_normalized"]
            with st.expander(f"WHD Cases for {emp_name}"):
                df_whd = _safe_query(
                    "SELECT * FROM whd_cases WHERE employer_normalized = ? ORDER BY findings_start_date DESC LIMIT 20",
                    conn, params=(emp_name,),
                )
                if not df_whd.empty:
                    st.dataframe(df_whd, use_container_width=True)
                else:
                    st.info("No WHD cases found.")

            with st.expander(f"OSHA Inspections for {emp_name}"):
                df_osha = _safe_query(
                    "SELECT * FROM osha_inspections WHERE employer_normalized = ? ORDER BY open_date DESC LIMIT 20",
                    conn, params=(emp_name,),
                )
                if not df_osha.empty:
                    st.dataframe(df_osha, use_container_width=True)
                else:
                    st.info("No OSHA inspections found.")

            with st.expander(f"NLRB Cases for {emp_name}"):
                df_nlrb = _safe_query(
                    "SELECT * FROM nlrb_cases WHERE employer_normalized = ? ORDER BY date_filed DESC LIMIT 20",
                    conn, params=(emp_name,),
                )
                if not df_nlrb.empty:
                    st.dataframe(df_nlrb, use_container_width=True)
                else:
                    st.info("No NLRB cases found.")
        else:
            st.warning(f"No employers found matching '{search_term}'")


def show_quality(conn):
    """Data quality section."""
    st.header("Data Quality")

    stats = _safe_get_stats(conn)

    if not _has_data(stats):
        st.warning(_NO_DATA_MSG)
        return

    col_q1, col_q2, col_q3 = st.columns(3)

    with col_q1:
        st.metric("WHD Avg Quality", f"{stats['avg_quality']['whd']:.3f}")
        if _table_exists(conn, "whd_cases"):
            df_q_whd = _safe_query("""
                SELECT
                    CASE WHEN quality_score >= 0.8 THEN 'High (>=0.8)'
                         WHEN quality_score >= 0.5 THEN 'Medium (0.5-0.8)'
                         ELSE 'Low (<0.5)' END as tier,
                    COUNT(*) as count
                FROM whd_cases WHERE quality_score > 0
                GROUP BY tier ORDER BY tier
            """, conn)
            if not df_q_whd.empty:
                fig = px.pie(df_q_whd, values="count", names="tier", title="WHD Quality Distribution")
                fig.update_layout(template="plotly_dark", paper_bgcolor="#0E1117", plot_bgcolor="#0E1117", height=300)
                st.plotly_chart(fig, use_container_width=True)

    with col_q2:
        st.metric("OSHA Avg Quality", f"{stats['avg_quality']['osha']:.3f}")
        if _table_exists(conn, "osha_inspections"):
            df_q_osha = _safe_query("""
                SELECT
                    CASE WHEN quality_score >= 0.8 THEN 'High (>=0.8)'
                         WHEN quality_score >= 0.5 THEN 'Medium (0.5-0.8)'
                         ELSE 'Low (<0.5)' END as tier,
                    COUNT(*) as count
                FROM osha_inspections WHERE quality_score > 0
                GROUP BY tier ORDER BY tier
            """, conn)
            if not df_q_osha.empty:
                fig = px.pie(df_q_osha, values="count", names="tier", title="OSHA Quality Distribution")
                fig.update_layout(template="plotly_dark", paper_bgcolor="#0E1117", plot_bgcolor="#0E1117", height=300)
                st.plotly_chart(fig, use_container_width=True)

    with col_q3:
        st.metric("NLRB Avg Quality", f"{stats['avg_quality']['nlrb']:.3f}")
        if _table_exists(conn, "nlrb_cases"):
            df_q_nlrb = _safe_query("""
                SELECT
                    CASE WHEN quality_score >= 0.8 THEN 'High (>=0.8)'
                         WHEN quality_score >= 0.5 THEN 'Medium (0.5-0.8)'
                         ELSE 'Low (<0.5)' END as tier,
                    COUNT(*) as count
                FROM nlrb_cases WHERE quality_score > 0
                GROUP BY tier ORDER BY tier
            """, conn)
            if not df_q_nlrb.empty:
                fig = px.pie(df_q_nlrb, values="count", names="tier", title="NLRB Quality Distribution")
                fig.update_layout(template="plotly_dark", paper_bgcolor="#0E1117", plot_bgcolor="#0E1117", height=300)
                st.plotly_chart(fig, use_container_width=True)


if __name__ == "__main__":
    main()
