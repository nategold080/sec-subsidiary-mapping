"""
OCC (Office of the Comptroller of the Currency) enforcement action scraper.

Scrapes enforcement actions from the OCC enforcement actions listing pages.
Source: https://www.occ.gov/topics/laws-and-regulations/enforcement-actions/

Built by Nathan Goldberg | nathanmauricegoldberg@gmail.com
"""

import re
import hashlib
import time
from typing import Optional

import requests
from rich.console import Console

console = Console()

OCC_SEARCH_URL = "https://apps.occ.gov/EASearch/api/enforcement-actions"
OCC_LIST_URL = "https://www.occ.gov/topics/laws-and-regulations/enforcement-actions/enforcement-action-list/index-enforcement-actions.html"

USER_AGENT = (
    "CFPB-Complaint-Tracker/0.1 "
    "(Research project by Nathan Goldberg; nathanmauricegoldberg@gmail.com)"
)

REQUEST_DELAY = 1.0
MAX_RETRIES = 3
MAX_PAGES = 50


def _generate_action_id(agency: str, name: str, date: str, action_type: str = "") -> str:
    """Generate a stable action_id from action properties."""
    key = f"{agency}|{name}|{date}|{action_type}".lower()
    return f"OCC-{hashlib.md5(key.encode()).hexdigest()[:12]}"


def _extract_penalty_amount(text: str) -> Optional[float]:
    """Extract dollar amount from description text with penalty context."""
    if not text:
        return None

    penalty_keywords = r"(?:penalty|fine|pay|paid|relief|restitution|assessment|forfeit)"
    pattern = rf"{penalty_keywords}[^$]*?\$\s*([\d,]+(?:\.\d+)?)\s*(?:million|billion)?"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        amount = float(match.group(1).replace(",", ""))
        text_after = text[match.start():match.end() + 20].lower()
        if "billion" in text_after:
            amount *= 1_000_000_000
        elif "million" in text_after:
            amount *= 1_000_000
        return amount

    # Also try pattern: $AMOUNT ... penalty/fine
    pattern2 = r"\$\s*([\d,]+(?:\.\d+)?)\s*(?:million|billion)?[^.]*?" + penalty_keywords
    match2 = re.search(pattern2, text, re.IGNORECASE)
    if match2:
        amount = float(match2.group(1).replace(",", ""))
        text_segment = text[match2.start():match2.end()].lower()
        if "billion" in text_segment:
            amount *= 1_000_000_000
        elif "million" in text_segment:
            amount *= 1_000_000
        return amount

    return None


def scrape_occ_enforcement_api(
    limit: Optional[int] = None,
) -> list[dict]:
    """
    Attempt to scrape OCC enforcement actions via their search API.

    Args:
        limit: Maximum number of records to fetch.

    Returns:
        List of enforcement action dicts.
    """
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }

    actions = []
    page = 1

    console.print("  Fetching OCC enforcement actions...")

    while page <= MAX_PAGES:
        try:
            params = {
                "page": page,
                "pageSize": 100,
                "sortField": "ActionDate",
                "sortOrder": "desc",
            }

            response = requests.get(
                OCC_SEARCH_URL,
                params=params,
                headers=headers,
                timeout=30,
            )

            if response.status_code == 403:
                console.print("  [yellow]OCC API returned 403 - trying HTML scraping fallback[/yellow]")
                return scrape_occ_enforcement_html(limit=limit)

            response.raise_for_status()
            data = response.json()

            records = data if isinstance(data, list) else data.get("results", data.get("data", []))
            if not records:
                break

            for record in records:
                action = _map_occ_api_record(record)
                if action:
                    actions.append(action)
                    if limit and len(actions) >= limit:
                        return actions

            console.print(f"  Page {page}: {len(actions)} total OCC actions...")
            page += 1
            time.sleep(REQUEST_DELAY)

        except requests.RequestException as e:
            console.print(f"  [yellow]OCC API error: {e} - trying HTML fallback[/yellow]")
            return scrape_occ_enforcement_html(limit=limit)

    console.print(f"  [green]Scraped {len(actions)} OCC enforcement actions[/green]")
    return actions


def _map_occ_api_record(record: dict) -> Optional[dict]:
    """Map an OCC API record to our schema."""
    name = record.get("RespondentName") or record.get("BankName") or record.get("institution_name")
    if not name:
        return None

    date = record.get("ActionDate") or record.get("action_date", "")
    action_type = record.get("ActionType") or record.get("action_type", "")
    docket = record.get("DocketNumber") or record.get("docket_number", "")
    description = record.get("Description") or record.get("description", "")
    url = record.get("Url") or record.get("url", "")
    penalty = record.get("PenaltyAmount") or _extract_penalty_amount(description)

    if isinstance(date, str) and "T" in date:
        date = date.split("T")[0]

    action_id = _generate_action_id("OCC", name, date, action_type)

    return {
        "action_id": action_id,
        "agency": "OCC",
        "institution_name": name.strip(),
        "cert_number": None,
        "action_type": action_type,
        "action_date": date,
        "penalty_amount": float(penalty) if penalty else None,
        "description": description[:2000] if description else None,
        "docket_number": docket,
        "source_url": url,
        "quality_score": 0.7 if penalty else 0.5,
    }


def scrape_occ_enforcement_html(limit: Optional[int] = None) -> list[dict]:
    """
    Fallback: scrape OCC enforcement actions from HTML listing pages.

    Args:
        limit: Maximum number of records.

    Returns:
        List of enforcement action dicts.
    """
    headers = {"User-Agent": USER_AGENT}
    actions = []

    try:
        response = requests.get(OCC_LIST_URL, headers=headers, timeout=30)
        if response.status_code != 200:
            console.print(f"  [yellow]OCC HTML scrape returned {response.status_code}[/yellow]")
            return actions

        html = response.text

        # Pattern for enforcement action entries in the OCC listing
        # OCC lists actions in structured HTML tables or lists
        patterns = [
            # Table row pattern
            r'<tr[^>]*>.*?<td[^>]*>(.*?)</td>.*?<td[^>]*>(.*?)</td>.*?<td[^>]*>(.*?)</td>.*?</tr>',
            # List item pattern
            r'<li[^>]*>.*?<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>.*?(\d{1,2}/\d{1,2}/\d{4})',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
            for match in matches:
                if len(match) >= 3:
                    clean_name = re.sub(r'<[^>]+>', '', match[0] if len(match[0]) > len(match[1]) else match[1]).strip()
                    clean_date = re.sub(r'<[^>]+>', '', match[2] if len(match) > 2 else "").strip()

                    if clean_name and len(clean_name) > 3:
                        action_id = _generate_action_id("OCC", clean_name, clean_date)
                        actions.append({
                            "action_id": action_id,
                            "agency": "OCC",
                            "institution_name": clean_name,
                            "cert_number": None,
                            "action_type": "Enforcement Action",
                            "action_date": clean_date,
                            "penalty_amount": None,
                            "description": None,
                            "docket_number": None,
                            "source_url": OCC_LIST_URL,
                            "quality_score": 0.3,
                        })

                        if limit and len(actions) >= limit:
                            return actions

    except requests.RequestException as e:
        console.print(f"  [yellow]OCC HTML scrape failed: {e}[/yellow]")

    console.print(f"  [green]Scraped {len(actions)} OCC enforcement actions (HTML)[/green]")
    return actions


def run_occ_pipeline(db_conn, limit: Optional[int] = None) -> int:
    """Run the OCC enforcement scrape and store pipeline."""
    from src.storage.database import store_regulatory_enforcement_batch

    actions = scrape_occ_enforcement_api(limit=limit)
    if actions:
        stored = store_regulatory_enforcement_batch(db_conn, actions)
        console.print(f"  [green]Stored {stored} OCC enforcement actions[/green]")
        return stored
    return 0
