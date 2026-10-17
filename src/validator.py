import io
from typing import Tuple, Optional, List
import pandas as pd
from .models import LeadInput
from .config import MAX_LEADS_PER_BATCH

# Permitted synonyms for canonical column names
COLUMN_MAPPINGS = {
    "company_name": ["company_name", "company", "name", "business_name", "organization", "company name"],
    "website": ["website", "url", "web", "site", "domain", "homepage", "company website"],
    "industry": ["industry", "sector", "vertical", "category", "business_type"],
    "description": ["description", "company_description", "about", "overview", "summary", "details", "short_description"]
}


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

    # Convert to LeadInput objects
    leads: List[LeadInput] = []
    for _, row in df.iterrows():
        leads.append(
            LeadInput(
                company_name=row["company_name"],
                website=row["website"],
                industry=row["industry"] if row["industry"] else "Unspecified",
                description=row["description"],
            )
        )

    return True, None, leads, df
