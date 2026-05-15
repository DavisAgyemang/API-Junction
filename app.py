from flask import Flask, render_template, request, send_file, make_response
import os
import requests
import io
from dotenv import load_dotenv
import pandas as pd
import json

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "default-dev-key-123")
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,  # Prevents scripts from stealing the session
    SESSION_COOKIE_SAMESITE="Lax",  # Required by modern browsers to allow redirects
)


@app.route('/')
def index():
    return render_template('index.html')


def get_nested_value(data, path):
    """Digs into a dict/list using dot notation (e.g., 'location.street.name')"""
    if not path: return data
    try:
        # If the API returns a list (like the Police API), grab the first item
        if isinstance(data, list) and len(data) > 0:
            data = data[0]

        for key in path.split('.'):
            data = data.get(key, "N/A")
        return data
    except:
        return "Path Error"


@app.route('/process', methods=['POST'])
def process():
    # 1. Capture Form Data
    api_type = request.form.get('api_type')
    output_path = request.form.get('output_path')
    file = request.files.get('file')

    # Parse the dynamic mapping data sent from script.js
    mappings = json.loads(request.form.get('mapping_data', '[]'))

    if not file:
        return "No file uploaded", 400

    # 2. Setup API Configuration based on Service Mode
    if api_type == 'native':
        url = os.getenv("ContractMap_URL")
        # Pre-set for Native Mode: Input key is 'description', Output is 'mapped_value'
        output_path = "AI_label"
        method = "POST"
        headers = {
            "Ocp-Apim-Subscription-Key": os.getenv("ContractMap_key"),
            "Content-Type": "application/json"
        }
        static_params = []
    else:
        # Custom Mode: Use user-provided settings
        url = request.form.get('custom_url')
        method = request.form.get('method', 'POST').upper()

        # Build Headers
        h_keys = request.form.getlist('header_keys[]')
        h_vals = request.form.getlist('header_values[]')
        headers = {k: v for k, v in zip(h_keys, h_vals) if k}

        api_key = request.form.get('api_key')
        if api_key:
            headers["Ocp-Apim-Subscription-Key"] = api_key

        # Build Static Query Parameters (e.g., candidates for name matching)
        p_keys = request.form.getlist('param_keys[]')
        p_vals = request.form.getlist('param_values[]')
        static_params = [(k, v) for k, v in zip(p_keys, p_vals) if k]

    # 3. Process Spreadsheet
    try:
        # Load data
        if file.filename.endswith('.csv'):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)

        api_results = []
        stop_processing = False

        for index, row in df.iterrows():
            # Circuit Breaker: If row 0 failed configuration, skip the rest instantly
            if stop_processing:
                api_results.append("Skipped: Previous row failed configuration check.")
                continue

            try:
                # Build the specific payload for this row based on mappings
                # payload = {'apiKey': 'columnValue', ...}
                row_payload = {m['apiKey']: row[m['colName']] for m in mappings if m['apiKey'] and m['colName']}

                if method == "POST":
                    # POST: data goes in JSON body, static params go in URL
                    response = requests.post(url, json=row_payload, headers=headers, params=static_params, timeout=15)
                else:
                    # GET: static params merged with row data as URL parameters
                    current_params = static_params + list(row_payload.items())
                    response = requests.get(url, headers=headers, params=current_params, timeout=15)

                res_data = response.json()
                res_str = str(res_data)

                # Validation: Check if API returned a Pydantic/FastAPI "missing field" error
                if "missing" in res_str and "loc" in res_str:
                    api_results.append(f"CRITICAL CONFIG ERROR: Key name mismatch. API said: {res_str}")
                    stop_processing = True
                else:
                    # Success: Dig into the JSON based on the output_path
                    result = get_nested_value(res_data, output_path)
                    api_results.append(str(result))

            except Exception as e:
                api_results.append(f"API Error: {str(e)}")
                # Optional: Uncomment below to stop on connection errors too
                # stop_processing = True

        # Attach results to dataframe
        df['API_Response'] = api_results

        # 4. Generate Excel in memory for download
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False)
        output.seek(0)

        response = make_response(send_file(
            output,
            as_attachment=True,
            download_name="api_results.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ))

        # Cookie used by some frontend logic to detect download start
        response.set_cookie('download_started', 'true', max_age=60)
        return response

    except Exception as e:
        return f"Processing Error: {str(e)}", 500

if __name__ == '__main__':
    app.run(debug=True)