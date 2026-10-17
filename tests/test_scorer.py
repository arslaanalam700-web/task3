import pytest
from unittest.mock import patch, MagicMock
from src.models import LeadInput, LeadScoreOutput, LeadCategory, ConfidenceLevel
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
        description="Full-service boutique digital marketing agency providing SEO and paid ads for emerging brands. Team is focused entirely on client campaigns and needs outsourced monthly bookkeeping and invoicing support."
    )
    result = mock_score_lead(agency_lead)
    assert result.category == LeadCategory.WARM.value
    assert 35 <= result.score <= 69
    assert result.confidence == ConfidenceLevel.MEDIUM.value
    assert "bookkeeping" in result.potential_services.lower()


def test_keyword_boundary_matching():
    """Verify word boundaries prevent false triggers (e.g. 'upscale' should not trigger 'scale')."""
    non_hot_lead = LeadInput(
        company_name="Bespoke Antiques",
        description="An upscale boutique showcasing 19th-century handcrafted mahogany furniture to private collectors."
    )
    result = mock_score_lead(non_hot_lead)
    # Should not be Hot because 'upscale' is not 'scale' or 'scaling'
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
    assert "Series A" in result.evidence or "tripled" in result.evidence


def test_score_category_alignment_validator():
    """Verify Pydantic model validator strictly enforces score and category consistency."""
    # Hot should be clamped to [70, 100]
    out_hot = LeadScoreOutput(
        category=LeadCategory.HOT,
        score=50,  # Below 70
        confidence=ConfidenceLevel.HIGH,
        evidence="Tripled orders",
        explanation="Scaling fast."
    )
    assert out_hot.score == 70

    # Warm should be clamped to [35, 69]
    out_warm = LeadScoreOutput(
        category=LeadCategory.WARM,
        score=85,  # Above 69
        confidence=ConfidenceLevel.MEDIUM,
        evidence="Clinic practice",
        explanation="Standard operations."
    )
    assert out_warm.score == 69

    # Cold should be clamped to [0, 34]
    out_cold = LeadScoreOutput(
        category=LeadCategory.COLD,
        score=60,  # Above 34
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


def test_batch_scoring_isolation():
    leads = [
        LeadInput(company_name="Co 1", description="Fast-growing SaaS startup tripling active accounts"),
        LeadInput(company_name="Co 2", description="Regional clinic dental practice"),
    ]

    progress_calls = []

    def progress_tracker(current, total, name):
        progress_calls.append((current, total, name))

    results = batch_score_leads(
        leads=leads,
        api_key="",
        use_mock=True,
        progress_callback=progress_tracker,
    )

    assert len(results) == 2
    assert len(progress_calls) == 2
    assert progress_calls[0] == (1, 2, "Co 1")
    assert progress_calls[1] == (2, 2, "Co 2")
    assert all(r.status == "SUCCESS" for r in results)
