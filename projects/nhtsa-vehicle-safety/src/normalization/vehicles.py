"""Vehicle make/model normalization."""

from __future__ import annotations

import re

# Common make name normalizations
MAKE_ALIASES = {
    "CHEVROLET": "CHEVROLET",
    "CHEVY": "CHEVROLET",
    "MERCEDES-BENZ": "MERCEDES-BENZ",
    "MERCEDES BENZ": "MERCEDES-BENZ",
    "MB": "MERCEDES-BENZ",
    "BMW": "BMW",
    "BAYERISCHE MOTOREN WERKE": "BMW",
    "VW": "VOLKSWAGEN",
    "VOLKSWAGEN": "VOLKSWAGEN",
    "GM": "GENERAL MOTORS",
    "GENERAL MOTORS": "GENERAL MOTORS",
    "FORD MOTOR COMPANY": "FORD",
    "FORD": "FORD",
    "TOYOTA MOTOR CORPORATION": "TOYOTA",
    "TOYOTA": "TOYOTA",
    "FCA US LLC": "CHRYSLER",
    "FCA US": "CHRYSLER",
    "FCA": "CHRYSLER",
    "CHRYSLER": "CHRYSLER",
    "STELLANTIS": "STELLANTIS",
    "HONDA": "HONDA",
    "AMERICAN HONDA MOTOR CO.": "HONDA",
    "NISSAN": "NISSAN",
    "NISSAN NORTH AMERICA": "NISSAN",
    "HYUNDAI": "HYUNDAI",
    "HYUNDAI MOTOR AMERICA": "HYUNDAI",
    "KIA": "KIA",
    "KIA MOTORS": "KIA",
    "SUBARU": "SUBARU",
    "SUBARU OF AMERICA": "SUBARU",
    "MAZDA": "MAZDA",
    "MAZDA MOTOR CORPORATION": "MAZDA",
    "TESLA": "TESLA",
    "TESLA, INC.": "TESLA",
    "VOLVO": "VOLVO",
    "VOLVO CAR": "VOLVO",
    "JAGUAR": "JAGUAR",
    "JAGUAR LAND ROVER": "JAGUAR LAND ROVER",
    "LAND ROVER": "LAND ROVER",
    "AUDI": "AUDI",
    "PORSCHE": "PORSCHE",
    "LEXUS": "LEXUS",
    "ACURA": "ACURA",
    "INFINITI": "INFINITI",
    "GENESIS": "GENESIS",
    "BUICK": "BUICK",
    "CADILLAC": "CADILLAC",
    "GMC": "GMC",
    "DODGE": "DODGE",
    "JEEP": "JEEP",
    "RAM": "RAM",
    "LINCOLN": "LINCOLN",
    "RIVIAN": "RIVIAN",
    "LUCID": "LUCID",
    "POLESTAR": "POLESTAR",
}

# Major automakers for tracking
MAJOR_MAKES = [
    "TOYOTA", "FORD", "CHEVROLET", "HONDA", "HYUNDAI",
    "NISSAN", "KIA", "JEEP", "SUBARU", "GMC",
    "RAM", "TESLA", "BMW", "MERCEDES-BENZ", "VOLKSWAGEN",
    "MAZDA", "LEXUS", "DODGE", "AUDI", "CHRYSLER",
    "ACURA", "CADILLAC", "BUICK", "LINCOLN", "VOLVO",
    "PORSCHE", "INFINITI", "GENESIS", "JAGUAR", "LAND ROVER",
    "RIVIAN", "LUCID", "POLESTAR",
]


def normalize_make(make: str) -> str:
    """Normalize a vehicle make name."""
    m = make.strip().upper()
    # Remove common suffixes
    m = re.sub(r",?\s*(MOTOR\s*(COMPANY|CORP\.?|CORPORATION)?|INC\.?|LLC|LTD\.?|CO\.?)\s*$", "", m)
    m = m.strip().rstrip(",")
    return MAKE_ALIASES.get(m, m)


def normalize_model(model: str) -> str:
    """Normalize a vehicle model name."""
    m = model.strip().upper()
    # Remove trailing year ranges
    m = re.sub(r"\s*\(\d{4}-\d{4}\)\s*$", "", m)
    m = re.sub(r"\s+", " ", m).strip()
    return m


def normalize_component(component: str) -> str:
    """Normalize a component name."""
    c = component.strip().upper()
    # Standard NHTSA component separators
    return c


def make_model_key(make: str, model: str) -> str:
    """Create a normalized key for matching make/model pairs."""
    return f"{normalize_make(make)}|{normalize_model(model)}"
