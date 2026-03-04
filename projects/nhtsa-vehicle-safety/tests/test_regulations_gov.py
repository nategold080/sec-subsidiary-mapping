"""Tests for Regulations.gov scraper document classification and parsing."""

import sqlite3

import pytest

from src.scrapers.regulations_gov import (
    classify_document_type,
    extract_determination,
    _parse_document,
    _parse_docket_results,
)
from src.storage.database import init_db


class TestClassifyDocumentType:
    def test_closing_notice(self):
        assert classify_document_type("Closing Resume for Investigation PE12345") == "closing_notice"
        assert classify_document_type("Investigation Closing Notice") == "closing_notice"

    def test_opening_notice(self):
        assert classify_document_type("Opening Notice for Investigation PE12345") == "opening_notice"
        assert classify_document_type("NHTSA Initiates Investigation") == "opening_notice"

    def test_pe_report(self):
        assert classify_document_type("Preliminary Evaluation Report") == "pe_report"
        assert classify_document_type("PE Report for Braking Defect") == "pe_report"

    def test_ea_report(self):
        assert classify_document_type("Engineering Analysis Report") == "ea_report"
        assert classify_document_type("EA Report - Final") == "ea_report"

    def test_recall_request(self):
        assert classify_document_type("Recall Query Letter") == "recall_request"
        assert classify_document_type("Recall Request to Manufacturer") == "recall_request"

    def test_manufacturer_response(self):
        assert classify_document_type("Manufacturer Response to NHTSA") == "manufacturer_response"
        assert classify_document_type("Manufacturer Communication from Ford") == "manufacturer_response"

    def test_public_comment(self):
        assert classify_document_type("Public Comment on Investigation") == "public_comment"

    def test_defect_petition(self):
        assert classify_document_type("Defect Petition DP12345") == "defect_petition"

    def test_tsb(self):
        assert classify_document_type("Technical Service Bulletin") == "tsb"

    def test_other(self):
        assert classify_document_type("Miscellaneous Document") == "other"
        assert classify_document_type("") == "other"


class TestExtractDetermination:
    def test_defect_found(self):
        assert extract_determination("Investigation Closed - Defect Found") == "defect_found"
        assert extract_determination("Defect Exists in Subject Vehicles") == "defect_found"

    def test_no_defect(self):
        assert extract_determination("No Defect Found After Analysis") == "no_defect"
        assert extract_determination("Defect Not Found") == "no_defect"

    def test_insufficient_evidence(self):
        assert extract_determination("Closed - Insufficient Evidence") == "insufficient_evidence"

    def test_recall_requested(self):
        assert extract_determination("Recall Conducted for Subject Vehicles") == "recall_requested"
        assert extract_determination("Manufacturer Recall Initiated") == "recall_requested"

    def test_upgraded(self):
        assert extract_determination("PE Upgrade to EA for Further Analysis") == "upgraded_to_ea"

    def test_none(self):
        assert extract_determination("Standard Investigation Document") is None
        assert extract_determination("") is None


class TestParseDocument:
    def test_standard_document(self):
        raw = {
            "id": "NHTSA-2024-0001-0001",
            "attributes": {
                "docketId": "NHTSA-2024-0001",
                "title": "Closing Resume for Investigation PE24001",
                "postedDate": "2024-06-15",
                "authorName": "NHTSA",
                "summary": "Investigation closed after defect found.",
                "fileUrl": "https://api.regulations.gov/file.pdf",
            }
        }
        doc = _parse_document(raw)
        assert doc is not None
        assert doc["document_id"] == "NHTSA-2024-0001-0001"
        assert doc["document_type"] == "closing_notice"
        assert doc["posted_date"] == "2024-06-15"

    def test_no_id_returns_none(self):
        raw = {"id": "", "attributes": {"title": "Test"}}
        doc = _parse_document(raw)
        assert doc is None

    def test_manufacturer_response(self):
        raw = {
            "id": "NHTSA-2024-0002-0005",
            "attributes": {
                "docketId": "NHTSA-2024-0002",
                "title": "Ford Motor Company Manufacturer Response",
                "postedDate": "2024-03-01",
                "authorName": "Ford Motor Company",
            }
        }
        doc = _parse_document(raw)
        assert doc["document_type"] == "manufacturer_response"
        assert doc["author"] == "Ford Motor Company"


class TestParseDocketResults:
    def test_single_result(self):
        results = [{
            "attributes": {
                "docketId": "NHTSA-2024-0001",
                "title": "Investigation PE24001 - Ford F-150 Brakes",
                "docketType": "Nonrulemaking",
                "documentCount": 15,
                "lastModifiedDate": "2024-06-30",
            }
        }]
        docket = _parse_docket_results(results, "PE24001")
        assert docket is not None
        assert docket["docket_id"] == "NHTSA-2024-0001"
        assert docket["investigation_number"] == "PE24001"
        assert docket["document_count"] == 15

    def test_empty_results(self):
        assert _parse_docket_results([], "PE99999") is None

    def test_no_docket_id(self):
        results = [{"attributes": {"docketId": "", "title": "Test"}}]
        assert _parse_docket_results(results, "PE99999") is None


class TestDatabaseIntegration:
    def test_docket_tables_created(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        init_db(conn)

        # Check tables exist
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = {t["name"] for t in tables}
        assert "investigation_dockets" in table_names
        assert "investigation_documents" in table_names

    def test_insert_docket(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        init_db(conn)

        conn.execute("""
            INSERT INTO investigation_dockets (
                docket_id, investigation_number, docket_type, title,
                document_count, quality_score
            ) VALUES ('NHTSA-2024-0001', 'PE24001', 'Nonrulemaking',
                     'Test Investigation', 10, 0.8)
        """)
        conn.commit()

        row = conn.execute(
            "SELECT * FROM investigation_dockets WHERE docket_id = 'NHTSA-2024-0001'"
        ).fetchone()
        assert row is not None
        assert row["investigation_number"] == "PE24001"

    def test_insert_document(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        init_db(conn)

        conn.execute("""
            INSERT INTO investigation_documents (
                document_id, docket_id, investigation_number,
                document_type, title, determination, quality_score
            ) VALUES ('DOC-001', 'NHTSA-2024-0001', 'PE24001',
                     'closing_notice', 'Investigation Closed - Defect Found',
                     'defect_found', 0.9)
        """)
        conn.commit()

        row = conn.execute(
            "SELECT * FROM investigation_documents WHERE document_id = 'DOC-001'"
        ).fetchone()
        assert row is not None
        assert row["determination"] == "defect_found"
        assert row["document_type"] == "closing_notice"
