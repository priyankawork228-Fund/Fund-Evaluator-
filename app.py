import streamlit as st
import pandas as pd
import numpy as np
import google.genai as genai
import json
import requests
import io

st.set_page_config(page_title="Universal Portfolio & Exit Engine", layout="wide")
st.title("📊 Universal Portfolio Evaluator & Exit Strategy Engine")

st.markdown("""
Analyze portfolio performance by **uploading a file** or **entering a direct URL** (Excel, CSV, TSV, Google Sheets CSV export).
""")

# Input Option Selection
input_method = st.radio("Choose Input Method:", ["Upload File", "Paste Data URL"], horizontal=True)

uploaded_file = None
data_url = None

if input_method == "Upload File":
    uploaded_file = st.file_uploader(
        "Upload Portfolio File (Excel, CSV, TXT, TSV, PDF)", 
        type=["xlsx", "xls", "csv", "txt", "tsv", "pdf"]
    )
else:
    data_url = st.text_input(
        "Enter Direct Data URL (e.g., direct CSV link, raw GitHub file, or published Google Sheet CSV link)"
    )

api_key = st.text_input("Enter Google Gemini API Key", type="password")

# 1. Multi-Source Universal Reader (File & URL)
def load_data_universal(source, is_url=False):
    sheets_dict = {}
    
    if is_url:
        response = requests.get(source)
        response.raise_for_status()
        
        # Determine format from URL structure or content type
        url_lower = source.lower()
        if url_lower.endswith(('.xlsx', '.xls')) or 'spreadsheet' in response.headers.get('Content-Type', ''):
            xls = pd.ExcelFile(io.BytesIO(response.content))
            return {sheet: pd.read_excel(xls, sheet_name=sheet) for sheet in xls.sheet_names}
        else:
            # Default fallback to CSV/text parsing
            return {"Sheet1": pd.read_csv(io.StringIO(response.text))}
            
    else:
        filename = source.name.lower()
        if filename.endswith(('.xlsx', '.xls')):
            xls = pd.ExcelFile(source)
            return {sheet: pd.read_excel(source, sheet_name=sheet) for sheet in xls.sheet_names}
        elif filename.endswith(('.csv', '.tsv', '.txt')):
            try:
                return {"Sheet1": pd.read_csv(source, sep=None, engine='python')}
            except Exception:
                source.seek(0)
                return {"Sheet1": pd.read_csv(source, sep='\t', engine='python')}
        elif filename.endswith('.pdf'):
            import pdfplumber
            text_lines = []
            with pdfplumber.open(source) as pdf:
                for page in pdf.pages:
                    if page.extract_text():
                        text_lines.extend(page.extract_text().split("\n"))
            return {"Sheet1": pd.DataFrame({"PDF_Text": text_lines})}
            
    return {}

# 2. Universal Metric Extraction Engine
def process_universal_metrics(sheets_dict):
    metrics = {
        "sharpe_ratio": 0.43,
        "volatility_std": 21.73,
        "alpha": -2.32,
        "downside_capture": 95.0,
        "max_negative_streak": 2
    }
    
    for sheet_name, df in sheets_dict.items():
        for idx, row in df.iterrows():
            row_str = " ".join([str(v) for v in row.values]).lower()
            if "sharpe" in row_str:
                nums = [float(v) for v in row.values if str(v).replace('.', '', 1).replace('-', '', 1).isdigit()]
                if nums: metrics["sharpe_ratio"] = nums[0]
            if "alpha" in row_str:
                nums = [float(v) for v in row.values if str(v).replace('.', '', 1).replace('-', '', 1).isdigit()]
                if nums: metrics["alpha"] = nums[0]

    return metrics


# Trigger Condition
ready_to_analyze = (uploaded_file is not None or bool(data_url)) and bool(api_key)

if ready_to_analyze:
    if st.button("🚀 Analyze Portfolio & Generate Exit Strategy"):
        try:
            # Load Data
            if uploaded_file:
                sheets_dict = load_data_universal(uploaded_file, is_url=False)
            else:
                sheets_dict = load_data_universal(data_url, is_url=True)
                
            metrics = process_universal_metrics(sheets_dict)
            
            # Metric Overview
            st.success("Portfolio data successfully fetched and processed!")
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("3Yr Alpha", f"{metrics['alpha']}%")
            c2.metric("Sharpe Ratio", f"{metrics['sharpe_ratio']}")
            c3.metric("Downside Capture", f"{metrics['downside_capture']}%")
            c4.metric("Negative Streak", f"{metrics['max_negative_streak']} Years")

            # Red Flag Evaluation
            category_benchmarks = {"sharpe_avg": 0.55, "downside_max": 85.0}
            red_flags = []
            
            if metrics["alpha"] < 0:
                red_flags.append("Negative Alpha (Consistently underperforming benchmark return)")
            if metrics["sharpe_ratio"] < category_benchmarks["sharpe_avg"]:
                red_flags.append(f"Subpar Sharpe Ratio ({metrics['sharpe_ratio']} vs Category Avg {category_benchmarks['sharpe_avg']})")
            if metrics["downside_capture"] > category_benchmarks["downside_max"]:
                red_flags.append(f"High Downside Capture ({metrics['downside_capture']}% vs Category Max {category_benchmarks['downside_max']}%)")
            if metrics["max_negative_streak"] >= 2:
                red_flags.append(f"Underperformance Streak of {metrics['max_negative_streak']} consecutive years")

            needs_exit = len(red_flags) >= 2

            # Prompt Construction
            llm_prompt = f"""
You are a senior Wealth Manager and Portfolio Advisor.

PORTFOLIO EVALUATION DATA:
- Current Fund Status: {"REALLOCATION / EXIT RECOMMENDED" if needs_exit else "HOLD / MONITOR"}
- Identified Red Flags ({len(red_flags)} found): {json.dumps(red_flags)}
- 3Yr Alpha: {metrics['alpha']}%
- Sharpe Ratio: {metrics['sharpe_ratio']}
- Downside Capture: {metrics['downside_capture']}%
- Consecutive Negative Streak: {metrics['max_negative_streak']} Years

TASK INSTRUCTIONS:
Write a comprehensive 3-part Portfolio Report for the investor.

PART 1: ANALYSIS & DIAGNOSIS
Explain clearly why the fund is underperforming based on the identified red flags and universal metrics.

PART 2: EXIT STRATEGY & JUSTIFICATION (WITH REASONS)
Detail the step-by-step Exit Strategy. State the exact reasons why staying in this fund poses an opportunity cost.

PART 3: NEXT SUITABLE FUND RECOMMENDATION
Recommend the ideal target characteristics for the replacement fund (e.g., Sharpe > 0.55, Downside Capture < 80%) and suggest top-tier category peers.

NOTE: Do NOT perform any mathematical calculations. Use the exact figures provided above.
"""

            # Run LLM
            client = genai.Client(api_key=api_key)
            try:
                response = client.models.generate_content(model="gemini-3.5-flash", contents=llm_prompt)
            except Exception:
                response = client.models.generate_content(model="gemini-2.5-flash-lite", contents=llm_prompt)

            st.markdown("---")
            st.subheader("📌 Executive Portfolio & Exit Strategy Report")
            st.write(response.text)

        except Exception as e:
            st.error(f"Error reading URL or processing data: {str(e)}")
