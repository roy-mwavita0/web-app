import streamlit as st
import requests
import pandas as pd
import plotly.express as px

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

# File Upload
uploaded_file = st.file_uploader("Upload Registration List (CSV)", type="csv")
if uploaded_file is not None:
    files = {"file": uploaded_file}
    response = requests.post(f"{BACKEND_URL}/upload/", files=files)
    if response.status_code == 200:
        st.success("File uploaded successfully!")
    else:
        st.error(f"Error uploading file: {response.json().get('detail', 'Unknown error')}")

# File Upload for Viral Load Report
viral_load_file = st.file_uploader("Upload Viral Load Report (CSV)", type="csv")
if viral_load_file is not None:
    files = {"file": viral_load_file}
    response = requests.post(f"{BACKEND_URL}/upload-viral-load/", files=files)
    if response.status_code == 200:
        st.success("Viral load file uploaded successfully!")
    else:
        st.error(f"Error uploading viral load file: {response.json().get('detail', 'Unknown error')}")

# Get filter options only if a file is uploaded
if uploaded_file is not None:
    filters = fetch_data("filters") or {"lip": [], "constituency": [], "ward": []}
else:
    filters = {"lip": [], "constituency": [], "ward": []}

# Sidebar Filters
st.sidebar.header("🔎 Filters")
lip_options = filters["lip"]
if lip_options:  # Check if lip_options is not empty
    lip = st.sidebar.multiselect("Select LIP", lip_options, default=["Project"])
else:
    lip = st.sidebar.multiselect("Select LIP", ["Project"], default=["Project"])

constituency = st.sidebar.multiselect("Select Constituency", filters["constituency"])
ward = st.sidebar.multiselect("Select Ward", filters["ward"])

# Apply Filters Button
if st.sidebar.button("Apply Filters"):
    if uploaded_file is None:
        st.error("Please upload a file first.")
    else:
        params = {"lip": lip, "constituency": constituency, "ward": ward}
        summary_data = fetch_data("summaries", params)

        if summary_data:
            # Tabs
            tab1, tab2, tab3 = st.tabs(["📊 Reporting Summaries", "📈 Epidemic Control", "🚨 Data Gaps"])

            with tab1:
                st.subheader("")
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
                    
                # OVC Eligible for Reporting Summary
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
                if uploaded_file is not None and viral_load_file is not None:
                    st.subheader("High Viral Load Trend Across Years")
                    trend_data = fetch_data("viral-load-trend")
                    if trend_data:
                        df_trend = pd.DataFrame(trend_data)
                        st.plotly_chart(px.line(
                        df_trend,
                        x="year",
                        y="vl_suppression",
                        labels={"year": "Year", "vl_suppression": "# of Unsuppressed CALHIV"},
                        title=""
                    ))
                    else:
                        st.error("No data available for viral load trend.")
                else:
                    st.warning("Please upload both the registration list and viral load report to view the trend.")
                

            with tab3:
                st.subheader("Data Gaps")
                st.write("🚧 Data gaps analysis and insights will be displayed here.")