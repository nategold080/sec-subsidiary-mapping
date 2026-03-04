"""Tests for manufacturer risk scoring and profile builder."""

import sqlite3

import pytest

from src.normalization.manufacturer_profiles import (
    MIN_COMPLAINTS_FOR_SCORING,
    RISK_TIERS,
    RISK_WEIGHTS,
    _compute_risk_scores,
    _compute_trend,
    _get_tier,
    _score_profile_quality,
    build_manufacturer_profiles,
)
from src.storage.database import init_db


@pytest.fixture
def db():
    """Create an in-memory database with schema and test data."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _seed_complaints(conn, manufacturer, make, model, count, deaths=0, injuries=0, fires=0, crashes=0, year=2023):
    """Insert test complaint records."""
    for i in range(count):
        conn.execute("""
            INSERT OR IGNORE INTO complaints (
                odi_number, manufacturer, make, model, model_year,
                crash, fire, num_injuries, num_deaths,
                date_complaint_filed, components, summary, quality_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            10000000 + hash(f"{manufacturer}{i}{year}") % 9000000,
            manufacturer, make, model, year,
            1 if i < crashes else 0,
            1 if i < fires else 0,
            1 if i < injuries else 0,
            1 if i < deaths else 0,
            f"{year}-01-15", "ENGINE", f"Test complaint {i}", 0.8,
        ))
    conn.commit()


def _seed_recalls(conn, manufacturer, make, model, count, year=2023, affected=1000):
    """Insert test recall records."""
    for i in range(count):
        conn.execute("""
            INSERT OR IGNORE INTO recalls (
                campaign_number, manufacturer, make, model, model_year,
                report_received_date, component, summary, consequence, remedy,
                num_potentially_affected, quality_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            f"{year % 100}V{100 + i + hash(manufacturer) % 800:03d}000",
            manufacturer, make, model, year,
            f"{year}-06-15", "ENGINE", "Test recall", "May cause crash", "Fix it",
            affected, 0.9,
        ))
    conn.commit()


def _seed_investigations(conn, make, model, count, year_start=2023, year_end=2024, status="Open"):
    """Insert test investigation records."""
    for i in range(count):
        conn.execute("""
            INSERT OR IGNORE INTO investigations (
                investigation_number, make, model, model_year_start, model_year_end,
                investigation_type, status, open_date, subject, description, quality_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            f"PE{year_start}{100 + i + hash(make) % 800}",
            make, model, year_start, year_end,
            "PE", status, f"{year_start}-03-01",
            f"Test investigation {i}", "NHTSA opened investigation", 0.8,
        ))
    conn.commit()


class TestBuildManufacturerProfiles:
    def test_basic_profile_creation(self, db):
        """Test that profiles are created from complaint data."""
        _seed_complaints(db, "TOYOTA MOTOR CORPORATION", "TOYOTA", "CAMRY", 100,
                        deaths=2, injuries=10, fires=5, crashes=15)
        _seed_recalls(db, "TOYOTA MOTOR CORPORATION", "TOYOTA", "CAMRY", 3)

        result = build_manufacturer_profiles(db)
        assert result["profiles_created"] > 0

        profile = db.execute(
            "SELECT * FROM manufacturer_profiles WHERE manufacturer_name = 'TOYOTA'"
        ).fetchone()
        assert profile is not None
        assert profile["total_complaints"] == 100
        assert profile["total_recalls"] == 3
        assert profile["total_deaths"] == 2
        assert profile["total_injuries"] == 10
        assert profile["total_fires"] == 5
        assert profile["total_crashes"] == 15

    def test_multiple_manufacturers(self, db):
        """Test profiles for multiple manufacturers."""
        _seed_complaints(db, "FORD MOTOR COMPANY", "FORD", "F-150", 200,
                        deaths=5, injuries=30, fires=10, crashes=40)
        _seed_complaints(db, "TOYOTA MOTOR CORPORATION", "TOYOTA", "CAMRY", 150,
                        deaths=1, injuries=8, fires=3, crashes=12)
        _seed_recalls(db, "FORD MOTOR COMPANY", "FORD", "F-150", 5)
        _seed_recalls(db, "TOYOTA MOTOR CORPORATION", "TOYOTA", "CAMRY", 2)

        result = build_manufacturer_profiles(db)
        assert result["profiles_created"] >= 2

        ford = db.execute(
            "SELECT * FROM manufacturer_profiles WHERE manufacturer_name = 'FORD'"
        ).fetchone()
        toyota = db.execute(
            "SELECT * FROM manufacturer_profiles WHERE manufacturer_name = 'TOYOTA'"
        ).fetchone()
        assert ford is not None
        assert toyota is not None
        assert ford["total_complaints"] == 200
        assert toyota["total_complaints"] == 150

    def test_yearly_metrics_created(self, db):
        """Test that yearly metrics are created."""
        _seed_complaints(db, "FORD MOTOR COMPANY", "FORD", "F-150", 100,
                        deaths=2, injuries=5, year=2022)
        _seed_complaints(db, "FORD MOTOR COMPANY", "FORD", "F-150", 120,
                        deaths=3, injuries=8, year=2023)

        result = build_manufacturer_profiles(db)
        assert result["yearly_metrics_created"] > 0

        yearly = db.execute("""
            SELECT * FROM manufacturer_yearly_metrics
            WHERE manufacturer_name = 'FORD' ORDER BY year
        """).fetchall()
        assert len(yearly) >= 2

    def test_empty_database(self, db):
        """Test with no data."""
        result = build_manufacturer_profiles(db)
        assert result["profiles_created"] == 0
        assert result["yearly_metrics_created"] == 0

    def test_idempotent(self, db):
        """Test that running twice doesn't duplicate."""
        _seed_complaints(db, "TOYOTA MOTOR CORPORATION", "TOYOTA", "CAMRY", 100)
        build_manufacturer_profiles(db)
        result = build_manufacturer_profiles(db)
        count = db.execute("SELECT COUNT(*) FROM manufacturer_profiles").fetchone()[0]
        assert count == result["profiles_created"]


class TestRiskScoring:
    def test_risk_tiers_boundaries(self):
        """Test risk tier classification at boundaries."""
        assert _get_tier(0.0) == "LOW"
        assert _get_tier(0.29) == "LOW"
        assert _get_tier(0.30) == "MEDIUM"
        assert _get_tier(0.59) == "MEDIUM"
        assert _get_tier(0.60) == "HIGH"
        assert _get_tier(0.79) == "HIGH"
        assert _get_tier(0.80) == "CRITICAL"
        assert _get_tier(1.0) == "CRITICAL"

    def test_risk_weights_sum(self):
        """Risk weights should sum to 1.0."""
        assert abs(sum(RISK_WEIGHTS.values()) - 1.0) < 0.001

    def test_high_severity_manufacturer_gets_higher_score(self, db):
        """Manufacturer with more deaths/injuries should have higher risk score."""
        # Dangerous manufacturer
        _seed_complaints(db, "DANGER", "DANGER", "DEATHCAR", 100,
                        deaths=20, injuries=50, fires=30, crashes=60)
        # Safe manufacturer
        _seed_complaints(db, "SAFE", "SAFE", "SAFECAR", 100,
                        deaths=0, injuries=1, fires=0, crashes=2)
        # Need more manufacturers for percentile ranking
        _seed_complaints(db, "MID", "MID", "MIDCAR", 100,
                        deaths=5, injuries=10, fires=5, crashes=10)

        build_manufacturer_profiles(db)

        danger = db.execute(
            "SELECT risk_score FROM manufacturer_profiles WHERE manufacturer_name = 'DANGER'"
        ).fetchone()
        safe = db.execute(
            "SELECT risk_score FROM manufacturer_profiles WHERE manufacturer_name = 'SAFE'"
        ).fetchone()
        assert danger is not None
        assert safe is not None
        assert danger["risk_score"] > safe["risk_score"]

    def test_below_threshold_gets_low_tier(self, db):
        """Manufacturers below MIN_COMPLAINTS_FOR_SCORING get LOW tier."""
        _seed_complaints(db, "TINY", "TINY", "SMALL", 10, deaths=5)

        build_manufacturer_profiles(db)

        profile = db.execute(
            "SELECT * FROM manufacturer_profiles WHERE manufacturer_name = 'TINY'"
        ).fetchone()
        assert profile is not None
        assert profile["risk_tier"] == "LOW"
        assert profile["risk_score"] == 0.0

    def test_compute_risk_scores_no_scorable(self):
        """No profiles above threshold should not crash."""
        profiles = [
            {"manufacturer_name": "A", "total_complaints": 10,
             "death_rate": 0, "injury_rate": 0, "fire_rate": 0,
             "total_recalls": 0, "total_investigations": 0,
             "complaint_trend": "stable", "severity_trend": "stable",
             "risk_score": 0.0, "risk_tier": "LOW"},
        ]
        _compute_risk_scores(profiles)
        assert profiles[0]["risk_score"] == 0.0


class TestSeverityMetrics:
    def test_death_rate_calculation(self, db):
        """Test death rate per 10,000 complaints."""
        _seed_complaints(db, "TESTMFR", "TEST", "MODEL", 1000, deaths=5)

        build_manufacturer_profiles(db)

        profile = db.execute(
            "SELECT death_rate FROM manufacturer_profiles WHERE manufacturer_name = 'TESTMFR'"
        ).fetchone()
        assert profile is not None
        assert abs(profile["death_rate"] - 50.0) < 0.01  # 5/1000 * 10000 = 50

    def test_severity_index(self, db):
        """Test severity index formula: (deaths*10 + injuries*3 + fires*2 + crashes) / complaints."""
        _seed_complaints(db, "TESTMFR", "TEST", "MODEL", 100,
                        deaths=2, injuries=10, fires=5, crashes=20)

        build_manufacturer_profiles(db)

        profile = db.execute(
            "SELECT severity_index FROM manufacturer_profiles WHERE manufacturer_name = 'TESTMFR'"
        ).fetchone()
        # (2*10 + 10*3 + 5*2 + 20) / 100 = (20 + 30 + 10 + 20) / 100 = 0.8
        assert profile is not None
        assert abs(profile["severity_index"] - 0.8) < 0.01

    def test_zero_complaints_no_divide_error(self, db):
        """Manufacturer with only recalls and no complaints shouldn't cause division by zero."""
        _seed_recalls(db, "RECALLONLY", "RECALL", "MODEL", 5)

        build_manufacturer_profiles(db)

        profile = db.execute(
            "SELECT * FROM manufacturer_profiles WHERE manufacturer_name = 'RECALLONLY'"
        ).fetchone()
        # Should exist (from recalls) and have no rate errors
        if profile:
            assert profile["death_rate"] == 0.0 or profile["death_rate"] is None


class TestTrendAnalysis:
    def test_increasing_trend(self):
        """Values going up should be 'increasing'."""
        assert _compute_trend([100, 200, 400]) == "increasing"

    def test_decreasing_trend(self):
        """Values going down should be 'decreasing'."""
        assert _compute_trend([400, 200, 100]) == "decreasing"

    def test_stable_trend(self):
        """Roughly equal values should be 'stable'."""
        assert _compute_trend([100, 102, 98]) == "stable"

    def test_single_value(self):
        """Single value should be 'stable'."""
        assert _compute_trend([100]) == "stable"

    def test_empty_values(self):
        """Empty list should be 'stable'."""
        assert _compute_trend([]) == "stable"

    def test_all_zeros(self):
        """All zeros should be 'stable'."""
        assert _compute_trend([0, 0, 0]) == "stable"

    def test_two_values_increasing(self):
        """Two values increasing should work."""
        assert _compute_trend([100, 200]) == "increasing"


class TestProfileQuality:
    def test_full_profile_quality(self):
        profile = {
            "total_complaints": 100, "total_recalls": 5, "total_investigations": 3,
            "years_active_start": 2015, "years_active_end": 2025,
            "unique_models": 10, "severity_index": 0.5, "risk_score": 0.6,
        }
        score = _score_profile_quality(profile)
        assert score == 1.0

    def test_empty_profile_quality(self):
        profile = {
            "total_complaints": 0, "total_recalls": 0, "total_investigations": 0,
            "years_active_start": None, "years_active_end": None,
            "unique_models": 0, "severity_index": None, "risk_score": 0.0,
        }
        score = _score_profile_quality(profile)
        assert score == 0.0

    def test_partial_profile_quality(self):
        profile = {
            "total_complaints": 50, "total_recalls": 0, "total_investigations": 0,
            "years_active_start": 2020, "years_active_end": 2023,
            "unique_models": 3, "severity_index": 0.2, "risk_score": 0.0,
        }
        score = _score_profile_quality(profile)
        assert 0.0 < score < 1.0


class TestManufacturerNormalization:
    def test_aliases_merge_correctly(self, db):
        """Multiple manufacturer names for same company should merge."""
        _seed_complaints(db, "FORD MOTOR COMPANY", "FORD", "F-150", 50)
        _seed_complaints(db, "FORD", "FORD", "ESCAPE", 50)

        build_manufacturer_profiles(db)

        ford = db.execute(
            "SELECT * FROM manufacturer_profiles WHERE manufacturer_name = 'FORD'"
        ).fetchone()
        assert ford is not None
        assert ford["total_complaints"] == 100

    def test_tesla_inc_normalization(self, db):
        """Tesla, Inc. should normalize to TESLA."""
        _seed_complaints(db, "TESLA, INC.", "TESLA", "MODEL 3", 60)

        build_manufacturer_profiles(db)

        tesla = db.execute(
            "SELECT * FROM manufacturer_profiles WHERE manufacturer_name = 'TESLA'"
        ).fetchone()
        assert tesla is not None
        assert tesla["total_complaints"] == 60
