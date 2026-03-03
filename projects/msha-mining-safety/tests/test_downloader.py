"""Tests for the downloader/parser module."""

import os
import tempfile
import pytest
from src.scrapers.downloader import (
    _clean_val, _parse_int, _parse_float, parse_pipe_delimited,
    parse_mines, parse_accidents, parse_inspections, parse_violations,
    parse_assessed_violations, parse_penalties,
)


class TestCleanVal:
    def test_basic(self):
        assert _clean_val('"Hello"') == "Hello"

    def test_whitespace(self):
        assert _clean_val('  "Test"  ') == "Test"

    def test_empty(self):
        assert _clean_val("") == ""

    def test_no_quotes(self):
        assert _clean_val("Plain") == "Plain"

    def test_nested_quotes(self):
        assert _clean_val('"He said "hi""') == 'He said "hi'


class TestParseInt:
    def test_basic(self):
        assert _parse_int("42") == 42

    def test_quoted(self):
        assert _parse_int('"100"') == 100

    def test_empty(self):
        assert _parse_int("") is None

    def test_question_mark(self):
        assert _parse_int("?") is None

    def test_float_string(self):
        assert _parse_int("3.7") == 3

    def test_invalid(self):
        assert _parse_int("abc") is None


class TestParseFloat:
    def test_basic(self):
        assert _parse_float("3.14") == 3.14

    def test_integer(self):
        assert _parse_float("42") == 42.0

    def test_empty(self):
        assert _parse_float("") is None

    def test_question_mark(self):
        assert _parse_float("?") is None

    def test_invalid(self):
        assert _parse_float("xyz") is None


class TestParsePipeDelimited:
    def test_basic(self, tmp_path):
        content = 'COL_A|COL_B|COL_C\n"val1"|"val2"|"val3"\n"a"|"b"|"c"\n'
        path = tmp_path / "test.txt"
        path.write_text(content)
        records = parse_pipe_delimited(str(path))
        assert len(records) == 2
        assert records[0]["COL_A"] == "val1"
        assert records[1]["COL_C"] == "c"

    def test_empty_values(self, tmp_path):
        content = 'A|B|C\n"1"||"3"\n'
        path = tmp_path / "test.txt"
        path.write_text(content)
        records = parse_pipe_delimited(str(path))
        assert records[0]["B"] == ""

    def test_empty_file(self, tmp_path):
        path = tmp_path / "empty.txt"
        path.write_text("A|B|C\n")
        records = parse_pipe_delimited(str(path))
        assert len(records) == 0


class TestParseMines:
    def test_basic(self, tmp_path):
        header = "MINE_ID|CURRENT_MINE_NAME|COAL_METAL_IND|CURRENT_MINE_TYPE|CURRENT_MINE_STATUS|CURRENT_STATUS_DT|CURRENT_CONTROLLER_ID|CURRENT_CONTROLLER_NAME|CURRENT_OPERATOR_ID|CURRENT_OPERATOR_NAME|STATE|BOM_STATE_CD|FIPS_CNTY_CD|FIPS_CNTY_NM|CONG_DIST_CD|COMPANY_TYPE|CURRENT_CONTROLLER_BEGIN_DT|DISTRICT|OFFICE_CD|OFFICE_NAME|ASSESS_CTRL_NO|PRIMARY_SIC_CD|PRIMARY_SIC|PRIMARY_SIC_CD_1|PRIMARY_SIC_CD_SFX|SECONDARY_SIC_CD|SECONDARY_SIC|SECONDARY_SIC_CD_1|SECONDARY_SIC_CD_SFX|PRIMARY_CANVASS_CD|PRIMARY_CANVASS|SECONDARY_CANVASS_CD|SECONDARY_CANVASS|CURRENT_103I|CURRENT_103I_DT|PORTABLE_OPERATION|PORTABLE_FIPS_ST_CD|DAYS_PER_WEEK|HOURS_PER_SHIFT|PROD_SHIFTS_PER_DAY|MAINT_SHIFTS_PER_DAY|NO_EMPLOYEES|PART48_TRAINING|LONGITUDE|LATITUDE|AVG_MINE_HEIGHT|MINE_GAS_CATEGORY_CD|METHANE_LIBERATION|NO_PRODUCING_PITS|NO_NONPRODUCING_PITS|NO_TAILING_PONDS|PILLAR_RECOVERY_USED|HIGHWALL_MINER_USED|MULTIPLE_PITS|MINERS_REP_IND|SAFETY_COMMITTEE_IND|MILES_FROM_OFFICE|DIRECTIONS_TO_MINE|NEAREST_TOWN"
        row = '"0100003"|"Test Mine"|"M"|"Surface"|"Active"|"01/22/1979"|"C001"|"TestCo"|"O001"|"TestOp"|"AL"|"01"|"117"|"Shelby"|"06"|"Corporation"|"07/01/1989"|"M3"|"M3661"|"Birmingham"|"12345"|"327400"|"Lime"|"3274"|"00"|""|""|""|""|"1"|"Coal"|""|""|""|""|"N"|""|5|8|1|0|50|"N"|"-86.5"|"33.2"|0|""|0|0|0|0|"N"|"N"|"N"|"N"|"N"|10|"Go north"|"Testville"'
        path = tmp_path / "Mines.txt"
        path.write_text(f"{header}\n{row}\n")
        records = parse_mines(str(path))
        assert len(records) == 1
        assert records[0]["mine_id"] == "0100003"
        assert records[0]["mine_name"] == "Test Mine"
        assert records[0]["state"] == "AL"
        assert records[0]["no_employees"] == 50


class TestParseAccidents:
    def test_basic(self, tmp_path):
        header = "MINE_ID|CONTROLLER_ID|CONTROLLER_NAME|OPERATOR_ID|OPERATOR_NAME|CONTRACTOR_ID|DOCUMENT_NO|SUBUNIT_CD|SUBUNIT|ACCIDENT_DT|CAL_YR|CAL_QTR|FISCAL_YR|FISCAL_QTR|ACCIDENT_TIME|DEGREE_INJURY_CD|DEGREE_INJURY|FIPS_STATE_CD|UG_LOCATION_CD|UG_LOCATION|UG_MINING_METHOD_CD|UG_MINING_METHOD|MINING_EQUIP_CD|MINING_EQUIP|EQUIP_MFR_CD|EQUIP_MFR_NAME|EQUIP_MODEL_NO|SHIFT_BEGIN_TIME|CLASSIFICATION_CD|CLASSIFICATION|ACCIDENT_TYPE_CD|ACCIDENT_TYPE|NO_INJURIES|TOT_EXPER|MINE_EXPER|JOB_EXPER|OCCUPATION_CD|OCCUPATION|ACTIVITY_CD|ACTIVITY|INJURY_SOURCE_CD|INJURY_SOURCE|NATURE_INJURY_CD|NATURE_INJURY|INJ_BODY_PART_CD|INJ_BODY_PART|SCHEDULE_CHARGE|DAYS_RESTRICT|DAYS_LOST|TRANS_TERM|RETURN_TO_WORK_DT|IMMED_NOTIFY_CD|IMMED_NOTIFY|INVEST_BEGIN_DT|NARRATIVE|CLOSED_DOC_NO|COAL_METAL_IND"
        row = '"0100003"|"C001"|"TestCo"|"O001"|"TestOp"||"220132310045"|"03"|"STRIP"|"08/12/2013"|2013|3|2013|4|"1815"|"01"|"FATALITY"|"01"|"?"|"NO VALUE"|"?"|"NO VALUE"|"67"|"Truck"|"12"|"CAT"|"Model1"|"0800"|"01"|"Powered haulage"|"01"|"Fall"|1|10.5|5.0|3.0|"123"|"Miner"|"01"|"Mining"|"01"|"Rock"|"01"|"Crushing"|"01"|"Head"|6000|0|0|"N"|""|"01"|"Death"|""|"Test narrative"|""|"M"'
        path = tmp_path / "Accidents.txt"
        path.write_text(f"{header}\n{row}\n")
        records = parse_accidents(str(path))
        assert len(records) == 1
        assert records[0]["document_no"] == "220132310045"
        assert records[0]["degree_injury_cd"] == "01"
        assert records[0]["degree_injury"] == "FATALITY"
        assert records[0]["cal_yr"] == 2013


class TestParseInspections:
    def test_basic(self, tmp_path):
        header = "EVENT_NO|MINE_ID|INSPECTION_BEGIN_DT|INSPECTION_END_DT|CONTROLLER_ID|CONTROLLER_NAME|OPERATOR_ID|OPERATOR_NAME|CAL_YR|CAL_QTR|FISCAL_YR|FISCAL_QTR|INSPECT_OFFICE_CD|ACTIVITY_CODE|ACTIVITY|ACTIVE_SECTIONS|IDLE_SECTIONS|SHAFT_SLOPE_SINK|IMPOUND_CONSTR|BLDG_CONSTR_SITES|DRAGLINES|UNCLASSIFIED_CONSTR|CO_RECORDS|SURF_UG_MINE|SURF_FACILITY_MINE|REFUSE_PILES|EXPLOSIVE_STORAGE|OUTBY_AREAS|MAJOR_CONSTR|SHAFTS_SLOPES|COAL_METAL_IND"
        row = '"EV001"|"M001"|"01/01/2020"|"01/05/2020"|"C001"|"TestCo"|"O001"|"TestOp"|2020|1|2020|2|"DIST1"|"A01"|"Regular Inspection"|1|0|"N"|"N"|"N"|"N"|"N"|"N"|"N"|"N"|"N"|"N"|"N"|"N"|"N"|"C"'
        path = tmp_path / "Inspections.txt"
        path.write_text(f"{header}\n{row}\n")
        records = parse_inspections(str(path))
        assert len(records) == 1
        assert records[0]["event_no"] == "EV001"
        assert records[0]["cal_yr"] == 2020


class TestParseViolations:
    def test_basic(self, tmp_path):
        header = "EVENT_NO|INSPECTION_BEGIN_DT|INSPECTION_END_DT|VIOLATION_NO|CONTROLLER_ID|CONTROLLER_NAME|VIOLATOR_ID|VIOLATOR_NAME|VIOLATOR_TYPE_CD|MINE_ID|MINE_NAME|MINE_TYPE|COAL_METAL_IND|CONTRACTOR_ID|VIOLATION_ISSUE_DT|VIOLATION_OCCUR_DT|CAL_YR|CAL_QTR|FISCAL_YR|FISCAL_QTR|VIOLATION_ISSUE_TIME|SIG_SUB|SECTION_OF_ACT|SECTION_OF_ACT_DESC|PART_SECTION|PART_SECTION_DESC|PROPOSED_PENALTY|AMOUNT_PAID"
        row = '"EV001"|"01/01/2020"|"01/05/2020"|"V001"|"C001"|"TestCo"|"O001"|"TestOp"|"Operator"|"M001"|"Test Mine"|"Surface"|"M"||"01/02/2020"|"01/02/2020"|2020|1|2020|2|"0900"|"Y"|"104(a)"|"Citation"|"56.14132(a)"|"Guards"|1500.00|1200.00'
        path = tmp_path / "Violations.txt"
        path.write_text(f"{header}\n{row}\n")
        records = parse_violations(str(path))
        assert len(records) == 1
        assert records[0]["violation_no"] == "V001"
        assert records[0]["sig_sub"] == "Y"
        assert records[0]["proposed_penalty"] == 1500.0


class TestParseAssessed:
    def test_basic(self, tmp_path):
        header = "VIOLATION_NO|ASSESSED_ID|MINE_ID|CONTROLLER_ID|CONTROLLER_NAME|OPERATOR_ID|OPERATOR_NAME|CAL_YR|VIOLATION_ISSUE_DT|SECTION_OF_ACT|PART_SECTION|PROPOSED_PENALTY_AMT|PAID_PROPOSED_PENALTY_AMT|PENALTY_POINTS|SIG_SUB|LIKELY|INJURY_ILLNESS|NEGLIGENCE|GRAVITY"
        row = '"V001"|"A001"|"M001"|"C001"|"TestCo"|"O001"|"TestOp"|2020|"01/02/2020"|"104(a)"|"56.14132(a)"|2000.00|1800.00|45|"Y"|"Reasonably Likely"|"Lost Workdays"|"Moderate"|"Significant"'
        path = tmp_path / "AssessedViolations.txt"
        path.write_text(f"{header}\n{row}\n")
        records = parse_assessed_violations(str(path))
        assert len(records) == 1
        assert records[0]["proposed_penalty_amt"] == 2000.0
        assert records[0]["sig_sub"] == "Y"
