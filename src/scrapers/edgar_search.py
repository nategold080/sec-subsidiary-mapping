"""SEC EDGAR filing discovery scraper.

Discovers 10-K filings containing Exhibit 21 (subsidiary lists) using the
EDGAR Full-Text Search (EFTS) API. Also fetches company metadata from the
Submissions API and downloads raw Exhibit 21 HTML/text files.

Rate limit: 10 requests/second with identified User-Agent.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

console = Console()

PROJECT_ROOT = Path(__file__).parent.parent.parent
CACHE_DIR = PROJECT_ROOT / "data" / "raw" / "filings"
EXHIBIT_DIR = PROJECT_ROOT / "data" / "raw" / "exhibits"

USER_AGENT = (
    "DataFactory/1.0 (SEC-Subsidiary-Mapping; research; "
    "nathanmauricegoldberg@gmail.com)"
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json",
    "Accept-Encoding": "gzip, deflate",
}

HTML_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,*/*",
    "Accept-Encoding": "gzip, deflate",
}

# SEC rate limit: 10 requests/second. We use 0.12s delay (~ 8/sec) for safety.
DELAY_SECONDS = 0.12

EFTS_URL = "https://efts.sec.gov/LATEST/search-index"
SUBMISSIONS_URL = "https://data.sec.gov/submissions"
ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data"
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"


def discover_filings(
    start_date: str = "2020-01-01",
    end_date: Optional[str] = None,
    max_filings: int = 5000,
    force: bool = False,
) -> list[dict]:
    """Discover 10-K filings containing Exhibit 21 via EFTS.

    Args:
        start_date: Start date (YYYY-MM-DD).
        end_date: End date (YYYY-MM-DD). Defaults to today.
        max_filings: Maximum filings to discover.
        force: Re-discover even if cache exists.

    Returns:
        List of filing metadata dicts with keys:
        accession, filename, cik, company_name, ticker, file_date, exhibit_url
    """
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"filings_{start_date}_{end_date}.json"

    if cache_file.exists() and not force:
        console.print("[dim]Loading cached filing discovery...[/dim]")
        with open(cache_file) as f:
            filings = json.load(f)
        console.print(f"[green]Loaded {len(filings)} cached filings[/green]")
        return filings

    console.print(
        f"[cyan]Discovering Exhibit 21 filings ({start_date} to {end_date})...[/cyan]"
    )

    filings = []
    offset = 0
    page_size = 100

    with httpx.Client(timeout=30, headers=HEADERS) as client:
        while offset < max_filings:
            params = {
                "q": '"exhibit 21"',
                "forms": "10-K",
                "dateRange": "custom",
                "startdt": start_date,
                "enddt": end_date,
                "from": offset,
                "size": page_size,
            }

            try:
                resp = client.get(EFTS_URL, params=params)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                console.print(f"[red]EFTS search error at offset {offset}: {e}[/red]")
                break

            hits = data.get("hits", {}).get("hits", [])
            total = data.get("hits", {}).get("total", {}).get("value", 0)

            if not hits:
                break

            for hit in hits:
                filing = _parse_efts_hit(hit)
                if filing:
                    filings.append(filing)

            console.print(
                f"[dim]  Page {offset // page_size + 1}: "
                f"{len(filings)}/{total} filings[/dim]"
            )

            offset += page_size
            if offset >= total:
                break

            time.sleep(DELAY_SECONDS)

    # Deduplicate by accession number
    seen = set()
    unique = []
    for f in filings:
        if f["accession"] not in seen:
            seen.add(f["accession"])
            unique.append(f)
    filings = unique

    # Cache results
    with open(cache_file, "w") as f:
        json.dump(filings, f, indent=2)

    console.print(
        f"[green]Discovered {len(filings)} unique Exhibit 21 filings[/green]"
    )
    return filings


def _parse_efts_hit(hit: dict) -> Optional[dict]:
    """Parse a single EFTS search result into a filing record."""
    try:
        hit_id = hit["_id"]
        src = hit["_source"]

        # _id format: "accession:filename"
        parts = hit_id.split(":", 1)
        accession = parts[0]
        filename = parts[1] if len(parts) > 1 else ""

        ciks = src.get("ciks", [])
        cik = ciks[0] if ciks else ""
        # Strip leading zeros for URL construction but keep padded for API
        cik_num = cik.lstrip("0") if cik else ""

        display_names = src.get("display_names", [])
        display = display_names[0] if display_names else ""

        # Parse "COMPANY NAME  (TICKER)  (CIK 0000NNNNNN)"
        company_name = ""
        ticker = ""
        if display:
            # Extract company name (before first parenthesis)
            name_match = re.match(r"^(.+?)\s*\(", display)
            if name_match:
                company_name = name_match.group(1).strip()
            else:
                company_name = display.strip()

            # Extract ticker
            ticker_match = re.search(r"\(([A-Z0-9, -]+)\)", display)
            if ticker_match:
                ticker_text = ticker_match.group(1)
                if not ticker_text.startswith("CIK"):
                    ticker = ticker_text.split(",")[0].strip()

        file_date = src.get("file_date", "")

        # Build exhibit URL
        acc_path = accession.replace("-", "")
        exhibit_url = f"{ARCHIVES_URL}/{cik_num}/{acc_path}/{filename}"

        return {
            "accession": accession,
            "filename": filename,
            "cik": cik,
            "cik_num": cik_num,
            "company_name": company_name,
            "ticker": ticker,
            "file_date": file_date,
            "exhibit_url": exhibit_url,
        }
    except Exception:
        return None


def fetch_exhibit(
    filing: dict,
    client: Optional[httpx.Client] = None,
) -> Optional[str]:
    """Fetch the raw HTML/text content of an Exhibit 21 file.

    Caches locally to avoid re-fetching. Returns the file content as string.
    """
    EXHIBIT_DIR.mkdir(parents=True, exist_ok=True)

    # Cache filename: CIK_accession_filename
    safe_name = re.sub(r"[^\w.-]", "_", f"{filing['cik']}_{filing['accession']}_{filing['filename']}")
    cache_path = EXHIBIT_DIR / safe_name

    if cache_path.exists():
        return cache_path.read_text(errors="replace")

    url = filing["exhibit_url"]

    close_client = False
    if client is None:
        client = httpx.Client(timeout=30, headers=HTML_HEADERS, follow_redirects=True)
        close_client = True

    try:
        resp = client.get(url)
        if resp.status_code != 200:
            return None

        content = resp.text
        cache_path.write_text(content)
        return content
    except Exception:
        return None
    finally:
        if close_client:
            client.close()


def fetch_exhibits_batch(
    filings: list[dict],
    max_fetch: Optional[int] = None,
    force: bool = False,
) -> dict[str, str]:
    """Fetch Exhibit 21 HTML/text for a batch of filings.

    Returns dict mapping accession number to HTML content.
    """
    EXHIBIT_DIR.mkdir(parents=True, exist_ok=True)

    results = {}
    to_fetch = filings[:max_fetch] if max_fetch else filings

    already_cached = 0
    for f in to_fetch:
        safe_name = re.sub(r"[^\w.-]", "_", f"{f['cik']}_{f['accession']}_{f['filename']}")
        cache_path = EXHIBIT_DIR / safe_name
        if cache_path.exists():
            already_cached += 1

    console.print(
        f"[cyan]Fetching {len(to_fetch)} exhibits "
        f"({already_cached} cached)...[/cyan]"
    )

    with httpx.Client(timeout=30, headers=HTML_HEADERS, follow_redirects=True) as client:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            console=console,
        ) as progress:
            task = progress.add_task("Fetching exhibits", total=len(to_fetch))

            for filing in to_fetch:
                content = fetch_exhibit(filing, client=client)
                if content:
                    results[filing["accession"]] = content

                progress.advance(task)
                time.sleep(DELAY_SECONDS)

    console.print(
        f"[green]Fetched {len(results)}/{len(to_fetch)} exhibits[/green]"
    )
    return results


def fetch_company_info(cik: str) -> Optional[dict]:
    """Fetch company metadata from SEC Submissions API.

    Returns dict with name, sic, sicDescription, tickers, exchanges.
    """
    padded = cik.zfill(10)
    url = f"{SUBMISSIONS_URL}/CIK{padded}.json"

    try:
        resp = httpx.get(url, headers=HEADERS, timeout=30)
        if resp.status_code != 200:
            return None

        data = resp.json()
        return {
            "cik": data.get("cik", cik),
            "name": data.get("name", ""),
            "sic": data.get("sic", ""),
            "sic_description": data.get("sicDescription", ""),
            "tickers": data.get("tickers", []),
            "exchanges": data.get("exchanges", []),
            "state_of_incorporation": data.get("stateOfIncorporation", ""),
            "fiscal_year_end": data.get("fiscalYearEnd", ""),
        }
    except Exception:
        return None


def fetch_company_tickers() -> dict[str, dict]:
    """Fetch SEC company tickers JSON (CIK -> ticker mapping).

    Returns dict keyed by CIK (zero-padded) with ticker and company name.
    """
    cache_path = CACHE_DIR / "company_tickers.json"
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if cache_path.exists():
        with open(cache_path) as f:
            return json.load(f)

    try:
        resp = httpx.get(TICKERS_URL, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        raw = resp.json()

        # raw format: {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}, ...}
        result = {}
        for entry in raw.values():
            cik_padded = str(entry["cik_str"]).zfill(10)
            result[cik_padded] = {
                "cik": cik_padded,
                "ticker": entry.get("ticker", ""),
                "company_name": entry.get("title", ""),
            }

        with open(cache_path, "w") as f:
            json.dump(result, f, indent=2)

        console.print(f"[green]Loaded {len(result)} company tickers[/green]")
        return result
    except Exception as e:
        console.print(f"[red]Error fetching company tickers: {e}[/red]")
        return {}
