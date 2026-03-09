"""
Entity resolution for financial institution names.

Matches CFPB consumer complaint company names to FDIC institution records
using a three-stage pipeline:
    1. Exact match (confidence: 1.0)
    2. Normalized match after stripping suffixes (confidence: 0.95)
    3. Fuzzy match via thefuzz token_sort_ratio (confidence: variable, min 0.85)

This module is the core intellectual property of the cross-linking system.
All matching is deterministic and rule-based -- zero LLM dependency.

Built by Nathan Goldberg | nathanmauricegoldberg@gmail.com
"""

import re
from typing import Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

console = Console()

# ---------------------------------------------------------------------------
# Suffix / Normalization Configuration
# ---------------------------------------------------------------------------

# Ordered from longest to shortest to avoid partial matches
COMPANY_SUFFIXES = [
    ", National Association",
    " National Association",
    ", N.A.",
    " N.A.",
    ", F.S.B.",
    " F.S.B.",
    ", S.S.B.",
    " S.S.B.",
    ", FSB",
    " FSB",
    ", SSB",
    " SSB",
    ", Inc.",
    ", Inc",
    " Inc.",
    " Inc",
    ", LLC",
    ", L.L.C.",
    " LLC",
    " L.L.C.",
    ", Corp.",
    ", Corporation",
    " Corp.",
    " Corp",
    " Corporation",
    ", Co.",
    " Co.",
    " Company",
    " & Trust",
    " Trust",
    " Bank",
    ", a division of",
]

# Pre-compile regex for whitespace normalization
_MULTI_SPACE_RE = re.compile(r"\s+")
_PUNCTUATION_RE = re.compile(r"[.,;:'\"\-/\\()&]+")


# ---------------------------------------------------------------------------
# Name Normalization
# ---------------------------------------------------------------------------

def _normalize_company_name(name: str) -> str:
    """
    Normalize a company name for matching purposes.

    Steps:
        1. Strip leading/trailing whitespace
        2. Convert to uppercase
        3. Remove known suffixes (N.A., FSB, SSB, National Association, etc.)
        4. Remove punctuation
        5. Collapse multiple spaces to single space
        6. Strip again

    Args:
        name: Raw company name string.

    Returns:
        Normalized company name string suitable for matching.

    Examples:
        >>> _normalize_company_name("Wells Fargo Bank, N.A.")
        'WELLS FARGO'
        >>> _normalize_company_name("JPMORGAN CHASE BANK, NATIONAL ASSOCIATION")
        'JPMORGAN CHASE'
        >>> _normalize_company_name("Citibank, N.A.")
        'CITIBANK'
    """
    if not name:
        return ""

    result = name.strip().upper()

    # Strip known suffixes (longest first to avoid partial matches)
    for suffix in COMPANY_SUFFIXES:
        suffix_upper = suffix.upper()
        if result.endswith(suffix_upper):
            result = result[: -len(suffix_upper)]

    # Remove punctuation
    result = _PUNCTUATION_RE.sub(" ", result)

    # Collapse whitespace
    result = _MULTI_SPACE_RE.sub(" ", result).strip()

    return result


def _build_institution_lookup(institutions: list[dict]) -> dict:
    """
    Build lookup dictionaries from institution records for fast matching.

    Creates three dictionaries:
        - exact_lookup: institution_name (uppercase) -> cert_number
        - normalized_lookup: normalized name -> cert_number
        - all_names: list of (normalized_name, cert_number) for fuzzy matching

    Args:
        institutions: List of institution dicts with 'institution_name' and 'cert_number'.

    Returns:
        dict with keys 'exact', 'normalized', 'fuzzy_candidates'.
    """
    exact = {}
    normalized = {}
    fuzzy_candidates = []

    for inst in institutions:
        name = inst.get("institution_name", "")
        cert = inst.get("cert_number")
        if not name or cert is None:
            continue

        # Exact lookup (uppercase)
        upper_name = name.strip().upper()
        exact[upper_name] = cert

        # Normalized lookup
        norm_name = _normalize_company_name(name)
        if norm_name:
            normalized[norm_name] = cert

        # Fuzzy candidate
        fuzzy_candidates.append((norm_name, cert))

    return {
        "exact": exact,
        "normalized": normalized,
        "fuzzy_candidates": fuzzy_candidates,
    }


# ---------------------------------------------------------------------------
# Matching Pipeline
# ---------------------------------------------------------------------------

def _match_exact(
    company_name: str,
    lookup: dict[str, int],
) -> Optional[tuple[int, float, str]]:
    """
    Attempt exact match of company name against institution lookup.

    Args:
        company_name: Company name from CFPB complaint.
        lookup: Dict mapping uppercase institution names to cert numbers.

    Returns:
        Tuple of (cert_number, confidence, method) or None if no match.
    """
    upper = company_name.strip().upper()
    cert = lookup.get(upper)
    if cert is not None:
        return (cert, 1.0, "exact")
    return None


def _match_normalized(
    company_name: str,
    lookup: dict[str, int],
) -> Optional[tuple[int, float, str]]:
    """
    Attempt normalized match after stripping suffixes.

    Args:
        company_name: Company name from CFPB complaint.
        lookup: Dict mapping normalized institution names to cert numbers.

    Returns:
        Tuple of (cert_number, confidence, method) or None if no match.
    """
    norm = _normalize_company_name(company_name)
    if not norm:
        return None
    cert = lookup.get(norm)
    if cert is not None:
        return (cert, 0.95, "normalized")
    return None


def _match_fuzzy(
    company_name: str,
    candidates: list[tuple[str, int]],
    threshold: int = 85,
) -> Optional[tuple[int, float, str]]:
    """
    Attempt fuzzy match using thefuzz token_sort_ratio.

    Args:
        company_name: Company name from CFPB complaint.
        candidates: List of (normalized_name, cert_number) tuples.
        threshold: Minimum fuzzy score (0-100) to accept. Default: 85.

    Returns:
        Tuple of (cert_number, confidence, method) or None if no match above threshold.
    """
    from thefuzz import fuzz

    norm = _normalize_company_name(company_name)
    if not norm:
        return None

    best_score = 0
    best_cert = None

    for candidate_name, cert in candidates:
        if not candidate_name:
            continue
        score = fuzz.token_sort_ratio(norm, candidate_name)
        if score > best_score:
            best_score = score
            best_cert = cert

    if best_score >= threshold and best_cert is not None:
        # Convert 0-100 score to 0.0-1.0 confidence
        confidence = best_score / 100.0
        return (best_cert, confidence, "fuzzy")

    return None


def match_company_to_institution(
    company_name: str,
    lookup: dict,
    fuzzy_threshold: int = 85,
) -> Optional[tuple[int, float, str]]:
    """
    Match a single company name to an FDIC institution using the
    three-stage pipeline: exact -> normalized -> fuzzy.

    Args:
        company_name: Company name from a CFPB complaint.
        lookup: Lookup dict from _build_institution_lookup().
        fuzzy_threshold: Minimum fuzzy score to accept.

    Returns:
        Tuple of (cert_number, confidence, method) or None if no match found.
    """
    if not company_name or not company_name.strip():
        return None

    # Stage 1: Exact match
    result = _match_exact(company_name, lookup["exact"])
    if result:
        return result

    # Stage 2: Normalized match
    result = _match_normalized(company_name, lookup["normalized"])
    if result:
        return result

    # Stage 3: Fuzzy match
    result = _match_fuzzy(company_name, lookup["fuzzy_candidates"], fuzzy_threshold)
    if result:
        return result

    return None


# ---------------------------------------------------------------------------
# Bulk Matching
# ---------------------------------------------------------------------------

def match_complaints_to_institutions(
    db_conn,
    fuzzy_threshold: int = 85,
    batch_size: int = 1000,
) -> dict:
    """
    Run entity resolution across all CFPB complaints, matching company
    names to FDIC institutions.

    This is the main entry point for the normalization pipeline. It:
    1. Loads all institutions and builds lookup tables
    2. Gets distinct company names from complaints
    3. Matches each company name using the three-stage pipeline
    4. Stores cross-links in the institution_complaints table

    Args:
        db_conn: Active SQLite database connection.
        fuzzy_threshold: Minimum fuzzy score (0-100) for fuzzy matches.
        batch_size: Number of cross-links to store per batch.

    Returns:
        dict with matching statistics:
            - total_companies: Number of distinct company names processed
            - exact_matches: Number matched via exact match
            - normalized_matches: Number matched via normalized match
            - fuzzy_matches: Number matched via fuzzy match
            - unmatched: Number of company names with no match
            - total_links_created: Total cross-link records created
    """
    from src.storage.database import (
        get_all_institutions,
        store_institution_complaint_links,
    )

    stats = {
        "total_companies": 0,
        "exact_matches": 0,
        "normalized_matches": 0,
        "fuzzy_matches": 0,
        "unmatched": 0,
        "total_links_created": 0,
    }

    # 1. Load all institutions and build lookup tables
    institutions = get_all_institutions(db_conn)
    inst_dicts = [dict(row) for row in institutions]
    lookup = _build_institution_lookup(inst_dicts)
    console.print(f"  Loaded {len(inst_dicts):,} institutions for matching")

    # 2. Get distinct company names
    cursor = db_conn.execute(
        "SELECT DISTINCT company FROM cfpb_complaints WHERE company IS NOT NULL"
    )
    companies = [row[0] for row in cursor.fetchall()]
    stats["total_companies"] = len(companies)
    console.print(f"  Found {len(companies):,} distinct company names to match")

    # 3. Match each company and insert cross-links directly via SQL
    # Uses INSERT...SELECT to avoid loading millions of link records into Python memory
    insert_sql = """
        INSERT OR IGNORE INTO institution_complaints (complaint_id, cert_number, match_confidence, match_method)
        SELECT complaint_id, ?, ?, ?
        FROM cfpb_complaints WHERE company = ?
    """
    total_links = 0
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
    ) as progress:
        task = progress.add_task("Matching companies...", total=len(companies))
        for i, company_name in enumerate(companies):
            result = match_company_to_institution(
                company_name, lookup, fuzzy_threshold
            )
            if result:
                cert, confidence, method = result
                # Track stats by method
                if method == "exact":
                    stats["exact_matches"] += 1
                elif method == "normalized":
                    stats["normalized_matches"] += 1
                elif method == "fuzzy":
                    stats["fuzzy_matches"] += 1

                # Insert cross-links directly via SQL (no Python memory needed)
                cursor = db_conn.execute(insert_sql, (cert, confidence, method, company_name))
                total_links += cursor.rowcount
                if (i + 1) % 100 == 0:
                    db_conn.commit()
            else:
                stats["unmatched"] += 1

            progress.update(task, advance=1)

    db_conn.commit()
    stats["total_links_created"] = total_links

    console.print(f"  [green]Entity resolution complete:[/green]")
    console.print(f"    Exact matches:      {stats['exact_matches']:,}")
    console.print(f"    Normalized matches:  {stats['normalized_matches']:,}")
    console.print(f"    Fuzzy matches:       {stats['fuzzy_matches']:,}")
    console.print(f"    Unmatched:           {stats['unmatched']:,}")
    console.print(f"    Total links created: {stats['total_links_created']:,}")

    return stats
