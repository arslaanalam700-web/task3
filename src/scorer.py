import json
import logging
import re
import time
from typing import List, Callable, Optional
from google import genai
from google.genai import types
from google.genai.errors import APIError

from .models import LeadInput, LeadScoreOutput, ScoredLead, LeadCategory, ConfidenceLevel
from .prompt import SYSTEM_INSTRUCTION, build_lead_prompt

logger = logging.getLogger(__name__)

# Precompiled regex patterns for accurate keyword and phrase matching
TRIVIAL_PATTERN = re.compile(
    r"^(n/a|none|tbd|test|coming soon|blank|stealth|\?|-+)$",
    re.IGNORECASE
)

IN_HOUSE_PATTERNS = [
    re.compile(r"\bstrictly maintains 100% in-house\b", re.IGNORECASE),
    re.compile(r"\bfully centralized in-house\b", re.IGNORECASE),
    re.compile(r"\ball operations in-house\b", re.IGNORECASE),
    re.compile(r"\bdedicated internal divisions\b", re.IGNORECASE),
    re.compile(r"\b85,000 employees\b", re.IGNORECASE),
]

HOT_PATTERNS = [
    re.compile(r"\bseries [ab]\b", re.IGNORECASE),
    re.compile(r"\bseed funded\b", re.IGNORECASE),
    re.compile(r"\brapidly growing\b", re.IGNORECASE),
    re.compile(r"\bscaling (aggressively|rapidly)\b", re.IGNORECASE),
    re.compile(r"\btripled\b", re.IGNORECASE),
    re.compile(r"\bdoubling\b", re.IGNORECASE),
    re.compile(r"\boverwhelmed\b", re.IGNORECASE),
    re.compile(r"\bbacklog\b", re.IGNORECASE),
    re.compile(r"\blean (team|management team)\b", re.IGNORECASE),
    re.compile(r"\bexpanding (nationwide|coverage|from \d+ to \d+)\b", re.IGNORECASE),
    re.compile(r"\burgently needing\b", re.IGNORECASE),
    re.compile(r"\bacute bottlenecks?\b", re.IGNORECASE),
    re.compile(r"\bsurge in (sales|order|contracted)\b", re.IGNORECASE),
    re.compile(r"\bstruggling with\b", re.IGNORECASE),
    re.compile(r"\bacquired two (competitor|regional)\b", re.IGNORECASE),
]

WARM_PATTERNS = [
    re.compile(r"\b(dental practice|dental clinic|medical clinic|physical therapy|rehabilitation)\b", re.IGNORECASE),
    re.compile(r"\b(litigation firm|law firm|boutique commercial|legal)\b", re.IGNORECASE),
    re.compile(r"\b(wealth management|advisory firm|financial services)\b", re.IGNORECASE),
    re.compile(r"\b(e-commerce|online store|retail brand)\b", re.IGNORECASE),
    re.compile(r"\b(freight brokerage|trucking|logistics)\b", re.IGNORECASE),
    re.compile(r"\b(digital marketing agency|creative agency|advertising)\b", re.IGNORECASE),
    re.compile(r"\b(business process outsourcing|bpo|contact center)\b", re.IGNORECASE),
    re.compile(r"\b(managed service provider|msp|it solutions)\b", re.IGNORECASE),
    re.compile(r"\b(drone inspection|aerial inspection|surveying)\b", re.IGNORECASE),
    re.compile(r"\b(cabinetry|woodworking|manufacturing)\b", re.IGNORECASE),
]


def extract_matching_snippet(text: str, pattern: re.Pattern) -> str:
    """Extract a clean sentence or matching phrase from the text to serve as evidence."""
    match = pattern.search(text)
    if not match:
        return ""
    start, end = match.span()
    # Attempt to grab surrounding sentence
    sentences = re.split(r"(?<=[.!?])\s+", text)
    for s in sentences:
        if match.group(0).lower() in s.lower():
            return s.strip()
    return text[max(0, start - 20):min(len(text), end + 20)].strip()


def mock_score_lead(lead: LeadInput) -> ScoredLead:
    """
    Deterministic scoring logic for tests or offline demonstration.
    Uses regex word-boundary pattern matching and evidence extraction.
    """
    raw_desc = lead.description.strip()
    desc = raw_desc.lower()
    ind = lead.industry.strip().lower()
    name = lead.company_name.strip()

    # Case 1: Insufficient data -> Needs Research (Score: 20)
    if not raw_desc or len(raw_desc) < 30 or TRIVIAL_PATTERN.match(desc):
        return ScoredLead(
            company_name=name,
            website=lead.website,
            industry=lead.industry,
            description=lead.description,
            domain=lead.domain,
            is_duplicate=lead.is_duplicate,
            category=LeadCategory.NEEDS_RESEARCH.value,
            score=20,
            confidence=ConfidenceLevel.LOW.value,
            evidence=f'"{raw_desc}"' if raw_desc else "No description provided in input data.",
            explanation="Insufficient company details provided to determine operational outsourcing needs. Further research required.",
            potential_services="Needs Further Research",
            status="SUCCESS",
            error_message=None,
        )

    # Case 2: Explicit In-House Operations -> Cold (Score: 15)
    for p in IN_HOUSE_PATTERNS:
        if p.search(raw_desc):
            evidence_snippet = extract_matching_snippet(raw_desc, p)
            return ScoredLead(
                company_name=name,
                website=lead.website,
                industry=lead.industry,
                description=lead.description,
                domain=lead.domain,
                is_duplicate=lead.is_duplicate,
                category=LeadCategory.COLD.value,
                score=15,
                confidence=ConfidenceLevel.HIGH.value,
                evidence=evidence_snippet,
                explanation="The company maintains dedicated in-house departments or strictly non-outsourced operations, indicating minimal viability for external business services.",
                potential_services="None / In-House",
                status="SUCCESS",
                error_message=None,
            )

    # Case 3: Hot Triggers -> Hot (Score: 88)
    for p in HOT_PATTERNS:
        if p.search(raw_desc):
            evidence_snippet = extract_matching_snippet(raw_desc, p)
            services = []
            if re.search(r"\b(support|tickets|orders|inquiries|intake|calls)\b", desc):
                services.append("Customer Support & Intake")
            if re.search(r"\b(hiring|talent|team|growth|payroll)\b", desc):
                services.append("Payroll & HR Recruitment")
            if re.search(r"\b(cloud|software|tech|devops)\b", desc):
                services.append("IT & Cloud Infrastructure")
            if re.search(r"\b(billing|invoice|claims|bookkeeping)\b", desc):
                services.append("Billing & Invoicing")
            if not services:
                services = ["Customer Support", "Bookkeeping & Payroll", "Operational Support"]

            return ScoredLead(
                company_name=name,
                website=lead.website,
                industry=lead.industry,
                description=lead.description,
                domain=lead.domain,
                is_duplicate=lead.is_duplicate,
                category=LeadCategory.HOT.value,
                score=88,
                confidence=ConfidenceLevel.HIGH.value,
                evidence=evidence_snippet,
                explanation="Explicit signals of rapid expansion, capacity pressure, and back-office bottlenecks indicate an acute need for outsourced operational support.",
                potential_services=", ".join(services),
                status="SUCCESS",
                error_message=None,
            )

    # Case 4: Warm Triggers -> Warm (Score: 55)
    # Includes agencies, dental, legal, logistics, or wealth management without acute hot crises
    for p in WARM_PATTERNS:
        if p.search(raw_desc) or p.search(ind):
            evidence_snippet = extract_matching_snippet(raw_desc, p) or f"Operates in {lead.industry}"
            services = ["Bookkeeping & Invoicing", "Administrative Support", "Compliance/HR Support"]
            return ScoredLead(
                company_name=name,
                website=lead.website,
                industry=lead.industry,
                description=lead.description,
                domain=lead.domain,
                is_duplicate=lead.is_duplicate,
                category=LeadCategory.WARM.value,
                score=55,
                confidence=ConfidenceLevel.MEDIUM.value,
                evidence=evidence_snippet,
                explanation="The business operates in a sector with steady operational demands, making it a viable candidate for outsourced business services.",
                potential_services=", ".join(services),
                status="SUCCESS",
                error_message=None,
            )

    # Case 5: Default Cold (Score: 25)
    return ScoredLead(
        company_name=name,
        website=lead.website,
        industry=lead.industry,
        description=lead.description,
        domain=lead.domain,
        is_duplicate=lead.is_duplicate,
        category=LeadCategory.COLD.value,
        score=25,
        confidence=ConfidenceLevel.MEDIUM.value,
        evidence="No operational growth or outsourcing triggers identified in description.",
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
    Handles exceptions gracefully, marking API failures as Unscored/Error rather than Cold.
    """
    if use_mock or not api_key:
        return mock_score_lead(lead)

    # Check for empty or trivial description -> Needs Research without unnecessary API call
    raw_desc = lead.description.strip()
    if not raw_desc or len(raw_desc) < 25 or TRIVIAL_PATTERN.match(raw_desc.lower()):
        return ScoredLead(
            company_name=lead.company_name,
            website=lead.website,
            industry=lead.industry,
            description=lead.description,
            domain=lead.domain,
            is_duplicate=lead.is_duplicate,
            category=LeadCategory.NEEDS_RESEARCH.value,
            score=20,
            confidence=ConfidenceLevel.LOW.value,
            evidence=f'"{raw_desc}"' if raw_desc else "No description provided in input data.",
            explanation="Insufficient company details provided to determine operational outsourcing needs. Further research required.",
            potential_services="Needs Further Research",
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
            cleaned_text = raw_text.strip()
            if cleaned_text.startswith("```json"):
                cleaned_text = cleaned_text[7:]
            elif cleaned_text.startswith("```"):
                cleaned_text = cleaned_text[3:]
            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text[:-3]
            cleaned_text = cleaned_text.strip()

            parsed = LeadScoreOutput.model_validate_json(cleaned_text)

            return ScoredLead(
                company_name=lead.company_name,
                website=lead.website,
                industry=lead.industry,
                description=lead.description,
                domain=lead.domain,
                is_duplicate=lead.is_duplicate,
                category=parsed.category.value,
                score=parsed.score,
                confidence=parsed.confidence.value,
                evidence=parsed.evidence,
                explanation=parsed.explanation,
                potential_services=", ".join(parsed.potential_services) if parsed.potential_services else "None",
                status="SUCCESS",
                error_message=None,
            )

        except APIError as e:
            if ("RESOURCE_EXHAUSTED" in str(e) or "429" in str(e)) and attempt < max_attempts - 1:
                time.sleep(2.0)
                continue
            logger.error(f"API Error scoring lead '{lead.company_name}': {e}")
            return ScoredLead(
                company_name=lead.company_name,
                website=lead.website,
                industry=lead.industry,
                description=lead.description,
                domain=lead.domain,
                is_duplicate=lead.is_duplicate,
                category=LeadCategory.UNSCORED.value,
                score=None,
                confidence="N/A",
                evidence="N/A",
                explanation="Evaluation failed due to an API error.",
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
                domain=lead.domain,
                is_duplicate=lead.is_duplicate,
                category=LeadCategory.UNSCORED.value,
                score=None,
                confidence="N/A",
                evidence="N/A",
                explanation="Evaluation failed due to internal parsing or service error.",
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

        if not use_mock and idx < total:
            time.sleep(delay_between_calls)

    return results
