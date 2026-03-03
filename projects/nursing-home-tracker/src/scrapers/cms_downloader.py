"""CMS Data Downloader — fetches CSV datasets from data.cms.gov.

This module downloads nursing home datasets from CMS's Provider Data Catalog.
All datasets are freely available as CSV downloads. We cache raw files locally
to avoid re-downloading on subsequent runs.
"""

import hashlib
import time
from datetime import datetime
from pathlib import Path

import httpx
import yaml
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()
PROJECT_ROOT = Path(__file__).parent.parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "sources.yaml"
CACHE_DIR = PROJECT_ROOT / "data" / "raw"

USER_AGENT = "DataFactory/1.0 (research; contact: nathanmauricegoldberg@gmail.com)"
DELAY_SECONDS = 2


def load_config() -> dict:
    """Load source configuration from YAML."""
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def get_cache_path(source_key: str) -> Path:
    """Get the cache file path for a given source."""
    return CACHE_DIR / f"{source_key}.csv"


def is_cached(source_key: str) -> bool:
    """Check if a source's data is already cached."""
    cache_path = get_cache_path(source_key)
    if not cache_path.exists():
        return False
    # Consider cache valid for 24 hours
    age_hours = (time.time() - cache_path.stat().st_mtime) / 3600
    return age_hours < 24


def download_csv(url: str, dest: Path, source_name: str) -> bool:
    """Download a CSV file from CMS with proper headers and error handling."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/csv,application/csv,*/*",
    }

    try:
        console.print(f"  Downloading [cyan]{source_name}[/cyan]...")
        with httpx.Client(timeout=120.0, follow_redirects=True) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()

            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(response.content)

            size_mb = len(response.content) / (1024 * 1024)
            console.print(f"  [green]✓[/green] {source_name}: {size_mb:.1f} MB saved to {dest.name}")
            return True

    except httpx.HTTPStatusError as e:
        console.print(f"  [red]✗[/red] {source_name}: HTTP {e.response.status_code}")
        return False
    except httpx.RequestError as e:
        console.print(f"  [red]✗[/red] {source_name}: {e}")
        return False


def download_source(source_key: str, force: bool = False) -> bool:
    """Download a single CMS dataset."""
    config = load_config()
    sources = config.get("sources", {})

    if source_key not in sources:
        console.print(f"[red]Unknown source: {source_key}[/red]")
        console.print(f"Available sources: {', '.join(sources.keys())}")
        return False

    source = sources[source_key]
    cache_path = get_cache_path(source_key)

    if not force and is_cached(source_key):
        console.print(f"  [yellow]⟳[/yellow] {source['name']}: cached (use --force to re-download)")
        return True

    url = source.get("download_url", source["url"])
    success = download_csv(url, cache_path, source["name"])

    if success:
        time.sleep(DELAY_SECONDS)

    return success


def download_all(force: bool = False) -> dict:
    """Download all CMS datasets. Returns dict of source_key -> success."""
    config = load_config()
    sources = config.get("sources", {})
    results = {}

    console.print(f"\n[bold blue]Downloading {len(sources)} CMS datasets...[/bold blue]")
    console.print(f"Cache directory: {CACHE_DIR}\n")

    for source_key in sources:
        results[source_key] = download_source(source_key, force=force)

    succeeded = sum(1 for v in results.values() if v)
    console.print(f"\n[bold]Download complete: {succeeded}/{len(sources)} succeeded[/bold]")

    return results
