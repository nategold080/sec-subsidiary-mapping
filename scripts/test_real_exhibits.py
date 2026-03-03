"""Test parser against real SEC Exhibit 21 files."""

import time
import httpx
from src.extractors.exhibit21_parser import parse_exhibit21
from src.normalization.jurisdictions import normalize_jurisdiction

headers = {
    "User-Agent": "DataFactory/1.0 (SEC-Subsidiary-Mapping; research; nathanmauricegoldberg@gmail.com)",
}

tests = [
    ("Apple", "https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/a10-kexhibit21109282024.htm"),
    ("Alpha Pro Tech", "https://www.sec.gov/Archives/edgar/data/884269/000143774924007539/ex_633896.htm"),
    ("Union Pacific", "https://www.sec.gov/Archives/edgar/data/100885/000143774924003599/ex_605066.htm"),
]

for name, url in tests:
    r = httpx.get(url, headers=headers, timeout=30, follow_redirects=True)
    if r.status_code != 200:
        print(f"{name}: HTTP {r.status_code}")
        continue

    result = parse_exhibit21(r.text)
    print(f"=== {name} ===")
    print(f"  Method: {result.parse_method}")
    print(f"  Subsidiaries: {len(result.subsidiaries)}")
    if result.error:
        print(f"  Error: {result.error}")

    for sub in result.subsidiaries[:5]:
        norm = normalize_jurisdiction(sub.jurisdiction_raw)
        haven = " [TAX HAVEN]" if norm and norm.is_tax_haven else ""
        code = norm.code if norm else "???"
        pct = f" ({sub.ownership_pct}%)" if sub.ownership_pct else ""
        print(f"    {sub.name:40s} | {sub.jurisdiction_raw:25s} -> {code}{haven}{pct}")
    if len(result.subsidiaries) > 5:
        print(f"    ... and {len(result.subsidiaries) - 5} more")

    havens = 0
    normalized_count = 0
    for sub in result.subsidiaries:
        norm = normalize_jurisdiction(sub.jurisdiction_raw)
        if norm:
            normalized_count += 1
            if norm.is_tax_haven:
                havens += 1
    print(f"  Normalized: {normalized_count}/{len(result.subsidiaries)}")
    print(f"  Tax havens: {havens}")
    print()
    time.sleep(0.5)
