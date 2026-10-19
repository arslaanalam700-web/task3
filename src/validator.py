import io
import re
import urllib.parse
from typing import Tuple, Optional, List
import pandas as pd
from .models import LeadInput
from .config import MAX_LEADS_PER_BATCH

# Permitted synonyms for canonical column names
COLUMN_MAPPINGS = {
    "company_name": ["company_name", "company", "name", "business_name", "organization", "company name"],
    "website": ["website", "url", "web", "site", "domain", "homepage", "company website"],
    "industry": ["industry", "sector", "vertical", "category", "business_type"],
    "description": ["description", "company_description", "about", "overview", "summary", "details", "short_description"],
    "expected_category": ["expected_category", "expected", "ground_truth", "manual_category", "label"]
}


def extract_domain(url: str) -> str:
    """Extract clean domain (e.g. 'company.com') from a website URL."""
    if not url:
        return ""
    clean = url.strip().lower()
    if not clean.startswith(("http://", "https://")):
        clean = "https://" + clean
    try:
        parsed = urllib.parse.urlparse(clean)
        domain = parsed.netloc or parsed.path.split("/")[0]
        domain = domain.split(":")[0]  # Remove port if present
        if domain.startswith("www."):
            domain = domain[4:]
        return domain.strip()
    except Exception:
        return ""


def validate_evidence(
    evidence: str,
    description: str,
    company_name: str = "",
    industry: str = ""
) -> Tuple[bool, str]:
    """
    Validates that the AI-extracted evidence is genuinely grounded in the actual company details,
    preventing unsupported or hallucinated claims from being accepted.

    Returns:
        (is_valid: bool, verified_or_flagged_evidence: str)
    """
    if not evidence or not evidence.strip():
        return False, "No evidence provided."

    ev_clean = evidence.strip().strip('"\'')
    desc_clean = description.strip()
    full_context = f"{company_name} {industry} {desc_clean}".strip().lower()

    # 1. Accept standard placeholder phrases for insufficient information
    ev_lower = ev_clean.lower()
    placeholders = [
        "no specific operational evidence",
        "insufficient information",
        "insufficient company details",
        "none provided",
        "no description provided",
        "needs further research",
        "n/a",
    ]
    if any(p in ev_lower for p in placeholders):
        return True, ev_clean

    if not desc_clean:
        return False, f"[Unsupported - No description provided] {ev_clean}"

    # 2. Exact substring match in description or full context
    if ev_lower in full_context:
        return True, ev_clean

    # 3. Normalized whitespace and punctuation match
    norm_ev = re.sub(r"[^a-z0-9\s]", " ", ev_lower)
    norm_ev = " ".join(norm_ev.split())
    norm_context = re.sub(r"[^a-z0-9\s]", " ", full_context)
    norm_context = " ".join(norm_context.split())

    if norm_ev in norm_context:
        return True, ev_clean

    # 4. Token & N-gram overlap check (handles slightly trimmed or paraphrased quotes)
    words = [w for w in norm_ev.split() if len(w) > 2]
    if not words:
        return True, ev_clean

    context_words = set(norm_context.split())
    matched_words = [w for w in words if w in context_words]
    overlap_ratio = len(matched_words) / len(words)

    # Check for at least one contiguous 3-gram match if evidence has 3+ words
    has_trigram = False
    if len(words) >= 3:
        for i in range(len(words) - 2):
            trigram = " ".join(words[i:i + 3])
            if trigram in norm_context:
                has_trigram = True
                break
    else:
        has_trigram = overlap_ratio >= 0.75

    if overlap_ratio >= 0.70 and (has_trigram or len(words) < 3):
        return True, ev_clean

    # 5. Unsupported claim detected
    return False, f"[Unverified Claim] {ev_clean}"


def normalize_column_name(raw_name: str) -> Optional[str]:
    """Map a raw column header to its canonical equivalent if recognized."""
    cleaned = raw_name.strip().lower().replace("-", "_").replace(" ", "_")
    for canonical, synonyms in COLUMN_MAPPINGS.items():
        if cleaned in [s.replace("-", "_").replace(" ", "_") for s in synonyms]:
            return canonical
    return None


def validate_and_parse_csv(
    file_content: bytes | str | io.StringIO | io.BytesIO,
    max_rows: int = MAX_LEADS_PER_BATCH
) -> Tuple[bool, Optional[str], Optional[List[LeadInput]], Optional[pd.DataFrame]]:
    """
    Validates the uploaded CSV file and extracts standardized LeadInput objects.
    Identifies duplicate leads using normalized website domains or company names.

    Returns:
        (is_valid, error_message, lead_inputs, normalized_dataframe)
    """
    if file_content is None:
        return False, "No file content provided.", None, None

    # Handle empty byte stream or string
    if isinstance(file_content, (bytes, bytearray)) and len(file_content) == 0:
        return False, "The uploaded file is empty (0 bytes).", None, None

    try:
        if isinstance(file_content, (bytes, bytearray)):
            stream = io.BytesIO(file_content)
            df = pd.read_csv(stream, encoding="utf-8")
        elif isinstance(file_content, str):
            stream = io.StringIO(file_content)
            df = pd.read_csv(stream)
        else:
            df = pd.read_csv(file_content)
    except UnicodeDecodeError:
        try:
            # Fallback encoding attempt
            if isinstance(file_content, (bytes, bytearray)):
                stream = io.BytesIO(file_content)
                df = pd.read_csv(stream, encoding="latin-1")
            else:
                return False, "Failed to decode CSV with UTF-8 or Latin-1.", None, None
        except Exception as e:
            return False, f"Could not decode file encoding: {str(e)}", None, None
    except pd.errors.EmptyDataError:
        return False, "The uploaded CSV file is empty (contains no data or headers).", None, None
    except Exception as e:
        return False, f"Error parsing CSV file: {str(e)}", None, None

    if df.empty:
        return False, "The uploaded CSV file is empty (has no rows).", None, None

    # Map column headers to canonical names
    rename_dict = {}
    found_canonicals = set()
    for col in df.columns:
        canonical = normalize_column_name(str(col))
        if canonical and canonical not in found_canonicals:
            rename_dict[col] = canonical
            found_canonicals.add(canonical)

    df = df.rename(columns=rename_dict)

    # Check for required canonical columns
    required_cols = ["company_name", "description"]
    missing_cols = [col for col in required_cols if col not in df.columns]

    if missing_cols:
        readable_missing = ", ".join(f"'{c}'" for c in missing_cols)
        available = ", ".join(f"'{c}'" for c in df.columns)
        return (
            False,
            f"Missing required column(s): {readable_missing}. Found columns: [{available}]. "
            "Please ensure your CSV includes at least company name and description columns.",
            None,
            None,
        )

    # Ensure optional columns exist
    if "website" not in df.columns:
        df["website"] = ""
    if "industry" not in df.columns:
        df["industry"] = "Unspecified"
    if "expected_category" not in df.columns:
        df["expected_category"] = None

    # Fill NA and clean strings
    for col in ["company_name", "website", "industry", "description"]:
        df[col] = df[col].fillna("").astype(str).str.strip()

    # Drop rows where company_name is entirely blank
    df = df[df["company_name"] != ""].copy()

    if df.empty:
        return False, "All rows in the CSV have blank company names.", None, None

    # Enforce row limit
    if len(df) > max_rows:
        return (
            False,
            f"File exceeds maximum batch limit of {max_rows} leads (found {len(df)} rows). "
            f"Please reduce the file size to {max_rows} rows or fewer.",
            None,
            None,
        )

    # Convert to LeadInput objects with domain extraction and duplicate detection
    leads: List[LeadInput] = []
    seen_domains = set()
    seen_names = set()

    for _, row in df.iterrows():
        raw_web = row["website"]
        clean_name = row["company_name"].strip().lower()
        domain = extract_domain(raw_web)

        is_dup = False
        if domain:
            if domain in seen_domains:
                is_dup = True
            else:
                seen_domains.add(domain)
        else:
            if clean_name in seen_names:
                is_dup = True
            else:
                seen_names.add(clean_name)

        expected_cat = row["expected_category"] if pd.notnull(row.get("expected_category")) and str(row.get("expected_category")).strip() else None

        leads.append(
            LeadInput(
                company_name=row["company_name"],
                website=row["website"],
                industry=row["industry"] if row["industry"] else "Unspecified",
                description=row["description"],
                domain=domain,
                is_duplicate=is_dup,
                expected_category=expected_cat,
            )
        )

    df["domain"] = [l.domain for l in leads]
    df["is_duplicate"] = [l.is_duplicate for l in leads]

    return True, None, leads, df
