"""
Federal Reserve enforcement action downloader.

Downloads enforcement action data from the Federal Reserve's public listing.
Source: https://www.federalreserve.gov/supervisionreg/enforcementactions.htm

Built by Nathan Goldberg | nathanmauricegoldberg@gmail.com
"""

import re
import hashlib
import time
from typing import Optional

import requests
from rich.console import Console

console = Console()

# Fed enforcement actions search page
FED_ENFORCEMENT_URL = "https://www.federalreserve.gov/supervisionreg/enforcementactions.htm"
FED_API_URL = "https://efts.sec.gov/LATEST/search-index?q=%22enforcement+action%22&dateRange=custom"

USER_AGENT = (
    "CFPB-Complaint-Tracker/0.1 "
    "(Research project by Nathan Goldberg; nathanmauricegoldberg@gmail.com)"
)

REQUEST_DELAY = 1.5
MAX_RETRIES = 3


def _generate_action_id(name: str, date: str, action_type: str = "") -> str:
    """Generate a stable action_id for a Fed enforcement action."""
    key = f"FED|{name}|{date}|{action_type}".lower()
    return f"FED-{hashlib.md5(key.encode()).hexdigest()[:12]}"


def _extract_penalty_amount(text: str) -> Optional[float]:
    """Extract penalty dollar amount from description text."""
    if not text:
        return None

    penalty_keywords = r"(?:penalty|fine|pay|paid|relief|assessment|forfeit|civil money)"
    pattern = rf"(?:{penalty_keywords})[^$]*?\$\s*([\d,]+(?:\.\d+)?)\s*(million|billion)?"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        amount = float(match.group(1).replace(",", ""))
        if match.group(2):
            multiplier = match.group(2).lower()
            if multiplier == "billion":
                amount *= 1_000_000_000
            elif multiplier == "million":
                amount *= 1_000_000
        return amount
    return None


def scrape_fed_enforcement(limit: Optional[int] = None) -> list[dict]:
    """
    Scrape Federal Reserve enforcement actions from their public listing.

    Args:
        limit: Maximum number of records to fetch.

    Returns:
        List of enforcement action dicts.
    """
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html"}
    actions = []

    console.print("  Fetching Federal Reserve enforcement actions...")

    try:
        response = requests.get(FED_ENFORCEMENT_URL, headers=headers, timeout=30)
        if response.status_code != 200:
            console.print(f"  [yellow]Fed enforcement page returned {response.status_code}[/yellow]")
            return actions

        html = response.text

        # Parse the Fed's enforcement action HTML listing
        # The Fed typically lists actions in a structured table/div format
        # Pattern: date | institution name | action type | document links

        # Try structured table rows first
        row_pattern = re.compile(
            r'<tr[^>]*>\s*'
            r'<td[^>]*>\s*([\d/]+)\s*</td>\s*'
            r'<td[^>]*>\s*(.*?)\s*</td>\s*'
            r'<td[^>]*>\s*(.*?)\s*</td>',
            re.DOTALL | re.IGNORECASE,
        )

        matches = row_pattern.findall(html)

        if not matches:
            # Alternative: try div-based listing
            div_pattern = re.compile(
                r'class="[^"]*enforcement[^"]*"[^>]*>.*?'
                r'(\d{1,2}/\d{1,2}/\d{4}).*?'
                r'<a[^>]*>(.*?)</a>.*?'
                r'(?:consent\s*order|cease\s*and\s*desist|civil\s*money\s*penalty|'
                r'written\s*agreement|prohibition|removal|assessment)',
                re.DOTALL | re.IGNORECASE,
            )
            matches = div_pattern.findall(html)

        # Also extract from anchor tags that link to enforcement documents
        link_pattern = re.compile(
            r'<a[^>]*href="(/supervisionreg/[^"]*enforcement[^"]*)"[^>]*>(.*?)</a>',
            re.DOTALL | re.IGNORECASE,
        )
        link_matches = link_pattern.findall(html)

        for url_path, text in link_matches:
            clean_text = re.sub(r'<[^>]+>', '', text).strip()
            if len(clean_text) < 5:
                continue

            # Try to extract institution name and date from the text
            date_match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', clean_text)
            date_str = date_match.group(1) if date_match else ""

            # Remove date from the name
            name = re.sub(r'\d{1,2}/\d{1,2}/\d{4}', '', clean_text).strip()
            name = re.sub(r'[-–—]\s*$', '', name).strip()

            if not name or len(name) < 3:
                continue

            # Determine action type from URL or text
            action_type = "Enforcement Action"
            for keyword, atype in [
                ("consent", "Consent Order"),
                ("cease", "Cease and Desist"),
                ("penalty", "Civil Money Penalty"),
                ("prohibition", "Prohibition Order"),
                ("removal", "Removal/Prohibition"),
                ("agreement", "Written Agreement"),
                ("assessment", "Civil Money Penalty"),
            ]:
                if keyword in clean_text.lower() or keyword in url_path.lower():
                    action_type = atype
                    break

            action_id = _generate_action_id(name, date_str, action_type)
            full_url = f"https://www.federalreserve.gov{url_path}" if url_path.startswith("/") else url_path

            actions.append({
                "action_id": action_id,
                "agency": "FED",
                "institution_name": name,
                "cert_number": None,
                "action_type": action_type,
                "action_date": date_str,
                "penalty_amount": _extract_penalty_amount(clean_text),
                "description": clean_text[:2000],
                "docket_number": None,
                "source_url": full_url,
                "quality_score": 0.5,
            })

            if limit and len(actions) >= limit:
                break

        # Deduplicate by action_id
        seen = set()
        unique_actions = []
        for action in actions:
            if action["action_id"] not in seen:
                seen.add(action["action_id"])
                unique_actions.append(action)

        console.print(f"  [green]Scraped {len(unique_actions)} Federal Reserve enforcement actions[/green]")
        return unique_actions

    except requests.RequestException as e:
        console.print(f"  [yellow]Fed enforcement scrape failed: {e}[/yellow]")
        return actions


def run_fed_pipeline(db_conn, limit: Optional[int] = None) -> int:
    """Run the Federal Reserve enforcement scrape and store pipeline."""
    from src.storage.database import store_regulatory_enforcement_batch

    actions = scrape_fed_enforcement(limit=limit)
    if actions:
        stored = store_regulatory_enforcement_batch(db_conn, actions)
        console.print(f"  [green]Stored {stored} Fed enforcement actions[/green]")
        return stored
    return 0
