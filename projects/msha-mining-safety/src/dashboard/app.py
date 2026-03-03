"""MSHA Mining Safety & Enforcement Tracker — Streamlit Dashboard."""

import os
import sqlite3

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "msha.db")


@st.cache_resource
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


@st.cache_data(ttl=600)
def query(sql, params=None):
    conn = get_conn()
    return pd.read_sql_query(sql, conn, params=params or [])


def fmt(n):
    if isinstance(n, float):
        return f"${n:,.0f}" if n > 100 else f"{n:.2f}"
    return f"{n:,}"


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
    "Accident Analysis",
    "Operator Profiles",
    "Violation Explorer",
    "Penalty Analysis",
    "Mine Search",
    "State Comparison",
    "Data Quality",
])

# ─── OVERVIEW ────────────────────────────────────────────────────────────────
if page == "Overview":
    st.title("⛏️ MSHA Mining Safety & Enforcement Tracker")
    st.markdown("Comprehensive analysis of U.S. mine safety data from the Mine Safety and Health Administration.")

    stats = query("""
        SELECT
            (SELECT COUNT(*) FROM mines) as mines,
            (SELECT COUNT(*) FROM mines WHERE mine_status = 'Active') as active_mines,
            (SELECT COUNT(*) FROM accidents) as accidents,
            (SELECT COUNT(*) FROM accidents WHERE degree_injury_cd = '01') as fatalities,
            (SELECT COUNT(*) FROM inspections) as inspections,
            (SELECT COUNT(*) FROM violations) as violations,
            (SELECT COALESCE(SUM(proposed_penalty_amt), 0) FROM assessed_violations) as proposed_penalties,
            (SELECT COALESCE(SUM(paid_proposed_penalty_amt), 0) FROM assessed_violations) as paid_penalties,
            (SELECT COUNT(*) FROM operator_profiles) as profiles,
            (SELECT COUNT(DISTINCT state) FROM mines WHERE state != '') as states
    """).iloc[0]

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Mines", fmt(int(stats["mines"])))
    c2.metric("Active Mines", fmt(int(stats["active_mines"])))
    c3.metric("Accidents/Injuries", fmt(int(stats["accidents"])))
    c4.metric("Fatalities", fmt(int(stats["fatalities"])))
    c5.metric("Violations", fmt(int(stats["violations"])))

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Inspections", fmt(int(stats["inspections"])))
    c2.metric("Proposed Penalties", f"${stats['proposed_penalties']:,.0f}")
    c3.metric("Paid Penalties", f"${stats['paid_penalties']:,.0f}")
    c4.metric("Operator Profiles", fmt(int(stats["profiles"])))
    c5.metric("States/Territories", fmt(int(stats["states"])))

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
        fig = go.Figure()
        fig.add_trace(go.Bar(x=df["year"], y=df["count"], name="All Accidents", marker_color="#0984E3"))
        fig.add_trace(go.Bar(x=df["year"], y=df["fatalities"], name="Fatalities", marker_color="#D63031"))
        fig.update_layout(
            barmode="overlay", template="plotly_dark",
            paper_bgcolor="#0E1117", plot_bgcolor="#0E1117",
            height=400,
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Risk Tier Distribution")
        df = query("""
            SELECT risk_tier, COUNT(*) as count
            FROM operator_profiles
            GROUP BY risk_tier
        """)
        color_map = {"LOW": "#00B894", "MEDIUM": "#FDCB6E", "HIGH": "#E17055", "CRITICAL": "#D63031"}
        fig = px.pie(df, values="count", names="risk_tier",
                     color="risk_tier", color_discrete_map=color_map)
        fig.update_layout(template="plotly_dark", paper_bgcolor="#0E1117",
                          plot_bgcolor="#0E1117", height=400)
        st.plotly_chart(fig, use_container_width=True)

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
        fig = px.bar(df, x="state", y="violations", color_discrete_sequence=["#0984E3"])
        fig.update_layout(template="plotly_dark", paper_bgcolor="#0E1117",
                          plot_bgcolor="#0E1117", height=350)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Top 10 Operators by Penalties")
        df = query("""
            SELECT normalized_name, total_proposed_penalties
            FROM operator_profiles
            WHERE total_proposed_penalties > 0
            ORDER BY total_proposed_penalties DESC LIMIT 10
        """)
        fig = px.bar(df, x="normalized_name", y="total_proposed_penalties",
                     color_discrete_sequence=["#D63031"])
        fig.update_layout(template="plotly_dark", paper_bgcolor="#0E1117",
                          plot_bgcolor="#0E1117", height=350,
                          xaxis_title="Operator", yaxis_title="Proposed Penalties ($)")
        st.plotly_chart(fig, use_container_width=True)

# ─── ACCIDENT ANALYSIS ───────────────────────────────────────────────────────
elif page == "Accident Analysis":
    st.title("Accident & Injury Analysis")

    col1, col2 = st.columns(2)
    with col1:
        yr_range = query("SELECT MIN(cal_yr) as mn, MAX(cal_yr) as mx FROM accidents WHERE cal_yr IS NOT NULL").iloc[0]
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
        fig.update_layout(template="plotly_dark", paper_bgcolor="#0E1117",
                          plot_bgcolor="#0E1117", height=400, xaxis_tickangle=-45)
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
        fig.update_layout(template="plotly_dark", paper_bgcolor="#0E1117",
                          plot_bgcolor="#0E1117", height=400)
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
        fig.update_layout(template="plotly_dark", paper_bgcolor="#0E1117",
                          plot_bgcolor="#0E1117", height=400)
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
        fig.update_layout(template="plotly_dark", paper_bgcolor="#0E1117",
                          plot_bgcolor="#0E1117", height=400)
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
    fig.update_layout(barmode="stack", template="plotly_dark",
                      paper_bgcolor="#0E1117", plot_bgcolor="#0E1117", height=350)
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
    fig.update_layout(template="plotly_dark", paper_bgcolor="#0E1117",
                      plot_bgcolor="#0E1117", height=300)
    st.plotly_chart(fig, use_container_width=True)

# ─── VIOLATION EXPLORER ──────────────────────────────────────────────────────
elif page == "Violation Explorer":
    st.title("Violation Explorer")

    col1, col2, col3 = st.columns(3)
    with col1:
        yr_range = query("SELECT MIN(cal_yr) as mn, MAX(cal_yr) as mx FROM violations WHERE cal_yr IS NOT NULL").iloc[0]
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
        fig.update_layout(barmode="stack", template="plotly_dark",
                          paper_bgcolor="#0E1117", plot_bgcolor="#0E1117", height=400)
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
    fig.update_layout(template="plotly_dark", paper_bgcolor="#0E1117",
                      plot_bgcolor="#0E1117", height=350, xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)

# ─── PENALTY ANALYSIS ────────────────────────────────────────────────────────
elif page == "Penalty Analysis":
    st.title("Penalty & Enforcement Analysis")

    stats = query("""
        SELECT
            COALESCE(SUM(proposed_penalty_amt), 0) as total_proposed,
            COALESCE(SUM(paid_proposed_penalty_amt), 0) as total_paid,
            COUNT(*) as total_assessed,
            AVG(proposed_penalty_amt) as avg_penalty,
            MAX(proposed_penalty_amt) as max_penalty,
            AVG(penalty_points) as avg_points
        FROM assessed_violations
        WHERE proposed_penalty_amt IS NOT NULL
    """).iloc[0]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Proposed", f"${stats['total_proposed']:,.0f}")
    c2.metric("Total Paid", f"${stats['total_paid']:,.0f}")
    c3.metric("Collection Rate", f"{stats['total_paid']/max(stats['total_proposed'],1)*100:.1f}%")
    c4.metric("Avg Penalty", f"${stats['avg_penalty']:,.0f}")

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
        fig.update_layout(template="plotly_dark", paper_bgcolor="#0E1117",
                          plot_bgcolor="#0E1117", height=400, yaxis_title="$ Amount")
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
        fig.update_layout(template="plotly_dark", paper_bgcolor="#0E1117",
                          plot_bgcolor="#0E1117", height=400)
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
        fig.update_layout(template="plotly_dark", paper_bgcolor="#0E1117",
                          plot_bgcolor="#0E1117", height=400)
        st.plotly_chart(fig, use_container_width=True)

# ─── MINE SEARCH ─────────────────────────────────────────────────────────────
elif page == "Mine Search":
    st.title("Mine Search & Detail")

    col1, col2, col3 = st.columns(3)
    with col1:
        mine_search = st.text_input("Search mine name or ID")
    with col2:
        state_filter = st.selectbox("State", ["All"] + query(
            "SELECT DISTINCT state FROM mines WHERE state != '' ORDER BY state"
        )["state"].tolist())
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

# ─── STATE COMPARISON ────────────────────────────────────────────────────────
elif page == "State Comparison":
    st.title("State-by-State Comparison")

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
               SUM(CASE WHEN a.degree_injury_cd = '01' THEN 1 ELSE 0 END) as fatalities
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

    merged = df.merge(acc_df, on="state", how="left").merge(viol_df, on="state", how="left").fillna(0)
    for col in ["accidents", "fatalities", "violations", "ss_violations"]:
        merged[col] = merged[col].astype(int)

    st.dataframe(merged, use_container_width=True, hide_index=True)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Mines by State (Top 15)")
        top15 = merged.nlargest(15, "mines")
        fig = px.bar(top15, x="state", y="mines", color_discrete_sequence=["#0984E3"])
        fig.update_layout(template="plotly_dark", paper_bgcolor="#0E1117",
                          plot_bgcolor="#0E1117", height=350)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Fatalities by State (Top 15)")
        top15 = merged.nlargest(15, "fatalities")
        fig = px.bar(top15, x="state", y="fatalities", color_discrete_sequence=["#D63031"])
        fig.update_layout(template="plotly_dark", paper_bgcolor="#0E1117",
                          plot_bgcolor="#0E1117", height=350)
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Violations per Mine (Top 15 States)")
    merged["violations_per_mine"] = (merged["violations"] / merged["mines"].replace(0, 1)).round(1)
    top15 = merged.nlargest(15, "violations_per_mine")
    fig = px.bar(top15, x="state", y="violations_per_mine", color_discrete_sequence=["#E17055"])
    fig.update_layout(template="plotly_dark", paper_bgcolor="#0E1117",
                      plot_bgcolor="#0E1117", height=350)
    st.plotly_chart(fig, use_container_width=True)

# ─── DATA QUALITY ────────────────────────────────────────────────────────────
elif page == "Data Quality":
    st.title("Data Quality Analysis")

    tables = ["mines", "accidents", "inspections", "violations", "assessed_violations", "penalties"]
    quality_stats = []
    for table in tables:
        row = query(f"""
            SELECT COUNT(*) as total,
                   AVG(quality_score) as avg_score,
                   SUM(CASE WHEN quality_score >= 0.8 THEN 1 ELSE 0 END) as high_quality,
                   MIN(quality_score) as min_score,
                   MAX(quality_score) as max_score
            FROM {table}
        """).iloc[0]
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
        fig.update_layout(template="plotly_dark", paper_bgcolor="#0E1117",
                          plot_bgcolor="#0E1117", height=300)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        df = query("SELECT quality_score FROM accidents WHERE quality_score IS NOT NULL")
        fig = px.histogram(df, x="quality_score", nbins=50, title="Accidents",
                           color_discrete_sequence=["#E17055"])
        fig.update_layout(template="plotly_dark", paper_bgcolor="#0E1117",
                          plot_bgcolor="#0E1117", height=300)
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
