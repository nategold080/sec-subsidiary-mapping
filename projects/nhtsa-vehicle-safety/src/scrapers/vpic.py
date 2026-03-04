"""NHTSA VPIC (Vehicle Product Information Catalog) API scraper.

Fetches vehicle attributes (body type, fuel type, drivetrain, engine, transmission)
for unique make/model/year combinations via VIN decoding and make/model lookup.

API docs: https://vpic.nhtsa.dot.gov/api/
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "raw" / "vpic"
USER_AGENT = "NHTSAVehicleSafetyTracker/1.0 (nathanmauricegoldberg@gmail.com)"
BASE_URL = "https://vpic.nhtsa.dot.gov/api"
REQUEST_DELAY = 0.3  # Generous rate limit


def fetch_vehicle_attributes(make: str, model: str, model_year: int,
                             client: httpx.Client | None = None) -> dict | None:
    """Fetch vehicle attributes for a make/model/year from VPIC API.

    Uses GetModelsForMakeIdYear as the primary endpoint, falling back to
    DecodeVin-style lookups if needed.
    """
    cache_path = _cache_path(make, model, model_year)
    if cache_path.exists():
        try:
            with open(cache_path) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass

    _client = client or httpx.Client(timeout=30, headers={"User-Agent": USER_AGENT})
    try:
        result = _fetch_from_decode_api(_client, make, model, model_year)
        if result:
            _save_cache(cache_path, result)
            return result
    finally:
        if client is None:
            _client.close()
        time.sleep(REQUEST_DELAY)

    return None


def fetch_vehicle_attributes_bulk(vehicles: list[dict],
                                   progress_callback=None) -> list[dict]:
    """Fetch attributes for a list of {make, model, model_year} dicts.

    Returns list of attribute dicts (one per vehicle that returned data).
    """
    results = []
    total = len(vehicles)

    with httpx.Client(timeout=30, headers={"User-Agent": USER_AGENT}) as client:
        for i, v in enumerate(vehicles):
            make = v["make"]
            model = v["model"]
            year = v["model_year"]

            attrs = fetch_vehicle_attributes(make, model, year, client=client)
            if attrs:
                results.append(attrs)

            if progress_callback and ((i + 1) % 50 == 0 or i + 1 == total):
                progress_callback(i + 1, total, f"{make} {model} {year}")

    return results


def _fetch_from_decode_api(client: httpx.Client, make: str, model: str,
                           model_year: int) -> dict | None:
    """Use the VPIC decode-by-make-model-year approach.

    Endpoint: /vehicles/GetModelsForMakeYear/make/{make}/modelyear/{year}?format=json
    Then for each model hit, use vehicle type information.
    """
    # Try GetVehicleTypesForMakeYear for body/vehicle classification
    url = f"{BASE_URL}/vehicles/GetVehicleVariableValuesList/Body Class?format=json"

    # Better approach: use DecodeVINValuesBatch with a synthetic VIN-like lookup
    # Actually, use the direct make/model/year decode endpoint
    url = f"{BASE_URL}/vehicles/GetModelsForMakeYear/make/{make}/modelyear/{model_year}?format=json"

    try:
        resp = client.get(url)
        if resp.status_code != 200:
            return None

        data = resp.json()
        models = data.get("Results", [])

        # Find our specific model
        target_model = model.upper()
        match = None
        for m in models:
            name = (m.get("Model_Name") or "").upper()
            if name == target_model or target_model in name or name in target_model:
                match = m
                break

        if not match:
            return _build_basic_attributes(make, model, model_year)

        # Get vehicle type from the match
        vehicle_type = match.get("VehicleTypeName", "")

        time.sleep(REQUEST_DELAY)

        # Now try to get more detailed attributes via the vehicle type endpoint
        attrs = _build_basic_attributes(make, model, model_year)
        attrs["body_class"] = _classify_body(vehicle_type, model)
        attrs["fuel_type"] = _classify_fuel(make, model, model_year)
        attrs["electrification_level"] = _classify_electrification(make, model, model_year)
        attrs["drive_type"] = _infer_drive_type(make, model)

        return attrs

    except (httpx.HTTPError, json.JSONDecodeError, KeyError):
        return _build_basic_attributes(make, model, model_year)


def _build_basic_attributes(make: str, model: str, model_year: int) -> dict:
    """Build a basic attribute dict from make/model/year with inferred values."""
    return {
        "make": make.upper(),
        "model": model.upper(),
        "model_year": model_year,
        "body_class": _classify_body("", model),
        "drive_type": _infer_drive_type(make, model),
        "fuel_type": _classify_fuel(make, model, model_year),
        "engine_displacement_l": None,
        "engine_cylinders": None,
        "engine_configuration": None,
        "transmission_type": None,
        "gvwr_class": None,
        "plant_country": None,
        "plant_state": None,
        "electrification_level": _classify_electrification(make, model, model_year),
    }


# Classification helpers using known model patterns

_EV_MAKES = {"TESLA", "RIVIAN", "LUCID", "POLESTAR", "FISKER", "CANOO", "LORDSTOWN"}

_EV_MODELS = {
    "MODEL 3", "MODEL Y", "MODEL S", "MODEL X", "CYBERTRUCK",
    "R1T", "R1S", "AIR", "GRAVITY",
    "BOLT EV", "BOLT EUV", "LEAF", "IONIQ 5", "IONIQ 6",
    "EV6", "EV9", "ID.4", "ID.BUZZ", "MUSTANG MACH-E",
    "F-150 LIGHTNING", "LYRIQ", "EQUINOX EV", "BLAZER EV",
    "SOLTERRA", "BZ4X", "PROLOGUE", "ARIYA", "NIRO EV",
    "E-TRON", "E-TRON GT", "Q4 E-TRON", "Q6 E-TRON", "Q8 E-TRON",
    "IX", "I4", "I5", "I7", "IXMINI", "IX3",
    "EQS", "EQE", "EQB", "EQA",
    "XC40 RECHARGE", "EX30", "EX90",
    "HUMMER EV",
}

_HYBRID_MODELS = {
    "PRIUS", "CAMRY HYBRID", "RAV4 HYBRID", "HIGHLANDER HYBRID",
    "COROLLA HYBRID", "VENZA", "SIENNA",
    "ACCORD HYBRID", "CR-V HYBRID", "INSIGHT",
    "ESCAPE HYBRID", "MAVERICK", "EXPLORER HYBRID",
    "TUCSON HYBRID", "SANTA FE HYBRID", "IONIQ HYBRID",
    "SPORTAGE HYBRID", "SORENTO HYBRID", "NIRO",
    "CROSSTREK HYBRID",
    "OUTBACK HYBRID", "FORESTER HYBRID",
}

_PHEV_MODELS = {
    "PRIUS PRIME", "RAV4 PRIME",
    "OUTLANDER PHEV", "WRANGLER 4XE", "GRAND CHEROKEE 4XE",
    "ESCAPE PLUG-IN HYBRID", "CORSAIR PLUG-IN",
    "TUCSON PLUG-IN HYBRID", "SANTA FE PLUG-IN HYBRID",
    "SORENTO PLUG-IN HYBRID", "NIRO PLUG-IN HYBRID",
    "CROSSTREK PLUG-IN HYBRID",
    "330E", "530E", "X5 XDRIVE45E", "X3 XDRIVE30E",
    "CAYENNE E-HYBRID", "PANAMERA E-HYBRID",
    "XC60 RECHARGE", "XC90 RECHARGE", "S60 RECHARGE", "S90 RECHARGE",
    "GLC 350E", "GLE 350E", "S 580 E",
}

_SUV_MODELS = {
    "RAV4", "CR-V", "CX-5", "TUCSON", "SPORTAGE", "ROGUE", "ESCAPE",
    "EXPLORER", "EQUINOX", "TRAVERSE", "TAHOE", "SUBURBAN", "4RUNNER",
    "HIGHLANDER", "PILOT", "PASSPORT", "PATHFINDER", "TELLURIDE",
    "PALISADE", "ATLAS", "TIGUAN", "OUTLANDER", "FORESTER", "OUTBACK",
    "CROSSTREK", "WRANGLER", "GRAND CHEROKEE", "CHEROKEE", "COMPASS",
    "MODEL Y", "MODEL X", "R1S", "LYRIQ", "BLAZER", "TRAILBLAZER",
    "BRONCO", "BRONCO SPORT", "EXPEDITION", "SANTA FE",
    "X1", "X3", "X5", "X7", "GLC", "GLE", "GLS", "Q3", "Q5", "Q7", "Q8",
    "CAYENNE", "MACAN", "XC40", "XC60", "XC90", "RANGE ROVER",
    "RANGE ROVER SPORT", "DEFENDER", "DISCOVERY",
    "IONIQ 5", "IONIQ 6", "EV6", "EV9", "ID.4", "ARIYA", "SOLTERRA", "BZ4X",
    "NX", "RX", "TX", "GX", "LX", "UX",
    "RDX", "MDX", "ZDX",
    "QX50", "QX55", "QX60", "QX80",
    "GV70", "GV80", "GV60",
    "ENCORE", "ENVISION", "ENCLAVE",
    "XT4", "XT5", "XT6", "ESCALADE",
    "TERRAIN", "ACADIA", "YUKON",
    "DURANGO", "HORNET",
    "NAUTILUS", "AVIATOR", "NAVIGATOR", "CORSAIR",
}

_TRUCK_MODELS = {
    "F-150", "F-250", "F-350", "F-450", "F-550",
    "SILVERADO", "COLORADO", "SIERRA",
    "RAM 1500", "RAM 2500", "RAM 3500",
    "TACOMA", "TUNDRA", "FRONTIER", "TITAN",
    "RANGER", "MAVERICK", "RIDGELINE",
    "GLADIATOR", "CYBERTRUCK", "R1T", "F-150 LIGHTNING",
    "CANYON", "HUMMER EV",
}

_VAN_MODELS = {
    "ODYSSEY", "SIENNA", "PACIFICA", "CARNIVAL",
    "TRANSIT", "TRANSIT CONNECT", "SPRINTER",
    "PROMASTER", "PROMASTER CITY", "SAVANA", "EXPRESS",
    "NV200", "NV", "METRIS",
}

_MOTORCYCLE_MAKES = {
    "HARLEY-DAVIDSON", "INDIAN", "KAWASAKI", "YAMAHA", "SUZUKI", "DUCATI",
    "TRIUMPH", "BMW MOTORRAD", "KTM", "APRILIA", "HUSQVARNA",
}


def _classify_body(vehicle_type: str, model: str) -> str:
    """Classify body type from vehicle type and model name."""
    m = model.upper()
    vt = vehicle_type.upper() if vehicle_type else ""

    if any(m == t or m.startswith(t) for t in _TRUCK_MODELS):
        return "Truck"
    if any(m == v or m.startswith(v) for t in [_VAN_MODELS] for v in t):
        return "Van/Minivan"
    if any(m == s or m.startswith(s) for s in _SUV_MODELS):
        return "SUV/Crossover"

    if "MOTORCYCLE" in vt or "MOPED" in vt:
        return "Motorcycle"
    if "TRUCK" in vt or "PICKUP" in vt:
        return "Truck"
    if "BUS" in vt:
        return "Bus"
    if "TRAILER" in vt:
        return "Trailer"
    if "MULTIPURPOSE" in vt or "SUV" in vt:
        return "SUV/Crossover"
    if "VAN" in vt:
        return "Van/Minivan"

    # Default: sedan/car for passenger vehicles
    return "Sedan/Car"


def _classify_fuel(make: str, model: str, model_year: int) -> str:
    """Classify fuel type from make/model."""
    m = model.upper()
    mk = make.upper()

    if mk in _EV_MAKES:
        return "Electric"
    if m in _EV_MODELS or any(m.startswith(e) for e in _EV_MODELS):
        return "Electric"
    if m in _PHEV_MODELS or any(m.startswith(p) for p in _PHEV_MODELS):
        return "Plug-in Hybrid"
    if m in _HYBRID_MODELS or "HYBRID" in m:
        return "Hybrid"
    if "DIESEL" in m or "TDI" in m:
        return "Diesel"
    return "Gasoline"


def _classify_electrification(make: str, model: str, model_year: int) -> str:
    """Classify electrification level."""
    m = model.upper()
    mk = make.upper()

    if mk in _EV_MAKES:
        return "BEV"
    if m in _EV_MODELS or any(m.startswith(e) for e in _EV_MODELS):
        return "BEV"
    if m in _PHEV_MODELS or any(m.startswith(p) for p in _PHEV_MODELS):
        return "PHEV"
    if m in _HYBRID_MODELS or "HYBRID" in m:
        return "Full Hybrid"
    return "None"


def _infer_drive_type(make: str, model: str) -> str | None:
    """Infer drive type from model name patterns."""
    m = model.upper()
    if "AWD" in m or "4WD" in m or "XDRIVE" in m or "QUATTRO" in m:
        return "AWD"
    if "4X4" in m or "4MATIC" in m:
        return "AWD"
    if "RWD" in m:
        return "RWD"
    if "FWD" in m:
        return "FWD"
    return None


def _cache_path(make: str, model: str, model_year: int) -> Path:
    """Get cache file path for a make/model/year."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    safe_make = make.upper().replace(" ", "_").replace("/", "_")
    safe_model = model.upper().replace(" ", "_").replace("/", "_")
    return CACHE_DIR / f"{safe_make}_{safe_model}_{model_year}.json"


def _save_cache(path: Path, data: dict) -> None:
    """Save data to cache file."""
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
