"""
CFPB Enforcement Actions scraper.

Scrapes enforcement action listings from the CFPB website and extracts
respondent names, dates, descriptions, and penalty amounts.

Data source: https://www.consumerfinance.gov/enforcement/actions/

Built by Nathan Goldberg | nathanmauricegoldberg@gmail.com
"""

import re
import time
from datetime import datetime
from typing import Generator, Optional

import requests
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = "https://www.consumerfinance.gov/enforcement/actions/"
USER_AGENT = (
    "CFPB-Complaint-Tracker/0.1 "
    "(Research project by Nathan Goldberg; nathanmauricegoldberg@gmail.com)"
)
REQUEST_DELAY = 1.0  # seconds between page requests
MAX_PAGES = 20


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _parse_date(date_str: str) -> Optional[str]:
    """Parse CFPB date formats to ISO format."""
    if not date_str:
        return None
    date_str = date_str.strip()
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%b. %d, %Y", "%B. %d, %Y"):
        try:
            dt = datetime.strptime(date_str.upper()
                                   .replace("JAN", "Jan").replace("FEB", "Feb")
                                   .replace("MAR", "Mar").replace("APR", "Apr")
                                   .replace("MAY", "May").replace("JUN", "Jun")
                                   .replace("JUL", "Jul").replace("AUG", "Aug")
                                   .replace("SEP", "Sep").replace("OCT", "Oct")
                                   .replace("NOV", "Nov").replace("DEC", "Dec"),
                                   fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    # Try direct parsing
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return date_str
    except ValueError:
        return None


def _extract_penalty_amount(text: str) -> Optional[float]:
    """Extract penalty/fine amount from description text.

    Only matches dollar amounts in penalty-related context (e.g., "pay $X",
    "civil money penalty of $X", "fine of $X"). Ignores dollar amounts that
    describe assets, revenue, or other non-penalty figures.
    """
    if not text:
        return None

    # Context keywords that indicate a penalty amount follows
    penalty_contexts = [
        r'(?:pay|paid|penalty|penalt|fine|fined|relief|redress|restitution|refund|disgorgement|judgment)\s+(?:of\s+)?(?:approximately\s+)?(?:more than\s+)?(?:at least\s+)?',
        r'(?:ordered to pay|required to pay|agreed to pay|will pay|must pay)\s+(?:approximately\s+)?(?:more than\s+)?(?:at least\s+)?',
        r'(?:civil money penalty|monetary relief|consumer relief|total relief)\s+(?:of\s+)?(?:approximately\s+)?(?:more than\s+)?(?:at least\s+)?',
    ]

    for ctx_pattern in penalty_contexts:
        pattern = ctx_pattern + r'(\$[\d,]+(?:\.\d+)?(?:\s*(?:billion|million))?)'
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            amount_str = match.group(1)
            num_str = re.sub(r'[,$]', '', amount_str.split()[0].replace('$', ''))
            try:
                amount = float(num_str)
                if 'billion' in amount_str.lower():
                    amount *= 1_000_000_000
                elif 'million' in amount_str.lower():
                    amount *= 1_000_000
                return amount
            except ValueError:
                continue
    return None


def _parse_enforcement_page(html: str) -> list[dict]:
    """
    Parse a single page of enforcement actions from HTML.

    Returns:
        List of enforcement action dicts.
    """
    actions = []

    # Split HTML by action entry headers
    blocks = re.split(
        r'(?=<h[234][^>]*>\s*<a[^>]*href="/enforcement/actions/)',
        html,
    )

    for block in blocks[1:]:
        # Extract name and URL
        match = re.search(
            r'<a[^>]*href="(/enforcement/actions/[^"]+)"[^>]*>([^<]+)</a>',
            block,
        )
        if not match:
            continue

        url, name = match.groups()
        name = (
            name.strip()
            .replace("&amp;", "&")
            .replace("&#39;", "'")
            .replace("&quot;", '"')
        )

        # Extract date filed
        date = None
        date_match = re.search(
            r'Date filed:.*?(\w+ \d{1,2}, \d{4})', block, re.DOTALL
        )
        if date_match:
            date = _parse_date(date_match.group(1))

        # Extract description text
        text = re.sub(r'<[^>]+>', ' ', block[:3000])
        text = re.sub(r'\s+', ' ', text).strip()
        desc_match = re.search(r'(On \w+ \d+.*?)Date filed:', text)
        description = desc_match.group(1).strip() if desc_match else ""

        # Try to extract penalty amount from description
        penalty = _extract_penalty_amount(description)

        # Determine action type from description
        action_type = None
        desc_lower = description.lower()
        if "consent order" in desc_lower:
            action_type = "Consent Order"
        elif "complaint" in desc_lower and "order" not in desc_lower:
            action_type = "Complaint"
        elif "order" in desc_lower:
            action_type = "Order"
        elif "lawsuit" in desc_lower:
            action_type = "Lawsuit"
        elif "settlement" in desc_lower:
            action_type = "Settlement"

        actions.append({
            "agency": "CFPB",
            "respondent_name": name,
            "action_date": date,
            "action_type": action_type,
            "penalty_amount": penalty,
            "description": description[:1000] if description else None,
            "url": f"https://www.consumerfinance.gov{url}",
            "institution_cert": None,  # Will be resolved during normalization
        })

    return actions


# ---------------------------------------------------------------------------
# Scraping
# ---------------------------------------------------------------------------

def scrape_enforcement_actions(
    max_pages: int = MAX_PAGES,
) -> Generator[dict, None, None]:
    """
    Scrape all CFPB enforcement actions from the website.

    Paginates through the enforcement actions listing and parses
    each page for action details.

    Args:
        max_pages: Maximum number of pages to scrape.

    Yields:
        dict: Enforcement action records.
    """
    headers = {"User-Agent": USER_AGENT}
    total_yielded = 0

    console.print("  Scraping CFPB enforcement actions...")

    for page_num in range(1, max_pages + 1):
        url = f"{BASE_URL}?page={page_num}"
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            console.print(f"  [yellow]Failed to fetch page {page_num}: {e}[/yellow]")
            break

        actions = _parse_enforcement_page(response.text)
        if not actions:
            console.print(f"  No actions found on page {page_num}, stopping.")
            break

        for action in actions:
            yield action
            total_yielded += 1

        console.print(f"  Page {page_num}: {len(actions)} actions (total: {total_yielded})")
        time.sleep(REQUEST_DELAY)

    console.print(f"  [green]Scraped {total_yielded} enforcement actions[/green]")


# ---------------------------------------------------------------------------
# Pipeline Integration
# ---------------------------------------------------------------------------

def run_enforcement_pipeline(
    db_conn,
    max_pages: int = MAX_PAGES,
    batch_size: int = 500,
) -> int:
    """
    Run the full enforcement action scrape-and-store pipeline.

    Args:
        db_conn: Active SQLite database connection.
        max_pages: Maximum pages to scrape.
        batch_size: Number of records per database batch insert.

    Returns:
        Total number of records stored.
    """
    from src.storage.database import (
        store_enforcement_actions_batch,
        start_pipeline_run,
        complete_pipeline_run,
    )

    run_id = start_pipeline_run(db_conn, "cfpb_enforcement")
    try:
        batch = []
        total = 0
        for action in scrape_enforcement_actions(max_pages=max_pages):
            batch.append(action)
            if len(batch) >= batch_size:
                store_enforcement_actions_batch(db_conn, batch)
                total += len(batch)
                batch = []
        if batch:
            store_enforcement_actions_batch(db_conn, batch)
            total += len(batch)
        complete_pipeline_run(db_conn, run_id, total)
        console.print(f"  [green]Stored {total} enforcement actions[/green]")
        return total
    except Exception as e:
        complete_pipeline_run(db_conn, run_id, 0, status="failed", notes=str(e))
        raise
