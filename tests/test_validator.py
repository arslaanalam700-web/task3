import io
import pytest
from src.validator import validate_and_parse_csv, extract_domain, validate_evidence


def test_domain_extraction():
    assert extract_domain("https://www.novatechcloud.io/pricing") == "novatechcloud.io"
    assert extract_domain("http://greenleafdental.com/contact/") == "greenleafdental.com"
    assert extract_domain("www.apexlogisticsfreight.com") == "apexlogisticsfreight.com"
    assert extract_domain("https://sub.domain.co.uk:8080/path?q=1") == "sub.domain.co.uk"
    assert extract_domain("") == ""
    assert extract_domain("   ") == ""


def test_validate_evidence_supported():
    desc = "Active customer base has tripled in 4 months, and the 8-person engineering team is completely overwhelmed."
    # Exact quote
    is_valid, ev = validate_evidence("Active customer base has tripled in 4 months", desc)
    assert is_valid is True
    assert "tripled" in ev

    # Slightly trimmed quote
    is_valid, ev = validate_evidence("engineering team is completely overwhelmed", desc)
    assert is_valid is True


def test_validate_evidence_hallucinated():
    desc = "Small local dental clinic with 4 chairs and friendly hygienists."
    # Fabricated claim not in text
    is_valid, ev = validate_evidence("Company raised $50M Series B and employs 300 software engineers", desc)
    assert is_valid is False
    assert "[Unverified Claim]" in ev


def test_validate_evidence_placeholder():
    desc = ""
    is_valid, ev = validate_evidence("No specific operational evidence available in provided description.", desc)
    assert is_valid is True


def test_duplicate_domain_detection():
    csv_content = """company_name,website,industry,description
Acme Main,https://acme.com,Manufacturing,Growing fast and needs IT support.
Acme Branch,https://www.acme.com/branch,Manufacturing,Branch office for Acme.
Beta LLC,https://beta.io,Healthcare,Dental clinic seeking billing help.
Beta Second,,Healthcare,Another branch with same company name.
Beta Second,,Healthcare,Duplicate company name with no website.
"""
    is_valid, err, leads, df = validate_and_parse_csv(csv_content)
    assert is_valid is True
    assert len(leads) == 5
    # First Acme is original
    assert leads[0].is_duplicate is False
    # Second Acme shares domain 'acme.com'
    assert leads[1].is_duplicate is True
    # Beta LLC is unique
    assert leads[2].is_duplicate is False
    # Beta Second first occurrence is original
    assert leads[3].is_duplicate is False
    # Beta Second second occurrence shares company name
    assert leads[4].is_duplicate is True
    # DataFrame also includes is_duplicate flag
    assert df["is_duplicate"].sum() == 2


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
