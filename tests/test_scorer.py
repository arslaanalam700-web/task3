import pytest
from unittest.mock import patch, MagicMock
from src.models import (
    LeadInput,
    LeadScoreOutput,
    LeadCategory,
    ConfidenceLevel,
    OutreachPriority,
    compute_outreach_priority,
)
from src.scorer import mock_score_lead, score_single_lead, batch_score_leads


def test_api_failure_marked_unscored_not_cold():
    """Verify API failures are tagged as 'Unscored' with score=None rather than 'Cold'."""
    lead = LeadInput(company_name="Faulty Lead", description="Valid description with enough characters to analyze.")

    with patch("google.genai.Client") as mock_client:
        mock_instance = MagicMock()
        mock_instance.models.generate_content.side_effect = Exception("Simulated connection timeout")
        mock_client.return_value = mock_instance

        result = score_single_lead(lead, api_key="test_key", use_mock=False)
        assert result.status == "ERROR"
        assert result.category == LeadCategory.UNSCORED.value
        assert result.score is None
        assert result.confidence == "N/A"
        assert "Simulated connection timeout" in result.error_message


def test_needs_research_category():
    """Verify leads with sparse or trivial descriptions are classified as Needs Research."""
    leads = [
        LeadInput(company_name="TrivialCo", description="N/A"),
        LeadInput(company_name="ShortCo", description="Stealth AI"),
        LeadInput(company_name="BlankCo", description=""),
    ]
    for lead in leads:
        result = mock_score_lead(lead)
        assert result.category == LeadCategory.NEEDS_RESEARCH.value
        assert result.confidence == ConfidenceLevel.LOW.value
        assert 0 <= result.score <= 34
        assert "insufficient" in result.explanation.lower()
        assert result.status == "SUCCESS"


def test_agency_not_automatically_cold():
    """Verify agencies and BPO companies with operational needs are NOT classified as Cold."""
    agency_lead = LeadInput(
        company_name="CreativePulse Media",
        website="https://creativepulse.agency",
        industry="Marketing & Advertising",
        description="Full-service boutique digital marketing agency managing custom client apps and needing dedicated dev execution partner."
    )
    result = mock_score_lead(agency_lead, profile="blackfold")
    assert result.category in [LeadCategory.HOT.value, LeadCategory.WARM.value]
    assert result.status == "SUCCESS"


def test_keyword_boundary_matching():
    """Verify word boundaries prevent false triggers (e.g. 'upscale' should not trigger 'scale')."""
    non_hot_lead = LeadInput(
        company_name="Bespoke Antiques",
        description="An upscale boutique showcasing 19th-century handcrafted mahogany furniture to private collectors."
    )
    result = mock_score_lead(non_hot_lead, profile="general")
    assert result.category != LeadCategory.HOT.value


def test_evidence_extraction():
    """Verify that direct evidence quotes are extracted from description."""
    lead = LeadInput(
        company_name="NovaTech Cloud",
        description="High-growth B2B SaaS startup that recently closed a $6M Series A. Active customer base has tripled in 4 months."
    )
    result = mock_score_lead(lead)
    assert result.category == LeadCategory.HOT.value
    assert result.evidence != ""
    assert result.evidence_validated is True


def test_score_category_alignment_validator():
    """Verify Pydantic model validator strictly enforces score and category consistency."""
    # Hot should be clamped to [70, 100]
    out_hot = LeadScoreOutput(
        category=LeadCategory.HOT,
        score=50,
        confidence=ConfidenceLevel.HIGH,
        evidence="Tripled orders",
        explanation="Scaling fast."
    )
    assert out_hot.score == 70

    # Warm should be clamped to [35, 69]
    out_warm = LeadScoreOutput(
        category=LeadCategory.WARM,
        score=85,
        confidence=ConfidenceLevel.MEDIUM,
        evidence="Clinic practice",
        explanation="Standard operations."
    )
    assert out_warm.score == 69

    # Cold should be clamped to [0, 34]
    out_cold = LeadScoreOutput(
        category=LeadCategory.COLD,
        score=60,
        confidence=ConfidenceLevel.HIGH,
        evidence="100% in-house",
        explanation="In-house enterprise."
    )
    assert out_cold.score == 34

    # Needs Research should be clamped to [0, 34] and enforce Low confidence
    out_research = LeadScoreOutput(
        category=LeadCategory.NEEDS_RESEARCH,
        score=90,
        confidence=ConfidenceLevel.HIGH,
        evidence="N/A",
        explanation="Insufficient info."
    )
    assert out_research.score == 20
    assert out_research.confidence == ConfidenceLevel.LOW
    assert out_research.is_insufficient_data is True


def test_batch_deduplication_avoids_repeated_evaluations():
    """Verify identical duplicate leads reuse results without calling scoring repeatedly."""
    leads = [
        LeadInput(company_name="Alpha Tech", website="https://alphatech.io", description="Fast-growing SaaS startup building platform", domain="alphatech.io"),
        LeadInput(company_name="Alpha Tech Branch", website="https://www.alphatech.io/contact", description="Fast-growing SaaS startup building platform", domain="alphatech.io"),
        LeadInput(company_name="Beta Med", website="https://betamed.com", description="Medical clinic practice", domain="betamed.com"),
    ]

    progress_messages = []
    def track_progress(current, total, msg):
        progress_messages.append(msg)

    results = batch_score_leads(
        leads=leads,
        api_key="",
        use_mock=True,
        progress_callback=track_progress,
    )

    assert len(results) == 3
    # Second lead was recognized as duplicate and cached because description matched
    assert results[1].is_duplicate is True
    assert "[Reused from identical lead" in results[1].explanation
    assert any("Cached" in m for m in progress_messages)


def test_shared_domain_distinct_descriptions_not_cached():
    """Verify that leads sharing a domain but having different descriptions are evaluated independently."""
    leads = [
        LeadInput(
            company_name="NovaTech SaaS",
            website="https://novatechcloud.io",
            domain="novatechcloud.io",
            description="Fast-growing SaaS startup building platform and engineering team is completely overwhelmed by backlog."
        ),
        LeadInput(
            company_name="NovaTech Cafe",
            website="https://novatechcloud.io/cafe",
            domain="novatechcloud.io",
            description="An artisanal sourdough bakery and neighborhood espresso bar operated by two founding bakers."
        ),
    ]

    results = batch_score_leads(leads=leads, api_key="", use_mock=True, profile="blackfold")

    # They should NOT share evaluations! Lead 0 is Hot, Lead 1 is Cold!
    assert results[0].category == LeadCategory.HOT.value
    assert results[1].category == LeadCategory.COLD.value
    assert "[Reused" not in results[1].explanation


def test_blackfold_profile_scoring():
    """Verify Blackfold profile identifies development and workflow automation needs."""
    dev_lead = LeadInput(
        company_name="FinEdge",
        description="Scaling fintech platform with heavy manual spreadsheets and acute bottlenecks with driver proof processing, needing custom API integration."
    )
    result = mock_score_lead(dev_lead, profile="blackfold")
    assert result.category == LeadCategory.HOT.value
    assert result.score >= 70
    assert "Automation" in result.potential_services or "Custom Software" in result.potential_services

    bakery_lead = LeadInput(
        company_name="Artisanal Bakes",
        description="An artisanal sourdough bakery and neighborhood espresso bar serving fresh pastries."
    )
    result_cold = mock_score_lead(bakery_lead, profile="blackfold")
    assert result_cold.category == LeadCategory.COLD.value
    assert result_cold.score <= 34


def test_outreach_priority_calculation():
    """Verify outreach priorities map cleanly from categories and scores."""
    assert compute_outreach_priority("Hot", 88) == OutreachPriority.P1_URGENT.value
    assert compute_outreach_priority("Hot", 72) == OutreachPriority.P1_HIGH.value
    assert compute_outreach_priority("Warm", 55) == OutreachPriority.P2_MEDIUM.value
    assert compute_outreach_priority("Warm", 40) == OutreachPriority.P3_LOW.value
    assert compute_outreach_priority("Cold", 20) == OutreachPriority.P4_COLD.value
    assert compute_outreach_priority("Needs Research", 20) == OutreachPriority.NEEDS_RESEARCH.value
    assert compute_outreach_priority("Unscored", None) == OutreachPriority.UNSCORED.value
