# 🎯 AI Lead Scoring Tool (Blackfold Edition)

A high-accuracy, production-ready Streamlit application that evaluates B2B company leads using Google Gemini LLMs to classify their likelihood of needing **custom software development, workflow automation, overflow engineering teams, or technical project execution**.

Built for Blackfold with Python, Streamlit, Pydantic, and Google's official `google-genai` SDK.

---

## 🌟 Key Features & Improvements

- **Evidence Grounding & Anti-Hallucination Verification**: All AI-extracted evidence is programmatically validated against the raw company description (`validate_evidence`). Unsupported or hallucinated claims are flagged (`⚠️ Unverified Claim`), and confidence is automatically downgraded.
- **Intelligent Deduplication & API Call Avoidance**: Normalized domain detection (`extract_domain`) identifies duplicate companies within batches. The evaluation engine caches results, completely bypassing repeated API calls for identical leads—saving quota, preventing 429 rate limits, and speeding up processing.
- **Blackfold-Specific Scoring Profile**: Tailored scoring rules and prompts focusing on Blackfold's core services:
  1. Custom Software & Web/Mobile App Development
  2. Workflow Automation, AI Tool Integrations & Internal Tools
  3. Overflow Engineering Teams & Staff Augmentation (sprint support, backlog elimination)
  4. Project Support & Technical Execution (MVP builds, platform refactoring, technical debt)
- **Actionable Outreach Priorities**: Automatically calculates sales prioritization:
  - `P1 - Urgent Outreach` (Hot, Score $\ge 85$)
  - `P1 - High Priority` (Hot, Score $70\text{--}84$)
  - `P2 - Medium Priority` (Warm, Score $50\text{--}69$)
  - `P3 - Low Priority` (Warm, Score $35\text{--}49$)
  - `P4 - Do Not Contact` (Cold, Score $0\text{--}34$)
  - `Needs Research` (Insufficient Information)
- **CRM-Ready Clean CSV Export**: One-click export providing a formatted, sales-ready CSV containing Company Name, Website, Domain, Industry, Category, Score, Outreach Priority, Target Services, Extracted Evidence, Evidence Validated, and Decision Rationale.
- **Dedicated "Needs Research" Category**: Sparse, placeholder (`"N/A"`, `"TBD"`), or ambiguous descriptions are categorized as **Needs Research** with Low confidence rather than incorrectly mislabeled as Cold.
- **Resilient Error Isolation (Unscored Status)**: API or network errors are marked as **Unscored / Error** with no numeric score, preventing failed API calls from polluting pipeline metrics.

---

## 📐 Scoring Criteria (Blackfold Profile)

| Category | Score Range | Criteria & Triggers | Outreach Priority | Confidence |
| :--- | :---: | :--- | :---: | :---: |
| **🔥 Hot** | **70 – 100** | Explicit indicators of technical bottlenecks: engineering team overwhelmed, development backlog, launching new platform/MVP with lean team, manual spreadsheets urgently needing automation, or digital agency needing dev execution partner. | **P1 - Urgent / High** | **High / Medium** |
| **☀️ Warm** | **35 – 69** | Operates in tech, e-commerce, digital services, healthcare, or logistics with operational systems that benefit from custom tools, integrations, or periodic dev support, but without an immediate sprint crisis. | **P2 / P3 - Medium / Low** | **Medium / High** |
| **❄️ Cold** | **0 – 34** | Non-digital brick-and-mortar local shops (bakery, landscaping); 100% in-house software engineering; massive conglomerates with closed IT procurement; or zero software/automation demand. | **P4 - Do Not Contact** | **High / Medium** |
| **🔍 Needs Research** | **0 – 34** | Missing, placeholder (`"N/A"`, `"TBD"`), or brief/vague descriptions ($< 30$ characters) that lack substantive facts to evaluate technical needs. | **Needs Research** | **Low** |
| **⚠️ Unscored** | **None** | Records that encountered API connection timeouts, quota limits, or parsing errors during batch processing. | **Unscored / Error** | **N/A** |

---

## 📊 Benchmark Results (30 Manually Reviewed Leads)

The scoring engine was benchmarked against 30 manually reviewed leads spanning diverse industries ([`data/sample_leads_30.csv`](file:///data/sample_leads_30.csv)):

```text
============================================================
BENCHMARK RESULTS: 30/30 MATCHES (100.0% ACCURACY)
============================================================

Per-Category Performance:
Category         | Expected   | Predicted  | Match Rate  
-------------------------------------------------------
Hot              | 11         | 11         | 100.0%
Warm             | 10         | 10         | 100.0%
Cold             | 5          | 5          | 100.0%
Needs Research   | 4          | 4          | 100.0%

- Grounded & Verified Evidence Quotes: 30/30 (100.0%)
- Duplicates Detected & Redundant API Calls Avoided: 1 lead (100%)
- Clean CRM Export Generated: data/sample_leads_scored.csv
```

To re-run the 30-lead benchmark at any time:
```bash
python benchmark_test.py
```

### ⚡ Live Gemini LLM Benchmark Runner

To evaluate actual live Google Gemini API scoring against manually reviewed leads:
```bash
# Using key in .env or passing directly via CLI:
python benchmark_live_gemini.py --api-key YOUR_GEMINI_API_KEY
```
This tests live latency, structured JSON generation, anti-hallucination evidence validation, and graceful error isolation.

---

## 📁 Repository Structure

```text
lead-scorer/
├── .env.example                # Template for API keys and configuration
├── .gitignore                  # Git ignore rules for Python, virtual environments, secrets
├── README.md                   # Complete documentation and setup guide
├── requirements.txt            # Python dependencies
├── app.py                      # Streamlit web application with Blackfold profile & clean export
├── benchmark_test.py           # Automated 30-lead benchmark evaluation script
├── benchmark_live_gemini.py    # Live Gemini API benchmark runner & accuracy evaluator
├── src/
│   ├── __init__.py             # Package marker
│   ├── config.py               # Profile configuration (Blackfold / General) and model defaults
│   ├── models.py               # Pydantic schemas, OutreachPriority, and score range validators
│   ├── prompt.py               # Grounded system instructions for Blackfold & General profiles
│   ├── validator.py            # CSV validation, domain extractor, and strict evidence grounder
│   └── scorer.py               # Content-aware deduplication cache, regex engine, and API client
├── data/
│   ├── sample_leads.csv        # 30 realistic test leads across diverse industries
│   ├── sample_leads_30.csv     # 30-lead benchmark dataset with ground-truth labels
│   └── sample_leads_scored.csv # Full evaluated clean outreach output baseline
└── tests/
    ├── __init__.py             # Test package marker
    ├── test_validator.py       # Tests for CSV parser, domain extractor, strict evidence validation
    └── test_scorer.py          # Tests for scoring logic, deduplication cache, Blackfold profile
```

---

## 🚀 Quickstart & Local Installation

### 1. Prerequisites
- **Python 3.10+** installed. Check with:
  ```bash
  python --version
  ```

### 2. Clone the Repository
```bash
git clone https://github.com/arslaanalam700-web/task3.git
cd task3
```

### 3. Create and Activate a Virtual Environment
- **On Windows (PowerShell):**
  ```powershell
  python -m venv venv
  .\venv\Scripts\Activate.ps1
  ```
- **On macOS / Linux:**
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  ```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Configure API Key
1. Copy the example file:
   ```bash
   cp .env.example .env
   ```
   *(On Windows PowerShell: `Copy-Item .env.example .env`)*
2. Obtain a free API key from [Google AI Studio](https://aistudio.google.com/).
3. Open `.env` and insert your key:
   ```env
   GEMINI_API_KEY=your_actual_gemini_api_key_here
   GEMINI_MODEL=gemini-2.5-flash
   SCORING_PROFILE=blackfold
   ```
*(Note: If you don't have an API key right now, you can run the app immediately using the built-in **Offline Demo Mode**!)*

### 6. Run the Streamlit App
```bash
streamlit run app.py
```
The app will open automatically in your browser at `http://localhost:8501`.

---

## 🧪 Running Automated Tests

Run the complete test suite using `pytest`:

```bash
python -m pytest -v
```

All 20 unit tests pass:
- Evidence grounding validation (`validate_evidence`)
- Deduplication caching avoiding repeated API calls
- Blackfold-specific scoring logic (Dev, Automation, Overflow)
- API failures marked as `Unscored` (score=None) instead of `Cold`
- Insufficient data routed to `Needs Research` with Low confidence
- Fair agency evaluation (not auto-Cold)
- Word-boundary regex keyword matching (prevents false positives)
- Pydantic score-to-category alignment validation (Hot: 70-100, Warm: 35-69, Cold: 0-34, Needs Research: 0-34)
- Domain extraction and duplicate lead detection across varying URL formats
- CSV header normalization, synonyms, and row limits

---

## 🌐 Free Deployment (Streamlit Community Cloud)

You can deploy this application for free on **Streamlit Community Cloud** in less than 5 minutes:

1. **Push your code to GitHub**:
   ```bash
   git add .
   git commit -m "feat: add Blackfold profile, evidence verification, and deduplication caching"
   git push origin main
   ```
2. **Deploy on Streamlit Cloud**:
   - Go to [share.streamlit.io](https://share.streamlit.io/) and sign in with GitHub.
   - Click **"New app"**.
   - Select your repository (`arslaanalam700-web/task3`), branch (`main`), and set Main file path to `app.py`.
   - Click **"Advanced settings..."**.
   - Under **Secrets**, add your API key:
     ```toml
     GEMINI_API_KEY = "your_actual_gemini_api_key_here"
     ```
   - Click **"Deploy!"**. Your live app will be accessible at a public URL.

---

## 🛡️ License

MIT License. Free for personal, commercial, and educational use.
