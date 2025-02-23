from fastapi import FastAPI, HTTPException, Query, UploadFile, File
import pandas as pd
import numpy as np
import janitor
from fastapi.middleware.cors import CORSMiddleware
import io

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

# Global variables to store the uploaded data
registration_df = None
viral_load_df = None

@app.post("/upload/")
async def upload_file(file: UploadFile = File(...)):
    """Endpoint to upload the registration list file."""
    global registration_df
    try:
        if file.filename.endswith('.csv'):
            # Read the file content
            content = await file.read()
            df = pd.read_csv(io.StringIO(content.decode('utf-8')))
            registration_df = (
                df.clean_names()
                .query("void_person != 'VOIDED'")  # Remove voided persons
                .assign(
                    lip=lambda x: np.select(
                        [
                            x['cbo'].str.contains('AMURT', case=False, na=False),
                            x['cbo'].str.contains('CIPK', case=False, na=False),
                            x['cbo'].str.contains('KWETU', case=False, na=False)
                        ],
                        ['AMURT', 'CIPK', 'KWETU'],
                        default='WOFAK'
                    )
                )
            )
            registration_df = registration_df.assign(
                exit_date=pd.to_datetime(registration_df['exit_date'], errors='coerce'),
                registration_date=pd.to_datetime(registration_df['registration_date'], errors='coerce'),
                date_of_event=pd.to_datetime(registration_df['date_of_event'], errors='coerce'),
                age=pd.to_numeric(registration_df['age'], errors='coerce'),
                viral_load=pd.to_numeric(registration_df['viral_load'], errors='coerce')
            )
            return {"message": "File uploaded and processed successfully."}
        else:
            raise HTTPException(status_code=400, detail="Invalid file format. Please upload a CSV file.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

@app.post("/upload-viral-load/")
async def upload_viral_load(file: UploadFile = File(...)):
    """Endpoint to upload the viral load report file."""
    global viral_load_df
    try:
        if file.filename.endswith('.csv'):
            # Read the file content
            content = await file.read()
            viral_load_df = pd.read_csv(io.StringIO(content.decode('utf-8')))
            viral_load_df = viral_load_df.clean_names()  # Clean column names

            viral_load_df = viral_load_df.assign(
                date_of_event=pd.to_datetime(viral_load_df['date_of_event'], errors='coerce'),
                viral_load=pd.to_numeric(viral_load_df['viral_load'], errors='coerce')
            )

            return {"message": "Viral load file uploaded and processed successfully."}
        else:
            raise HTTPException(status_code=400, detail="Invalid file format. Please upload a CSV file.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing viral load file: {str(e)}")

@app.get("/viral-load-trend/")
def get_viral_load_trend():
    """Generate viral load trend by filtering and processing registration list and viral load report."""
    global registration_df, viral_load_df
    if registration_df is None or viral_load_df is None:
        raise HTTPException(status_code=400, detail="Both registration list and viral load report must be uploaded.")
    try:
        # Step 1: Filter registration_df for POSITIVE ovchivstatus
        calhiv_df = registration_df[registration_df['ovchivstatus'] == 'POSITIVE']

        # Step 2: Select required columns from both datasets
        calhiv_columns = calhiv_df[['cpims_ovc_id', 'viral_load', 'date_of_event']] 
        vl_columns = viral_load_df[['cpims_ovc_id', 'viral_load', 'date_of_event']]  

        # Step 3: Merge the datasets on cpims_ovc_id
        merged_vl = pd.concat([calhiv_columns, vl_columns], ignore_index=True)

        # Step 4: Sort by date_of_event (latest to oldest)
        merged_vl = merged_vl.sort_values(by='date_of_event', ascending=False)

        # Step 5: Remove duplicates by cpims_ovc_id and date_of_event
        merged_vl = merged_vl.drop_duplicates(subset=['cpims_ovc_id'], keep='first')


        # Function to categorize viral_load values
        def categorize_viral_load(row):
            if pd.isna(row['date_of_event']):
                return 'missing vl'
            elif pd.isna(row['viral_load']):
                return 'a.LDL'
            elif row['viral_load'] <= 49:
                return 'a.LDL'
            elif row['viral_load'] <= 199:
                return 'b.50-199'
            elif row['viral_load'] <= 999:
                return 'c.200-999 (unsuppressed)'
            else:
                return 'd.1000+ (suspected treatment failure)'

        # Apply the function to each row to create a new column
        merged_vl['vl_suppression'] = merged_vl.apply(categorize_viral_load, axis=1)

        calhiv_viral_load = (
            merged_vl[merged_vl['viral_load'] > 199]  # Step 1: Filter viral_load > 199
           .drop_duplicates(subset=['cpims_ovc_id', 'date_of_event'])  # Step 2: Remove duplicates
           .dropna(subset='date_of_event') # Step 3: Remove rows with blanks in date_of_event
        )

        # Step 6: Group by time period and calculate viral load trends
        calhiv_viral_load['year'] = pd.to_datetime(calhiv_viral_load['date_of_event']).dt.year

        calhiv_viral_load['year'] = calhiv_viral_load['year'].astype(int)

        # Filter data for years 2021 and later
        calhiv_viral_load = (
            calhiv_viral_load[calhiv_viral_load['year'] >= 2021]
            .sort_values(by='year', ascending=False)
            .drop_duplicates(subset=['cpims_ovc_id', 'year'])
        )

        # Group the data
        trend_data = calhiv_viral_load.groupby('year')['vl_suppression'].count().reset_index()

        # Convert Period to string for JSON serialization
        trend_data['year'] = trend_data['year'].astype(int)

        return trend_data.to_dict(orient='records')
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating viral load trend: {str(e)}")


@app.get("/filters/")
def get_filters():
    """Retrieve unique filter values."""
    global registration_df
    if registration_df is None:
        raise HTTPException(status_code=400, detail="No data uploaded yet.")
    try:
        unique_lips = sorted(registration_df["lip"].dropna().unique().tolist())

        # Ensure "Project" is included only once
        if "Project" not in unique_lips:
            unique_lips.insert(0, "Project")

        return {
            "lip": unique_lips,
            "constituency": sorted(registration_df["constituency"].dropna().unique().tolist()),
            "ward": sorted(registration_df["ward"].dropna().unique().tolist())
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving filters: {str(e)}")

@app.get("/summaries/")
def get_summaries(
    lip: list[str] = Query(default=[]),
    constituency: list[str] = Query(default=[]),
    ward: list[str] = Query(default=[])
):
    """Retrieve filtered summary data."""
    global registration_df
    if registration_df is None:
        raise HTTPException(status_code=400, detail="No data uploaded yet.")
    try:
        filtered_df = registration_df.copy()

        # Apply filters
        if lip and "Project" not in lip:  # Exclude "Project" from filtering
            filtered_df = filtered_df[filtered_df['lip'].isin(lip)]
        if constituency:
            filtered_df = filtered_df[filtered_df['constituency'].isin(constituency)]
        if ward:
            filtered_df = filtered_df[filtered_df['ward'].isin(ward)]

        # Filter for active and valid exited cases
        reporting_reglist = filtered_df[
            (filtered_df['exit_status'] == 'ACTIVE') |
            ((filtered_df['exit_status'] == 'EXITED') & 
             (filtered_df['exit_reason'] != 'Duplicated') & 
             (filtered_df['exit_date'].notna()) & 
             (filtered_df['exit_date'] >= pd.Timestamp('2024-10-01')))
        ]

        # Reporting Summary
        reporting_reglist['reporting_status'] = np.select(
            [
                reporting_reglist["exit_status"] == "ACTIVE",
                reporting_reglist["exit_reason"] == "Case Plan Achievement",
                reporting_reglist["exit_reason"].str.contains("Transfer", case=False, na=False)
            ],
            ["Case Load", "Graduated", "Transfers"],
            default="Exits"
        )

        reporting_summary = reporting_reglist.drop_duplicates(subset='cpims_ovc_id')['reporting_status'].value_counts().to_dict()

        # Active OVCs
        active_ovc = reporting_reglist[reporting_reglist['exit_status'] == 'ACTIVE'].drop_duplicates(subset=['cpims_ovc_id'])

        # Exited Cases
        exited_ovc = reporting_reglist.drop_duplicates(subset=['cpims_ovc_id'])

        # Exit Reasons
        exit_reasons = exited_ovc['exit_reason'].value_counts().to_dict()

        # HIV Status
        hivstatus_summary = active_ovc['ovchivstatus'].value_counts().to_dict()

        # Birth Certificate Uptake
        birth_cert_uptake = active_ovc['birthcert'].value_counts().to_dict()

        # Reporting Category
        total_ovc_count = len(active_ovc)
        total_ovc_above_5 = len(active_ovc[active_ovc['age'] > 5])
        ovc_has_birth = active_ovc[active_ovc['birthcert'] == 'HAS BIRTHCERT']
        ovc_has_disability = active_ovc[active_ovc['ovcdisability'] == 'HAS DISABILITY']
        ovc_schoolgoing = active_ovc[
            (active_ovc['schoollevel'] != 'Not in School') & (active_ovc['age'] > 5)
        ]

        category_summary = {
            "Has Birth Certificate": {
                "Count": len(ovc_has_birth),
                "Percentage": f"{round(len(ovc_has_birth) / total_ovc_count * 100):.0f}%"
            },
            "School Going": {
                "Count": len(ovc_schoolgoing),
                "Percentage": f"{round(len(ovc_schoolgoing) / total_ovc_above_5 * 100):.0f}%"
            },
            "Has Disability": {
                "Count": len(ovc_has_disability),
                "Percentage": f"{round(len(ovc_has_disability) / total_ovc_count * 100):.0f}%"
            },
        }


        # CALHIV summary

        # Return
        return {
            "exit_reasons": exit_reasons,
            "birth_cert_uptake": birth_cert_uptake,
            "reporting_summary": reporting_summary,
            "hivstatus_summary": hivstatus_summary,
            "category_summary": category_summary
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing data: {str(e)}")