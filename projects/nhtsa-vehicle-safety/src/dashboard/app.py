"""Streamlit dashboard for NHTSA Vehicle Safety Defect Tracker."""

import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

DB_PATH = Path(__file__).parent.parent.parent / "data" / "nhtsa_safety.db"

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


@st.cache_resource
def get_conn():
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def main():
    st.set_page_config(
        page_title="NHTSA Vehicle Safety Defect Tracker",
        page_icon="🚗",
        layout="wide",
    )

    st.title("NHTSA Vehicle Safety Defect Tracker")
    st.markdown("Cross-linked database of complaints, recalls, and investigations")

    conn = get_conn()

    # Sidebar navigation
    page = st.sidebar.radio("Navigate", [
        "Overview",
        "Complaint Explorer",
        "Recall Tracker",
        "Investigation Monitor",
        "Vehicle Deep Dive",
        "Safety Trends",
        "Component Analysis",
        "Manufacturer Risk Profiles",
        "Vehicle Segmentation",
        "Investigation Outcomes",
        "Data Quality",
    ])

    if page == "Overview":
        show_overview(conn)
    elif page == "Complaint Explorer":
        show_complaints(conn)
    elif page == "Recall Tracker":
        show_recalls(conn)
    elif page == "Investigation Monitor":
        show_investigations(conn)
    elif page == "Vehicle Deep Dive":
        show_vehicle_deep_dive(conn)
    elif page == "Safety Trends":
        show_trends(conn)
    elif page == "Component Analysis":
        show_components(conn)
    elif page == "Manufacturer Risk Profiles":
        show_manufacturer_risk(conn)
    elif page == "Vehicle Segmentation":
        show_vehicle_segmentation(conn)
    elif page == "Investigation Outcomes":
        show_investigation_outcomes(conn)
    elif page == "Data Quality":
        show_quality(conn)

    # Footer
    st.markdown("---")
    st.markdown(
        "**Built by Nathan Goldberg** | "
        "nathanmauricegoldberg@gmail.com | "
        "[LinkedIn](https://www.linkedin.com/in/nathan-goldberg-62a44522a/)"
    )


def show_overview(conn):
    """Overview dashboard with KPI cards."""
    st.header("Overview")

    if not _table_exists(conn, "complaints"):
        st.warning(_NO_DATA_MSG)
        return

    # KPI cards
    complaint_count = _safe_fetchone(conn, "SELECT COUNT(*) FROM complaints")
    recall_count = _safe_fetchone(conn, "SELECT COUNT(*) FROM recalls")
    inv_count = _safe_fetchone(conn, "SELECT COUNT(*) FROM investigations")
    link_count = _safe_fetchone(conn, "SELECT COUNT(*) FROM cross_links")
    crash_count = _safe_fetchone(conn, "SELECT COUNT(*) FROM complaints WHERE crash = 1")
    death_count = _safe_fetchone(conn, "SELECT COALESCE(SUM(num_deaths), 0) FROM complaints")
    injury_count = _safe_fetchone(conn, "SELECT COALESCE(SUM(num_injuries), 0) FROM complaints")
    fire_count = _safe_fetchone(conn, "SELECT COUNT(*) FROM complaints WHERE fire = 1")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Complaints", f"{complaint_count:,}")
    c2.metric("Recalls", f"{recall_count:,}")
    c3.metric("Investigations", f"{inv_count:,}")
    c4.metric("Cross-Links", f"{link_count:,}")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Crashes Reported", f"{crash_count:,}")
    c6.metric("Deaths Reported", f"{death_count:,}")
    c7.metric("Injuries Reported", f"{injury_count:,}")
    c8.metric("Fires Reported", f"{fire_count:,}")

    # Top makes
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Top Makes by Complaints")
        df = _safe_query("""
            SELECT make, COUNT(*) as complaints,
                   SUM(crash) as crashes, SUM(fire) as fires,
                   SUM(num_deaths) as deaths
            FROM complaints
            GROUP BY make ORDER BY complaints DESC LIMIT 15
        """, conn)
        if not df.empty:
            fig = px.bar(df, x="make", y="complaints",
                         color="crashes", color_continuous_scale="Reds",
                         title="Complaints by Vehicle Make")
            fig.update_layout(template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Top Components")
        df = _safe_query("""
            SELECT components, COUNT(*) as cnt
            FROM complaints WHERE components != ''
            GROUP BY components ORDER BY cnt DESC LIMIT 15
        """, conn)
        if not df.empty:
            fig = px.bar(df, x="cnt", y="components", orientation="h",
                         title="Most Common Component Complaints")
            fig.update_layout(template="plotly_dark", yaxis={"autorange": "reversed"})
            st.plotly_chart(fig, use_container_width=True)


def show_complaints(conn):
    """Complaint explorer with search and filter."""
    st.header("Complaint Explorer")

    if not _table_exists(conn, "complaints"):
        st.warning(_NO_DATA_MSG)
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        makes = _safe_query(
            "SELECT DISTINCT make FROM complaints ORDER BY make", conn
        )
        makes = makes["make"].tolist() if not makes.empty else []
        selected_make = st.selectbox("Make", ["All"] + makes)
    with col2:
        if selected_make != "All":
            models = pd.read_sql_query(
                "SELECT DISTINCT model FROM complaints WHERE make = ? ORDER BY model",
                conn, params=[selected_make]
            )["model"].tolist()
        else:
            models = []
        selected_model = st.selectbox("Model", ["All"] + models)
    with col3:
        crash_only = st.checkbox("Crashes only")
        fire_only = st.checkbox("Fires only")

    query = "SELECT * FROM complaints WHERE 1=1"
    params = []
    if selected_make != "All":
        query += " AND make = ?"
        params.append(selected_make)
    if selected_model != "All":
        query += " AND model = ?"
        params.append(selected_model)
    if crash_only:
        query += " AND crash = 1"
    if fire_only:
        query += " AND fire = 1"
    query += " ORDER BY date_complaint_filed DESC LIMIT 500"

    df = pd.read_sql_query(query, conn, params=params)
    st.write(f"Showing {len(df)} complaints")
    if not df.empty:
        st.dataframe(
            df[["odi_number", "make", "model", "model_year", "crash", "fire",
                "num_injuries", "num_deaths", "date_complaint_filed",
                "components", "summary"]],
            use_container_width=True,
            height=500,
        )


def show_recalls(conn):
    """Recall tracker."""
    st.header("Recall Tracker")

    if not _table_exists(conn, "recalls"):
        st.warning(_NO_DATA_MSG)
        return

    df = pd.read_sql_query("""
        SELECT campaign_number, manufacturer, make, model, model_year,
               report_received_date, component, summary, consequence,
               num_potentially_affected, park_it
        FROM recalls ORDER BY report_received_date DESC LIMIT 500
    """, conn)

    if df.empty:
        st.info("No recall data loaded yet. Run `python -m src.cli pipeline` with recall fetching enabled.")
        return

    # Park It alerts
    park_it_count = df[df["park_it"] == 1].shape[0]
    if park_it_count > 0:
        st.warning(f"{park_it_count} recalls have 'Park It' (Do Not Drive) advisories")

    affected = df["num_potentially_affected"].sum()
    st.metric("Total Potentially Affected Vehicles", f"{affected:,.0f}")

    st.dataframe(df, use_container_width=True, height=500)


def show_investigations(conn):
    """Investigation monitor."""
    st.header("Investigation Monitor")

    if not _table_exists(conn, "investigations"):
        st.warning(_NO_DATA_MSG)
        return

    df = pd.read_sql_query("""
        SELECT investigation_number, make, model, model_year_start, model_year_end,
               investigation_type, status, open_date, subject
        FROM investigations ORDER BY open_date DESC LIMIT 500
    """, conn)

    if df.empty:
        st.info("No investigation data loaded yet.")
        return

    # Status breakdown
    col1, col2 = st.columns(2)
    with col1:
        status_df = df["status"].value_counts().reset_index()
        status_df.columns = ["Status", "Count"]
        fig = px.pie(status_df, names="Status", values="Count",
                     title="Investigations by Status")
        fig.update_layout(template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        type_df = df["investigation_type"].value_counts().reset_index()
        type_df.columns = ["Type", "Count"]
        fig = px.pie(type_df, names="Type", values="Count",
                     title="Investigations by Type")
        fig.update_layout(template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)

    st.dataframe(df, use_container_width=True, height=400)


def show_vehicle_deep_dive(conn):
    """Deep dive into a specific vehicle."""
    st.header("Vehicle Deep Dive")

    if not _table_exists(conn, "complaints"):
        st.warning(_NO_DATA_MSG)
        return

    makes_df = _safe_query(
        "SELECT DISTINCT make FROM complaints ORDER BY make", conn
    )
    makes = makes_df["make"].tolist() if not makes_df.empty else []
    selected_make = st.selectbox("Select Make", makes if makes else ["No data"])

    if selected_make and selected_make != "No data":
        models = pd.read_sql_query(
            "SELECT DISTINCT model FROM complaints WHERE make = ? ORDER BY model",
            conn, params=[selected_make],
        )["model"].tolist()
        selected_model = st.selectbox("Select Model", models if models else ["All"])

        if selected_model:
            # Complaints for this vehicle
            complaints_df = pd.read_sql_query("""
                SELECT model_year, COUNT(*) as complaints,
                       SUM(crash) as crashes, SUM(fire) as fires,
                       SUM(num_deaths) as deaths, SUM(num_injuries) as injuries
                FROM complaints WHERE make = ? AND model = ?
                GROUP BY model_year ORDER BY model_year
            """, conn, params=[selected_make, selected_model])

            if not complaints_df.empty:
                st.subheader(f"{selected_make} {selected_model} — Complaints by Year")
                fig = px.bar(complaints_df, x="model_year", y="complaints",
                             color="crashes", color_continuous_scale="Reds",
                             title=f"Complaints by Model Year")
                fig.update_layout(template="plotly_dark")
                st.plotly_chart(fig, use_container_width=True)

                # Component breakdown
                comp_df = pd.read_sql_query("""
                    SELECT components, COUNT(*) as cnt
                    FROM complaints WHERE make = ? AND model = ? AND components != ''
                    GROUP BY components ORDER BY cnt DESC LIMIT 10
                """, conn, params=[selected_make, selected_model])
                if not comp_df.empty:
                    st.subheader("Top Components")
                    fig = px.bar(comp_df, x="cnt", y="components", orientation="h")
                    fig.update_layout(template="plotly_dark")
                    st.plotly_chart(fig, use_container_width=True)

            # Related recalls
            recalls_df = pd.read_sql_query("""
                SELECT campaign_number, model_year, report_received_date,
                       component, summary, num_potentially_affected
                FROM recalls WHERE make = ? AND model = ?
                ORDER BY report_received_date DESC
            """, conn, params=[selected_make, selected_model])

            if not recalls_df.empty:
                st.subheader(f"Recalls ({len(recalls_df)})")
                st.dataframe(recalls_df, use_container_width=True)


def show_trends(conn):
    """Safety trends over time."""
    st.header("Safety Trends")

    if not _table_exists(conn, "complaints"):
        st.warning(_NO_DATA_MSG)
        return

    df = pd.read_sql_query("""
        SELECT substr(date_complaint_filed, 1, 7) as month,
               COUNT(*) as complaints,
               SUM(crash) as crashes,
               SUM(fire) as fires,
               SUM(num_deaths) as deaths
        FROM complaints
        WHERE date_complaint_filed != '' AND date_complaint_filed >= '2015-01'
        GROUP BY month ORDER BY month
    """, conn)

    if df.empty:
        st.info("No data available for trends.")
        return

    fig = px.line(df, x="month", y="complaints",
                  title="Monthly Complaint Volume")
    fig.update_layout(template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        fig = px.line(df, x="month", y="crashes",
                      title="Monthly Crashes", color_discrete_sequence=["#E74C3C"])
        fig.update_layout(template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = px.line(df, x="month", y="fires",
                      title="Monthly Fires", color_discrete_sequence=["#E67E22"])
        fig.update_layout(template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)


def show_components(conn):
    """Component analysis."""
    st.header("Component Analysis")

    if not _table_exists(conn, "complaints"):
        st.warning(_NO_DATA_MSG)
        return

    df = pd.read_sql_query("""
        SELECT components, COUNT(*) as complaints,
               SUM(crash) as crashes, SUM(fire) as fires,
               SUM(num_deaths) as deaths, SUM(num_injuries) as injuries
        FROM complaints WHERE components != ''
        GROUP BY components ORDER BY complaints DESC LIMIT 25
    """, conn)

    if df.empty:
        st.info("No component data available.")
        return

    fig = px.bar(df, x="complaints", y="components", orientation="h",
                 color="deaths", color_continuous_scale="Reds",
                 title="Components by Complaint Volume (colored by deaths)")
    fig.update_layout(template="plotly_dark", height=700,
                      yaxis={"autorange": "reversed"})
    st.plotly_chart(fig, use_container_width=True)

    # Death rate by component
    df["death_rate"] = (df["deaths"] / df["complaints"] * 10000).round(1)
    st.subheader("Death Rate per 10,000 Complaints")
    death_df = df[df["deaths"] > 0].sort_values("death_rate", ascending=False)
    if not death_df.empty:
        fig = px.bar(death_df, x="death_rate", y="components", orientation="h",
                     title="Deaths per 10,000 Complaints by Component")
        fig.update_layout(template="plotly_dark",
                          yaxis={"autorange": "reversed"})
        st.plotly_chart(fig, use_container_width=True)


def show_investigation_outcomes(conn):
    """Investigation outcomes and docket analysis."""
    st.header("Investigation Outcomes")

    if not _table_exists(conn, "investigations"):
        st.warning(_NO_DATA_MSG)
        return

    # Check if docket tables have data
    try:
        docket_count = conn.execute("SELECT COUNT(*) FROM investigation_dockets").fetchone()[0]
        doc_count = conn.execute("SELECT COUNT(*) FROM investigation_documents").fetchone()[0]
    except Exception:
        docket_count = doc_count = 0

    if docket_count == 0:
        st.info(
            "No investigation docket data loaded yet. This requires a free Regulations.gov API key.\n\n"
            "1. Get a free key at: https://open.gsa.gov/api/regulationsgov/\n"
            "2. Run: `REGULATIONS_GOV_API_KEY=your_key python -m src.cli fetch-investigation-dockets`"
        )

        # Still show investigation analysis from existing data
        st.subheader("Investigation Analysis (From Existing Data)")

    # Investigation status/type analysis from existing data
    col1, col2 = st.columns(2)

    with col1:
        status_df = _safe_query("""
            SELECT status, COUNT(*) as count
            FROM investigations WHERE status != ''
            GROUP BY status
        """, conn)
        if not status_df.empty:
            fig = px.pie(status_df, names="status", values="count",
                         title="Investigation Status Distribution")
            fig.update_layout(template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        type_df = _safe_query("""
            SELECT investigation_type, COUNT(*) as count
            FROM investigations WHERE investigation_type != ''
            GROUP BY investigation_type ORDER BY count DESC
        """, conn)
        if not type_df.empty:
            fig = px.bar(type_df, x="investigation_type", y="count",
                         title="Investigation Types",
                         color="investigation_type")
            fig.update_layout(template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)

    # Investigations that led to recalls (via cross-links)
    st.subheader("Investigation-Recall Linkage")
    linked_df = _safe_query("""
        SELECT i.make, COUNT(DISTINCT i.investigation_number) as investigations,
               COUNT(DISTINCT cl.source_id) as linked_to_recalls
        FROM investigations i
        LEFT JOIN cross_links cl ON cl.target_id = i.investigation_number
                                AND cl.target_type = 'investigation'
                                AND cl.source_type = 'recall'
        WHERE i.make != ''
        GROUP BY i.make
        HAVING investigations >= 5
        ORDER BY investigations DESC LIMIT 20
    """, conn)

    if not linked_df.empty:
        linked_df["recall_rate"] = (linked_df["linked_to_recalls"] / linked_df["investigations"] * 100).round(1)
        fig = px.bar(linked_df, x="make", y=["investigations", "linked_to_recalls"],
                     title="Investigations vs Recall-Linked (Top 20 Makes)",
                     barmode="group")
        fig.update_layout(template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)

    # Duration analysis
    st.subheader("Investigation Duration Analysis")
    duration_df = _safe_query("""
        SELECT make,
               AVG(julianday(close_date) - julianday(open_date)) as avg_days,
               COUNT(*) as closed_count
        FROM investigations
        WHERE status = 'Closed' AND open_date != '' AND close_date != ''
              AND make != ''
        GROUP BY make
        HAVING closed_count >= 3
        ORDER BY avg_days DESC LIMIT 15
    """, conn)
    if not duration_df.empty:
        duration_df["avg_days"] = duration_df["avg_days"].round(0)
        fig = px.bar(duration_df, x="avg_days", y="make", orientation="h",
                     title="Average Investigation Duration by Make (Days)",
                     color="closed_count", color_continuous_scale="Blues")
        fig.update_layout(template="plotly_dark", yaxis={"autorange": "reversed"})
        st.plotly_chart(fig, use_container_width=True)

    # Show docket data if available
    if docket_count > 0:
        st.subheader(f"Docket Data ({docket_count:,} dockets, {doc_count:,} documents)")

        # Document type breakdown
        doc_type_df = pd.read_sql_query("""
            SELECT document_type, COUNT(*) as count
            FROM investigation_documents
            GROUP BY document_type ORDER BY count DESC
        """, conn)
        if not doc_type_df.empty:
            fig = px.pie(doc_type_df, names="document_type", values="count",
                         title="Document Types in Dockets")
            fig.update_layout(template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)

        # Determinations
        det_df = pd.read_sql_query("""
            SELECT determination, COUNT(*) as count
            FROM investigation_documents
            WHERE determination IS NOT NULL
            GROUP BY determination ORDER BY count DESC
        """, conn)
        if not det_df.empty:
            fig = px.bar(det_df, x="determination", y="count",
                         title="Investigation Determinations")
            fig.update_layout(template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)


def show_vehicle_segmentation(conn):
    """Vehicle segmentation analysis by body type, fuel type, etc."""
    st.header("Vehicle Segmentation")

    # Check if vehicle_attributes table has data
    try:
        attr_count = conn.execute("SELECT COUNT(*) FROM vehicle_attributes").fetchone()[0]
    except Exception:
        st.info("No vehicle attributes loaded yet. Run `python -m src.cli fetch-vehicle-attributes`.")
        return

    if attr_count == 0:
        st.info("No vehicle attributes loaded yet. Run `python -m src.cli fetch-vehicle-attributes`.")
        return

    st.write(f"Vehicle attributes enriched: **{attr_count:,}** vehicles")

    col1, col2 = st.columns(2)

    with col1:
        # Body type distribution
        body_df = pd.read_sql_query("""
            SELECT va.body_class, COUNT(*) as vehicles,
                   SUM(c_stats.complaints) as complaints,
                   SUM(c_stats.crashes) as crashes,
                   SUM(c_stats.fires) as fires,
                   SUM(c_stats.deaths) as deaths
            FROM vehicle_attributes va
            LEFT JOIN (
                SELECT make, model, model_year,
                       COUNT(*) as complaints,
                       SUM(crash) as crashes, SUM(fire) as fires,
                       SUM(num_deaths) as deaths
                FROM complaints GROUP BY make, model, model_year
            ) c_stats ON UPPER(c_stats.make) = va.make
                     AND UPPER(c_stats.model) = va.model
                     AND c_stats.model_year = va.model_year
            WHERE va.body_class IS NOT NULL
            GROUP BY va.body_class
            ORDER BY complaints DESC
        """, conn)
        if not body_df.empty:
            fig = px.pie(body_df, names="body_class", values="complaints",
                         title="Complaints by Body Type")
            fig.update_layout(template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        # Fuel type distribution
        fuel_df = pd.read_sql_query("""
            SELECT va.fuel_type, COUNT(*) as vehicles,
                   SUM(c_stats.complaints) as complaints,
                   SUM(c_stats.fires) as fires,
                   SUM(c_stats.deaths) as deaths
            FROM vehicle_attributes va
            LEFT JOIN (
                SELECT make, model, model_year,
                       COUNT(*) as complaints,
                       SUM(fire) as fires, SUM(num_deaths) as deaths
                FROM complaints GROUP BY make, model, model_year
            ) c_stats ON UPPER(c_stats.make) = va.make
                     AND UPPER(c_stats.model) = va.model
                     AND c_stats.model_year = va.model_year
            WHERE va.fuel_type IS NOT NULL
            GROUP BY va.fuel_type
            ORDER BY complaints DESC
        """, conn)
        if not fuel_df.empty:
            fig = px.pie(fuel_df, names="fuel_type", values="complaints",
                         title="Complaints by Fuel Type")
            fig.update_layout(template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)

    # Electrification analysis
    st.subheader("Electrification Analysis")
    ev_df = pd.read_sql_query("""
        SELECT va.electrification_level, COUNT(DISTINCT va.vehicle_id) as vehicles,
               COALESCE(SUM(c_stats.complaints), 0) as complaints,
               COALESCE(SUM(c_stats.fires), 0) as fires,
               COALESCE(SUM(c_stats.crashes), 0) as crashes,
               COALESCE(SUM(c_stats.deaths), 0) as deaths
        FROM vehicle_attributes va
        LEFT JOIN (
            SELECT make, model, model_year,
                   COUNT(*) as complaints,
                   SUM(fire) as fires, SUM(crash) as crashes, SUM(num_deaths) as deaths
            FROM complaints GROUP BY make, model, model_year
        ) c_stats ON UPPER(c_stats.make) = va.make
                 AND UPPER(c_stats.model) = va.model
                 AND c_stats.model_year = va.model_year
        WHERE va.electrification_level IS NOT NULL
        GROUP BY va.electrification_level
    """, conn)
    if not ev_df.empty:
        ev_df["fire_rate"] = (ev_df["fires"] / ev_df["complaints"].replace(0, 1) * 10000).round(1)
        ev_df["crash_rate"] = (ev_df["crashes"] / ev_df["complaints"].replace(0, 1) * 10000).round(1)

        col_a, col_b = st.columns(2)
        with col_a:
            fig = px.bar(ev_df, x="electrification_level", y="fire_rate",
                         title="Fire Rate per 10K Complaints by Electrification",
                         color="electrification_level")
            fig.update_layout(template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)
        with col_b:
            fig = px.bar(ev_df, x="electrification_level", y="complaints",
                         title="Total Complaints by Electrification Level",
                         color="electrification_level")
            fig.update_layout(template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)

    # Data table
    st.subheader("Vehicle Attribute Summary")
    summary_df = pd.read_sql_query("""
        SELECT va.body_class as "Body Type",
               va.fuel_type as "Fuel Type",
               va.electrification_level as "Electrification",
               COUNT(*) as "Vehicles",
               COALESCE(SUM(c_stats.complaints), 0) as "Complaints",
               COALESCE(SUM(c_stats.fires), 0) as "Fires",
               COALESCE(SUM(c_stats.deaths), 0) as "Deaths"
        FROM vehicle_attributes va
        LEFT JOIN (
            SELECT make, model, model_year,
                   COUNT(*) as complaints,
                   SUM(fire) as fires, SUM(num_deaths) as deaths
            FROM complaints GROUP BY make, model, model_year
        ) c_stats ON UPPER(c_stats.make) = va.make
                 AND UPPER(c_stats.model) = va.model
                 AND c_stats.model_year = va.model_year
        GROUP BY va.body_class, va.fuel_type, va.electrification_level
        ORDER BY "Complaints" DESC
        LIMIT 30
    """, conn)
    if not summary_df.empty:
        st.dataframe(summary_df, use_container_width=True, height=400)


def show_manufacturer_risk(conn):
    """Manufacturer risk profiles dashboard."""
    st.header("Manufacturer Risk Profiles")

    # Check if table exists and has data
    try:
        profile_count = conn.execute("SELECT COUNT(*) FROM manufacturer_profiles").fetchone()[0]
    except Exception:
        st.info("No manufacturer profiles built yet. Run `python -m src.cli build-manufacturer-profiles`.")
        return

    if profile_count == 0:
        st.info("No manufacturer profiles built yet. Run `python -m src.cli build-manufacturer-profiles`.")
        return

    # KPI cards
    scored = conn.execute(
        "SELECT COUNT(*) FROM manufacturer_profiles WHERE total_complaints >= 50"
    ).fetchone()[0]
    critical = conn.execute(
        "SELECT COUNT(*) FROM manufacturer_profiles WHERE risk_tier = 'CRITICAL'"
    ).fetchone()[0]
    high = conn.execute(
        "SELECT COUNT(*) FROM manufacturer_profiles WHERE risk_tier = 'HIGH'"
    ).fetchone()[0]
    highest_risk = conn.execute(
        "SELECT manufacturer_name FROM manufacturer_profiles ORDER BY risk_score DESC LIMIT 1"
    ).fetchone()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Profiles", f"{profile_count:,}")
    c2.metric("Risk-Scored (50+ complaints)", f"{scored:,}")
    c3.metric("Critical / High Risk", f"{critical} / {high}")
    c4.metric("Highest Risk", highest_risk[0] if highest_risk else "N/A")

    # Risk tier distribution
    col1, col2 = st.columns(2)
    with col1:
        tier_df = pd.read_sql_query("""
            SELECT risk_tier, COUNT(*) as count
            FROM manufacturer_profiles
            WHERE total_complaints >= 50
            GROUP BY risk_tier
        """, conn)
        if not tier_df.empty:
            color_map = {"CRITICAL": "#E74C3C", "HIGH": "#E67E22", "MEDIUM": "#F1C40F", "LOW": "#2ECC71"}
            fig = px.pie(tier_df, names="risk_tier", values="count",
                         title="Risk Tier Distribution (Major Manufacturers)",
                         color="risk_tier", color_discrete_map=color_map)
            fig.update_layout(template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        scatter_df = pd.read_sql_query("""
            SELECT manufacturer_name, total_complaints, severity_index,
                   risk_score, risk_tier, total_deaths
            FROM manufacturer_profiles
            WHERE total_complaints >= 50
        """, conn)
        if not scatter_df.empty:
            fig = px.scatter(
                scatter_df, x="total_complaints", y="severity_index",
                color="risk_tier", size="total_deaths",
                hover_name="manufacturer_name",
                color_discrete_map={"CRITICAL": "#E74C3C", "HIGH": "#E67E22", "MEDIUM": "#F1C40F", "LOW": "#2ECC71"},
                title="Complaints vs Severity Index",
                log_x=True,
            )
            fig.update_layout(template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)

    # Top 20 highest risk table
    st.subheader("Highest Risk Manufacturers")
    top_df = pd.read_sql_query("""
        SELECT manufacturer_name as "Manufacturer",
               risk_tier as "Risk Tier",
               ROUND(risk_score, 4) as "Risk Score",
               total_complaints as "Complaints",
               total_recalls as "Recalls",
               total_investigations as "Investigations",
               total_deaths as "Deaths",
               total_injuries as "Injuries",
               total_fires as "Fires",
               ROUND(severity_index, 4) as "Severity Index",
               complaint_trend as "Complaint Trend"
        FROM manufacturer_profiles
        WHERE total_complaints >= 50
        ORDER BY risk_score DESC LIMIT 20
    """, conn)
    if not top_df.empty:
        st.dataframe(top_df, use_container_width=True, height=500)

    # Manufacturer deep-dive
    st.subheader("Manufacturer Deep Dive")
    mfrs = pd.read_sql_query(
        "SELECT manufacturer_name FROM manufacturer_profiles WHERE total_complaints >= 50 ORDER BY manufacturer_name",
        conn
    )["manufacturer_name"].tolist()

    selected_mfr = st.selectbox("Select Manufacturer", mfrs if mfrs else ["No data"])
    if selected_mfr and selected_mfr != "No data":
        profile = pd.read_sql_query(
            "SELECT * FROM manufacturer_profiles WHERE manufacturer_name = ?",
            conn, params=[selected_mfr]
        )
        if not profile.empty:
            p = profile.iloc[0]
            mc1, mc2, mc3, mc4 = st.columns(4)
            mc1.metric("Risk Score", f"{p['risk_score']:.4f}")
            mc2.metric("Risk Tier", p["risk_tier"])
            mc3.metric("Severity Index", f"{p['severity_index']:.4f}")
            mc4.metric("Complaint Trend", p["complaint_trend"])

            mc5, mc6, mc7, mc8 = st.columns(4)
            mc5.metric("Total Complaints", f"{p['total_complaints']:,}")
            mc6.metric("Total Recalls", f"{p['total_recalls']:,}")
            mc7.metric("Deaths", f"{p['total_deaths']:,}")
            mc8.metric("Fires", f"{p['total_fires']:,}")

        # Yearly trends
        yearly_df = pd.read_sql_query("""
            SELECT year, complaint_count, recall_count,
                   death_count, injury_count, fire_count, crash_count,
                   severity_index
            FROM manufacturer_yearly_metrics
            WHERE manufacturer_name = ? AND year >= 2015
            ORDER BY year
        """, conn, params=[selected_mfr])

        if not yearly_df.empty:
            fig = px.bar(yearly_df, x="year", y="complaint_count",
                         title=f"{selected_mfr} — Complaints by Year",
                         color="death_count", color_continuous_scale="Reds")
            fig.update_layout(template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)

            col_a, col_b = st.columns(2)
            with col_a:
                fig = px.line(yearly_df, x="year", y="severity_index",
                              title="Severity Index Over Time")
                fig.update_layout(template="plotly_dark")
                st.plotly_chart(fig, use_container_width=True)
            with col_b:
                fig = px.bar(yearly_df, x="year", y=["fire_count", "crash_count"],
                             title="Fires and Crashes by Year", barmode="group")
                fig.update_layout(template="plotly_dark")
                st.plotly_chart(fig, use_container_width=True)


def show_quality(conn):
    """Data quality dashboard."""
    st.header("Data Quality")

    if not _table_exists(conn, "complaints") and not _table_exists(conn, "recalls") and not _table_exists(conn, "investigations"):
        st.warning(_NO_DATA_MSG)
        return

    tables_to_check = []
    for tbl, col in [("complaints", "quality_score"), ("recalls", "quality_score"), ("investigations", "quality_score")]:
        if _table_exists(conn, tbl):
            tables_to_check.append((tbl, col))
    if _table_exists(conn, "manufacturer_profiles"):
        tables_to_check.append(("manufacturer_profiles", "quality_score"))
    if _table_exists(conn, "vehicle_attributes"):
        tables_to_check.append(("vehicle_attributes", "quality_score"))

    if not tables_to_check:
        st.warning(_NO_DATA_MSG)
        return

    for table_name, score_col in tables_to_check:
        total = _safe_fetchone(conn, f"SELECT COUNT(*) FROM {table_name}")
        scored = _safe_fetchone(conn, f"SELECT COUNT(*) FROM {table_name} WHERE {score_col} > 0")
        above_threshold = _safe_fetchone(
            conn, f"SELECT COUNT(*) FROM {table_name} WHERE {score_col} >= 0.4"
        )
        avg_score = _safe_fetchone(
            conn, f"SELECT AVG({score_col}) FROM {table_name} WHERE {score_col} > 0", default=0
        )

        st.subheader(f"{table_name.title()}")
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Records", f"{total:,}")
        c2.metric("Avg Quality Score", f"{avg_score:.3f}")
        c3.metric("Above Threshold", f"{above_threshold:,} ({100*above_threshold/max(total,1):.1f}%)")

    # Cross-link coverage
    st.subheader("Cross-Link Coverage")
    link_types = _safe_query("""
        SELECT source_type || ' → ' || target_type as link_type,
               link_method, COUNT(*) as count,
               ROUND(AVG(confidence), 3) as avg_confidence
        FROM cross_links
        GROUP BY source_type, target_type, link_method
        ORDER BY count DESC
    """, conn)
    if not link_types.empty:
        st.dataframe(link_types, use_container_width=True)
    else:
        st.info("No cross-links generated yet.")


if __name__ == "__main__":
    main()
