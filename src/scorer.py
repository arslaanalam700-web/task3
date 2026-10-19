import hashlib
import json
import logging
import re
import time
from typing import List, Callable, Optional
from google import genai
from google.genai import types
from google.genai.errors import APIError

from .models import (
    LeadInput,
    LeadScoreOutput,
    ScoredLead,
    LeadCategory,
    ConfidenceLevel,
    compute_outreach_priority,
)
from .prompt import get_system_instruction, build_lead_prompt
from .validator import validate_evidence

logger = logging.getLogger(__name__)

# Precompiled regex patterns for accurate keyword and phrase matching
TRIVIAL_PATTERN = re.compile(
    r"^(n/a|none|tbd|test|coming soon|blank|stealth|\?|-+|\[no description.*\])$",
    re.IGNORECASE
)

IN_HOUSE_PATTERNS = [
    re.compile(r"\bstrictly maintains 100% in-house\b", re.IGNORECASE),
    re.compile(r"\bfully centralized in-house\b", re.IGNORECASE),
    re.compile(r"\ball operations in-house\b", re.IGNORECASE),
    re.compile(r"\bdedicated internal divisions\b", re.IGNORECASE),
    re.compile(r"\b85,000 employees\b", re.IGNORECASE),
]

# Non-digital brick-and-mortar with minimal software needs
NON_DIGITAL_PATTERNS = [
    re.compile(r"\b(artisanal sourdough bakery|neighborhood espresso bar|bakery & cafe)\b", re.IGNORECASE),
    re.compile(r"\b(landscape gardening|lawn care|hand-carved|woodworking workshop)\b", re.IGNORECASE),
]

# Blackfold-specific Hot patterns: Development, Automation, Overflow, Project Execution
BLACKFOLD_HOT_PATTERNS = [
    re.compile(r"\b(overwhelmed.*(support|tickets|engineering|dev)|backlog|technical debt)\b", re.IGNORECASE),
    re.compile(r"\b(building.*(platform|app|web|mvp|system)|telehealth mvp|launching.*(saas|platform)|mvp)\b", re.IGNORECASE),
    re.compile(r"\b(manual (spreadsheets|dispatch|intake|reconciliation|processing)|bottlenecks with driver proof|acute bottlenecks)\b", re.IGNORECASE),
    re.compile(r"\b(overflow engineering|engineering team is completely overwhelmed|talent shortage|lean (8-person|engineering|management))\b", re.IGNORECASE),
    re.compile(r"\b(custom integration|api integration|automated lead distribution|workflow automation|payment api)\b", re.IGNORECASE),
    re.compile(r"\b(automate.*(ticket|routing|workflow|process)|custom (ai|script|tool|dashboard)|internal.*dashboard)\b", re.IGNORECASE),
    re.compile(r"\b(scaling aggressively|surged \d+%.*sales|tripled in \d+ months|series a)\b", re.IGNORECASE),
    re.compile(r"\b(dev execution partner|development partner|custom client apps|overflow teams?)\b", re.IGNORECASE),
]

# Blackfold-specific Warm patterns: Digital, E-commerce, Logistics, Tech platforms
BLACKFOLD_WARM_PATTERNS = [
    re.compile(r"\b(software|saas|fintech|healthtech|edtech|platform|marketplace|e-commerce|shopify)\b", re.IGNORECASE),
    re.compile(r"\b(freight brokerage|logistics|trucking|dispatch system|courier schedules)\b", re.IGNORECASE),
    re.compile(r"\b(digital marketing agency|creative agency|advertising|bpo|contact center|msp|it managed)\b", re.IGNORECASE),
    re.compile(r"\b(dental practice|medical practice|clinic|physical therapy|wealth management|litigation firm)\b", re.IGNORECASE),
    re.compile(r"\b(drone (inspection|surveying)|architectural cabinetry|custom millwork|chemical distributor)\b", re.IGNORECASE),
    re.compile(r"\b(interactive web apps?|event management|polling tools?|ordering portal)\b", re.IGNORECASE),
]

# General BPO patterns
GENERAL_HOT_PATTERNS = [
    re.compile(r"\bseries [ab]\b", re.IGNORECASE),
    re.compile(r"\brapidly growing\b", re.IGNORECASE),
    re.compile(r"\bscaling (aggressively|rapidly)\b", re.IGNORECASE),
    re.compile(r"\btripled\b", re.IGNORECASE),
    re.compile(r"\boverwhelmed\b", re.IGNORECASE),
    re.compile(r"\bbacklog\b", re.IGNORECASE),
    re.compile(r"\blean (team|management team)\b", re.IGNORECASE),
    re.compile(r"\burgently needing\b", re.IGNORECASE),
    re.compile(r"\bacute bottlenecks?\b", re.IGNORECASE),
    re.compile(r"\bsurge in (sales|order|contracted)\b", re.IGNORECASE),
]

GENERAL_WARM_PATTERNS = [
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
    sentences = re.split(r"(?<=[.!?])\s+", text)
    for s in sentences:
        if match.group(0).lower() in s.lower():
            return s.strip()
    return text[max(0, start - 20):min(len(text), end + 20)].strip()


def mock_score_lead(lead: LeadInput, profile: str = "blackfold") -> ScoredLead:
    """
    Deterministic scoring logic for tests, benchmarks, or offline demonstration.
    Supports both 'blackfold' and 'general' scoring profiles.
    """
    raw_desc = lead.description.strip()
    desc = raw_desc.lower()
    ind = lead.industry.strip().lower()
    name = lead.company_name.strip()

    is_blackfold = (profile.lower() == "blackfold")

    # Case 1: Insufficient data -> Needs Research (Score: 20)
    if not raw_desc or len(raw_desc) < 30 or TRIVIAL_PATTERN.match(desc):
        score_val = 20
        cat_val = LeadCategory.NEEDS_RESEARCH.value
        ev_str = f'"{raw_desc}"' if raw_desc else "No description provided in input data."
        return ScoredLead(
            company_name=name,
            website=lead.website,
            industry=lead.industry,
            description=lead.description,
            domain=lead.domain,
            is_duplicate=lead.is_duplicate,
            category=cat_val,
            score=score_val,
            confidence=ConfidenceLevel.LOW.value,
            evidence=ev_str,
            evidence_validated=True,
            outreach_priority=compute_outreach_priority(cat_val, score_val),
            explanation="Insufficient company details provided to determine operational outsourcing needs. Further research required.",
            potential_services="Needs Further Research",
            status="SUCCESS",
            error_message=None,
        )

    # Case 2: Explicit In-House Operations or Enterprise -> Cold (Score: 15)
    for p in IN_HOUSE_PATTERNS:
        if p.search(raw_desc):
            evidence_snippet = extract_matching_snippet(raw_desc, p)
            cat_val = LeadCategory.COLD.value
            score_val = 15
            return ScoredLead(
                company_name=name,
                website=lead.website,
                industry=lead.industry,
                description=lead.description,
                domain=lead.domain,
                is_duplicate=lead.is_duplicate,
                category=cat_val,
                score=score_val,
                confidence=ConfidenceLevel.HIGH.value,
                evidence=evidence_snippet,
                evidence_validated=True,
                outreach_priority=compute_outreach_priority(cat_val, score_val),
                explanation="The company maintains dedicated in-house departments or strictly non-outsourced operations, indicating minimal viability for external technical or business services.",
                potential_services="None / In-House",
                status="SUCCESS",
                error_message=None,
            )

    # Case 3: Non-digital brick-and-mortar businesses (Cold for Blackfold dev/tech)
    if is_blackfold:
        for p in NON_DIGITAL_PATTERNS:
            if p.search(raw_desc):
                evidence_snippet = extract_matching_snippet(raw_desc, p)
                cat_val = LeadCategory.COLD.value
                score_val = 10
                return ScoredLead(
                    company_name=name,
                    website=lead.website,
                    industry=lead.industry,
                    description=lead.description,
                    domain=lead.domain,
                    is_duplicate=lead.is_duplicate,
                    category=cat_val,
                    score=score_val,
                    confidence=ConfidenceLevel.HIGH.value,
                    evidence=evidence_snippet,
                    evidence_validated=True,
                    outreach_priority=compute_outreach_priority(cat_val, score_val),
                    explanation="Local brick-and-mortar business with minimal operational complexity and zero requirement for custom software development, engineering teams, or automation.",
                    potential_services="None Identified",
                    status="SUCCESS",
                    error_message=None,
                )

    # Case 4: Hot Triggers
    hot_patterns = BLACKFOLD_HOT_PATTERNS if is_blackfold else GENERAL_HOT_PATTERNS
    for p in hot_patterns:
        if p.search(raw_desc):
            evidence_snippet = extract_matching_snippet(raw_desc, p)
            if is_blackfold:
                services = []
                if re.search(r"\b(backlog|engineering|overwhelmed|team|talent|overflow)\b", desc):
                    services.append("Overflow Engineering Team")
                if re.search(r"\b(manual|spreadsheets|dispatch|reconciliation|intake|bottlenecks)\b", desc):
                    services.append("Workflow Automation & Integrations")
                if re.search(r"\b(platform|app|web|mvp|building|saas)\b", desc):
                    services.append("Custom Software & Web/App Dev")
                if not services:
                    services = ["Custom Software Development", "Workflow Automation", "Project Execution Support"]
            else:
                services = ["Customer Support & Intake", "Billing & Invoicing", "Operational Support"]

            cat_val = LeadCategory.HOT.value
            score_val = 88
            is_valid_ev, validated_ev = validate_evidence(evidence_snippet, raw_desc, name, lead.industry)

            return ScoredLead(
                company_name=name,
                website=lead.website,
                industry=lead.industry,
                description=lead.description,
                domain=lead.domain,
                is_duplicate=lead.is_duplicate,
                category=cat_val,
                score=score_val,
                confidence=ConfidenceLevel.HIGH.value,
                evidence=validated_ev,
                evidence_validated=is_valid_ev,
                outreach_priority=compute_outreach_priority(cat_val, score_val),
                explanation="Strong signals of technical bottlenecks, manual operational friction, or rapid expansion indicate an urgent need for outsourced development, automation, or engineering overflow.",
                potential_services=", ".join(services),
                status="SUCCESS",
                error_message=None,
            )

    # Case 5: Warm Triggers
    warm_patterns = BLACKFOLD_WARM_PATTERNS if is_blackfold else GENERAL_WARM_PATTERNS
    for p in warm_patterns:
        if p.search(raw_desc) or p.search(ind):
            evidence_snippet = extract_matching_snippet(raw_desc, p)
            if not evidence_snippet:
                evidence_snippet = raw_desc.split(".")[0].strip() if raw_desc else f"Operates in {lead.industry}"
            if is_blackfold:
                services = ["Workflow Automation", "Custom Tool Development", "Project Support"]
                expl = "The business operates digital systems, e-commerce, or logistical workflows that would benefit from custom automation and development support, but lacks an acute crisis."
            else:
                services = ["Bookkeeping & Invoicing", "Administrative Support", "Compliance Support"]
                expl = "The business operates in a sector with steady operational demands, making it a viable candidate for outsourced business services."

            cat_val = LeadCategory.WARM.value
            score_val = 55
            is_valid_ev, validated_ev = validate_evidence(evidence_snippet, raw_desc, name, lead.industry)

            return ScoredLead(
                company_name=name,
                website=lead.website,
                industry=lead.industry,
                description=lead.description,
                domain=lead.domain,
                is_duplicate=lead.is_duplicate,
                category=cat_val,
                score=score_val,
                confidence=ConfidenceLevel.MEDIUM.value,
                evidence=validated_ev,
                evidence_validated=is_valid_ev,
                outreach_priority=compute_outreach_priority(cat_val, score_val),
                explanation=expl,
                potential_services=", ".join(services),
                status="SUCCESS",
                error_message=None,
            )

    # Case 6: Default Cold (Score: 25)
    cat_val = LeadCategory.COLD.value
    score_val = 25
    return ScoredLead(
        company_name=name,
        website=lead.website,
        industry=lead.industry,
        description=lead.description,
        domain=lead.domain,
        is_duplicate=lead.is_duplicate,
        category=cat_val,
        score=score_val,
        confidence=ConfidenceLevel.MEDIUM.value,
        evidence="No technical development or operational outsourcing triggers identified in description.",
        evidence_validated=True,
        outreach_priority=compute_outreach_priority(cat_val, score_val),
        explanation="No indicators of growth pressure, technical capacity constraints, or active demand for external services found in the provided description.",
        potential_services="None Identified",
        status="SUCCESS",
        error_message=None,
    )


def score_single_lead(
    lead: LeadInput,
    api_key: str,
    model_name: str = "gemini-2.5-flash",
    use_mock: bool = False,
    profile: str = "blackfold",
) -> ScoredLead:
    """
    Evaluates an individual company lead using Google Gemini API or Mock mode.
    Validates extracted evidence against the original description.
    """
    if use_mock or not api_key:
        return mock_score_lead(lead, profile=profile)

    # Check for empty or trivial description -> Needs Research without burning API quota
    raw_desc = lead.description.strip()
    if not raw_desc or len(raw_desc) < 25 or TRIVIAL_PATTERN.match(raw_desc.lower()):
        cat_val = LeadCategory.NEEDS_RESEARCH.value
        score_val = 20
        return ScoredLead(
            company_name=lead.company_name,
            website=lead.website,
            industry=lead.industry,
            description=lead.description,
            domain=lead.domain,
            is_duplicate=lead.is_duplicate,
            category=cat_val,
            score=score_val,
            confidence=ConfidenceLevel.LOW.value,
            evidence=f'"{raw_desc}"' if raw_desc else "No description provided in input data.",
            evidence_validated=True,
            outreach_priority=compute_outreach_priority(cat_val, score_val),
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
        profile=profile,
    )

    client = genai.Client(api_key=api_key)

    config = types.GenerateContentConfig(
        system_instruction=get_system_instruction(profile),
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

            # Validate extracted evidence against source description
            is_valid_evidence, validated_evidence_text = validate_evidence(
                evidence=parsed.evidence,
                description=lead.description,
                company_name=lead.company_name,
                industry=lead.industry,
            )

            explanation_text = parsed.explanation
            confidence_level = parsed.confidence.value

            # If evidence contains unverified claims, flag and adjust confidence
            if not is_valid_evidence and parsed.category == LeadCategory.HOT:
                confidence_level = ConfidenceLevel.LOW.value
                explanation_text += " [Note: Extracted evidence could not be verified in input text.]"

            cat_val = parsed.category.value
            score_val = parsed.score

            return ScoredLead(
                company_name=lead.company_name,
                website=lead.website,
                industry=lead.industry,
                description=lead.description,
                domain=lead.domain,
                is_duplicate=lead.is_duplicate,
                category=cat_val,
                score=score_val,
                confidence=confidence_level,
                evidence=validated_evidence_text,
                evidence_validated=is_valid_evidence,
                outreach_priority=compute_outreach_priority(cat_val, score_val),
                explanation=explanation_text,
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
                evidence_validated=False,
                outreach_priority=compute_outreach_priority(LeadCategory.UNSCORED.value, None),
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
                evidence_validated=False,
                outreach_priority=compute_outreach_priority(LeadCategory.UNSCORED.value, None),
                explanation="Evaluation failed due to internal parsing or service error.",
                potential_services="Unknown",
                status="ERROR",
                error_message=f"Error: {str(e)[:120]}",
            )


def get_lead_cache_key(lead: LeadInput) -> str:
    """
    Computes a content-aware signature for caching evaluations.
    Requires matching identity (domain or company name) AND matching normalized description.
    Prevents reusing scores when two leads share a domain but have different information.
    """
    domain_or_name = lead.domain if lead.domain else re.sub(r"[^a-z0-9]", "", lead.company_name.lower())
    norm_desc = " ".join(re.sub(r"[^a-z0-9\s]", " ", lead.description.lower()).split())
    desc_hash = hashlib.sha256(norm_desc.encode("utf-8")).hexdigest()[:16]
    return f"{domain_or_name}::{desc_hash}"


def batch_score_leads(
    leads: List[LeadInput],
    api_key: str,
    model_name: str = "gemini-2.5-flash",
    use_mock: bool = False,
    profile: str = "blackfold",
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    delay_between_calls: float = 0.5,
) -> List[ScoredLead]:
    """
    Processes a list of leads with intelligent deduplication:
    Only genuinely identical leads (matching domain/name AND matching description)
    reuse previous evaluation results, avoiding redundant API calls.
    """
    results: List[ScoredLead] = []
    total = len(leads)

    # Evaluation cache by content-aware signature (identity + description hash)
    eval_cache: dict[str, ScoredLead] = {}

    for idx, lead in enumerate(leads, start=1):
        dedup_key = get_lead_cache_key(lead)

        # Only reuse score when lead information actually matches!
        if dedup_key and dedup_key in eval_cache:
            primary = eval_cache[dedup_key]
            if progress_callback:
                progress_callback(idx, total, f"{lead.company_name} (Identical Lead - Cached, skipping API call)")

            reused_lead = ScoredLead(
                company_name=lead.company_name,
                website=lead.website,
                industry=lead.industry,
                description=lead.description,
                domain=lead.domain,
                is_duplicate=True,
                category=primary.category,
                score=primary.score,
                confidence=primary.confidence,
                evidence=primary.evidence,
                evidence_validated=primary.evidence_validated,
                outreach_priority=primary.outreach_priority,
                explanation=f"[Reused from identical lead '{primary.company_name}'] {primary.explanation}",
                potential_services=primary.potential_services,
                status="SUCCESS",
                error_message=None,
            )
            results.append(reused_lead)
            continue

        if progress_callback:
            progress_callback(idx, total, lead.company_name)

        scored = score_single_lead(
            lead=lead,
            api_key=api_key,
            model_name=model_name,
            use_mock=use_mock,
            profile=profile,
        )

        # Cache valid evaluation for identical leads
        if dedup_key and scored.status == "SUCCESS":
            eval_cache[dedup_key] = scored

        results.append(scored)

        if not use_mock and idx < total:
            time.sleep(delay_between_calls)

    return results
