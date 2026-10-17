# 🎯 AI Lead Scoring Tool

A clean, production-ready Streamlit application that evaluates B2B company leads using Google Gemini LLMs to classify their likelihood of needing **outsourced business services** (e.g., Bookkeeping, IT Support, Customer Support, HR/Recruiting, and Digital Marketing).

Built with Python, Streamlit, Pydantic, and Google's official `google-genai` SDK.

---

## 🌟 Key Features

- **Strict Grounding & Anti-Hallucination**: The model evaluates leads *strictly* on the provided CSV details. If information is sparse or missing, it explicitly marks the confidence as **Low** and flags insufficient data rather than inventing company details.
- **Structured JSON Output**: Uses schema-enforced JSON generation validated via **Pydantic** (`LeadScoreOutput`), ensuring uniform data types, scores (0-100), and categories.
- **Error Isolation**: Individual API failures or network hiccups do not crash the batch. Failed leads are tagged with an error status while preserving all successful evaluations.
- **Dual Execution Engine**:
  - **Live Gemini API**: Connects to Google's generous free-tier models (`gemini-2.5-flash`, `gemini-2.0-flash`, `gemini-1.5-flash`).
  - **Offline Demo Mode**: Fast, deterministic local heuristic evaluator that allows instant testing without an API key or internet connection.
- **Flexible CSV Ingestion**: Case-insensitive column synonym matching (`company_name` / `name` / `company`, `description` / `about` / `overview`), null checking, and validation feedback.
- **Interactive Streamlit Interface**:
  - Real-time progress bar and status indicator.
  - KPI metric cards (Total Leads, Hot %, Warm %, Cold %, Errors).
  - Search and category filters.
  - Deep-dive card view for reviewing decision rationales and target services.
  - One-click CSV export of full evaluation results.
  - Built-in sample CSV download button.

---

## 📐 Scoring Criteria (Outsourced Business Services)

| Category | Score Range | Criteria & Triggers | Confidence |
| :--- | :---: | :--- | :---: |
| **🔥 Hot** | **70 – 100** | Explicit signals of rapid growth (Series A/B, doubling orders, expanding footprint), lean core teams, overwhelmed operations, acute customer service backlogs, or urgent hiring bottlenecks. | **High / Medium** |
| **☀️ Warm** | **35 – 69** | Operates in an industry where outsourcing non-core functions is standard (e.g., medical clinics, law firms, boutique wealth management, regional logistics, custom trade shops), but lacks an explicit growth crisis. | **Medium / High** |
| **❄️ Cold** | **0 – 34** | Competitors / BPO agencies / IT MSPs that sell outsourced services themselves; giant enterprises with dedicated in-house departments; 100% in-house operations; micro-shops with no budget; or **insufficient/blank descriptions**. | **High / Low** |

> **Insufficient Data Handling**: When descriptions are blank, placeholder (e.g., `"N/A"`, `"Stealth"`), or under 20-30 characters without actionable operational details, the lead is classified as **Cold (Score <= 30)** with **Low Confidence** and the explanation: *"Insufficient information provided in the input data to determine outsourcing need."*

---

## 📁 Repository Structure

```text
lead-scorer/
├── .env.example             # Template for API keys and configuration
├── .gitignore                # Git ignore rules for Python, virtual environments, secrets
├── README.md                 # Project documentation and setup guide
├── requirements.txt          # Python dependencies
├── app.py                    # Streamlit web application
├── src/
│   ├── __init__.py           # Package marker
│   ├── config.py             # Environment variable and model configuration
│   ├── models.py             # Pydantic models for input validation and structured output
│   ├── prompt.py             # Grounded system instructions and scoring prompts
│   ├── validator.py          # CSV schema validation and column normalization
│   └── scorer.py             # Gemini API client, mock engine, and batch coordinator
├── data/
│   ├── sample_leads.csv        # 20 realistic test leads across diverse industries
│   └── sample_leads_scored.csv # Baseline evaluation output for the 20 test leads
└── tests/
    ├── __init__.py           # Test package marker
    ├── test_validator.py     # Unit tests for CSV parser, headers, and edge cases
    └── test_scorer.py        # Unit tests for scoring heuristics, Pydantic, and error isolation
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
git clone https://github.com/your-username/lead-scorer.git
cd lead-scorer
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
*(Note: If you don't have an API key right now, you can still run the app immediately using the built-in **Offline Demo Mode**!)*

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

All 13 unit tests should pass:
- CSV header normalization and synonym matching
- Missing column and empty file handling
- Trivial/blank row filtering and batch size restrictions
- Hot, Warm, Cold, and Insufficient Data scoring logic
- Pydantic schema validation and constraint enforcement
- Single-lead error isolation and batch progress callback

---

## 🌐 Free Deployment (Streamlit Community Cloud)

You can deploy this application for free on **Streamlit Community Cloud** in less than 5 minutes:

1. **Push your code to GitHub**:
   ```bash
   git init
   git add .
   git commit -m "Initial commit of AI Lead Scoring tool"
   git branch -M main
   git remote add origin https://github.com/<your-username>/<your-repo-name>.git
   git push -u origin main
   ```
2. **Deploy on Streamlit Cloud**:
   - Go to [share.streamlit.io](https://share.streamlit.io/) and sign in with GitHub.
   - Click **"New app"**.
   - Select your repository (`<your-username>/<your-repo-name>`), branch (`main`), and set Main file path to `app.py`.
   - Click **"Advanced settings..."**.
   - Under **Secrets**, add your API key in TOML format:
     ```toml
     GEMINI_API_KEY = "your_actual_gemini_api_key_here"
     ```
   - Click **"Deploy!"**. Your live app will be accessible at a public URL.

---

## 📊 Sample Data

The repository includes a ready-to-use dataset with 20 realistic leads spanning diverse scenarios:
- **Hot Leads**: Venture-backed SaaS (`NovaTech Cloud`), freight brokerage with invoice bottlenecks (`Apex Logistics`), high-growth DTC apparel (`SwiftCommerce`), scaling HVAC franchise (`BlueSky Comfort`), clinical diagnostic laboratory (`BioPure Diagnostics`).
- **Warm Leads**: Dental clinic group (`GreenLeaf Dental`), boutique litigation law firm (`Harbor View Law`), physical rehabilitation clinic (`Summit Physical Therapy`), boutique wealth management (`Vanguard Wealth Advisors`).
- **Cold Leads**:
  - *Competitors/Providers*: BPO call center (`OmniConnect`), digital marketing agency (`CreativePulse`), IT MSP (`Zenith IT`).
  - *In-house Enterprise*: Fortune 50 hardware conglomerate with 85k employees (`Global Tech Titan`).
  - *Micro-local*: Neighborhood artisanal bakery (`Heritage Bakery`).
  - *Insufficient Data*: Sparse edge cases (`Project Ghost Stealth`, `StealthCo`).

Check [`data/sample_leads.csv`](file:///data/sample_leads.csv) and [`data/sample_leads_scored.csv`](file:///data/sample_leads_scored.csv) to inspect the raw input and full evaluated outputs.

---

## 🛡️ License

MIT License. Free for personal, commercial, and educational use.
