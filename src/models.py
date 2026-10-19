from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field, model_validator


class LeadCategory(str, Enum):
    HOT = "Hot"
    WARM = "Warm"
    COLD = "Cold"
    NEEDS_RESEARCH = "Needs Research"
    UNSCORED = "Unscored"


class ConfidenceLevel(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class OutreachPriority(str, Enum):
    P1_URGENT = "P1 - Urgent Outreach"
    P1_HIGH = "P1 - High Priority"
    P2_MEDIUM = "P2 - Medium Priority"
    P3_LOW = "P3 - Low Priority"
    P4_COLD = "P4 - Do Not Contact"
    NEEDS_RESEARCH = "Needs Research"
    UNSCORED = "Unscored / Error"


def compute_outreach_priority(category: str, score: Optional[int]) -> str:
    """Calculates standardized outreach priority from lead category and score."""
    if category == LeadCategory.HOT.value or category == "Hot":
        if score is not None and score >= 85:
            return OutreachPriority.P1_URGENT.value
        return OutreachPriority.P1_HIGH.value
    elif category == LeadCategory.WARM.value or category == "Warm":
        if score is not None and score >= 50:
            return OutreachPriority.P2_MEDIUM.value
        return OutreachPriority.P3_LOW.value
    elif category == LeadCategory.COLD.value or category == "Cold":
        return OutreachPriority.P4_COLD.value
    elif category == LeadCategory.NEEDS_RESEARCH.value or category == "Needs Research":
        return OutreachPriority.NEEDS_RESEARCH.value
    return OutreachPriority.UNSCORED.value


class LeadInput(BaseModel):
    """Raw lead details parsed and normalized from the uploaded CSV."""
    company_name: str
    website: str = ""
    industry: str = ""
    description: str = ""
    domain: str = ""
    is_duplicate: bool = False
    expected_category: Optional[str] = None  # Optional field for benchmarking


class LeadScoreOutput(BaseModel):
    """Structured response required from the LLM for each lead assessment."""
    category: LeadCategory = Field(
        ...,
        description="Classification: 'Hot' (70-100), 'Warm' (35-69), 'Cold' (0-34), or 'Needs Research' (insufficient info)."
    )
    score: int = Field(
        ...,
        ge=0,
        le=100,
        description="Numeric score strictly matching category: Hot (70-100), Warm (35-69), Cold (0-34), Needs Research (0-34)."
    )
    confidence: ConfidenceLevel = Field(
        ...,
        description="Confidence in evaluation: 'High', 'Medium', or 'Low' (must be Low for Needs Research)."
    )
    evidence: str = Field(
        ...,
        description="Direct quote or specific factual snippet from the description justifying the evaluation."
    )
    explanation: str = Field(
        ...,
        description="2-3 sentence rationale strictly grounded in the provided details."
    )
    potential_services: List[str] = Field(
        default_factory=list,
        description="Specific services that would benefit this company (e.g. Custom Software Development, Workflow Automation, Overflow Engineering, Project Execution)."
    )
    is_insufficient_data: bool = Field(
        default=False,
        description="True if the input description lacked substantive facts to form an informed judgment."
    )

    @model_validator(mode="after")
    def enforce_category_score_alignment(self):
        """Strictly guarantees that the score aligns with the category range."""
        if self.category == LeadCategory.HOT:
            if self.score < 70:
                self.score = 70
            elif self.score > 100:
                self.score = 100
        elif self.category == LeadCategory.WARM:
            if self.score < 35:
                self.score = 35
            elif self.score > 69:
                self.score = 69
        elif self.category == LeadCategory.COLD:
            if self.score < 0:
                self.score = 0
            elif self.score > 34:
                self.score = 34
        elif self.category == LeadCategory.NEEDS_RESEARCH:
            if self.score < 0 or self.score > 34:
                self.score = 20
            self.confidence = ConfidenceLevel.LOW
            self.is_insufficient_data = True
        return self


class ScoredLead(BaseModel):
    """Full record containing original lead information and the evaluation result."""
    company_name: str
    website: str = ""
    industry: str = ""
    description: str = ""
    domain: str = ""
    is_duplicate: bool = False
    category: str = "Unscored"
    score: Optional[int] = None
    confidence: str = "Low"
    evidence: str = ""
    evidence_validated: bool = True
    outreach_priority: str = ""
    explanation: str = ""
    potential_services: str = ""
    status: str = "SUCCESS"  # 'SUCCESS' or 'ERROR'
    error_message: Optional[str] = None
