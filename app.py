import io
import os
import time
from datetime import datetime
import pandas as pd
import streamlit as st

from src.config import get_api_key, DEFAULT_MODEL, AVAILABLE_MODELS, MAX_LEADS_PER_BATCH
from src.validator import validate_and_parse_csv
from src.scorer import batch_score_leads
from src.models import ScoredLead

# Streamlit Page Setup
st.set_page_config(
    page_title="AI Lead Scoring Tool",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling for modern cards and badges
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        margin-bottom: 0.2rem;
        color: #1E293B;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #64748B;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 1rem;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)


def load_sample_csv() -> bytes:
    """Read bundled sample leads CSV for quick testing."""
    sample_path = os.path.join(os.path.dirname(__file__), "data", "sample_leads.csv")
    if os.path.exists(sample_path):
        with open(sample_path, "rb") as f:
            return f.read()
    return b""


# --- Sidebar ---
st.sidebar.title("⚙️ Settings")

# Execution Mode
mode = st.sidebar.radio(
    "Evaluation Engine",
    ["Gemini API (Live)", "Offline Demo Mode (No Key Required)"],
    help="Demo Mode uses deterministic regex and keyword evaluation so you can test immediately without an API key."
)
use_mock = mode == "Offline Demo Mode (No Key Required)"

api_key_env = get_api_key()
if not use_mock:
    api_key_input = st.sidebar.text_input(
        "Google Gemini API Key",
        value=api_key_env,
        type="password",
        placeholder="Enter AI Studio API key...",
        help="Free API key from https://aistudio.google.com/"
    )
    selected_model = st.sidebar.selectbox(
        "Gemini Model",
        AVAILABLE_MODELS,
        index=AVAILABLE_MODELS.index(DEFAULT_MODEL) if DEFAULT_MODEL in AVAILABLE_MODELS else 0
    )
    if not api_key_input:
        st.sidebar.info("💡 No API key detected. Add `GEMINI_API_KEY` to `.env` or switch to **Offline Demo Mode** above.")
else:
    api_key_input = ""
    selected_model = "offline-mock"
    st.sidebar.success("⚡ Running in Offline Demo Mode. Fast, deterministic, zero network calls.")

# Scoring Rubric Documentation in Sidebar
with st.sidebar.expander("📖 Scoring Criteria"):
    st.markdown("""
    **Target Need**: Outsourced Business Services (IT, Bookkeeping, Customer Support, HR, Legal, Marketing)

    - **🔥 Hot (70-100)**: Explicit expansion signals, funding, hiring bottlenecks, overwhelmed operations, rapid scaling with lean teams.
    - **☀️ Warm (35-69)**: Standard businesses in industries with natural back-office outsourcing needs (including growing agencies and BPOs), but without urgent growth crises.
    - **❄️ Cold (0-34)**: Explicitly 100% in-house operations, massive conglomerates with internal departments, or zero operational demand.
    - **🔍 Needs Research (0-34)**: Insufficient, placeholder, or ambiguous information requiring further data gathering.
    - **⚠️ Unscored**: API, network, or parsing errors isolated from lead categories.
    """)

# --- Main Page Header ---
st.markdown("<div class='main-header'>🎯 AI Lead Scoring Tool</div>", unsafe_allow_html=True)
st.markdown(
    "<div class='sub-header'>Upload company leads to automatically analyze their likelihood to need "
    "outsourced business services using Google Gemini.</div>",
    unsafe_allow_html=True
)

# Sample file helper banner
col_lead_info, col_sample_btn = st.columns([3, 1])
with col_lead_info:
    st.write("Need a test dataset? Download our 20-lead sample file containing realistic test companies across various industries.")
with col_sample_btn:
    sample_data = load_sample_csv()
    if sample_data:
        st.download_button(
            label="📥 Download Sample CSV",
            data=sample_data,
            file_name="sample_leads.csv",
            mime="text/csv",
            use_container_width=True
        )

st.divider()

# --- File Uploader ---
uploaded_file = st.file_uploader(
    "Choose a CSV file containing leads (Required columns: Company Name, Description)",
    type=["csv"],
    help="Max 100 rows per batch. Columns supported: company_name, website, industry, description."
)

if uploaded_file is not None:
    file_bytes = uploaded_file.getvalue()
    is_valid, err_msg, leads, normalized_df = validate_and_parse_csv(file_bytes, max_rows=MAX_LEADS_PER_BATCH)

    if not is_valid:
        st.error(f"❌ Input Validation Error: {err_msg}")
    else:
        st.success(f"✅ CSV validated successfully: **{len(leads)} leads** detected.")

        # Duplicate company warning banner
        dup_count = sum(1 for l in leads if l.is_duplicate)
        if dup_count > 0:
            st.warning(f"⚠️ **Duplicate Detection**: {dup_count} duplicate lead(s) detected based on website domain or company name.")

        with st.expander("👀 Preview Uploaded Data (First 5 Rows)", expanded=False):
            st.dataframe(normalized_df.head(5), use_container_width=True)

        # Action Button to run scoring
        start_button = st.button("🚀 Analyze & Score Leads", type="primary", use_container_width=False)

        if start_button:
            if not use_mock and not api_key_input:
                st.error("⚠️ Please provide a Gemini API Key in the sidebar or toggle 'Offline Demo Mode' to proceed.")
            else:
                progress_bar = st.progress(0)
                status_text = st.empty()

                def update_progress(current: int, total: int, company_name: str):
                    pct = current / total
                    progress_bar.progress(pct)
                    status_text.markdown(f"**Analyzing lead {current} of {total}:** *{company_name}*...")

                start_time = time.time()
                scored_results = batch_score_leads(
                    leads=leads,
                    api_key=api_key_input,
                    model_name=selected_model,
                    use_mock=use_mock,
                    progress_callback=update_progress,
                    delay_between_calls=0.3
                )
                duration = round(time.time() - start_time, 1)

                progress_bar.empty()
                status_text.empty()
                st.toast(f"Completed {len(scored_results)} leads in {duration}s!", icon="🎉")

                # Store in session state for persistence across re-renders
                st.session_state["results"] = scored_results

# --- Display Results ---
if "results" in st.session_state and st.session_state["results"]:
    results: list[ScoredLead] = st.session_state["results"]
    results_df = pd.DataFrame([r.model_dump() for r in results])

    st.subheader("📊 Lead Evaluation Summary")

    total_leads = len(results_df)
    hot_count = len(results_df[results_df["category"] == "Hot"])
    warm_count = len(results_df[results_df["category"] == "Warm"])
    cold_count = len(results_df[results_df["category"] == "Cold"])
    research_count = len(results_df[results_df["category"] == "Needs Research"])
    unscored_count = len(results_df[results_df["category"] == "Unscored"])

    # Executive KPI Metric Cards
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Total Leads", total_leads)
    m2.metric("🔥 Hot Leads", hot_count, f"{round((hot_count/total_leads)*100)}%" if total_leads else "0%")
    m3.metric("☀️ Warm Leads", warm_count, f"{round((warm_count/total_leads)*100)}%" if total_leads else "0%")
    m4.metric("❄️ Cold Leads", cold_count, f"{round((cold_count/total_leads)*100)}%" if total_leads else "0%")
    m5.metric("🔍 Needs Research", research_count, f"{round((research_count/total_leads)*100)}%" if total_leads else "0%")
    m6.metric("⚠️ Unscored/Errors", unscored_count)

    st.divider()

    # Filters and Search
    st.subheader("📋 Scored Leads Table")
    f_col1, f_col2 = st.columns([1, 2])
    
    available_categories = ["Hot", "Warm", "Cold", "Needs Research"]
    if unscored_count > 0:
        available_categories.append("Unscored")

    with f_col1:
        category_filter = st.multiselect(
            "Filter by Category",
            options=available_categories,
            default=available_categories
        )
    with f_col2:
        search_query = st.text_input("🔍 Search Company, Industry, or Evidence", placeholder="Type to filter...")

    filtered_df = results_df[results_df["category"].isin(category_filter)].copy()
    if search_query:
        query = search_query.strip().lower()
        filtered_df = filtered_df[
            filtered_df["company_name"].str.lower().str.contains(query) |
            filtered_df["industry"].str.lower().str.contains(query) |
            filtered_df["evidence"].str.lower().str.contains(query)
        ]

    # Format table for display
    display_cols = [
        "company_name", "category", "score", "confidence",
        "industry", "evidence", "potential_services", "explanation", "status"
    ]
    renamed_cols = {
        "company_name": "Company",
        "category": "Category",
        "score": "Score",
        "confidence": "Confidence",
        "industry": "Industry",
        "evidence": "Extracted Evidence",
        "potential_services": "Target Services",
        "explanation": "Decision Rationale",
        "status": "Status"
    }

    # Format score for display (handle None for unscored/errors)
    display_df = filtered_df[display_cols].copy()
    display_df["score"] = display_df["score"].apply(lambda s: f"{s}/100" if pd.notnull(s) else "—")

    st.dataframe(
        display_df.rename(columns=renamed_cols),
        use_container_width=True,
        hide_index=True,
    )

    # Detailed cards view
    with st.expander("🔎 Deep-Dive Lead Cards & Evidence", expanded=False):
        for idx, row in filtered_df.iterrows():
            if row["category"] == "Hot":
                cat_icon = "🔥"
            elif row["category"] == "Warm":
                cat_icon = "☀️"
            elif row["category"] == "Cold":
                cat_icon = "❄️"
            elif row["category"] == "Needs Research":
                cat_icon = "🔍"
            else:
                cat_icon = "⚠️"

            score_str = f"{row['score']}/100" if pd.notnull(row['score']) else "Unscored"
            dup_badge = " *(Duplicate)*" if row.get("is_duplicate") else ""
            st.markdown(f"#### {cat_icon} {row['company_name']}{dup_badge} — **{row['category']}** ({score_str})")
            
            c1, c2 = st.columns([1, 2])
            with c1:
                st.write(f"**Industry:** {row['industry']}")
                st.write(f"**Website / Domain:** {row['website'] if row['website'] else 'N/A'}")
                st.write(f"**Confidence:** {row['confidence']}")
                st.write(f"**Target Services:** {row['potential_services']}")
            with c2:
                st.write(f"**Input Description:** *{row['description']}*")
                st.markdown(f"**Direct Evidence:** `{row['evidence']}`")
                st.write(f"**Rationale:** {row['explanation']}")
                if row["status"] == "ERROR":
                    st.error(f"Error detail: {row['error_message']}")
            st.divider()

    # CSV Download Button
    csv_buffer = io.StringIO()
    results_df.to_csv(csv_buffer, index=False)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    st.download_button(
        label="📥 Download Scored Results (CSV)",
        data=csv_buffer.getvalue().encode("utf-8"),
        file_name=f"lead_scoring_results_{timestamp}.csv",
        mime="text/csv",
        type="primary"
    )
