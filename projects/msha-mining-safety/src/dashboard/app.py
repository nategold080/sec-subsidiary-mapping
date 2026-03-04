"""MSHA Mining Safety & Enforcement Tracker — Streamlit Dashboard."""

import os
import sqlite3

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "msha.db")


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
def get_conn():
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception:
        conn = sqlite3.connect(":memory:", check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn


@st.cache_data(ttl=600)
def query(sql, params=None):
    conn = get_conn()
    try:
        return pd.read_sql_query(sql, conn, params=params or [])
    except Exception:
        return pd.DataFrame()


def fmt(n):
    if isinstance(n, float):
        return f"${n:,.0f}" if n > 100 else f"{n:.2f}"
    return f"{n:,}"


DARK = dict(template="plotly_dark", paper_bgcolor="#0E1117", plot_bgcolor="#0E1117")

st.set_page_config(
    page_title="MSHA Mining Safety Tracker",
    page_icon="⛏️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Sidebar navigation
st.sidebar.title("⛏️ MSHA Mining Safety")
page = st.sidebar.radio("Navigate", [
    "Overview",
    "Safety Rates",
    "Production Analysis",
    "Ownership Changes",
    "Contractor Safety",
    "Accident Analysis",
    "Operator Profiles",
    "Violation Explorer",
    "Penalty Analysis",
    "Mine Search",
    "State Comparison",
    "Geographic Map",
    "Data Quality",
])

# ─── OVERVIEW ────────────────────────────────────────────────────────────────
if page == "Overview":
    st.title("⛏️ MSHA Mining Safety & Enforcement Tracker")
    st.markdown("Comprehensive analysis of U.S. mine safety data from the Mine Safety and Health Administration.")

    conn = get_conn()
    if not _table_exists(conn, "mines"):
        st.warning("No data loaded. Run the pipeline first: `python -m src.cli pipeline`")
        st.stop()

    _conn = get_conn()
    stats = {
        "mines": _safe_fetchone(_conn, "SELECT COUNT(*) FROM mines"),
        "active_mines": _safe_fetchone(_conn, "SELECT COUNT(*) FROM mines WHERE mine_status = 'Active'"),
        "accidents": _safe_fetchone(_conn, "SELECT COUNT(*) FROM accidents") if _table_exists(_conn, "accidents") else 0,
        "fatalities": _safe_fetchone(_conn, "SELECT COUNT(*) FROM accidents WHERE degree_injury_cd = '01'") if _table_exists(_conn, "accidents") else 0,
        "inspections": _safe_fetchone(_conn, "SELECT COUNT(*) FROM inspections") if _table_exists(_conn, "inspections") else 0,
        "violations": _safe_fetchone(_conn, "SELECT COUNT(*) FROM violations") if _table_exists(_conn, "violations") else 0,
        "proposed_penalties": _safe_fetchone(_conn, "SELECT COALESCE(SUM(proposed_penalty_amt), 0) FROM assessed_violations") if _table_exists(_conn, "assessed_violations") else 0,
        "paid_penalties": _safe_fetchone(_conn, "SELECT COALESCE(SUM(paid_proposed_penalty_amt), 0) FROM assessed_violations") if _table_exists(_conn, "assessed_violations") else 0,
        "profiles": _safe_fetchone(_conn, "SELECT COUNT(*) FROM operator_profiles") if _table_exists(_conn, "operator_profiles") else 0,
        "states": _safe_fetchone(_conn, "SELECT COUNT(DISTINCT state) FROM mines WHERE state != ''"),
        "total_hours": _safe_fetchone(_conn, "SELECT COALESCE(SUM(employee_hours), 0) FROM mine_production WHERE subunit_cd != '99'") if _table_exists(_conn, "mine_production") else 0,
        "controller_records": _safe_fetchone(_conn, "SELECT COUNT(*) FROM controller_history") if _table_exists(_conn, "controller_history") else 0,
        "closure_orders": _safe_fetchone(_conn, "SELECT COUNT(*) FROM closure_orders") if _table_exists(_conn, "closure_orders") else 0,
    }

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Mines", fmt(int(stats["mines"] or 0)))
    c2.metric("Active Mines", fmt(int(stats["active_mines"] or 0)))
    c3.metric("Accidents/Injuries", fmt(int(stats["accidents"] or 0)))
    c4.metric("Fatalities", fmt(int(stats["fatalities"] or 0)))
    c5.metric("Violations", fmt(int(stats["violations"] or 0)))

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Inspections", fmt(int(stats["inspections"] or 0)))
    c2.metric("Proposed Penalties", f"${(stats['proposed_penalties'] or 0):,.0f}")
    c3.metric("Paid Penalties", f"${(stats['paid_penalties'] or 0):,.0f}")
    c4.metric("Operator Profiles", fmt(int(stats["profiles"] or 0)))
    c5.metric("States/Territories", fmt(int(stats["states"] or 0)))

    # Enrichment KPIs
    total_hours = int(stats["total_hours"] or 0)
    if total_hours > 0:
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Employee Hours", f"{total_hours:,}")
        c2.metric("Controller History Records", fmt(int(stats["controller_records"] or 0)))
        c3.metric("Closure Orders", fmt(int(stats["closure_orders"] or 0)))

        # National incidence rate trend
        st.subheader("National Incidence Rate Trend")
        st.caption("Injuries per 200,000 employee-hours (industry benchmark: ~2.0)")
        df = query("""
            WITH hours AS (
                SELECT calendar_year as year, SUM(employee_hours) as hours
                FROM mine_production
                WHERE subunit_cd != '99' AND calendar_year BETWEEN 2000 AND 2026
                GROUP BY calendar_year
            ),
            injuries AS (
                SELECT cal_yr as year, COUNT(*) as injuries
                FROM accidents
                WHERE degree_injury_cd IN ('01','02','03','04','05')
                    AND cal_yr BETWEEN 2000 AND 2026
                GROUP BY cal_yr
            )
            SELECT h.year, h.hours, COALESCE(i.injuries, 0) as injuries
            FROM hours h
            LEFT JOIN injuries i ON h.year = i.year
            WHERE h.hours > 0
            ORDER BY h.year
        """)
        if not df.empty:
            df["incidence_rate"] = (df["injuries"] * 200_000 / df["hours"]).round(2)
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df["year"], y=df["incidence_rate"], name="National Rate",
                                     line=dict(color="#0984E3", width=3)))
            fig.add_hline(y=2.0, line_dash="dash", line_color="#FDCB6E",
                         annotation_text="Industry Benchmark (2.0)")
            fig.update_layout(**DARK, height=350, yaxis_title="Incidence Rate")
            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Accidents by Year")
        df = query("""
            SELECT cal_yr as year, COUNT(*) as count,
                   SUM(CASE WHEN degree_injury_cd = '01' THEN 1 ELSE 0 END) as fatalities
            FROM accidents
            WHERE cal_yr BETWEEN 2000 AND 2026
            GROUP BY cal_yr ORDER BY cal_yr
        """)
        if not df.empty:
            fig = go.Figure()
            fig.add_trace(go.Bar(x=df["year"], y=df["count"], name="All Accidents", marker_color="#0984E3"))
            fig.add_trace(go.Bar(x=df["year"], y=df["fatalities"], name="Fatalities", marker_color="#D63031"))
            fig.update_layout(barmode="overlay", **DARK, height=400)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No accident data available yet.")

    with col2:
        st.subheader("Risk Tier Distribution")
        df = query("""
            SELECT risk_tier, COUNT(*) as count
            FROM operator_profiles
            GROUP BY risk_tier
        """)
        if not df.empty:
            color_map = {"LOW": "#00B894", "MEDIUM": "#FDCB6E", "HIGH": "#E17055", "CRITICAL": "#D63031"}
            fig = px.pie(df, values="count", names="risk_tier",
                         color="risk_tier", color_discrete_map=color_map)
            fig.update_layout(**DARK, height=400)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No operator profile data available yet.")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Top 10 States by Violations")
        df = query("""
            SELECT m.state, COUNT(v.violation_no) as violations
            FROM violations v
            JOIN mines m ON v.mine_id = m.mine_id
            WHERE m.state IS NOT NULL AND m.state != ''
            GROUP BY m.state ORDER BY violations DESC LIMIT 10
        """)
        if not df.empty:
            fig = px.bar(df, x="state", y="violations", color_discrete_sequence=["#0984E3"])
            fig.update_layout(**DARK, height=350)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No violation data available yet.")

    with col2:
        st.subheader("Top 10 Operators by Penalties")
        df = query("""
            SELECT normalized_name, total_proposed_penalties
            FROM operator_profiles
            WHERE total_proposed_penalties > 0
            ORDER BY total_proposed_penalties DESC LIMIT 10
        """)
        if not df.empty:
            fig = px.bar(df, x="normalized_name", y="total_proposed_penalties",
                         color_discrete_sequence=["#D63031"])
            fig.update_layout(**DARK, height=350,
                              xaxis_title="Operator", yaxis_title="Proposed Penalties ($)")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No penalty data available yet.")

# ─── SAFETY RATES ─────────────────────────────────────────────────────────────
elif page == "Safety Rates":
    st.title("Industry-Standard Safety Rates")
    st.markdown("Incidence rates per 200,000 employee-hours — the standard measure used by MSHA and BLS.")

    conn = get_conn()
    if not _table_exists(conn, "mine_production") or not _table_exists(conn, "accidents") or not _table_exists(conn, "mines"):
        st.warning("No data loaded. Run the pipeline first: `python -m src.cli pipeline`")
        st.stop()

    has_prod = query("SELECT COUNT(*) as n FROM mine_production").iloc[0]["n"]
    if has_prod == 0:
        st.info("No production data available. Run `scrape-production` to enable rate calculations.")
        st.stop()

    col1, col2 = st.columns(2)
    with col1:
        yr_start = st.number_input("Start Year", value=2010, min_value=2000, max_value=2026)
    with col2:
        yr_end = st.number_input("End Year", value=2026, min_value=2000, max_value=2026)

    # State-level incidence rates
    st.subheader("Incidence Rate by State")
    st.caption("Injuries per 200,000 employee-hours. National avg ~2.0")
    df = query("""
        WITH hours AS (
            SELECT m.state, SUM(p.employee_hours) as hours
            FROM mine_production p
            JOIN mines m ON p.mine_id = m.mine_id
            WHERE p.subunit_cd != '99' AND p.calendar_year BETWEEN ? AND ?
                AND m.state IS NOT NULL AND m.state != ''
            GROUP BY m.state
        ),
        injuries AS (
            SELECT m.state, COUNT(*) as injuries
            FROM accidents a
            JOIN mines m ON a.mine_id = m.mine_id
            WHERE a.degree_injury_cd IN ('01','02','03','04','05')
                AND a.cal_yr BETWEEN ? AND ?
                AND m.state IS NOT NULL AND m.state != ''
            GROUP BY m.state
        )
        SELECT h.state, h.hours, COALESCE(i.injuries, 0) as injuries
        FROM hours h
        LEFT JOIN injuries i ON h.state = i.state
        WHERE h.hours > 100000
        ORDER BY h.hours DESC
    """, [yr_start, yr_end, yr_start, yr_end])
    if not df.empty:
        df["incidence_rate"] = (df["injuries"] * 200_000 / df["hours"]).round(2)
        df = df.sort_values("incidence_rate", ascending=False)
        fig = px.bar(df.head(20), x="state", y="incidence_rate",
                     color_discrete_sequence=["#E17055"])
        fig.add_hline(y=2.0, line_dash="dash", line_color="#FDCB6E",
                     annotation_text="National Avg (2.0)")
        fig.update_layout(**DARK, height=400, yaxis_title="Incidence Rate per 200K hours")
        st.plotly_chart(fig, use_container_width=True)

    # Coal vs Metal comparison
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Coal vs Metal/Non-Metal Rates")
        df = query("""
            WITH hours AS (
                SELECT coal_metal_ind, calendar_year as year, SUM(employee_hours) as hours
                FROM mine_production
                WHERE subunit_cd != '99' AND calendar_year BETWEEN ? AND ?
                    AND coal_metal_ind IN ('C', 'M')
                GROUP BY coal_metal_ind, calendar_year
            ),
            injuries AS (
                SELECT coal_metal_ind, cal_yr as year, COUNT(*) as injuries
                FROM accidents
                WHERE degree_injury_cd IN ('01','02','03','04','05')
                    AND cal_yr BETWEEN ? AND ?
                    AND coal_metal_ind IN ('C', 'M')
                GROUP BY coal_metal_ind, cal_yr
            )
            SELECT h.coal_metal_ind, h.year, h.hours,
                   COALESCE(i.injuries, 0) as injuries
            FROM hours h
            LEFT JOIN injuries i ON h.coal_metal_ind = i.coal_metal_ind AND h.year = i.year
            WHERE h.hours > 0
            ORDER BY h.year
        """, [yr_start, yr_end, yr_start, yr_end])
        if not df.empty:
            df["rate"] = (df["injuries"] * 200_000 / df["hours"]).round(2)
            coal = df[df["coal_metal_ind"] == "C"]
            metal = df[df["coal_metal_ind"] == "M"]
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=coal["year"], y=coal["rate"], name="Coal",
                                     line=dict(color="#E17055", width=2)))
            fig.add_trace(go.Scatter(x=metal["year"], y=metal["rate"], name="Metal/Non-Metal",
                                     line=dict(color="#0984E3", width=2)))
            fig.update_layout(**DARK, height=350, yaxis_title="Incidence Rate")
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Fatality Rate Trend")
        df = query("""
            WITH hours AS (
                SELECT calendar_year as year, SUM(employee_hours) as hours
                FROM mine_production
                WHERE subunit_cd != '99' AND calendar_year BETWEEN ? AND ?
                GROUP BY calendar_year
            ),
            fatalities AS (
                SELECT cal_yr as year, COUNT(*) as fatalities
                FROM accidents
                WHERE degree_injury_cd = '01' AND cal_yr BETWEEN ? AND ?
                GROUP BY cal_yr
            )
            SELECT h.year, h.hours, COALESCE(f.fatalities, 0) as fatalities
            FROM hours h
            LEFT JOIN fatalities f ON h.year = f.year
            WHERE h.hours > 0
            ORDER BY h.year
        """, [yr_start, yr_end, yr_start, yr_end])
        if not df.empty:
            df["rate"] = (df["fatalities"] * 200_000 / df["hours"]).round(4)
            fig = px.bar(df, x="year", y="rate", color_discrete_sequence=["#D63031"])
            fig.update_layout(**DARK, height=350, yaxis_title="Fatality Rate per 200K hours")
            st.plotly_chart(fig, use_container_width=True)

    # Top operators by incidence rate
    st.subheader("Highest Incidence Rate Operators (min 100K employee-hours)")
    df = query("""
        WITH hours AS (
            SELECT m.operator_id, m.operator_name,
                   SUM(p.employee_hours) as hours,
                   COUNT(DISTINCT m.mine_id) as mines
            FROM mine_production p
            JOIN mines m ON p.mine_id = m.mine_id
            WHERE p.subunit_cd != '99' AND p.calendar_year BETWEEN ? AND ?
                AND m.operator_name IS NOT NULL AND m.operator_name != ''
            GROUP BY m.operator_id
        ),
        injuries AS (
            SELECT operator_id, COUNT(*) as injuries
            FROM accidents
            WHERE degree_injury_cd IN ('01','02','03','04','05')
                AND cal_yr BETWEEN ? AND ?
                AND operator_id IS NOT NULL AND operator_id != ''
            GROUP BY operator_id
        )
        SELECT h.operator_name, h.hours,
               COALESCE(i.injuries, 0) as injuries, h.mines
        FROM hours h
        LEFT JOIN injuries i ON h.operator_id = i.operator_id
        WHERE h.hours > 100000
        ORDER BY (CAST(COALESCE(i.injuries, 0) AS REAL) * 200000 / h.hours) DESC
        LIMIT 25
    """, [yr_start, yr_end, yr_start, yr_end])
    if not df.empty:
        df["incidence_rate"] = (df["injuries"] * 200_000 / df["hours"]).round(2)
        st.dataframe(df, use_container_width=True, hide_index=True)

# ─── PRODUCTION ANALYSIS ──────────────────────────────────────────────────────
elif page == "Production Analysis":
    st.title("Production & Employment Analysis")

    conn = get_conn()
    if not _table_exists(conn, "mine_production") or not _table_exists(conn, "mines"):
        st.warning("No data loaded. Run the pipeline first: `python -m src.cli pipeline`")
        st.stop()

    has_prod = query("SELECT COUNT(*) as n FROM mine_production").iloc[0]["n"]
    if has_prod == 0:
        st.info("No production data available. Run `scrape-production` to enable.")
        st.stop()

    prod_stats = query("""
        SELECT
            SUM(employee_hours) as total_hours,
            SUM(avg_employee_cnt) as total_fte,
            SUM(coal_production) as total_coal,
            COUNT(DISTINCT mine_id) as mines_with_data,
            MIN(calendar_year) as min_year,
            MAX(calendar_year) as max_year
        FROM mine_production
        WHERE subunit_cd != '99'
    """).iloc[0]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Employee Hours", f"{int(prod_stats['total_hours'] or 0):,}")
    c2.metric("Mines with Data", fmt(int(prod_stats['mines_with_data'] or 0)))
    c3.metric("Coal Production (tons)", f"{int(prod_stats['total_coal'] or 0):,}")
    c4.metric("Year Range", f"{int(prod_stats['min_year'] or 0)}-{int(prod_stats['max_year'] or 0)}")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Employee Hours by Year")
        df = query("""
            SELECT calendar_year as year,
                   SUM(employee_hours) as hours,
                   SUM(avg_employee_cnt) as avg_employees
            FROM mine_production
            WHERE subunit_cd != '99' AND calendar_year BETWEEN 2000 AND 2026
            GROUP BY calendar_year ORDER BY year
        """)
        fig = px.bar(df, x="year", y="hours", color_discrete_sequence=["#0984E3"])
        fig.update_layout(**DARK, height=400, yaxis_title="Employee Hours")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Coal Production by Year")
        df = query("""
            SELECT calendar_year as year,
                   SUM(coal_production) as tons
            FROM mine_production
            WHERE coal_production IS NOT NULL AND coal_production > 0
                AND subunit_cd != '99' AND calendar_year BETWEEN 2000 AND 2026
            GROUP BY calendar_year ORDER BY year
        """)
        fig = px.bar(df, x="year", y="tons", color_discrete_sequence=["#E17055"])
        fig.update_layout(**DARK, height=400, yaxis_title="Tons")
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Top States by Employee Hours (Recent 5 Years)")
    df = query("""
        SELECT m.state, SUM(p.employee_hours) as hours,
               SUM(p.coal_production) as coal_tons
        FROM mine_production p
        JOIN mines m ON p.mine_id = m.mine_id
        WHERE p.subunit_cd != '99' AND p.calendar_year >= 2020
            AND m.state IS NOT NULL AND m.state != ''
        GROUP BY m.state
        ORDER BY hours DESC LIMIT 15
    """)
    fig = px.bar(df, x="state", y="hours", color_discrete_sequence=["#6C5CE7"])
    fig.update_layout(**DARK, height=350, yaxis_title="Employee Hours")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Employment by Subunit Type")
    df = query("""
        SELECT subunit_desc, SUM(employee_hours) as hours,
               ROUND(AVG(avg_employee_cnt), 0) as avg_employees
        FROM mine_production
        WHERE subunit_desc IS NOT NULL AND subunit_desc != ''
            AND subunit_cd != '99' AND calendar_year >= 2020
        GROUP BY subunit_desc ORDER BY hours DESC
    """)
    st.dataframe(df, use_container_width=True, hide_index=True)

# ─── OWNERSHIP CHANGES ───────────────────────────────────────────────────────
elif page == "Ownership Changes":
    st.title("Mine Ownership & Controller History")

    conn = get_conn()
    if not _table_exists(conn, "controller_history"):
        st.warning("No controller history data loaded. Run the pipeline first: `python -m src.cli pipeline`")
        st.stop()

    has_ctrl = query("SELECT COUNT(*) as n FROM controller_history").iloc[0]["n"]
    if has_ctrl == 0:
        st.info("No controller history data available. Run `scrape-controllers` to enable.")
        st.stop()

    ctrl_stats = query("""
        SELECT
            COUNT(*) as total_records,
            COUNT(DISTINCT mine_id) as mines_with_history,
            COUNT(DISTINCT controller_id) as unique_controllers,
            SUM(CASE WHEN is_current = 1 THEN 1 ELSE 0 END) as current_assignments
        FROM controller_history
    """).iloc[0]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("History Records", fmt(int(ctrl_stats["total_records"])))
    c2.metric("Mines with History", fmt(int(ctrl_stats["mines_with_history"])))
    c3.metric("Unique Controllers", fmt(int(ctrl_stats["unique_controllers"])))
    c4.metric("Current Assignments", fmt(int(ctrl_stats["current_assignments"])))

    st.subheader("Top Controllers by Mine Count")
    df = query("""
        SELECT controller_normalized as controller, controller_name,
               COUNT(DISTINCT mine_id) as mines_controlled,
               SUM(CASE WHEN is_current = 1 THEN 1 ELSE 0 END) as current_mines
        FROM controller_history
        WHERE controller_normalized IS NOT NULL AND controller_normalized != ''
        GROUP BY controller_normalized
        ORDER BY mines_controlled DESC LIMIT 20
    """)
    st.dataframe(df, use_container_width=True, hide_index=True)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Ownership Changes Over Time")
        df = query("""
            SELECT SUBSTR(effective_date, -4) as year, COUNT(*) as changes
            FROM controller_history
            WHERE effective_date IS NOT NULL AND effective_date != ''
                AND LENGTH(effective_date) >= 4
            GROUP BY year
            HAVING CAST(year AS INTEGER) BETWEEN 2000 AND 2026
            ORDER BY year
        """)
        if not df.empty:
            fig = px.bar(df, x="year", y="changes", color_discrete_sequence=["#FDCB6E"])
            fig.update_layout(**DARK, height=350, yaxis_title="Ownership Changes")
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Serial Acquirers")
        st.caption("Controllers who have controlled the most distinct mines")
        df = query("""
            SELECT controller_normalized as controller,
                   COUNT(DISTINCT mine_id) as total_mines,
                   SUM(CASE WHEN is_current = 1 THEN 1 ELSE 0 END) as current,
                   COUNT(DISTINCT operator_id) as operators_used
            FROM controller_history
            WHERE controller_normalized IS NOT NULL AND controller_normalized != ''
            GROUP BY controller_normalized
            HAVING total_mines >= 10
            ORDER BY total_mines DESC LIMIT 15
        """)
        fig = px.bar(df, x="controller", y="total_mines", color_discrete_sequence=["#0984E3"])
        fig.update_layout(**DARK, height=350, xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)

    # Mine detail: ownership timeline
    st.subheader("Mine Ownership Timeline")
    mine_id = st.text_input("Enter Mine ID to view ownership history")
    if mine_id:
        df = query("""
            SELECT controller_name, operator_name, effective_date, termination_date,
                   CASE WHEN is_current = 1 THEN 'Current' ELSE 'Historical' END as status
            FROM controller_history
            WHERE mine_id = ?
            ORDER BY effective_date DESC
        """, [mine_id])
        if df.empty:
            st.warning("No ownership history found for this mine.")
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)

# ─── CONTRACTOR SAFETY ────────────────────────────────────────────────────────
elif page == "Contractor Safety":
    st.title("Contractor Safety Analysis")

    conn = get_conn()
    if not _table_exists(conn, "contractor_production") or not _table_exists(conn, "mine_production"):
        st.warning("No contractor data loaded. Run the pipeline first: `python -m src.cli pipeline`")
        st.stop()

    has_contr = query("SELECT COUNT(*) as n FROM contractor_production").iloc[0]["n"]
    if has_contr == 0:
        st.info("No contractor production data available. Run `scrape-contractors` to enable.")
        st.stop()

    contr_stats = query("""
        SELECT
            COUNT(*) as total_records,
            COUNT(DISTINCT contractor_id) as unique_contractors,
            SUM(CASE WHEN subunit_cd != '99' THEN employee_hours ELSE 0 END) as total_hours,
            COUNT(DISTINCT calendar_year) as years_covered
        FROM contractor_production
    """).iloc[0]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Contractor Records", fmt(int(contr_stats["total_records"])))
    c2.metric("Unique Contractors", fmt(int(contr_stats["unique_contractors"])))
    c3.metric("Contractor Hours", f"{int(contr_stats['total_hours'] or 0):,}")
    c4.metric("Years Covered", int(contr_stats["years_covered"]))

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Operator vs Contractor Hours by Year")
        df = query("""
            SELECT 'Operator' as type, calendar_year as year, SUM(employee_hours) as hours
            FROM mine_production WHERE subunit_cd != '99' AND calendar_year BETWEEN 2010 AND 2026
            GROUP BY calendar_year
            UNION ALL
            SELECT 'Contractor' as type, calendar_year as year, SUM(employee_hours) as hours
            FROM contractor_production WHERE subunit_cd != '99' AND calendar_year BETWEEN 2010 AND 2026
            GROUP BY calendar_year
            ORDER BY year, type
        """)
        if not df.empty:
            fig = px.bar(df, x="year", y="hours", color="type", barmode="group",
                         color_discrete_map={"Operator": "#0984E3", "Contractor": "#E17055"})
            fig.update_layout(**DARK, height=400)
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Top Contractors by Employee Hours")
        df = query("""
            SELECT contractor_name as contractor, SUM(employee_hours) as hours,
                   COUNT(DISTINCT calendar_year) as years_active
            FROM contractor_production
            WHERE contractor_name IS NOT NULL AND contractor_name != ''
                AND subunit_cd != '99'
            GROUP BY contractor_id
            ORDER BY hours DESC LIMIT 15
        """)
        fig = px.bar(df, x="contractor", y="hours", color_discrete_sequence=["#6C5CE7"])
        fig.update_layout(**DARK, height=400, xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Contractor Accident Rate Comparison")
    st.caption("Comparing contractor vs operator incidence rates at the same mines")
    df = query("""
        WITH op_hours AS (
            SELECT calendar_year as year, SUM(employee_hours) as hours
            FROM mine_production
            WHERE subunit_cd != '99' AND calendar_year BETWEEN 2010 AND 2026
            GROUP BY calendar_year
        ),
        contr_hours AS (
            SELECT calendar_year as year, SUM(employee_hours) as hours
            FROM contractor_production
            WHERE subunit_cd != '99' AND calendar_year BETWEEN 2010 AND 2026
            GROUP BY calendar_year
        ),
        op_injuries AS (
            SELECT cal_yr as year, COUNT(*) as injuries
            FROM accidents
            WHERE degree_injury_cd IN ('01','02','03','04','05')
                AND (contractor_id IS NULL OR contractor_id = '')
                AND cal_yr BETWEEN 2010 AND 2026
            GROUP BY cal_yr
        ),
        contr_injuries AS (
            SELECT cal_yr as year, COUNT(*) as injuries
            FROM accidents
            WHERE degree_injury_cd IN ('01','02','03','04','05')
                AND contractor_id IS NOT NULL AND contractor_id != ''
                AND cal_yr BETWEEN 2010 AND 2026
            GROUP BY cal_yr
        )
        SELECT o.year,
               o.hours as op_hours,
               COALESCE(c.hours, 0) as contr_hours,
               COALESCE(oi.injuries, 0) as op_injuries,
               COALESCE(ci.injuries, 0) as contr_injuries
        FROM op_hours o
        LEFT JOIN contr_hours c ON o.year = c.year
        LEFT JOIN op_injuries oi ON o.year = oi.year
        LEFT JOIN contr_injuries ci ON o.year = ci.year
        WHERE o.hours > 0
        ORDER BY o.year
    """)
    if not df.empty:
        df["op_rate"] = (df["op_injuries"] * 200_000 / df["op_hours"]).round(2)
        df["contr_rate"] = df.apply(
            lambda r: round(r["contr_injuries"] * 200_000 / r["contr_hours"], 2) if r["contr_hours"] and r["contr_hours"] > 0 else 0, axis=1)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df["year"], y=df["op_rate"], name="Operator Rate",
                                 line=dict(color="#0984E3", width=2)))
        fig.add_trace(go.Scatter(x=df["year"], y=df["contr_rate"], name="Contractor Rate",
                                 line=dict(color="#E17055", width=2)))
        fig.update_layout(**DARK, height=350, yaxis_title="Incidence Rate per 200K hours")
        st.plotly_chart(fig, use_container_width=True)

# ─── ACCIDENT ANALYSIS ───────────────────────────────────────────────────────
elif page == "Accident Analysis":
    st.title("Accident & Injury Analysis")

    conn = get_conn()
    if not _table_exists(conn, "accidents") or not _table_exists(conn, "mines"):
        st.warning("No accident data loaded. Run the pipeline first: `python -m src.cli pipeline`")
        st.stop()

    yr_range_df = query("SELECT MIN(cal_yr) as mn, MAX(cal_yr) as mx FROM accidents WHERE cal_yr IS NOT NULL")
    if yr_range_df.empty or yr_range_df.iloc[0]["mn"] is None:
        st.info("No accident data available.")
        st.stop()

    yr_range = yr_range_df.iloc[0]
    col1, col2 = st.columns(2)
    with col1:
        yr_start, yr_end = st.slider("Year Range", int(yr_range["mn"]), int(yr_range["mx"]),
                                      (2010, int(yr_range["mx"])))
    with col2:
        coal_metal = st.selectbox("Coal/Metal", ["All", "C", "M"], index=0)

    where = "cal_yr BETWEEN ? AND ?"
    params = [yr_start, yr_end]
    if coal_metal != "All":
        where += " AND coal_metal_ind = ?"
        params.append(coal_metal)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Injury Severity Distribution")
        df = query(f"""
            SELECT degree_injury, COUNT(*) as count
            FROM accidents WHERE {where} AND degree_injury IS NOT NULL AND degree_injury != ''
            GROUP BY degree_injury ORDER BY count DESC
        """, params)
        fig = px.bar(df, x="degree_injury", y="count", color_discrete_sequence=["#E17055"])
        fig.update_layout(**DARK, height=400, xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Accident Classification")
        df = query(f"""
            SELECT classification, COUNT(*) as count
            FROM accidents WHERE {where} AND classification IS NOT NULL AND classification != ''
            GROUP BY classification ORDER BY count DESC LIMIT 15
        """, params)
        fig = px.bar(df, x="count", y="classification", orientation="h",
                     color_discrete_sequence=["#0984E3"])
        fig.update_layout(**DARK, height=400)
        st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Body Parts Injured")
        df = query(f"""
            SELECT inj_body_part, COUNT(*) as count
            FROM accidents WHERE {where} AND inj_body_part IS NOT NULL AND inj_body_part != ''
            GROUP BY inj_body_part ORDER BY count DESC LIMIT 15
        """, params)
        fig = px.bar(df, x="count", y="inj_body_part", orientation="h",
                     color_discrete_sequence=["#6C5CE7"])
        fig.update_layout(**DARK, height=400)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Worker Experience at Time of Injury")
        df = query(f"""
            SELECT CASE
                WHEN tot_exper < 1 THEN '< 1 yr'
                WHEN tot_exper < 5 THEN '1-5 yrs'
                WHEN tot_exper < 10 THEN '5-10 yrs'
                WHEN tot_exper < 20 THEN '10-20 yrs'
                ELSE '20+ yrs'
            END as experience,
            COUNT(*) as count
            FROM accidents WHERE {where} AND tot_exper IS NOT NULL
            GROUP BY experience ORDER BY MIN(tot_exper)
        """, params)
        fig = px.pie(df, values="count", names="experience")
        fig.update_layout(**DARK, height=400)
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Fatalities by Year")
    df = query(f"""
        SELECT cal_yr as year,
               SUM(CASE WHEN coal_metal_ind = 'C' THEN 1 ELSE 0 END) as coal,
               SUM(CASE WHEN coal_metal_ind = 'M' THEN 1 ELSE 0 END) as metal
        FROM accidents
        WHERE degree_injury_cd = '01' AND cal_yr BETWEEN ? AND ?
        GROUP BY cal_yr ORDER BY cal_yr
    """, [yr_start, yr_end])
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df["year"], y=df["coal"], name="Coal", marker_color="#E17055"))
    fig.add_trace(go.Bar(x=df["year"], y=df["metal"], name="Metal/Non-Metal", marker_color="#0984E3"))
    fig.update_layout(barmode="stack", **DARK, height=350)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Recent Fatal Accidents")
    df = query("""
        SELECT a.accident_dt, a.mine_id, m.mine_name, m.state, a.operator_name,
               a.classification, a.narrative
        FROM accidents a
        LEFT JOIN mines m ON a.mine_id = m.mine_id
        WHERE a.degree_injury_cd = '01'
        ORDER BY a.accident_dt DESC LIMIT 25
    """)
    st.dataframe(df, use_container_width=True, hide_index=True)

# ─── OPERATOR PROFILES ───────────────────────────────────────────────────────
elif page == "Operator Profiles":
    st.title("Operator Safety Profiles")

    conn = get_conn()
    if not _table_exists(conn, "operator_profiles"):
        st.warning("No operator profiles loaded. Run the pipeline first: `python -m src.cli pipeline`")
        st.stop()

    col1, col2, col3 = st.columns(3)
    with col1:
        risk_filter = st.multiselect("Risk Tier", ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
                                      default=["HIGH", "CRITICAL"])
    with col2:
        min_mines = st.number_input("Minimum Mines", value=1, min_value=0)
    with col3:
        search = st.text_input("Search Operator Name")

    where_parts = []
    params = []
    if risk_filter:
        placeholders = ",".join(["?"] * len(risk_filter))
        where_parts.append(f"risk_tier IN ({placeholders})")
        params.extend(risk_filter)
    where_parts.append("mine_count >= ?")
    params.append(min_mines)
    if search:
        where_parts.append("(normalized_name LIKE ? OR operator_name LIKE ?)")
        params.extend([f"%{search.upper()}%", f"%{search}%"])

    where = " AND ".join(where_parts)

    df = query(f"""
        SELECT operator_name, normalized_name, risk_tier, safety_score,
               mine_count, active_mine_count, total_employees,
               total_fatalities, total_injuries, total_violations,
               sig_sub_violations, total_proposed_penalties, total_paid_penalties,
               days_lost, states
        FROM operator_profiles
        WHERE {where}
        ORDER BY safety_score ASC
        LIMIT 500
    """, params)

    st.markdown(f"**{len(df):,} operators** matching filters")

    tier_counts = df["risk_tier"].value_counts()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("CRITICAL", tier_counts.get("CRITICAL", 0))
    c2.metric("HIGH", tier_counts.get("HIGH", 0))
    c3.metric("MEDIUM", tier_counts.get("MEDIUM", 0))
    c4.metric("LOW", tier_counts.get("LOW", 0))

    st.dataframe(df, use_container_width=True, hide_index=True,
                 column_config={
                     "safety_score": st.column_config.ProgressColumn(
                         "Safety Score", min_value=0, max_value=1, format="%.3f"),
                     "total_proposed_penalties": st.column_config.NumberColumn(
                         "Proposed Penalties", format="$%d"),
                     "total_paid_penalties": st.column_config.NumberColumn(
                         "Paid Penalties", format="$%d"),
                 })

    st.subheader("Safety Score Distribution")
    fig = px.histogram(df, x="safety_score", nbins=50, color_discrete_sequence=["#0984E3"])
    fig.update_layout(**DARK, height=300)
    st.plotly_chart(fig, use_container_width=True)

# ─── VIOLATION EXPLORER ──────────────────────────────────────────────────────
elif page == "Violation Explorer":
    st.title("Violation Explorer")

    conn = get_conn()
    if not _table_exists(conn, "violations"):
        st.warning("No violation data loaded. Run the pipeline first: `python -m src.cli pipeline`")
        st.stop()

    yr_range_df = query("SELECT MIN(cal_yr) as mn, MAX(cal_yr) as mx FROM violations WHERE cal_yr IS NOT NULL")
    if yr_range_df.empty or yr_range_df.iloc[0]["mn"] is None:
        st.info("No violation data available.")
        st.stop()

    yr_range = yr_range_df.iloc[0]
    col1, col2, col3 = st.columns(3)
    with col1:
        viol_yr = st.slider("Year Range", int(yr_range["mn"]), int(yr_range["mx"]),
                             (2015, int(yr_range["mx"])), key="viol_yr")
    with col2:
        ss_only = st.checkbox("Significant & Substantial Only", value=False)
    with col3:
        min_penalty = st.number_input("Min Proposed Penalty ($)", value=0, min_value=0)

    where = "cal_yr BETWEEN ? AND ?"
    params = [viol_yr[0], viol_yr[1]]
    if ss_only:
        where += " AND sig_sub = 'Y'"
    if min_penalty > 0:
        where += " AND proposed_penalty >= ?"
        params.append(min_penalty)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Top Violated Standards")
        df = query(f"""
            SELECT part_section, part_section_desc, COUNT(*) as count,
                   SUM(proposed_penalty) as total_penalty
            FROM violations
            WHERE {where} AND part_section IS NOT NULL AND part_section != ''
            GROUP BY part_section, part_section_desc
            ORDER BY count DESC LIMIT 20
        """, params)
        st.dataframe(df, use_container_width=True, hide_index=True,
                     column_config={"total_penalty": st.column_config.NumberColumn(format="$%d")})

    with col2:
        st.subheader("S&S Violations by Year")
        df = query("""
            SELECT cal_yr as year,
                   SUM(CASE WHEN sig_sub = 'Y' THEN 1 ELSE 0 END) as ss_count,
                   SUM(CASE WHEN sig_sub != 'Y' OR sig_sub IS NULL THEN 1 ELSE 0 END) as other
            FROM violations
            WHERE cal_yr BETWEEN 2000 AND 2026
            GROUP BY cal_yr ORDER BY cal_yr
        """)
        fig = go.Figure()
        fig.add_trace(go.Bar(x=df["year"], y=df["ss_count"], name="S&S", marker_color="#D63031"))
        fig.add_trace(go.Bar(x=df["year"], y=df["other"], name="Other", marker_color="#636E72"))
        fig.update_layout(barmode="stack", **DARK, height=400)
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Violations by Section of Act")
    df = query(f"""
        SELECT section_of_act, section_of_act_desc, COUNT(*) as count,
               ROUND(SUM(proposed_penalty), 0) as total_penalty,
               SUM(CASE WHEN sig_sub = 'Y' THEN 1 ELSE 0 END) as ss_count
        FROM violations
        WHERE {where} AND section_of_act IS NOT NULL AND section_of_act != ''
        GROUP BY section_of_act, section_of_act_desc
        ORDER BY count DESC
    """, params)
    fig = px.bar(df, x="section_of_act_desc", y="count", color_discrete_sequence=["#0984E3"])
    fig.update_layout(**DARK, height=350, xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)

# ─── PENALTY ANALYSIS ────────────────────────────────────────────────────────
elif page == "Penalty Analysis":
    st.title("Penalty & Enforcement Analysis")

    conn = get_conn()
    if not _table_exists(conn, "assessed_violations"):
        st.warning("No penalty data loaded. Run the pipeline first: `python -m src.cli pipeline`")
        st.stop()

    penalty_stats_df = query("""
        SELECT
            COALESCE(SUM(proposed_penalty_amt), 0) as total_proposed,
            COALESCE(SUM(paid_proposed_penalty_amt), 0) as total_paid,
            COUNT(*) as total_assessed,
            AVG(proposed_penalty_amt) as avg_penalty,
            MAX(proposed_penalty_amt) as max_penalty,
            AVG(penalty_points) as avg_points
        FROM assessed_violations
        WHERE proposed_penalty_amt IS NOT NULL
    """)
    if penalty_stats_df.empty:
        st.info("No penalty data available.")
        st.stop()

    stats = penalty_stats_df.iloc[0]
    avg_penalty = stats['avg_penalty'] if stats['avg_penalty'] is not None else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Proposed", f"${stats['total_proposed']:,.0f}")
    c2.metric("Total Paid", f"${stats['total_paid']:,.0f}")
    c3.metric("Collection Rate", f"{stats['total_paid']/max(stats['total_proposed'],1)*100:.1f}%")
    c4.metric("Avg Penalty", f"${avg_penalty:,.0f}")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Penalties by Year")
        df = query("""
            SELECT cal_yr as year,
                   ROUND(SUM(proposed_penalty_amt), 0) as proposed,
                   ROUND(SUM(paid_proposed_penalty_amt), 0) as paid
            FROM assessed_violations
            WHERE cal_yr BETWEEN 2000 AND 2026
            GROUP BY cal_yr ORDER BY cal_yr
        """)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df["year"], y=df["proposed"], name="Proposed",
                                 line=dict(color="#D63031", width=2)))
        fig.add_trace(go.Scatter(x=df["year"], y=df["paid"], name="Paid",
                                 line=dict(color="#00B894", width=2)))
        fig.update_layout(**DARK, height=400, yaxis_title="$ Amount")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Penalty Point Distribution")
        df = query("""
            SELECT CASE
                WHEN penalty_points < 10 THEN '0-9'
                WHEN penalty_points < 30 THEN '10-29'
                WHEN penalty_points < 60 THEN '30-59'
                WHEN penalty_points < 90 THEN '60-89'
                ELSE '90+'
            END as bracket,
            COUNT(*) as count
            FROM assessed_violations
            WHERE penalty_points IS NOT NULL
            GROUP BY bracket ORDER BY MIN(penalty_points)
        """)
        fig = px.bar(df, x="bracket", y="count", color_discrete_sequence=["#FDCB6E"])
        fig.update_layout(**DARK, height=400)
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Negligence Assessment")
    df = query("""
        SELECT negligence, COUNT(*) as count,
               ROUND(AVG(proposed_penalty_amt), 0) as avg_penalty,
               ROUND(SUM(proposed_penalty_amt), 0) as total_penalty
        FROM assessed_violations
        WHERE negligence IS NOT NULL AND negligence != ''
        GROUP BY negligence ORDER BY total_penalty DESC
    """)
    st.dataframe(df, use_container_width=True, hide_index=True,
                 column_config={
                     "avg_penalty": st.column_config.NumberColumn(format="$%d"),
                     "total_penalty": st.column_config.NumberColumn(format="$%d"),
                 })

    st.subheader("Gravity vs Likelihood Matrix")
    df = query("""
        SELECT gravity, likely, COUNT(*) as count,
               ROUND(AVG(proposed_penalty_amt), 0) as avg_penalty
        FROM assessed_violations
        WHERE gravity IS NOT NULL AND gravity != '' AND likely IS NOT NULL AND likely != ''
        GROUP BY gravity, likely
    """)
    if not df.empty:
        pivot = df.pivot_table(index="gravity", columns="likely", values="count", fill_value=0)
        fig = px.imshow(pivot, text_auto=True, color_continuous_scale="Reds")
        fig.update_layout(**DARK, height=400)
        st.plotly_chart(fig, use_container_width=True)

# ─── MINE SEARCH ─────────────────────────────────────────────────────────────
elif page == "Mine Search":
    st.title("Mine Search & Detail")

    conn = get_conn()
    if not _table_exists(conn, "mines"):
        st.warning("No mine data loaded. Run the pipeline first: `python -m src.cli pipeline`")
        st.stop()

    col1, col2, col3 = st.columns(3)
    with col1:
        mine_search = st.text_input("Search mine name or ID")
    with col2:
        _states_df = query("SELECT DISTINCT state FROM mines WHERE state != '' ORDER BY state")
        state_filter = st.selectbox("State", ["All"] + (_states_df["state"].tolist() if not _states_df.empty else []))
    with col3:
        status_filter = st.selectbox("Status", ["All", "Active", "Abandoned", "Intermittent",
                                                  "Temporarily Idle", "New Mine"])

    where_parts = ["1=1"]
    params = []
    if mine_search:
        where_parts.append("(mine_name LIKE ? OR mine_id LIKE ?)")
        params.extend([f"%{mine_search}%", f"%{mine_search}%"])
    if state_filter != "All":
        where_parts.append("state = ?")
        params.append(state_filter)
    if status_filter != "All":
        where_parts.append("mine_status = ?")
        params.append(status_filter)

    where = " AND ".join(where_parts)
    df = query(f"""
        SELECT mine_id, mine_name, state, mine_type, mine_status, operator_name,
               controller_name, primary_sic, no_employees, quality_score
        FROM mines WHERE {where} ORDER BY mine_name LIMIT 200
    """, params)

    st.markdown(f"**{len(df):,} mines** found (showing max 200)")
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Mine Detail View")
    mine_id = st.text_input("Enter Mine ID for full detail")
    if mine_id:
        mine = query("SELECT * FROM mines WHERE mine_id = ?", [mine_id])
        if mine.empty:
            st.warning("Mine not found.")
        else:
            m = mine.iloc[0]
            c1, c2, c3 = st.columns(3)
            c1.metric("Mine Name", m["mine_name"])
            c2.metric("State", m["state"])
            c3.metric("Status", m["mine_status"])

            c1, c2, c3 = st.columns(3)
            c1.metric("Operator", m["operator_name"])
            c2.metric("Employees", fmt(int(m["no_employees"])) if m["no_employees"] else "N/A")
            c3.metric("Type", m["mine_type"])

            st.markdown("#### Accidents at this mine")
            acc = query("""
                SELECT accident_dt, degree_injury, classification, narrative
                FROM accidents WHERE mine_id = ? ORDER BY accident_dt DESC LIMIT 20
            """, [mine_id])
            st.dataframe(acc, use_container_width=True, hide_index=True)

            st.markdown("#### Recent Violations")
            viol = query("""
                SELECT violation_issue_dt, part_section, part_section_desc, sig_sub,
                       proposed_penalty
                FROM violations WHERE mine_id = ? ORDER BY violation_issue_dt DESC LIMIT 20
            """, [mine_id])
            st.dataframe(viol, use_container_width=True, hide_index=True)

            # Enrichment: production history
            prod = query("""
                SELECT calendar_year, subunit_desc, avg_employee_cnt, employee_hours,
                       coal_production
                FROM mine_production WHERE mine_id = ? ORDER BY calendar_year DESC
            """, [mine_id])
            if not prod.empty:
                st.markdown("#### Production & Employment History")
                st.dataframe(prod, use_container_width=True, hide_index=True)

            # Enrichment: ownership history
            ctrl = query("""
                SELECT controller_name, operator_name, effective_date, termination_date,
                       CASE WHEN is_current = 1 THEN 'Current' ELSE 'Historical' END as status
                FROM controller_history WHERE mine_id = ? ORDER BY effective_date DESC
            """, [mine_id])
            if not ctrl.empty:
                st.markdown("#### Ownership History")
                st.dataframe(ctrl, use_container_width=True, hide_index=True)

            # Enrichment: closure orders
            orders = query("""
                SELECT order_no, order_type_desc, issue_date, terminate_date,
                       section_of_act, part_section
                FROM closure_orders WHERE mine_id = ? ORDER BY issue_date DESC
            """, [mine_id])
            if not orders.empty:
                st.markdown("#### Closure Orders")
                st.dataframe(orders, use_container_width=True, hide_index=True)

# ─── STATE COMPARISON ────────────────────────────────────────────────────────
elif page == "State Comparison":
    st.title("State-by-State Comparison")

    conn = get_conn()
    if not _table_exists(conn, "mines") or not _table_exists(conn, "accidents") or not _table_exists(conn, "violations"):
        st.warning("No data loaded. Run the pipeline first: `python -m src.cli pipeline`")
        st.stop()

    df = query("""
        SELECT m.state,
               COUNT(DISTINCT m.mine_id) as mines,
               SUM(CASE WHEN m.mine_status = 'Active' THEN 1 ELSE 0 END) as active_mines,
               COALESCE(SUM(m.no_employees), 0) as employees
        FROM mines m
        WHERE m.state IS NOT NULL AND m.state != ''
        GROUP BY m.state
        ORDER BY mines DESC
    """)

    acc_df = query("""
        SELECT m.state,
               COUNT(*) as accidents,
               SUM(CASE WHEN a.degree_injury_cd = '01' THEN 1 ELSE 0 END) as fatalities,
               SUM(CASE WHEN a.degree_injury_cd IN ('01','02','03','04','05') THEN 1 ELSE 0 END) as injuries
        FROM accidents a
        JOIN mines m ON a.mine_id = m.mine_id
        WHERE m.state IS NOT NULL AND m.state != ''
        GROUP BY m.state
    """)

    viol_df = query("""
        SELECT m.state,
               COUNT(*) as violations,
               SUM(CASE WHEN v.sig_sub = 'Y' THEN 1 ELSE 0 END) as ss_violations
        FROM violations v
        JOIN mines m ON v.mine_id = m.mine_id
        WHERE m.state IS NOT NULL AND m.state != ''
        GROUP BY m.state
    """)

    # Enrichment: add employee hours per state
    hours_df = query("""
        SELECT m.state, SUM(p.employee_hours) as employee_hours
        FROM mine_production p
        JOIN mines m ON p.mine_id = m.mine_id
        WHERE p.subunit_cd != '99' AND m.state IS NOT NULL AND m.state != ''
        GROUP BY m.state
    """)

    merged = df.merge(acc_df, on="state", how="left").merge(viol_df, on="state", how="left")
    merged = merged.merge(hours_df, on="state", how="left").fillna(0)
    for col in ["accidents", "fatalities", "injuries", "violations", "ss_violations"]:
        merged[col] = merged[col].astype(int)
    merged["employee_hours"] = merged["employee_hours"].astype(int)

    # Add rate columns — use injuries (degree codes 01-05), not raw accident count
    merged["incidence_rate"] = merged.apply(
        lambda r: round(r["injuries"] * 200_000 / r["employee_hours"], 2) if r["employee_hours"] > 0 else 0, axis=1)

    st.dataframe(merged, use_container_width=True, hide_index=True)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Mines by State (Top 15)")
        top15 = merged.nlargest(15, "mines")
        fig = px.bar(top15, x="state", y="mines", color_discrete_sequence=["#0984E3"])
        fig.update_layout(**DARK, height=350)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Fatalities by State (Top 15)")
        top15 = merged.nlargest(15, "fatalities")
        fig = px.bar(top15, x="state", y="fatalities", color_discrete_sequence=["#D63031"])
        fig.update_layout(**DARK, height=350)
        st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Violations per Mine (Top 15 States)")
        merged["violations_per_mine"] = (merged["violations"] / merged["mines"].replace(0, 1)).round(1)
        top15 = merged.nlargest(15, "violations_per_mine")
        fig = px.bar(top15, x="state", y="violations_per_mine", color_discrete_sequence=["#E17055"])
        fig.update_layout(**DARK, height=350)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Incidence Rate by State (Top 15)")
        top15 = merged[merged["employee_hours"] > 0].nlargest(15, "incidence_rate")
        fig = px.bar(top15, x="state", y="incidence_rate", color_discrete_sequence=["#6C5CE7"])
        fig.add_hline(y=2.0, line_dash="dash", line_color="#FDCB6E",
                     annotation_text="National Avg")
        fig.update_layout(**DARK, height=350)
        st.plotly_chart(fig, use_container_width=True)

# ─── GEOGRAPHIC MAP ──────────────────────────────────────────────────────────
elif page == "Geographic Map":
    st.title("Mine Geographic Map")
    st.markdown("Map of U.S. mines colored by safety risk and sized by employee count.")

    conn = get_conn()
    if not _table_exists(conn, "mines"):
        st.warning("No mine data loaded. Run the pipeline first: `python -m src.cli pipeline`")
        st.stop()

    col1, col2 = st.columns(2)
    with col1:
        map_status = st.selectbox("Mine Status", ["Active", "All", "Abandoned", "Temporarily Idle"])
    with col2:
        map_coal = st.selectbox("Mine Type", ["All", "Coal", "Metal/Non-Metal"])

    where_parts = [
        "latitude IS NOT NULL AND latitude != ''",
        "longitude IS NOT NULL AND longitude != ''",
        "CAST(latitude AS REAL) BETWEEN 18 AND 72",
        "CAST(longitude AS REAL) BETWEEN -180 AND -60",
    ]
    params = []
    if map_status != "All":
        where_parts.append("mine_status = ?")
        params.append(map_status)
    if map_coal == "Coal":
        where_parts.append("coal_metal_ind = 'C'")
    elif map_coal == "Metal/Non-Metal":
        where_parts.append("coal_metal_ind = 'M'")

    where = " AND ".join(where_parts)
    df = query(f"""
        SELECT mine_id, mine_name, state, mine_type, mine_status,
               operator_name, CAST(latitude AS REAL) as lat, CAST(longitude AS REAL) as lon,
               COALESCE(no_employees, 1) as employees, coal_metal_ind
        FROM mines
        WHERE {where}
        LIMIT 5000
    """, params)

    if df.empty:
        st.info("No mines with geographic coordinates matching filters.")
    else:
        st.markdown(f"**{len(df):,} mines** displayed")
        color_col = "coal_metal_ind"
        color_map = {"C": "#E17055", "M": "#0984E3", "": "#636E72"}

        fig = px.scatter_mapbox(
            df, lat="lat", lon="lon",
            color=color_col, color_discrete_map=color_map,
            size="employees", size_max=15,
            hover_name="mine_name",
            hover_data={"state": True, "operator_name": True, "mine_status": True,
                        "employees": True, "lat": False, "lon": False},
            mapbox_style="carto-darkmatter",
            zoom=3, center={"lat": 39.0, "lon": -98.0},
            height=600,
        )
        fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig, use_container_width=True)

# ─── DATA QUALITY ────────────────────────────────────────────────────────────
elif page == "Data Quality":
    st.title("Data Quality Analysis")

    conn = get_conn()
    if not _table_exists(conn, "mines"):
        st.warning("No data loaded. Run the pipeline first: `python -m src.cli pipeline`")
        st.stop()

    tables = [
        "mines", "accidents", "inspections", "violations",
        "assessed_violations", "penalties",
        "mine_production", "contractor_production",
        "controller_history", "closure_orders",
    ]
    quality_stats = []
    for table in tables:
        if not _table_exists(conn, table):
            quality_stats.append({
                "table": table,
                "records": 0,
                "avg_quality": 0.0,
                "high_quality_pct": 0.0,
                "min_score": 0.0,
                "max_score": 0.0,
            })
            continue
        row = query(f"""
            SELECT COUNT(*) as total,
                   AVG(quality_score) as avg_score,
                   SUM(CASE WHEN quality_score >= 0.8 THEN 1 ELSE 0 END) as high_quality,
                   MIN(quality_score) as min_score,
                   MAX(quality_score) as max_score
            FROM {table}
        """)
        if row.empty:
            quality_stats.append({
                "table": table,
                "records": 0,
                "avg_quality": 0.0,
                "high_quality_pct": 0.0,
                "min_score": 0.0,
                "max_score": 0.0,
            })
            continue
        row = row.iloc[0]
        quality_stats.append({
            "table": table,
            "records": int(row["total"]),
            "avg_quality": round(float(row["avg_score"] or 0), 3),
            "high_quality_pct": round(float(row["high_quality"] or 0) / max(int(row["total"]), 1) * 100, 1),
            "min_score": round(float(row["min_score"] or 0), 3),
            "max_score": round(float(row["max_score"] or 0), 3),
        })

    df = pd.DataFrame(quality_stats)
    total_records = df["records"].sum()

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Records", fmt(total_records))
    c2.metric("Avg Quality Score", f"{df['avg_quality'].mean():.3f}")
    c3.metric("Tables", len(tables))

    st.dataframe(df, use_container_width=True, hide_index=True,
                 column_config={
                     "avg_quality": st.column_config.ProgressColumn(
                         "Avg Quality", min_value=0, max_value=1, format="%.3f"),
                     "high_quality_pct": st.column_config.ProgressColumn(
                         "High Quality %", min_value=0, max_value=100, format="%.1f%%"),
                 })

    st.subheader("Quality Score Distributions")
    col1, col2 = st.columns(2)
    with col1:
        df = query("SELECT quality_score FROM mines WHERE quality_score IS NOT NULL")
        fig = px.histogram(df, x="quality_score", nbins=50, title="Mines",
                           color_discrete_sequence=["#0984E3"])
        fig.update_layout(**DARK, height=300)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        df = query("SELECT quality_score FROM accidents WHERE quality_score IS NOT NULL")
        fig = px.histogram(df, x="quality_score", nbins=50, title="Accidents",
                           color_discrete_sequence=["#E17055"])
        fig.update_layout(**DARK, height=300)
        st.plotly_chart(fig, use_container_width=True)

# ─── FOOTER ──────────────────────────────────────────────────────────────────
st.divider()
st.markdown(
    "<div style='text-align: center; color: #636E72; padding: 1rem;'>"
    "Built by <b>Nathan Goldberg</b> · "
    "<a href='mailto:nathanmauricegoldberg@gmail.com'>nathanmauricegoldberg@gmail.com</a> · "
    "<a href='https://linkedin.com/in/nathanmauricegoldberg'>LinkedIn</a>"
    "</div>",
    unsafe_allow_html=True,
)
