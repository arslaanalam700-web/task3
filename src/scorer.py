import json
import logging
import time
from typing import List, Callable, Optional
from google import genai
from google.genai import types
from google.genai.errors import APIError

from .models import LeadInput, LeadScoreOutput, ScoredLead, LeadCategory, ConfidenceLevel
from .prompt import SYSTEM_INSTRUCTION, build_lead_prompt

logger = logging.getLogger(__name__)


def mock_score_lead(lead: LeadInput) -> ScoredLead:
    """
    Simulated deterministic scoring logic for testing or offline demonstration.
    Evaluates based strictly on keyword patterns and text presence.
    """
    desc = lead.description.strip().lower()
    ind = lead.industry.strip().lower()
    name = lead.company_name.strip()

    # Case 1: Insufficient data (empty, trivial, short or placeholder)
    trivial_words = ["n/a", "none", "tbd", "test", "coming soon", "blank", "stealth"]
    if not desc or len(desc) < 30 or any(desc == tw or f" {tw}" in desc for tw in trivial_words if len(desc) < 40):
        return ScoredLead(
            company_name=name,
            website=lead.website,
            industry=lead.industry,
            description=lead.description,
            category=LeadCategory.COLD.value,
            score=15,
            confidence=ConfidenceLevel.LOW.value,
            explanation="Insufficient information provided in the input data to determine outsourcing need.",
            potential_services="None / Not Applicable",
            status="SUCCESS",
            error_message=None,
        )

    # Case 2: In-house enterprise or explicit 100% in-house operations
    if "in-house" in desc or "centralized in-house" in desc or "85,000 employees" in desc:
        return ScoredLead(
            company_name=name,
            website=lead.website,
            industry=lead.industry,
            description=lead.description,
            category=LeadCategory.COLD.value,
            score=20,
            confidence=ConfidenceLevel.HIGH.value,
            explanation="The company maintains dedicated in-house departments or strictly non-outsourced operations, making external business services unlikely.",
            potential_services="None / In-House",
            status="SUCCESS",
            error_message=None,
        )

    # Case 3: Service Provider / BPO / Marketing Agency / MSP / Competitor
    competitor_keywords = [
        "bpo", "outsourcing provider", "staffing agency", "virtual assistant agency",
        "digital marketing agency", "it managed service provider", "accounting firm", "call center services",
        "consulting firm offering bookkeeping", "msp"
    ]
    if any(kw in desc for kw in competitor_keywords) or any(kw in ind for kw in ["bpo", "outsourcing", "staffing"]):
        return ScoredLead(
            company_name=name,
            website=lead.website,
            industry=lead.industry,
            description=lead.description,
            category=LeadCategory.COLD.value,
            score=10,
            confidence=ConfidenceLevel.HIGH.value,
            explanation="The company itself provides outsourced business services or staffing, making them a service provider rather than a prospective buyer.",
            potential_services="None / Competitor",
            status="SUCCESS",
            error_message=None,
        )

    # Case 4: Hot triggers (rapid scaling, lean team, overwhelmed operations, expanding, venture backed)
    hot_keywords = [
        "rapidly growing", "tripled", "scale", "scaling", "series a", "series b", "seed funded",
        "overwhelmed", "backlog", "lean team", "doubling", "expanding nationwide", "seeking partners",
        "struggling", "surge", "high-growth", "venture-backed", "urgently", "bottlenecks", "expanding coverage"
    ]
    is_hot = any(kw in desc for kw in hot_keywords)

    if is_hot:
        services = []
        if any(w in desc for w in ["support", "customers", "tickets", "orders", "users", "calls", "intake"]):
            services.append("Customer Support & Intake")
        if any(w in desc for w in ["hiring", "talent", "team", "growth", "engineers", "payroll"]):
            services.append("Payroll & HR Staffing")
        if any(w in desc for w in ["software", "tech", "platform", "cloud", "security", "devops"]):
            services.append("IT & Cloud Support")
        if any(w in desc for w in ["billing", "invoice", "bookkeeping", "claims"]):
            services.append("Billing & Invoicing")
        if not services:
            services = ["Customer Support", "Bookkeeping & Payroll", "Operational Support"]

        return ScoredLead(
            company_name=name,
            website=lead.website,
            industry=lead.industry,
            description=lead.description,
            category=LeadCategory.HOT.value,
            score=88,
            confidence=ConfidenceLevel.HIGH.value,
            explanation="Explicit signals of rapid expansion, capacity pressure, and back-office bottlenecks indicate an acute need for outsourced operational support.",
            potential_services=", ".join(services),
            status="SUCCESS",
            error_message=None,
        )

    # Case 5: Warm (standard operational business in healthcare, e-commerce, legal, logistics, finance, retail)
    warm_keywords = [
        "clinic", "dental", "medical", "practice", "law firm", "legal", "boutique", "e-commerce",
        "online store", "retailer", "logistics", "freight", "real estate", "property management",
        "wealth management", "advisory", "manufacturing", "distributor", "restaurant chain",
        "surveying", "cabinetry", "woodworking", "custom"
    ]
    is_warm = any(kw in desc for kw in warm_keywords) or any(kw in ind for kw in warm_keywords)

    if is_warm:
        services = ["Bookkeeping", "Customer Service", "Administrative Support"]
        return ScoredLead(
            company_name=name,
            website=lead.website,
            industry=lead.industry,
            description=lead.description,
            category=LeadCategory.WARM.value,
            score=60,
            confidence=ConfidenceLevel.MEDIUM.value,
            explanation="The business operates in an industry with clear back-office demands, but lacks explicit signals of immediate hiring surges or operational crises.",
            potential_services=", ".join(services),
            status="SUCCESS",
            error_message=None,
        )

    # Default to Cold with moderate confidence if no indicators found
    return ScoredLead(
        company_name=name,
        website=lead.website,
        industry=lead.industry,
        description=lead.description,
        category=LeadCategory.COLD.value,
        score=30,
        confidence=ConfidenceLevel.MEDIUM.value,
        explanation="No indicators of growth pressure, capacity constraints, or active demand for external business services found in the provided description.",
        potential_services="None Identified",
        status="SUCCESS",
        error_message=None,
    )


def score_single_lead(
    lead: LeadInput,
    api_key: str,
    model_name: str = "gemini-2.5-flash",
    use_mock: bool = False,
) -> ScoredLead:
    """
    Evaluates an individual company lead using Google Gemini API or Mock mode.
    Handles exceptions gracefully and returns a ScoredLead object.
    """
    if use_mock or not api_key:
        return mock_score_lead(lead)

    # Early check for completely missing description
    if not lead.description.strip() or len(lead.description.strip()) < 10:
        return ScoredLead(
            company_name=lead.company_name,
            website=lead.website,
            industry=lead.industry,
            description=lead.description,
            category=LeadCategory.COLD.value,
            score=10,
            confidence=ConfidenceLevel.LOW.value,
            explanation="Insufficient information provided in the input data to determine outsourcing need.",
            potential_services="None",
            status="SUCCESS",
            error_message=None,
        )

    user_prompt = build_lead_prompt(
        company_name=lead.company_name,
        website=lead.website,
        industry=lead.industry,
        description=lead.description,
    )

    client = genai.Client(api_key=api_key)

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        response_mime_type="application/json",
        response_schema=LeadScoreOutput,
        temperature=0.1,
    )

    max_attempts = 2
    for attempt in range(max_attempts):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=user_prompt,
                config=config,
            )

            raw_text = response.text or ""
            # Strip markdown formatting if any
            cleaned_text = raw_text.strip()
            if cleaned_text.startswith("```json"):
                cleaned_text = cleaned_text[7:]
            elif cleaned_text.startswith("```"):
                cleaned_text = cleaned_text[3:]
            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text[:-3]
            cleaned_text = cleaned_text.strip()

            parsed = LeadScoreOutput.model_validate_json(cleaned_text)

            # Enforce low confidence rule if is_insufficient_data flag was returned
            confidence_val = parsed.confidence.value
            category_val = parsed.category.value
            score_val = parsed.score

            if parsed.is_insufficient_data:
                confidence_val = ConfidenceLevel.LOW.value
                category_val = LeadCategory.COLD.value
                score_val = min(score_val, 30)

            return ScoredLead(
                company_name=lead.company_name,
                website=lead.website,
                industry=lead.industry,
                description=lead.description,
                category=category_val,
                score=score_val,
                confidence=confidence_val,
                explanation=parsed.explanation,
                potential_services=", ".join(parsed.potential_services) if parsed.potential_services else "None",
                status="SUCCESS",
                error_message=None,
            )

        except APIError as e:
            if "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e):
                if attempt < max_attempts - 1:
                    time.sleep(2.0)
                    continue
            logger.error(f"API Error scoring lead '{lead.company_name}': {e}")
            return ScoredLead(
                company_name=lead.company_name,
                website=lead.website,
                industry=lead.industry,
                description=lead.description,
                category=LeadCategory.COLD.value,
                score=0,
                confidence=ConfidenceLevel.LOW.value,
                explanation="Failed to evaluate due to API error.",
                potential_services="Unknown",
                status="ERROR",
                error_message=f"Gemini API Error: {str(e)[:120]}",
            )
        except Exception as e:
            logger.error(f"Unexpected error scoring lead '{lead.company_name}': {e}")
            return ScoredLead(
                company_name=lead.company_name,
                website=lead.website,
                industry=lead.industry,
                description=lead.description,
                category=LeadCategory.COLD.value,
                score=0,
                confidence=ConfidenceLevel.LOW.value,
                explanation="Failed to evaluate due to internal parsing or service error.",
                potential_services="Unknown",
                status="ERROR",
                error_message=f"Error: {str(e)[:120]}",
            )


def batch_score_leads(
    leads: List[LeadInput],
    api_key: str,
    model_name: str = "gemini-2.5-flash",
    use_mock: bool = False,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    delay_between_calls: float = 0.5,
) -> List[ScoredLead]:
    """
    Processes a list of leads sequentially with error isolation and live progress updates.
    """
    results: List[ScoredLead] = []
    total = len(leads)

    for idx, lead in enumerate(leads, start=1):
        if progress_callback:
            progress_callback(idx, total, lead.company_name)

        scored = score_single_lead(
            lead=lead,
            api_key=api_key,
            model_name=model_name,
            use_mock=use_mock,
        )
        results.append(scored)

        # Gentle throttle between API calls to avoid hitting rate limits on free tier
        if not use_mock and idx < total:
            time.sleep(delay_between_calls)

    return results
