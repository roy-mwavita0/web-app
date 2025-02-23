from flask import Flask, render_template, request, jsonify
import pandas as pd
import janitor
import numpy as np

app = Flask(__name__)

# Load data
registration_df = (
    pd.read_csv("D:/M&E/Reports/ip-RegistrationList.22022025.csv")
    .clean_names()
)

viral_load_df = (
    pd.read_csv("D:/M&E/Reports/ip-ViralLoad.22022025.csv")
    .clean_names()
)

# Convert exit_date to datetime format
registration_df['exit_date'] = pd.to_datetime(registration_df['exit_date'], errors='coerce')

# Filter data
reporting_reglist = registration_df.loc[
    (registration_df['exit_status'] == 'ACTIVE') |
    ((registration_df['exit_status'] == 'EXITED') &
     (registration_df['exit_reason'] != 'Duplicated') &
     (registration_df['exit_date'].notna()) & 
     (registration_df['exit_date'] >= pd.Timestamp('2024-10-01')))
]

# Extract active OVCs
active_df = registration_df.loc[registration_df['exit_status'] == 'ACTIVE']
active_ovc = active_df.drop_duplicates(subset=['cpims_ovc_id'])

# Extract exited cases (filtered from reporting_reglist)
exited = reporting_reglist.loc[
    reporting_reglist['exit_status'] == 'EXITED'
].drop_duplicates(subset=['cpims_ovc_id'])


@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/summary', methods=['GET'])
def get_summary():
    ward = request.args.get('ward')
    constituency = request.args.get('constituency')
    
    # Filter data based on ward and constituency
    filtered_unique_active = active_ovc[(active_ovc['ward'] == ward) & (active_ovc['constituency'] == constituency)]
    
    # Calculate metrics
    total_active = len(filtered_unique_active)
    birth_cert_count = filtered_unique_active['birthcert'].value_counts().get('HAS BIRTHCERT', 0)
    
    # Return JSON response
    return jsonify({
        'total_active': total_active,
        'birth_cert_count': birth_cert_count
    })

if __name__ == '__main__':
    app.run(debug=True)