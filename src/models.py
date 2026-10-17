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


class LeadInput(BaseModel):
    """Raw lead details parsed and normalized from the uploaded CSV."""
    company_name: str
    website: str = ""
    industry: str = ""
    description: str = ""
    domain: str = ""
    is_duplicate: bool = False


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
        description="Specific outsourced services that would benefit this company (e.g., Bookkeeping, IT Support, Lead Gen, Customer Support, HR/Payroll)."
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
    explanation: str = ""
    potential_services: str = ""
    status: str = "SUCCESS"  # 'SUCCESS' or 'ERROR'
    error_message: Optional[str] = None
