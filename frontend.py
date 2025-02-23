import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import matplotlib.pyplot as plt

# Set Web App Configuration
st.set_page_config(page_title="OVC Data Insights", page_icon="📊", layout="wide")

# App Title and Description
st.title("📊 OVC Data Insights Dashboard")
st.markdown("""
Gain real-time insights into **OVC program data**, including reporting summaries, epidemic control, and data gaps.
Use the filters to explore specific **LIPs, constituencies, and wards**.
""")

# Backend URL
BACKEND_URL = "http://127.0.0.1:8000"

def fetch_data(endpoint, params=None):
    """Fetch data from the backend API."""
    try:
        response = requests.get(f"{BACKEND_URL}/{endpoint}", params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error connecting to backend: {e}")
        return None

# Get filter options
filters = fetch_data("filters") or {"lip": [], "constituency": [], "ward": []}

# Sidebar Filters
st.sidebar.header("🔎 Filters")
lip = st.sidebar.multiselect("Select LIP", filters["lip"], default=["Project"])
constituency = st.sidebar.multiselect("Select Constituency", filters["constituency"])
ward = st.sidebar.multiselect("Select Ward", filters["ward"])

# Apply Filters Button
if st.sidebar.button("Apply Filters"):
    params = {"lip": lip, "constituency": constituency, "ward": ward}
    summary_data = fetch_data("summaries", params)

    if summary_data:
        # Tabs
        tab1, tab2, tab3 = st.tabs(["📊 Reporting Summaries", "📈 Epidemic Control", "🚨 Data Gaps"])

        with tab1:
            st.subheader("Reporting Summaries")

            # OVC Eligible for Reporting
            if "reporting_summary" in summary_data:
                st.subheader("OVC Eligible for Reporting")
                df_summary = pd.DataFrame(summary_data["reporting_summary"].items(), columns=["Status", "Count"])
                st.plotly_chart(px.bar(df_summary, 
                                       x="Status", 
                                       y="Count",  
                                       color="Status",
                                       labels={"Status": "", "Count": "# of OVC"}
                                    )
                                )
                
              # OVC Eligible for Reporting Summaries
            if "category_summary" in summary_data:
                st.subheader("OVC Eligible for Reporting Summaries")
                df_summary = pd.DataFrame([
                    {"Category": key, "Count": value["Count"], "Percentage": value["Percentage"]}
                    for key, value in summary_data["category_summary"].items()
                ])
                st.plotly_chart(px.bar(df_summary, 
                                       x="Category", 
                                       y="Count",  
                                       color="Category",
                                       text="Percentage",
                                       labels={"Category": "", "Count": "# of OVC"}
                                    )
                                )
            
            # HIV Status Summary (Pie Chart Fix)
            if "hivstatus_summary" in summary_data:
                st.subheader("Case Load by HIV Status")
                df_hivstatus = pd.DataFrame(summary_data["hivstatus_summary"].items(), columns=["Status", "Count"])
                fig = px.pie(df_hivstatus, values='Count', names='Status', title='')
                st.plotly_chart(fig)

            # Exit Reasons
            if "exit_reasons" in summary_data:
                st.subheader("OVC Exit Reasons")
                st.bar_chart(summary_data["exit_reasons"])


        with tab2:
            st.subheader("Epidemic Control")
            st.write("🔬 Epidemic control charts and summaries will go here.")

        with tab3:
            st.subheader("Data Gaps")
            st.write("🚧 Data gaps analysis and insights will be displayed here.")
