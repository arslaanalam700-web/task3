import io
import pytest
from src.validator import validate_and_parse_csv


def test_valid_csv_parsing():
    csv_content = """company_name,website,industry,description
Acme Corp,https://acme.com,Manufacturing,Growing fast and needs IT support.
Beta LLC,https://beta.com,Healthcare,Dental clinic seeking billing help.
"""
    is_valid, err, leads, df = validate_and_parse_csv(csv_content)
    assert is_valid is True
    assert err is None
    assert len(leads) == 2
    assert leads[0].company_name == "Acme Corp"
    assert leads[0].industry == "Manufacturing"
    assert leads[1].company_name == "Beta LLC"


def test_column_synonym_mapping():
    csv_content = """company,url,sector,about
Alpha Ltd,https://alpha.io,Tech,Scaling SaaS startup with support backlog.
"""
    is_valid, err, leads, df = validate_and_parse_csv(csv_content)
    assert is_valid is True
    assert len(leads) == 1
    assert leads[0].company_name == "Alpha Ltd"
    assert leads[0].website == "https://alpha.io"
    assert leads[0].industry == "Tech"
    assert "Scaling SaaS" in leads[0].description


def test_missing_required_column():
    csv_content = """company_name,website,industry
Missing Description,https://example.com,Retail
"""
    is_valid, err, leads, df = validate_and_parse_csv(csv_content)
    assert is_valid is False
    assert "Missing required column" in err
    assert "description" in err.lower()
    assert leads is None


def test_empty_content():
    # Test empty string
    is_valid, err, leads, df = validate_and_parse_csv("")
    assert is_valid is False
    assert "empty" in err.lower()

    # Test empty bytes
    is_valid, err, leads, df = validate_and_parse_csv(b"")
    assert is_valid is False
    assert "empty" in err.lower()

    # Test None
    is_valid, err, leads, df = validate_and_parse_csv(None)
    assert is_valid is False


def test_blank_company_names():
    csv_content = """company_name,website,industry,description
,https://emptyname.com,Finance,Valid description but missing company name.
"""
    is_valid, err, leads, df = validate_and_parse_csv(csv_content)
    assert is_valid is False
    assert "blank company names" in err


def test_batch_limit():
    rows = ["company_name,description"]
    for i in range(10):
        rows.append(f"Company {i},Description for company {i}")
    csv_content = "\n".join(rows)

    is_valid, err, leads, df = validate_and_parse_csv(csv_content, max_rows=5)
    assert is_valid is False
    assert "exceeds maximum batch limit" in err
