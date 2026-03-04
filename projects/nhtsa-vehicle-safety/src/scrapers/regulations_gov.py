"""Regulations.gov API scraper for NHTSA investigation dockets.

Fetches investigation documents, closing notices, and determination data
from the Regulations.gov API for NHTSA investigation numbers.

API docs: https://open.gsa.gov/api/regulationsgov/
Rate limit: 1,000 requests/hour with API key.
Requires free API key from https://open.gsa.gov/api/regulationsgov/
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

import httpx

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "raw" / "regulations"
BASE_URL = "https://api.regulations.gov/v4"
USER_AGENT = "NHTSAVehicleSafetyTracker/1.0 (nathanmauricegoldberg@gmail.com)"
REQUEST_DELAY = 4.0  # ~900 requests/hour to stay under 1000 limit


def get_api_key() -> str | None:
    """Get Regulations.gov API key from environment or config."""
    key = os.environ.get("REGULATIONS_GOV_API_KEY")
    if key:
        return key

    # Check config file
    config_path = Path(__file__).parent.parent.parent / "config" / "api_keys.yaml"
    if config_path.exists():
        import yaml
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}
        return config.get("regulations_gov_api_key")

    return None


def search_nhtsa_docket(investigation_number: str, api_key: str,
                        client: httpx.Client | None = None) -> dict | None:
    """Search for an NHTSA investigation docket by investigation number.

    Returns docket metadata dict or None if not found.
    """
    cache_path = _cache_path("docket", investigation_number)
    if cache_path.exists():
        try:
            with open(cache_path) as f:
                data = json.load(f)
                if data:
                    return data
        except (json.JSONDecodeError, IOError):
            pass

    _client = client or httpx.Client(timeout=30, headers={"User-Agent": USER_AGENT})
    try:
        # Search for dockets matching investigation number
        url = f"{BASE_URL}/documents"
        params = {
            "filter[agencyId]": "NHTSA",
            "filter[searchTerm]": investigation_number,
            "api_key": api_key,
            "page[size]": 25,
        }

        resp = _client.get(url, params=params)
        if resp.status_code != 200:
            return None

        data = resp.json()
        results = data.get("data", [])

        if not results:
            _save_cache(cache_path, {})
            return None

        # Build docket info from first matching result
        docket_info = _parse_docket_results(results, investigation_number)
        if docket_info:
            _save_cache(cache_path, docket_info)
        return docket_info

    except (httpx.HTTPError, json.JSONDecodeError, KeyError):
        return None
    finally:
        if client is None:
            _client.close()
        time.sleep(REQUEST_DELAY)


def fetch_docket_documents(docket_id: str, api_key: str,
                          client: httpx.Client | None = None) -> list[dict]:
    """Fetch documents for a specific docket.

    Returns list of document metadata dicts.
    """
    cache_path = _cache_path("docs", docket_id)
    if cache_path.exists():
        try:
            with open(cache_path) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass

    _client = client or httpx.Client(timeout=30, headers={"User-Agent": USER_AGENT})
    try:
        url = f"{BASE_URL}/documents"
        params = {
            "filter[docketId]": docket_id,
            "api_key": api_key,
            "page[size]": 100,
        }

        resp = _client.get(url, params=params)
        if resp.status_code != 200:
            return []

        data = resp.json()
        results = data.get("data", [])

        documents = [_parse_document(doc) for doc in results]
        documents = [d for d in documents if d]

        _save_cache(cache_path, documents)
        return documents

    except (httpx.HTTPError, json.JSONDecodeError):
        return []
    finally:
        if client is None:
            _client.close()
        time.sleep(REQUEST_DELAY)


def fetch_all_investigation_dockets(investigation_numbers: list[str], api_key: str,
                                    progress_callback=None) -> dict:
    """Fetch docket data for all investigation numbers.

    Returns dict with dockets and documents lists.
    """
    dockets = []
    documents = []
    total = len(investigation_numbers)

    with httpx.Client(timeout=30, headers={"User-Agent": USER_AGENT}) as client:
        for i, inv_num in enumerate(investigation_numbers):
            docket = search_nhtsa_docket(inv_num, api_key, client=client)
            if docket and docket.get("docket_id"):
                dockets.append(docket)

                # Fetch documents for this docket
                docs = fetch_docket_documents(docket["docket_id"], api_key, client=client)
                for doc in docs:
                    doc["investigation_number"] = inv_num
                documents.extend(docs)

            if progress_callback and ((i + 1) % 10 == 0 or i + 1 == total):
                progress_callback(i + 1, total, f"{inv_num}: {len(dockets)} dockets found")

    return {"dockets": dockets, "documents": documents}


def _parse_docket_results(results: list, investigation_number: str) -> dict | None:
    """Parse search results into a docket info dict."""
    for result in results:
        attrs = result.get("attributes", {})
        title = attrs.get("title", "")
        docket_id = attrs.get("docketId", "")

        if not docket_id:
            continue

        return {
            "docket_id": docket_id,
            "investigation_number": investigation_number,
            "docket_type": attrs.get("docketType", ""),
            "title": title,
            "document_count": attrs.get("documentCount", 0),
            "last_modified": attrs.get("lastModifiedDate", ""),
        }

    return None


def _parse_document(doc: dict) -> dict | None:
    """Parse a single document from the API response."""
    attrs = doc.get("attributes", {})
    doc_id = doc.get("id", "")
    if not doc_id:
        return None

    title = attrs.get("title", "")
    doc_type = classify_document_type(title)
    determination = extract_determination(title)

    return {
        "document_id": doc_id,
        "docket_id": attrs.get("docketId", ""),
        "document_type": doc_type,
        "title": title,
        "posted_date": attrs.get("postedDate", ""),
        "author": attrs.get("authorName", ""),
        "summary": (attrs.get("summary") or "")[:500],
        "determination": determination,
        "affected_population": None,
        "source_url": attrs.get("fileUrl", ""),
    }


def classify_document_type(title: str) -> str:
    """Classify document type from title text."""
    t = title.upper()

    if "CLOSING" in t and ("RESUME" in t or "INVESTIGATION" in t or "NOTICE" in t):
        return "closing_notice"
    if "OPENING" in t or "INITIAT" in t:
        return "opening_notice"
    if "PRELIMINARY EVALUATION" in t or "PE REPORT" in t:
        return "pe_report"
    if "ENGINEERING ANALYSIS" in t or "EA REPORT" in t:
        return "ea_report"
    if "RECALL" in t and ("REQUEST" in t or "QUERY" in t):
        return "recall_request"
    if "MANUFACTURER" in t and ("RESPONSE" in t or "COMMUNICATION" in t or "REPORT" in t):
        return "manufacturer_response"
    if "DEFECT" in t and "PETITION" in t:
        return "defect_petition"
    if "COMMENT" in t or "PUBLIC" in t:
        return "public_comment"
    if "TECHNICAL" in t and "SERVICE" in t:
        return "tsb"

    return "other"


def extract_determination(title: str) -> str | None:
    """Extract investigation determination from document title."""
    t = title.upper()

    # Check "no defect" patterns BEFORE "defect found" to avoid false positives
    if "NO DEFECT" in t or "DEFECT NOT FOUND" in t:
        return "no_defect"
    if "DEFECT FOUND" in t or "DEFECT EXISTS" in t:
        return "defect_found"
    if "INSUFFICIENT" in t and "EVIDENCE" in t:
        return "insufficient_evidence"
    if "RECALL" in t and ("CONDUCTED" in t or "INITIATED" in t or "ISSUED" in t):
        return "recall_requested"
    if "UPGRADE" in t and ("EA" in t or "ENGINEERING" in t):
        return "upgraded_to_ea"

    return None


def _cache_path(doc_type: str, identifier: str) -> Path:
    """Get cache file path."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    safe_id = re.sub(r"[^a-zA-Z0-9_-]", "_", identifier)
    return CACHE_DIR / f"{doc_type}_{safe_id}.json"


def _save_cache(path: Path, data) -> None:
    """Save data to cache."""
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
