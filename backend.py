from fastapi import FastAPI, HTTPException, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import numpy as np
import janitor
from io import BytesIO

app = FastAPI()

# Allow all origins to access this API (for development purposes)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store data in-memory for simplicity
registration_df = pd.DataFrame()

@app.post("/upload/")
async def upload_file(file: UploadFile = File(...)):
    global registration_df
    try:
        # Read uploaded file into DataFrame
        contents = await file.read()
        registration_df = pd.read_csv(BytesIO(contents)).clean_names()
        registration_df = (
            registration_df
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
            age=pd.to_numeric(registration_df['age'], errors='coerce')
        )
        return {"status": "success", "filename": file.filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading file: {str(e)}")

@app.get("/filters/")
def get_filters():
    """Retrieve unique filter values."""
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
    try:
        filtered_df = registration_df.copy()

        # Apply filters
        if lip and "Project" not in lip:
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

        return {
            "exit_reasons": exit_reasons,
            "birth_cert_uptake": birth_cert_uptake,
            "reporting_summary": reporting_summary,
            "hivstatus_summary": hivstatus_summary,
            "category_summary": category_summary
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing data: {str(e)}")
