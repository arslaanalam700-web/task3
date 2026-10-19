"""
Actual Dataset Scoring & Submission Generator
============================================
Scores any lead dataset using Google Gemini LLM (or verified offline mode if no key),
validates all evidence quotes against source text, avoids repeated calls for identical leads,
and generates a clean, submission-ready CSV.

Usage:
    python run_actual_scoring.py --input data/sample_leads_30.csv --api-key YOUR_KEY
    python run_actual_scoring.py --input data/sample_leads_30.csv --output data/submission_results.csv
"""

import argparse
import os
import sys
import time
import pandas as pd
from dotenv import load_dotenv

# Ensure root workspace is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.validator import validate_and_parse_csv
from src.scorer import batch_score_leads
from src.models import compute_outreach_priority


def score_dataset(
    input_file: str,
    output_file: str = "data/submission_results.csv",
    api_key: str = None,
    model_name: str = "gemini-2.5-flash",
    profile: str = "blackfold",
    use_mock: bool = False,
):
    print("=" * 70)
    print(" AI LEAD SCORING: ACTUAL DATASET EVALUATION")
    print("=" * 70)

    if not os.path.exists(input_file):
        print(f"[!] Error: Input file '{input_file}' not found.")
        sys.exit(1)

    with open(input_file, "rb") as f:
        content = f.read()

    is_valid, err, leads, raw_df = validate_and_parse_csv(content)
    if not is_valid:
        print(f"[!] Validation Error: {err}")
        sys.exit(1)

    print(f"Loaded:     {len(leads)} valid leads from '{input_file}'")
    print(f"Profile:    {profile.upper()}")
    print(f"Mode:       {'Offline Verified Engine' if use_mock else f'Live Google Gemini ({model_name})'}")
    if not use_mock:
        print(f"API Key:    {api_key[:6]}...{api_key[-4:] if len(api_key) > 10 else ''}")
    print("-" * 70)

    start_time = time.time()

    def progress(idx, total, name):
        print(f"[{idx:02d}/{total:02d}] Evaluating '{name[:35]}'...")

    scored_leads = batch_score_leads(
        leads=leads,
        api_key=api_key or "",
        model_name=model_name,
        use_mock=use_mock,
        profile=profile,
        progress_callback=progress,
        delay_between_calls=0.8 if not use_mock else 0.0,
    )

    elapsed = time.time() - start_time
    total = len(scored_leads)

    results_data = [r.model_dump() for r in scored_leads]
    results_df = pd.DataFrame(results_data)

    print("\n" + "=" * 70)
    print(" SCORING RESULTS SUMMARY")
    print("=" * 70)
    print(f"Total Leads Processed: {total}")
    print(f"Total Execution Time:   {elapsed:.1f}s (Avg {elapsed/total:.2f}s per lead)")

    # Category Breakdown
    cat_counts = results_df["category"].value_counts()
    print("\nCategory Distribution:")
    for cat, count in cat_counts.items():
        pct = (count / total) * 100
        print(f"  - {cat:<16}: {count:>2} leads ({pct:>5.1f}%)")

    # Outreach Priority Breakdown
    prio_counts = results_df["outreach_priority"].value_counts()
    print("\nSales Outreach Priorities:")
    for prio, count in prio_counts.items():
        print(f"  - {prio:<22}: {count:>2} leads")

    # Grounded Evidence Validation Rate
    valid_ev = results_df["evidence_validated"].sum()
    ev_pct = (valid_ev / total) * 100
    print(f"\nEvidence Grounding & Verification:")
    print(f"  - Verified Evidence Quotes: {valid_ev}/{total} ({ev_pct:.1f}%)")

    # Duplicates Avoided
    dups = results_df["is_duplicate"].sum()
    print(f"\nDeduplication Savings:")
    print(f"  - Identical leads cached (API calls saved): {dups} leads")

    # Clean Export
    clean_cols = [
        "company_name", "website", "domain", "industry",
        "category", "score", "outreach_priority",
        "potential_services", "evidence", "evidence_validated",
        "explanation", "is_duplicate", "status"
    ]
    renamed_clean = {
        "company_name": "Company Name",
        "website": "Website",
        "domain": "Domain",
        "industry": "Industry",
        "category": "Category",
        "score": "Score",
        "outreach_priority": "Outreach Priority",
        "potential_services": "Target Services",
        "evidence": "Extracted Evidence",
        "evidence_validated": "Evidence Validated",
        "explanation": "Decision Rationale",
        "is_duplicate": "Duplicate Lead",
        "status": "Status"
    }

    clean_export_df = results_df[clean_cols].rename(columns=renamed_clean)
    os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
    clean_export_df.to_csv(output_file, index=False)
    print("\n" + "=" * 70)
    print(f"[+] Clean Submission CSV exported to: {output_file}")
    print("=" * 70)


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Actual Dataset Scoring & Submission Generator")
    parser.add_argument("--input", default="data/sample_leads_30.csv", help="Path to input CSV file")
    parser.add_argument("--output", default="data/submission_results.csv", help="Path to output clean CSV file")
    parser.add_argument("--api-key", default=None, help="Google Gemini API key (or read from GEMINI_API_KEY env/dotenv)")
    parser.add_argument("--model", default=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"), help="Gemini model name")
    parser.add_argument("--profile", default="blackfold", help="Scoring profile (blackfold or general)")
    parser.add_argument("--offline", action="store_true", help="Force offline mode using verified deterministic logic")
    args = parser.parse_args()

    api_key = args.api_key or os.getenv("GEMINI_API_KEY", "").strip()
    is_placeholder = (not api_key or api_key == "your_gemini_api_key_here")

    if args.offline or is_placeholder:
        if is_placeholder and not args.offline:
            print("[!] Notice: No valid GEMINI_API_KEY provided in .env or via --api-key.")
            print("    Running offline verified scoring to produce submission results...\n")
        score_dataset(
            input_file=args.input,
            output_file=args.output,
            profile=args.profile,
            use_mock=True,
        )
    else:
        score_dataset(
            input_file=args.input,
            output_file=args.output,
            api_key=api_key,
            model_name=args.model,
            profile=args.profile,
            use_mock=False,
        )


if __name__ == "__main__":
    main()
