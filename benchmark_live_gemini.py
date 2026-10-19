"""
Live Gemini LLM Lead Scoring Benchmark
=======================================
Runs live scoring using the official Google Gemini API (gemini-2.5-flash)
on a curated, manually reviewed subset of diverse leads (Hot, Warm, Cold, Needs Research).

Usage:
    python benchmark_live_gemini.py
    python benchmark_live_gemini.py --api-key AIzaSy...
    python benchmark_live_gemini.py --model gemini-2.5-flash
"""

import argparse
import os
import sys
import time
from typing import List
import pandas as pd
from dotenv import load_dotenv

# Ensure root workspace is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.models import LeadInput, LeadCategory, OutreachPriority
from src.validator import validate_evidence
from src.scorer import score_single_lead, mock_score_lead

# Curated 8-lead benchmark subset representing all categories and edge cases
BENCHMARK_LEADS = [
    {
        "company_name": "NovaTech Cloud",
        "website": "https://novatechcloud.io",
        "industry": "Software & Cloud",
        "description": "High-growth B2B SaaS startup that recently closed a $6M Series A. Active customer base has tripled in 4 months, and the 8-person engineering team is completely overwhelmed by customer onboarding, technical support tickets, and sprint backlog.",
        "expected_category": "Hot",
        "expected_reason": "Rapid growth, overwhelmed lean dev team, Series A backlog"
    },
    {
        "company_name": "Apex Logistics & Freight",
        "website": "https://apexlogisticsfreight.com",
        "industry": "Logistics & Transportation",
        "description": "Mid-sized regional freight brokerage managing dispatch for 75 carrier partners. Facing acute bottlenecks with manual spreadsheets, driver proof-of-delivery processing, and carrier invoice audits.",
        "expected_category": "Hot",
        "expected_reason": "Acute manual bottlenecks, custom workflow automation required"
    },
    {
        "company_name": "HealthBridge Telehealth",
        "website": "https://healthbridgetelehealth.io",
        "industry": "Healthcare Technology",
        "description": "Digital health startup building a specialized pediatric telehealth platform and patient mobile app. Seeking an experienced outsourced development partner to accelerate MVP launch before Q4.",
        "expected_category": "Hot",
        "expected_reason": "Building MVP app/platform, actively seeking dev execution partner"
    },
    {
        "company_name": "GreenLeaf Dental Group",
        "website": "https://greenleafdental.com",
        "industry": "Healthcare",
        "description": "A regional dental practice with 4 suburban clinic locations. Managing steady patient appointments and looking for ways to automate appointment confirmations and streamline billing.",
        "expected_category": "Warm",
        "expected_reason": "Steady operations, seeking appointment automation & billing streamline"
    },
    {
        "company_name": "ClearSky Drone Surveying",
        "website": "https://clearskydrones.com",
        "industry": "Aviation & Surveying",
        "description": "Commercial drone aerial inspection firm with 12 full-time staff providing crop surveying. Exploring a custom web platform to allow clients to view 3D aerial maps online.",
        "expected_category": "Warm",
        "expected_reason": "Evaluating custom web platform development, moderate urgency"
    },
    {
        "company_name": "Heritage Bakery & Cafe",
        "website": "https://heritagebakerycafe.com",
        "industry": "Food & Hospitality",
        "description": "Single-location artisanal sourdough bakery and neighborhood espresso bar operated by two founding bakers and 4 counter staff serving walk-in customers.",
        "expected_category": "Cold",
        "expected_reason": "Brick-and-mortar cafe, no digital engineering or automation needs"
    },
    {
        "company_name": "Delta Precision Tooling",
        "website": "https://deltaprecisiontooling.com",
        "industry": "Industrial Manufacturing",
        "description": "Precision metal stamping and CNC machining manufacturer supplying automotive tiers. Strictly maintains 100% in-house engineering, proprietary in-house machine software, and internal IT.",
        "expected_category": "Cold",
        "expected_reason": "Strictly maintains 100% in-house operations and engineering"
    },
    {
        "company_name": "StealthCo",
        "website": "https://stealthco.test",
        "industry": "Technology",
        "description": "N/A",
        "expected_category": "Needs Research",
        "expected_reason": "Insufficient company description, requires further research"
    },
]


def run_live_benchmark(api_key: str, model_name: str = "gemini-2.5-flash", profile: str = "blackfold"):
    print("=" * 75)
    print(f" LIVE GEMINI BENCHMARK TEST: {model_name.upper()} ({profile.upper()} PROFILE)")
    print("=" * 75)
    print(f"Dataset Size: {len(BENCHMARK_LEADS)} manually reviewed leads")
    print(f"Target LLM:   {model_name}")
    print(f"API Key:      {api_key[:6]}...{api_key[-4:] if len(api_key) > 10 else ''}")
    print("-" * 75)

    results = []
    correct_matches = 0
    total_latency = 0.0

    for i, item in enumerate(BENCHMARK_LEADS, 1):
        lead = LeadInput(
            company_name=item["company_name"],
            website=item["website"],
            industry=item["industry"],
            description=item["description"],
        )

        print(f"[{i}/{len(BENCHMARK_LEADS)}] Scoring '{lead.company_name}' via Gemini API...", end="", flush=True)

        start_time = time.time()
        scored = score_single_lead(
            lead=lead,
            api_key=api_key,
            model_name=model_name,
            use_mock=False,
            profile=profile,
        )
        latency = time.time() - start_time
        total_latency += latency

        is_match = scored.category.strip().lower() == item["expected_category"].strip().lower()
        if is_match:
            correct_matches += 1
            status_symbol = "MATCH"
        else:
            status_symbol = f"MISMATCH (Expected: {item['expected_category']})"

        print(f" -> {scored.category} ({scored.score}/100) [{latency:.2f}s] - {status_symbol}")

        results.append({
            "company_name": lead.company_name,
            "expected_category": item["expected_category"],
            "predicted_category": scored.category,
            "score": scored.score,
            "confidence": scored.confidence,
            "evidence": scored.evidence,
            "evidence_validated": scored.evidence_validated,
            "outreach_priority": scored.outreach_priority,
            "target_services": scored.potential_services,
            "latency_s": round(latency, 2),
            "match": is_match,
            "api_status": scored.status,
            "error": scored.error_message,
        })

    print("\n" + "=" * 75)
    print(f"LIVE BENCHMARK SUMMARY: {correct_matches}/{len(BENCHMARK_LEADS)} MATCHES ({correct_matches/len(BENCHMARK_LEADS)*100:.1f}% ACCURACY)")
    print(f"Average API Latency: {total_latency/len(BENCHMARK_LEADS):.2f}s per lead")
    print("=" * 75)

    df = pd.DataFrame(results)
    
    print("\nDetailed Comparison:")
    header = f"{'Company':<24} | {'Expected':<14} | {'Predicted':<14} | {'Score':<5} | {'Ev Valid?':<9} | {'Latency':<7}"
    print(header)
    print("-" * len(header))
    for _, r in df.iterrows():
        ev_icon = "YES" if r["evidence_validated"] else "NO"
        print(f"{r['company_name'][:24]:<24} | {r['expected_category']:<14} | {r['predicted_category']:<14} | {str(r['score']):<5} | {ev_icon:<9} | {r['latency_s']}s")

    # Evidence validation rate
    ev_rate = df["evidence_validated"].sum() / len(df) * 100
    print(f"\nEvidence Grounding & Verification Rate: {ev_rate:.1f}%")

    # Export clean benchmark CSV
    export_path = "data/live_gemini_benchmark_results.csv"
    df.to_csv(export_path, index=False)
    print(f"Full benchmark output saved to {export_path}")
    return df


def run_offline_preview(profile: str = "blackfold"):
    print("=" * 75)
    print(f" OFFLINE BENCHMARK PREVIEW (DETERMINISTIC EVALUATION - {profile.upper()} PROFILE)")
    print("=" * 75)
    print(f"Dataset Size: {len(BENCHMARK_LEADS)} manually reviewed leads")
    print("Mode:         Offline / Mock scoring (No API key provided)")
    print("-" * 75)

    results = []
    correct_matches = 0

    for i, item in enumerate(BENCHMARK_LEADS, 1):
        lead = LeadInput(
            company_name=item["company_name"],
            website=item["website"],
            industry=item["industry"],
            description=item["description"],
        )

        scored = mock_score_lead(lead, profile=profile)
        is_match = scored.category.strip().lower() == item["expected_category"].strip().lower()
        if is_match:
            correct_matches += 1

        results.append({
            "company_name": lead.company_name,
            "expected_category": item["expected_category"],
            "predicted_category": scored.category,
            "score": scored.score,
            "confidence": scored.confidence,
            "evidence": scored.evidence,
            "evidence_validated": scored.evidence_validated,
            "outreach_priority": scored.outreach_priority,
            "target_services": scored.potential_services,
            "match": is_match,
        })

    df = pd.DataFrame(results)
    header = f"{'Company':<24} | {'Expected':<14} | {'Predicted':<14} | {'Score':<5} | {'Ev Valid?':<9} | {'Priority':<12}"
    print(header)
    print("-" * len(header))
    for _, r in df.iterrows():
        ev_icon = "YES" if r["evidence_validated"] else "NO"
        print(f"{r['company_name'][:24]:<24} | {r['expected_category']:<14} | {r['predicted_category']:<14} | {str(r['score']):<5} | {ev_icon:<9} | {r['outreach_priority']}")

    print("\n" + "=" * 75)
    print(f"OFFLINE BENCHMARK SUMMARY: {correct_matches}/{len(BENCHMARK_LEADS)} MATCHES ({correct_matches/len(BENCHMARK_LEADS)*100:.1f}% ACCURACY)")
    print("=" * 75)
    print("\nTo run with live Google Gemini calls:")
    print("  1. Add your free Gemini API key to .env: GEMINI_API_KEY=AIzaSy...")
    print("  2. Or pass it directly via CLI: python benchmark_live_gemini.py --api-key YOUR_KEY")
    return df


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Live Gemini Lead Scoring Benchmark")
    parser.add_argument("--api-key", help="Google Gemini API key", default=None)
    parser.add_argument("--model", help="Gemini model name", default=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))
    parser.add_argument("--profile", help="Scoring profile (blackfold or general)", default="blackfold")
    args = parser.parse_args()

    api_key = args.api_key or os.getenv("GEMINI_API_KEY", "").strip()

    if not api_key or api_key == "your_gemini_api_key_here":
        print("[!] Notice: No valid GEMINI_API_KEY found in environment or .env.")
        print("Running offline benchmark preview with verified scoring logic...\n")
        run_offline_preview(profile=args.profile)
    else:
        try:
            run_live_benchmark(api_key=api_key, model_name=args.model, profile=args.profile)
        except Exception as e:
            print(f"\n[!] Live API Benchmark encountered an error: {e}")
            print("Falling back to offline deterministic preview...")
            run_offline_preview(profile=args.profile)


if __name__ == "__main__":
    main()
