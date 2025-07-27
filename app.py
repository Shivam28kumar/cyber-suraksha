# --- 1. Imports ---
import json
import time
import random
import uuid
import requests
import os
from datetime import datetime

# Flask and CORS
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS, cross_origin

# Google Cloud libraries
import gspread
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import service_account

# --- 2. App Initialization & CORS Configuration ---
app = Flask(__name__, static_folder='static')
CORS(app, resources={r"/*": {"origins": "*"}})

# --- 3. Configuration Variables ---
PROJECT_ID = "i4c-final-project-6"
LOCATION = "asia-south1"
AGENT_ID = "bda082c9-bcfc-4b5b-8eed-21ea49516592"
SHEET_NAME = "I4C-Final-Reports"
CREDENTIALS_FILE = 'credentials.json'
SCOPES = [
    'https://www.googleapis.com/auth/cloud-platform', 'https://www.googleapis.com/auth/dialogflow',
    'https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'
]
COLUMN_ORDER = [
    'Reference_ID', 'complaint_subcategory', 'incident_datetime', 'delay_in_reporting', 'delay_reason',
    'incident_description', 'victim_account_type', 'victim_bank_name', 'victim_account_id', 'transaction_id',
    'amount_lost', 'Transaction_date', 'victim_name', 'victim_mobile', 'Gender', 'Age', 'Address',
    'pin_code', 'district', 'police_station', 'victim_email'
]

# --- 4. Helper Functions ---
def get_gspread_client():
    """Authenticates for Google Sheets."""
    try:
        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
        return gspread.authorize(creds)
    except Exception as e:
        print(f"Error getting gspread client: {e}")
        return None

def get_dialogflow_access_token():
    """Creates a short-lived access token for calling the Dialogflow API."""
    try:
        creds = service_account.Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
        creds.refresh(GoogleAuthRequest())
        return creds.token
    except Exception as e:
        print(f"Error getting Dialogflow token: {e}")
        return None

# --- 5. Routes ---
@app.route('/')
def home():
    """Serve the main page"""
    return send_from_directory('static', 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    """Serve static files"""
    return send_from_directory('static', filename)

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

@app.route('/chat', methods=['POST', 'OPTIONS'])
@cross_origin()
def chat_handler():
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    if request.method == 'POST':
        try:
            data = request.get_json()
            if not data:
                return jsonify({"error": "No JSON data received"}), 400
                
            user_input = data.get('message')
            if not user_input:
                return jsonify({"error": "No message provided"}), 400
                
            session_id = data.get('session_id', str(uuid.uuid4()))

            # Date grounding fix
            current_date_for_llm = datetime.now().strftime('%B %d, %Y')
            final_input_for_dialogflow = f"System instruction: For context, the current date is {current_date_for_llm}. User message: {user_input}"
            print(f"Sending to Dialogflow: '{final_input_for_dialogflow}'")
            
            access_token = get_dialogflow_access_token()
            if not access_token:
                return jsonify({"response": "Service temporarily unavailable. Please try again."}), 503

            dialogflow_url = (
                f"https://{LOCATION}-dialogflow.googleapis.com/v3/projects/{PROJECT_ID}/locations/{LOCATION}/agents/{AGENT_ID}/sessions/{session_id}:detectIntent")

            headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
            payload = {
                "queryInput": {
                    "text": {
                        "text": final_input_for_dialogflow
                    },
                    "languageCode": "en"
                }
            }

            response = requests.post(dialogflow_url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()

            response_data = response.json()
            messages = response_data.get("queryResult", {}).get("responseMessages", [])
            bot_response = " ".join(" ".join(msg.get("text", {}).get("text", [])) for msg in messages if "text" in msg)
            if not bot_response: 
                bot_response = "I'm sorry, I could not process a response."

            return jsonify({"response": bot_response, "session_id": session_id})

        except Exception as e:
            print(f"Chat handler error: {e}")
            return jsonify({"response": "Sorry, an error occurred. Please try again."}), 500

@app.route('/webhook', methods=['POST'])
@cross_origin()
def i4c_playbook_webhook():
    try:
        req = request.get_json(force=True)
        params = req
        print("Webhook received with params:", json.dumps(params, indent=2))

        client = get_gspread_client()
        if not client:
            error_text = "Sorry, unable to connect to database."
            return jsonify({"fulfillment_response": {"messages": [{"text": {"text": [error_text]}}]}})

        sheet = client.open(SHEET_NAME).sheet1

        timestamp = int(time.time())
        random_suffix = ''.join(random.choices('0123456789ABCDEF', k=6))
        reference_id = f"I4C-{timestamp}-{random_suffix}"

        row_data = [reference_id] + [str(params.get(col, 'N/A')) for col in COLUMN_ORDER[1:]]
        sheet.append_row(row_data)

        response_text = f"Thank you, your report has been recorded successfully. Your official Reference ID is {reference_id}."
        response_payload = {"fulfillment_response": {"messages": [{"text": {"text": [response_text]}}]}}
        return jsonify(response_payload)
        
    except Exception as e:
        print(f"Webhook error: {e}")
        error_text = "Sorry, a technical error occurred while saving your report."
        return jsonify({"fulfillment_response": {"messages": [{"text": {"text": [error_text]}}]}})

# --- 6. Run the App ---
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)