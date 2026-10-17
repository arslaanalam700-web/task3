# 🎯 AI Lead Scoring Tool

A clean, production-ready Streamlit application that evaluates B2B company leads using Google Gemini LLMs to classify their likelihood of needing **outsourced business services** (e.g., Bookkeeping/Accounting, IT Support/Helpdesk, Customer Support, HR/Recruiting, Legal/Compliance, and Digital Marketing).

Built with Python, Streamlit, Pydantic, and Google's official `google-genai` SDK.

---

## 🌟 Key Features & Improvements

- **Evidence-Backed Justifications**: For every lead evaluated, the AI extracts and quotes direct evidence from the company's description to justify its score and categorization.
- **Strict Score-to-Category Alignment**: Enforced by Pydantic model validation:
  - **🔥 Hot**: Scores strictly between **70 and 100**.
  - **☀️ Warm**: Scores strictly between **35 and 69**.
  - **❄️ Cold**: Scores strictly between **0 and 34**.
  - **🔍 Needs Research**: Scores strictly between **0 and 34** with guaranteed **Low confidence**.
- **Fair Agency & BPO Assessment**: Marketing agencies, IT consultancies, and BPO providers are **not** automatically classified as Cold. They are evaluated on their operational demands (e.g., an agency seeking outsourced bookkeeping, payroll, or IT support is qualified as Warm or Hot).
- **Dedicated "Needs Research" Category**: Sparse, placeholder (`"N/A"`, `"TBD"`), or ambiguous descriptions are categorized as **Needs Research** rather than incorrectly labeled Cold.
- **Resilient Error Isolation (Unscored Status)**: API or network errors are marked as **Unscored / Error** with no numeric score, preventing failed API calls from polluting Cold lead metrics.
- **Website Domain Duplicate Detection**: Extracts canonical domains (`extract_domain`) to detect and flag duplicate company entries across varying URLs (e.g., `https://novatechcloud.io/about` vs `https://www.novatechcloud.io/contact`).
- **Dual Execution Engine**:
  - **Live Gemini API**: Connects to Google's generous free-tier models (`gemini-2.5-flash`, `gemini-2.0-flash`, `gemini-1.5-flash`).
  - **Offline Demo Mode**: Word-boundary regex matching engine with evidence extraction for instant, deterministic testing without an API key or internet connection.
- **Interactive Streamlit Interface**:
  - KPI metric cards (Total Leads, Hot %, Warm %, Cold %, Needs Research %, Unscored).
  - Domain duplicate warning banner.
  - Multi-category filters and keyword search over company name, industry, and extracted evidence.
  - Deep-dive card view for examining decision rationales and target services.
  - One-click CSV export with evidence, domain, and duplicate status.
  - Built-in sample CSV download button.

---

## 📐 Scoring Criteria (Outsourced Business Services)

| Category | Score Range | Criteria & Triggers | Confidence |
| :--- | :---: | :--- | :---: |
| **🔥 Hot** | **70 – 100** | Explicit signals of rapid growth (Series A/B, doubling orders, expanding footprint), lean core teams, overwhelmed operations, acute customer service backlogs, or urgent hiring bottlenecks. | **High / Medium** |
| **☀️ Warm** | **35 – 69** | Operates in an industry with steady back-office outsourcing needs (healthcare clinics, law firms, wealth management, freight logistics, e-commerce, **or growing marketing agencies / BPOs needing back-office help**), without an acute growth crisis. | **Medium / High** |
| **❄️ Cold** | **0 – 34** | Explicitly maintains 100% in-house operations with zero external vendors; massive conglomerates with fully centralized internal departments; micro-local shops with no operating budget; or zero operational demand. | **High / Medium** |
| **🔍 Needs Research** | **0 – 34** | Missing, placeholder (`"N/A"`, `"TBD"`, `"coming soon"`), or brief/vague descriptions (< 30 characters) that lack substantive facts to evaluate outsourcing needs. | **Low** |
| **⚠️ Unscored** | **None** | Records that encountered API connection timeouts, quota limits, or parsing errors during batch processing. | **N/A** |

---

## 📁 Repository Structure

```text
lead-scorer/
├── .env.example              # Template for API keys and configuration
├── .gitignore                # Git ignore rules for Python, virtual environments, secrets
├── README.md                 # Project documentation and setup guide
├── requirements.txt          # Python dependencies
├── app.py                    # Streamlit web application
├── src/
│   ├── __init__.py           # Package marker
│   ├── config.py             # Environment variable and model configuration
│   ├── models.py             # Pydantic schemas, validation rules, and duplicate tracking
│   ├── prompt.py             # Grounded system instructions, rubric, and evidence requirement
│   ├── validator.py          # CSV schema validation, domain extractor, duplicate detection
│   └── scorer.py             # Gemini API client, regex mock engine, and batch coordinator
├── data/
│   ├── sample_leads.csv        # 20 realistic test leads across diverse industries
│   └── sample_leads_scored.csv # Full evaluated baseline output for the 20 test leads
└── tests/
    ├── __init__.py           # Test package marker
    ├── test_validator.py     # Unit tests for CSV parser, domain extractor, and duplicates
    └── test_scorer.py        # Unit tests for scoring logic, Unscored errors, and evidence
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

All 15 unit tests pass:
- API failures marked as `Unscored` (score=None) instead of `Cold`
- Insufficient data routed to `Needs Research` with Low confidence
- Fair agency evaluation (not auto-Cold)
- Word-boundary regex keyword matching (prevents false positives)
- Direct evidence quote extraction from input text
- Pydantic score-to-category alignment validation (Hot: 70-100, Warm: 35-69, Cold: 0-34, Needs Research: 0-34)
- Domain extraction and duplicate lead detection across varying URL formats
- CSV header normalization, synonyms, and row limits

---

## 🌐 Free Deployment (Streamlit Community Cloud)

You can deploy this application for free on **Streamlit Community Cloud** in less than 5 minutes:

1. **Push your code to GitHub**:
   ```bash
   git add .
   git commit -m "feat: improve scoring accuracy, evidence extraction, and duplicate detection"
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

## 📊 Sample Data

The repository includes a ready-to-use dataset with 20 realistic leads spanning diverse scenarios:
- **Hot Leads**: Venture-backed SaaS (`NovaTech Cloud`), freight brokerage with invoice bottlenecks (`Apex Logistics`), high-growth DTC apparel (`SwiftCommerce`), scaling HVAC franchise (`BlueSky Comfort`), clinical diagnostic laboratory (`BioPure Diagnostics`).
- **Warm Leads**: Dental clinic group (`GreenLeaf Dental`), boutique litigation law firm (`Harbor View Law`), physical rehabilitation clinic (`Summit Physical Therapy`), boutique wealth management (`Vanguard Wealth Advisors`), **plus growing agencies and BPOs needing back-office help** (`OmniConnect BPO Services`, `CreativePulse Media`, `Zenith IT Managed Solutions`).
- **Cold Leads**:
  - *In-house Enterprise*: Fortune 50 hardware conglomerate with 85k employees (`Global Tech Titan`).
  - *Micro-local*: Neighborhood artisanal bakery (`Heritage Bakery`).
- **Needs Research Leads**: Sparse or placeholder descriptions (`Project Ghost Stealth`, `StealthCo`).
- **Duplicate Detection**: `NovaTech Cloud Secondary` sharing canonical domain `novatechcloud.io`.

Check [`data/sample_leads.csv`](file:///data/sample_leads.csv) and [`data/sample_leads_scored.csv`](file:///data/sample_leads_scored.csv) to inspect the raw input and full evaluated outputs.

---

## 🛡️ License

MIT License. Free for personal, commercial, and educational use.
