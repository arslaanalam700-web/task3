"""
Benchmark evaluation script for testing lead scoring against 30 manually reviewed leads.
Evaluates accuracy, confusion matrix, evidence validation, duplicate API avoidance, and exports clean CSV.
"""
import pandas as pd
from src.validator import validate_and_parse_csv
from src.scorer import batch_score_leads


def run_benchmark():
    with open("data/sample_leads_30.csv", "rb") as f:
        content = f.read()

    is_valid, err, leads, df = validate_and_parse_csv(content)
    if not is_valid:
        print(f"Validation failed: {err}")
        return

    print(f"Loaded {len(leads)} leads for benchmarking.\n")

    # Run batch scoring with Blackfold profile
    scored_results = batch_score_leads(
        leads=leads,
        api_key="",
        use_mock=True,
        profile="blackfold",
    )

    # Convert to DataFrame
    results_df = pd.DataFrame([r.model_dump() for r in scored_results])
    results_df["expected_category"] = [l.expected_category for l in leads]

    # Evaluate accuracy
    total = len(results_df)
    matches = (results_df["category"] == results_df["expected_category"]).sum()
    accuracy = (matches / total) * 100

    print("=" * 60)
    print(f"BENCHMARK RESULTS: {matches}/{total} MATCHES ({accuracy:.1f}% ACCURACY)")
    print("=" * 60)

    # Category breakdown
    categories = ["Hot", "Warm", "Cold", "Needs Research"]
    print("\nPer-Category Performance:")
    print(f"{'Category':<16} | {'Expected':<10} | {'Predicted':<10} | {'Match Rate':<12}")
    print("-" * 55)

    for cat in categories:
        exp_count = (results_df["expected_category"] == cat).sum()
        pred_count = (results_df["category"] == cat).sum()
        correct_cat = ((results_df["category"] == cat) & (results_df["expected_category"] == cat)).sum()
        rate = (correct_cat / exp_count * 100) if exp_count > 0 else 0
        print(f"{cat:<16} | {exp_count:<10} | {pred_count:<10} | {rate:.1f}%")

    # Mismatches (if any)
    mismatches = results_df[results_df["category"] != results_df["expected_category"]]
    if not mismatches.empty:
        print("\nMismatches Analysis:")
        for _, row in mismatches.iterrows():
            print(f"- {row['company_name']}: Expected '{row['expected_category']}', Got '{row['category']}'")
            print(f"  Evidence: {row['evidence']}")
            print(f"  Explanation: {row['explanation']}\n")
    else:
        print("\nPerfect 100% agreement across all 30 manually reviewed leads!")

    # Duplicate API Avoidance
    dup_count = results_df["is_duplicate"].sum()
    print(f"\nDuplicate Handling:")
    print(f"- Duplicates detected & repeated API calls avoided: {dup_count} leads")

    # Evidence Validation
    ev_valid_count = results_df["evidence_validated"].sum()
    print(f"\nEvidence Verification:")
    print(f"- Grounded & verified evidence quotes: {ev_valid_count}/{total} ({ev_valid_count/total*100:.1f}%)")

    # Export clean CSV
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
    clean_export_df.to_csv("data/sample_leads_scored.csv", index=False)
    print(f"\nClean CSV exported to data/sample_leads_scored.csv ({len(clean_export_df)} rows).")


if __name__ == "__main__":
    run_benchmark()
