"""Streamlit dashboard for CPSC Product Safety Tracker."""

import sqlite3
from pathlib import Path

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

DB_PATH = Path(__file__).parent.parent.parent / "data" / "cpsc_product_safety.db"


@st.cache_resource
def get_db():
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


@st.cache_data(ttl=3600)
def run_query(query, params=None):
    conn = get_db()
    return pd.read_sql_query(query, conn, params=params or [])


def main():
    st.set_page_config(page_title="CPSC Product Safety Tracker", page_icon="🛡️", layout="wide")

    st.title("CPSC Product Safety Tracker")
    st.caption("Cross-linked database of consumer product recalls, incidents, injuries, penalties, and import violations")

    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
        "Overview", "Manufacturer Search", "Top Manufacturers",
        "Risk Analysis", "Recalls", "NEISS Injuries",
        "Import Violations", "Data Explorer"
    ])

    with tab1:
        render_overview()
    with tab2:
        render_search()
    with tab3:
        render_top_manufacturers()
    with tab4:
        render_risk_analysis()
    with tab5:
        render_recalls()
    with tab6:
        render_neiss()
    with tab7:
        render_violations()
    with tab8:
        render_data_explorer()

    st.markdown("---")
    st.markdown(
        "Built by **Nathan Goldberg** · "
        "[nathanmauricegoldberg@gmail.com](mailto:nathanmauricegoldberg@gmail.com) · "
        "[LinkedIn](https://linkedin.com/in/nathanmauricegoldberg)"
    )


def render_overview():
    st.header("Overview")

    # KPI cards
    stats = run_query("""
        SELECT
            (SELECT COUNT(*) FROM recalls) as recalls,
            (SELECT COUNT(*) FROM incidents) as incidents,
            (SELECT COUNT(*) FROM neiss_injuries) as neiss,
            (SELECT COUNT(*) FROM penalties) as penalties,
            (SELECT COUNT(*) FROM import_violations) as violations,
            (SELECT COUNT(*) FROM manufacturer_profiles) as profiles,
            (SELECT COUNT(*) FROM cross_links) as links,
            (SELECT COALESCE(SUM(fine_amount), 0) FROM penalties) as total_fines,
            (SELECT COALESCE(SUM(weight), 0) FROM neiss_injuries) as neiss_estimate,
            (SELECT COUNT(*) FROM manufacturer_profiles WHERE risk_tier IN ('HIGH','CRITICAL')) as high_risk
    """)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Recall Campaigns", f"{stats['recalls'].iloc[0]:,}")
    c2.metric("Incident Reports", f"{stats['incidents'].iloc[0]:,}")
    c3.metric("NEISS ER Injuries", f"{stats['neiss'].iloc[0]:,}")
    c4.metric("Penalties", f"{stats['penalties'].iloc[0]:,}")
    c5.metric("Import Violations", f"{stats['violations'].iloc[0]:,}")

    c6, c7, c8, c9, c10 = st.columns(5)
    c6.metric("Manufacturer Profiles", f"{stats['profiles'].iloc[0]:,}")
    c7.metric("Cross-Links", f"{stats['links'].iloc[0]:,}")
    c8.metric("Total Fines", f"${stats['total_fines'].iloc[0]:,.0f}")
    c9.metric("Est. National Injuries", f"{stats['neiss_estimate'].iloc[0]:,.0f}")
    c10.metric("High/Critical Risk", f"{stats['high_risk'].iloc[0]:,}")

    # Recalls by year
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Recalls by Year")
        df = run_query("SELECT fiscal_year, COUNT(*) as count FROM recalls WHERE fiscal_year IS NOT NULL GROUP BY fiscal_year ORDER BY fiscal_year")
        if not df.empty:
            fig = px.bar(df, x="fiscal_year", y="count", labels={"fiscal_year": "Fiscal Year", "count": "Recalls"})
            fig.update_layout(template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Incidents by Category")
        df = run_query("SELECT product_category, COUNT(*) as count FROM incidents WHERE product_category != '' GROUP BY product_category ORDER BY count DESC LIMIT 10")
        if not df.empty:
            fig = px.bar(df, x="count", y="product_category", orientation="h",
                        labels={"product_category": "Category", "count": "Incidents"})
            fig.update_layout(template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)

    # Risk tier distribution
    col3, col4 = st.columns(2)
    with col3:
        st.subheader("Risk Tier Distribution")
        df = run_query("SELECT risk_tier, COUNT(*) as count FROM manufacturer_profiles GROUP BY risk_tier ORDER BY count DESC")
        if not df.empty:
            colors = {"LOW": "#2ecc71", "MEDIUM": "#f39c12", "HIGH": "#e74c3c", "CRITICAL": "#8e44ad"}
            fig = px.pie(df, values="count", names="risk_tier",
                        color="risk_tier", color_discrete_map=colors)
            fig.update_layout(template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)

    with col4:
        st.subheader("Top Penalty Amounts")
        df = run_query("""
            SELECT firm_name, SUM(fine_amount) as total_fines, COUNT(*) as count
            FROM penalties WHERE fine_amount > 0
            GROUP BY normalized_firm ORDER BY total_fines DESC LIMIT 10
        """)
        if not df.empty:
            fig = px.bar(df, x="total_fines", y="firm_name", orientation="h",
                        labels={"firm_name": "Firm", "total_fines": "Total Fines ($)"})
            fig.update_layout(template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)


def render_search():
    st.header("Manufacturer Search")
    query = st.text_input("Search manufacturer name", placeholder="e.g., Samsung, IKEA, Fisher-Price")

    if query:
        df = run_query("""
            SELECT manufacturer_name, normalized_name,
                   total_recalls, total_units_recalled,
                   total_incidents, total_penalties, total_fines,
                   total_import_violations, compliance_score, risk_tier,
                   first_seen_date, last_seen_date, data_sources
            FROM manufacturer_profiles
            WHERE manufacturer_name LIKE ? OR normalized_name LIKE ?
            ORDER BY total_recalls DESC LIMIT 50
        """, [f"%{query}%", f"%{query.upper()}%"])

        if df.empty:
            st.warning("No manufacturers found matching your search.")
        else:
            st.info(f"Found {len(df)} manufacturer(s)")
            for _, row in df.iterrows():
                with st.expander(f"{row['manufacturer_name']} — {row['risk_tier']} Risk (Score: {row['compliance_score']:.3f})"):
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Recalls", f"{row['total_recalls']:,}")
                    c2.metric("Incidents", f"{row['total_incidents']:,}")
                    c3.metric("Penalties", f"{row['total_penalties']:,}")
                    c4.metric("Fines", f"${row['total_fines']:,.0f}")

                    c5, c6, c7, c8 = st.columns(4)
                    c5.metric("Units Recalled", f"{row['total_units_recalled']:,}")
                    c6.metric("Import Violations", f"{row['total_import_violations']:,}")
                    c7.metric("First Seen", row['first_seen_date'] or "N/A")
                    c8.metric("Last Seen", row['last_seen_date'] or "N/A")

                    st.text(f"Data sources: {row['data_sources']}")


def render_top_manufacturers():
    st.header("Top Manufacturers")

    sort_by = st.selectbox("Sort by", ["Recalls", "Incidents", "Fines", "Import Violations", "Compliance Score"])
    sort_map = {
        "Recalls": "total_recalls DESC",
        "Incidents": "total_incidents DESC",
        "Fines": "total_fines DESC",
        "Import Violations": "total_import_violations DESC",
        "Compliance Score": "compliance_score ASC",
    }

    df = run_query(f"""
        SELECT manufacturer_name, total_recalls, total_incidents,
               total_penalties, total_fines, total_import_violations,
               compliance_score, risk_tier
        FROM manufacturer_profiles
        ORDER BY {sort_map[sort_by]}
        LIMIT 100
    """)

    if not df.empty:
        st.dataframe(df, use_container_width=True, height=600)

        csv = df.to_csv(index=False)
        st.download_button("Download CSV", csv, "top_manufacturers.csv", "text/csv")


def render_risk_analysis():
    st.header("Risk Analysis")

    # Compliance score distribution
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Compliance Score Distribution")
        df = run_query("SELECT compliance_score FROM manufacturer_profiles")
        if not df.empty:
            fig = px.histogram(df, x="compliance_score", nbins=50,
                             labels={"compliance_score": "Compliance Score"})
            fig.update_layout(template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Recalls vs Incidents")
        df = run_query("""
            SELECT manufacturer_name, total_recalls, total_incidents,
                   compliance_score, risk_tier
            FROM manufacturer_profiles
            WHERE total_recalls > 0 OR total_incidents > 0
            ORDER BY total_recalls DESC LIMIT 200
        """)
        if not df.empty:
            fig = px.scatter(df, x="total_recalls", y="total_incidents",
                           color="risk_tier", hover_name="manufacturer_name",
                           size="total_incidents",
                           color_discrete_map={"LOW": "#2ecc71", "MEDIUM": "#f39c12",
                                             "HIGH": "#e74c3c", "CRITICAL": "#8e44ad"})
            fig.update_layout(template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)

    # High/Critical risk table
    st.subheader("High & Critical Risk Manufacturers")
    df = run_query("""
        SELECT manufacturer_name, total_recalls, total_incidents,
               total_penalties, total_fines, total_import_violations,
               compliance_score, risk_tier
        FROM manufacturer_profiles
        WHERE risk_tier IN ('HIGH', 'CRITICAL')
        ORDER BY compliance_score ASC
    """)
    if not df.empty:
        st.dataframe(df, use_container_width=True)


def render_recalls():
    st.header("Recall Campaigns")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Recalls by Hazard Type")
        df = run_query("""
            SELECT hazard_types, COUNT(*) as count FROM recalls
            WHERE hazard_types != '' AND hazard_types IS NOT NULL
            GROUP BY hazard_types ORDER BY count DESC LIMIT 15
        """)
        if not df.empty:
            fig = px.bar(df, x="count", y="hazard_types", orientation="h",
                        labels={"hazard_types": "Hazard Type", "count": "Recalls"})
            fig.update_layout(template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Manufacturing Countries")
        df = run_query("""
            SELECT manufacturer_countries, COUNT(*) as count FROM recalls
            WHERE manufacturer_countries != '' AND manufacturer_countries IS NOT NULL
            GROUP BY manufacturer_countries ORDER BY count DESC LIMIT 10
        """)
        if not df.empty:
            fig = px.pie(df, values="count", names="manufacturer_countries")
            fig.update_layout(template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)

    # Recent recalls
    st.subheader("Recent Recalls")
    df = run_query("""
        SELECT recall_number, recall_date, title, manufacturer_names,
               hazard_description, number_of_units
        FROM recalls ORDER BY recall_date DESC LIMIT 50
    """)
    if not df.empty:
        st.dataframe(df, use_container_width=True, height=400)


def render_neiss():
    st.header("NEISS Emergency Room Injuries")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Injuries by Year")
        df = run_query("""
            SELECT neiss_year, COUNT(*) as count, SUM(weight) as national_estimate
            FROM neiss_injuries WHERE neiss_year IS NOT NULL
            GROUP BY neiss_year ORDER BY neiss_year
        """)
        if not df.empty:
            fig = px.bar(df, x="neiss_year", y="national_estimate",
                        labels={"neiss_year": "Year", "national_estimate": "National Estimate"})
            fig.update_layout(template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Top Diagnoses")
        df = run_query("""
            SELECT diagnosis_name, COUNT(*) as count FROM neiss_injuries
            WHERE diagnosis_name != '' AND diagnosis_name IS NOT NULL
            GROUP BY diagnosis_name ORDER BY count DESC LIMIT 10
        """)
        if not df.empty:
            fig = px.bar(df, x="count", y="diagnosis_name", orientation="h",
                        labels={"diagnosis_name": "Diagnosis", "count": "Cases"})
            fig.update_layout(template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)

    col3, col4 = st.columns(2)
    with col3:
        st.subheader("Disposition (Outcome)")
        df = run_query("""
            SELECT disposition_name, COUNT(*) as count FROM neiss_injuries
            WHERE disposition_name != '' AND disposition_name IS NOT NULL
            GROUP BY disposition_name ORDER BY count DESC
        """)
        if not df.empty:
            fig = px.pie(df, values="count", names="disposition_name")
            fig.update_layout(template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)

    with col4:
        st.subheader("Location of Injury")
        df = run_query("""
            SELECT location_name, COUNT(*) as count FROM neiss_injuries
            WHERE location_name != '' AND location_name IS NOT NULL AND location_name != 'Not Recorded'
            GROUP BY location_name ORDER BY count DESC
        """)
        if not df.empty:
            fig = px.pie(df, values="count", names="location_name")
            fig.update_layout(template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)

    # Age distribution
    st.subheader("Age Distribution of Injuries")
    df = run_query("""
        SELECT age, COUNT(*) as count FROM neiss_injuries
        WHERE age IS NOT NULL AND age >= 0 AND age <= 100
        GROUP BY age ORDER BY age
    """)
    if not df.empty:
        fig = px.bar(df, x="age", y="count", labels={"age": "Age", "count": "Injuries"})
        fig.update_layout(template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)


def render_violations():
    st.header("Import Violations")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Violations by Country")
        df = run_query("""
            SELECT country, COUNT(*) as count FROM import_violations
            WHERE country IS NOT NULL AND country != ''
            GROUP BY UPPER(country) ORDER BY count DESC LIMIT 15
        """)
        if not df.empty:
            fig = px.bar(df, x="count", y="country", orientation="h",
                        labels={"country": "Country", "count": "Violations"})
            fig.update_layout(template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Violation Types")
        df = run_query("""
            SELECT violation_type, COUNT(*) as count FROM import_violations
            WHERE violation_type IS NOT NULL AND violation_type != ''
            GROUP BY violation_type ORDER BY count DESC LIMIT 10
        """)
        if not df.empty:
            fig = px.pie(df, values="count", names="violation_type")
            fig.update_layout(template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)

    # CBP actions
    st.subheader("CBP Actions Taken")
    df = run_query("""
        SELECT cbp_action, COUNT(*) as count FROM import_violations
        WHERE cbp_action IS NOT NULL AND cbp_action != ''
        GROUP BY cbp_action ORDER BY count DESC
    """)
    if not df.empty:
        fig = px.bar(df, x="cbp_action", y="count",
                    labels={"cbp_action": "CBP Action", "count": "Count"})
        fig.update_layout(template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)

    # Top violating firms
    st.subheader("Top Violating Firms")
    df = run_query("""
        SELECT firm_name, COUNT(*) as violations, country
        FROM import_violations
        GROUP BY normalized_firm ORDER BY violations DESC LIMIT 20
    """)
    if not df.empty:
        st.dataframe(df, use_container_width=True)


def render_data_explorer():
    st.header("Data Explorer")

    table = st.selectbox("Select table", [
        "recalls", "incidents", "penalties", "import_violations",
        "manufacturer_profiles", "neiss_injuries", "cross_links"
    ])

    search = st.text_input("Search (searches text columns)", "")

    if table == "recalls":
        where = f"WHERE title LIKE '%{search}%' OR manufacturer_names LIKE '%{search}%'" if search else ""
        df = run_query(f"SELECT recall_number, recall_date, title, manufacturer_names, hazard_description, number_of_units, quality_score FROM recalls {where} ORDER BY recall_date DESC LIMIT 500")
    elif table == "incidents":
        where = f"WHERE product_description LIKE '%{search}%' OR manufacturer_name LIKE '%{search}%'" if search else ""
        df = run_query(f"SELECT report_number, report_date, product_category, manufacturer_name, severity, state, quality_score FROM incidents {where} ORDER BY report_date DESC LIMIT 500")
    elif table == "penalties":
        where = f"WHERE firm_name LIKE '%{search}%'" if search else ""
        df = run_query(f"SELECT penalty_id, firm_name, penalty_type, penalty_date, fine_amount, act, recall_number FROM penalties {where} ORDER BY fine_amount DESC LIMIT 500")
    elif table == "import_violations":
        where = f"WHERE firm_name LIKE '%{search}%' OR product_name LIKE '%{search}%'" if search else ""
        df = run_query(f"SELECT nov_date, product_name, violation_type, citation, firm_name, country, cbp_action FROM import_violations {where} ORDER BY nov_date DESC LIMIT 500")
    elif table == "manufacturer_profiles":
        where = f"WHERE manufacturer_name LIKE '%{search}%'" if search else ""
        df = run_query(f"SELECT manufacturer_name, total_recalls, total_incidents, total_penalties, total_fines, total_import_violations, compliance_score, risk_tier FROM manufacturer_profiles {where} ORDER BY compliance_score ASC LIMIT 500")
    elif table == "neiss_injuries":
        where = f"WHERE narrative LIKE '%{search}%'" if search else ""
        df = run_query(f"SELECT cpsc_case_number, treatment_date, age, sex, body_part_name, diagnosis_name, disposition_name, product_1_name, narrative FROM neiss_injuries {where} ORDER BY treatment_date DESC LIMIT 500")
    else:
        df = run_query(f"SELECT * FROM {table} LIMIT 500")

    if not df.empty:
        st.dataframe(df, use_container_width=True, height=500)
        csv = df.to_csv(index=False)
        st.download_button("Download CSV", csv, f"{table}.csv", "text/csv")
    else:
        st.info("No data found")


if __name__ == "__main__":
    main()
