"""Cross-link employer records across WHD, OSHA, and NLRB databases."""

from __future__ import annotations

import sqlite3
from collections import defaultdict

from rapidfuzz import fuzz

from src.normalization.employers import normalize_employer


# Minimum fuzzy match score to consider a link
FUZZY_THRESHOLD = 85


def cross_link_all(conn: sqlite3.Connection) -> dict:
    """Run all cross-linking and build employer profiles."""
    results = {}

    # Stage 1: Exact normalized name matching
    results["exact_matches"] = _link_exact(conn)

    # Stage 2: Fuzzy name matching for remaining unlinked records
    results["fuzzy_matches"] = _link_fuzzy(conn)

    # Stage 3: Build/update employer profiles
    results["employers_created"] = _build_employer_profiles(conn)

    conn.commit()
    return results


def _link_exact(conn: sqlite3.Connection) -> int:
    """Link records with exact normalized employer name matches."""
    # Index all records by normalized name
    whd_by_name = _index_by_employer(conn, "whd_cases", "trade_name", "case_id")
    osha_by_name = _index_by_employer(conn, "osha_inspections", "establishment_name", "activity_number")
    nlrb_by_name = _index_by_employer(conn, "nlrb_cases", "case_name", "case_number")

    linked = 0

    # WHD ↔ OSHA exact matches
    for name in whd_by_name:
        if name in osha_by_name:
            for whd_id in whd_by_name[name]:
                for osha_id in osha_by_name[name]:
                    if _insert_link(conn, "whd", whd_id, "osha", osha_id, "exact_name", 0.95):
                        linked += 1

    # WHD ↔ NLRB exact matches
    for name in whd_by_name:
        if name in nlrb_by_name:
            for whd_id in whd_by_name[name]:
                for nlrb_id in nlrb_by_name[name]:
                    if _insert_link(conn, "whd", whd_id, "nlrb", nlrb_id, "exact_name", 0.90):
                        linked += 1

    # OSHA ↔ NLRB exact matches
    for name in osha_by_name:
        if name in nlrb_by_name:
            for osha_id in osha_by_name[name]:
                for nlrb_id in nlrb_by_name[name]:
                    if _insert_link(conn, "osha", osha_id, "nlrb", nlrb_id, "exact_name", 0.90):
                        linked += 1

    return linked


def _link_fuzzy(conn: sqlite3.Connection) -> int:
    """Link records using fuzzy name matching for unlinked records."""
    # Get unique employer names from each source
    whd_names = _get_unique_employers(conn, "whd_cases", "trade_name")
    osha_names = _get_unique_employers(conn, "osha_inspections", "establishment_name")
    nlrb_names = _get_unique_employers(conn, "nlrb_cases", "case_name")

    # Get already-linked normalized names
    linked_pairs = set()
    existing = conn.execute("""
        SELECT source_type, source_id, target_type, target_id FROM cross_links
    """).fetchall()
    for row in existing:
        linked_pairs.add((row["source_type"], row["source_id"], row["target_type"], row["target_id"]))

    linked = 0

    # Fuzzy match WHD ↔ OSHA (only top candidates by state to limit comparisons)
    whd_by_state = _group_by_state(conn, "whd_cases", "state", "trade_name", "case_id")
    osha_by_state = _group_by_state(conn, "osha_inspections", "site_state", "establishment_name", "activity_number")

    for state in whd_by_state:
        if state not in osha_by_state:
            continue
        for whd_name, whd_ids in whd_by_state[state].items():
            for osha_name, osha_ids in osha_by_state[state].items():
                if whd_name == osha_name:
                    continue  # Already handled by exact
                score = fuzz.token_sort_ratio(whd_name, osha_name)
                if score >= FUZZY_THRESHOLD:
                    for wid in whd_ids:
                        for oid in osha_ids:
                            if ("whd", wid, "osha", oid) not in linked_pairs:
                                if _insert_link(conn, "whd", wid, "osha", oid, "fuzzy_name", score / 100.0):
                                    linked += 1

    return linked


def _build_employer_profiles(conn: sqlite3.Connection) -> int:
    """Build/update employer aggregate profiles from all sources."""
    # Collect all normalized names
    all_names = set()

    for row in conn.execute("SELECT DISTINCT employer_normalized FROM whd_cases WHERE employer_normalized != ''"):
        all_names.add(row["employer_normalized"])
    for row in conn.execute("SELECT DISTINCT employer_normalized FROM osha_inspections WHERE employer_normalized != ''"):
        all_names.add(row["employer_normalized"])
    for row in conn.execute("SELECT DISTINCT employer_normalized FROM nlrb_cases WHERE employer_normalized != ''"):
        all_names.add(row["employer_normalized"])

    created = 0
    for name in all_names:
        # Aggregate stats
        whd = conn.execute("""
            SELECT COUNT(*) as cnt, COALESCE(SUM(back_wages_owed), 0) as wages,
                   COALESCE(SUM(civil_penalties), 0) as penalties,
                   GROUP_CONCAT(DISTINCT naics_code) as naics,
                   GROUP_CONCAT(DISTINCT state) as states
            FROM whd_cases WHERE employer_normalized = ?
        """, (name,)).fetchone()

        osha = conn.execute("""
            SELECT COUNT(*) as cnt, COALESCE(SUM(total_current_penalty), 0) as penalties,
                   COALESCE(SUM(fatalities), 0) as fatalities,
                   COALESCE(SUM(willful_violations), 0) as willful
            FROM osha_inspections WHERE employer_normalized = ?
        """, (name,)).fetchone()

        nlrb = conn.execute("""
            SELECT COUNT(*) as cnt FROM nlrb_cases WHERE employer_normalized = ?
        """, (name,)).fetchone()

        from src.validation.quality import compute_compliance_score
        score = compute_compliance_score(
            whd_cases=whd["cnt"],
            osha_inspections=osha["cnt"],
            nlrb_cases=nlrb["cnt"],
            total_back_wages=whd["wages"],
            total_penalties=whd["penalties"] + osha["penalties"],
            total_fatalities=osha["fatalities"],
            willful_violations=osha["willful"],
        )

        # Get primary state (most frequent)
        states = (whd["states"] or "").split(",")
        primary_state = states[0] if states else ""

        rec = {
            "name_normalized": name,
            "trade_names": "",
            "naics_code": (whd["naics"] or "").split(",")[0] if whd["naics"] else "",
            "primary_state": primary_state,
            "whd_case_count": whd["cnt"],
            "osha_inspection_count": osha["cnt"],
            "nlrb_case_count": nlrb["cnt"],
            "total_back_wages": whd["wages"],
            "total_penalties": whd["penalties"] + osha["penalties"],
            "total_fatalities": osha["fatalities"],
            "compliance_score": score,
        }

        from src.storage.database import upsert_employer
        upsert_employer(conn, rec)
        created += 1

    return created


def _index_by_employer(
    conn: sqlite3.Connection,
    table: str,
    name_col: str,
    id_col: str,
) -> dict[str, list[str]]:
    """Build an index of normalized employer name -> record IDs."""
    index = defaultdict(list)
    rows = conn.execute(f"SELECT {id_col}, employer_normalized FROM {table} WHERE employer_normalized != ''").fetchall()
    for row in rows:
        index[row["employer_normalized"]].append(row[id_col])
    return index


def _get_unique_employers(
    conn: sqlite3.Connection,
    table: str,
    name_col: str,
) -> set[str]:
    """Get unique normalized employer names from a table."""
    rows = conn.execute(
        f"SELECT DISTINCT employer_normalized FROM {table} WHERE employer_normalized != ''"
    ).fetchall()
    return {row["employer_normalized"] for row in rows}


def _group_by_state(
    conn: sqlite3.Connection,
    table: str,
    state_col: str,
    name_col: str,
    id_col: str,
) -> dict[str, dict[str, list[str]]]:
    """Group records by state, then by normalized name."""
    result = defaultdict(lambda: defaultdict(list))
    rows = conn.execute(
        f"SELECT {id_col}, {state_col}, employer_normalized FROM {table} WHERE employer_normalized != '' AND {state_col} != ''"
    ).fetchall()
    for row in rows:
        result[row[state_col]][row["employer_normalized"]].append(row[id_col])
    return result


def _insert_link(
    conn: sqlite3.Connection,
    src_type: str,
    src_id: str,
    tgt_type: str,
    tgt_id: str,
    method: str,
    confidence: float,
) -> bool:
    """Insert a cross-link, return True if inserted."""
    try:
        conn.execute("""
            INSERT OR IGNORE INTO cross_links
            (source_type, source_id, target_type, target_id, link_method, confidence)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (src_type, src_id, tgt_type, tgt_id, method, confidence))
        return True
    except sqlite3.IntegrityError:
        return False
