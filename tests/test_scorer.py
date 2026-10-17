import pytest
from unittest.mock import patch, MagicMock
from src.models import LeadInput, LeadScoreOutput, LeadCategory, ConfidenceLevel
from src.scorer import mock_score_lead, score_single_lead, batch_score_leads


def test_mock_scoring_hot_lead():
    lead = LeadInput(
        company_name="HyperScale Systems",
        website="https://hyperscale.io",
        industry="SaaS",
        description="Fast-growing startup that raised a Series A and tripled revenue; core team is overwhelmed by customer support tickets and onboarding backlog."
    )
    result = mock_score_lead(lead)
    assert result.category == LeadCategory.HOT.value
    assert result.score >= 70
    assert result.confidence == ConfidenceLevel.HIGH.value
    assert "Customer Support" in result.potential_services
    assert result.status == "SUCCESS"


def test_mock_scoring_warm_lead():
    lead = LeadInput(
        company_name="Oak Valley Medical Practice",
        website="https://oakvalleymed.com",
        industry="Healthcare",
        description="Independent family medical clinic with two physician locations managing daily patient schedules and regular billing."
    )
    result = mock_score_lead(lead)
    assert result.category == LeadCategory.WARM.value
    assert 35 <= result.score <= 69
    assert result.confidence == ConfidenceLevel.MEDIUM.value
    assert result.status == "SUCCESS"


def test_mock_scoring_competitor_cold():
    lead = LeadInput(
        company_name="Apex BPO Partners",
        website="https://apexbpo.com",
        industry="Business Services",
        description="Global outsourcing provider providing contact center services and virtual assistant staffing for international clients."
    )
    result = mock_score_lead(lead)
    assert result.category == LeadCategory.COLD.value
    assert result.score <= 30
    assert "service provider" in result.explanation.lower()
    assert result.status == "SUCCESS"


def test_mock_scoring_insufficient_data():
    lead = LeadInput(
        company_name="Mystery Venture",
        website="https://mystery.xyz",
        industry="Tech",
        description="N/A"
    )
    result = mock_score_lead(lead)
    assert result.category == LeadCategory.COLD.value
    assert result.confidence == ConfidenceLevel.LOW.value
    assert "insufficient" in result.explanation.lower()
    assert result.status == "SUCCESS"


def test_lead_score_output_pydantic_validation():
    valid_data = {
        "category": "Hot",
        "score": 85,
        "confidence": "High",
        "explanation": "Explicit demand for IT services.",
        "potential_services": ["IT Support", "Bookkeeping"],
        "is_insufficient_data": False
    }
    model = LeadScoreOutput.model_validate(valid_data)
    assert model.category == LeadCategory.HOT
    assert model.score == 85

    # Invalid score (> 100) should raise ValidationError
    with pytest.raises(Exception):
        LeadScoreOutput.model_validate({**valid_data, "score": 150})


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


def test_individual_failure_resilience():
    lead = LeadInput(company_name="Faulty Lead", description="Valid description")

    # Mock genai.Client to raise an exception
    with patch("google.genai.Client") as mock_client:
        mock_instance = MagicMock()
        mock_instance.models.generate_content.side_effect = Exception("Simulated connection timeout")
        mock_client.return_value = mock_instance

        result = score_single_lead(lead, api_key="test_key", use_mock=False)
        assert result.status == "ERROR"
        assert "Simulated connection timeout" in result.error_message
        assert result.category == LeadCategory.COLD.value
