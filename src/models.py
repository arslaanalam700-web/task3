from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field


class LeadCategory(str, Enum):
    HOT = "Hot"
    WARM = "Warm"
    COLD = "Cold"


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


class LeadScoreOutput(BaseModel):
    """Structured response required from the LLM for each lead assessment."""
    category: LeadCategory = Field(
        ...,
        description="Classification: 'Hot' (strong outsourcing need), 'Warm' (moderate potential), or 'Cold' (unlikely/competitor/insufficient data)."
    )
    score: int = Field(
        ...,
        ge=0,
        le=100,
        description="Numeric score from 0 (lowest need) to 100 (urgent, high-value need)."
    )
    confidence: ConfidenceLevel = Field(
        ...,
        description="Confidence in evaluation: 'High', 'Medium', or 'Low' (use Low if information is sparse)."
    )
    explanation: str = Field(
        ...,
        description="2-3 sentence rationale strictly grounded in the provided details. Mention if data was insufficient."
    )
    potential_services: List[str] = Field(
        default_factory=list,
        description="Specific outsourced services that would benefit this company (e.g., Bookkeeping, IT Support, Lead Gen, Customer Support, HR/Payroll)."
    )
    is_insufficient_data: bool = Field(
        default=False,
        description="True if the input description lacked substantive facts to form an informed judgment."
    )


class ScoredLead(BaseModel):
    """Full record containing original lead information and the evaluation result."""
    company_name: str
    website: str = ""
    industry: str = ""
    description: str = ""
    category: str = "Cold"
    score: int = 0
    confidence: str = "Low"
    explanation: str = ""
    potential_services: str = ""
    status: str = "SUCCESS"  # 'SUCCESS' or 'ERROR'
    error_message: Optional[str] = None
