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

# Google Cloud imports
from google.oauth2 import service_account
from google.cloud import dialogflow
import gspread
from google.oauth2.service_account import Credentials

# --- 2. Initialize Flask App ---
app = Flask(__name__, static_folder='static')
CORS(app)

# --- 3. Google Cloud Configuration ---
def get_google_credentials():
    """Get Google credentials from environment variable or file"""
    try:
        # Try to get credentials from environment variable first (for Railway)
        credentials_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
        if credentials_json:
            # Parse the JSON string from environment variable
            credentials_info = json.loads(credentials_json)
            return service_account.Credentials.from_service_account_info(
                credentials_info,
                scopes=[
                    'https://www.googleapis.com/auth/cloud-platform',
                    'https://www.googleapis.com/auth/spreadsheets'
                ]
            )
        else:
            # Fallback to local file (for local development)
            return service_account.Credentials.from_service_account_file(
                'credentials.json',
                scopes=[
                    'https://www.googleapis.com/auth/cloud-platform',
                    'https://www.googleapis.com/auth/spreadsheets'
                ]
            )
    except Exception as e:
        print(f"Error loading Google credentials: {e}")
        return None

# Initialize credentials
credentials = get_google_credentials()
if not credentials:
    print("WARNING: Google credentials not found!")

# Dialogflow Configuration
PROJECT_ID = "i4c-final-project-6"  # Replace with your actual project ID
LANGUAGE_CODE = "en"

# Google Sheets Configuration
SPREADSHEET_ID = "1iN6xKHlgXTF_xOjkPTwTsUHJbY8Kpb6aRLiVbLy7rKw"  # Replace with your spreadsheet ID

# Initialize Google Sheets client
def get_sheets_client():
    """Initialize Google Sheets client"""
    try:
        if credentials:
            return gspread.authorize(credentials)
        return None
    except Exception as e:
        print(f"Error initializing Sheets client: {e}")
        return None

sheets_client = get_sheets_client()

# --- 4. Utility Functions ---
def get_dialogflow_response(user_message, session_id):
    """Send message to Dialogflow and get response"""
    try:
        if not credentials:
            return "I'm having trouble accessing my AI services. Please try again later."
        
        # Create Dialogflow session client
        session_client = dialogflow.SessionsClient(credentials=credentials)
        session_path = session_client.session_path(PROJECT_ID, session_id)
        
        # Add current date context
        current_date = datetime.now().strftime("%B %d, %Y")
        contextual_message = f"System instruction: For context, the current date is {current_date}. User message: {user_message}"
        
        print(f"Sending to Dialogflow: '{contextual_message}'")
        
        # Create text input
        text_input = dialogflow.TextInput(text=contextual_message, language_code=LANGUAGE_CODE)
        query_input = dialogflow.QueryInput(text=text_input)
        
        # Get response from Dialogflow
        response = session_client.detect_intent(
            request={"session": session_path, "query_input": query_input}
        )
        
        bot_response = response.query_result.fulfillment_text
        print(f"Dialogflow response: {bot_response}")
        
        return bot_response
        
    except Exception as e:
        print(f"Error getting Dialogflow response: {e}")
        return "I'm having trouble processing your request. Please try again."

def save_to_sheets(complaint_data):
    """Save complaint data to Google Sheets"""
    try:
        if not sheets_client:
            print("Sheets client not available")
            return False
            
        sheet = sheets_client.open_by_key(SPREADSHEET_ID).sheet1
        
        # Prepare row data
        row_data = [
            complaint_data.get('timestamp', ''),
            complaint_data.get('complaint_id', ''),
            complaint_data.get('name', ''),
            complaint_data.get('email', ''),
            complaint_data.get('phone', ''),
            complaint_data.get('crime_type', ''),
            complaint_data.get('description', ''),
            complaint_data.get('amount_lost', ''),
            complaint_data.get('location', ''),
            complaint_data.get('suspect_info', ''),
            complaint_data.get('evidence', ''),
            complaint_data.get('status', 'Submitted')
        ]
        
        # Add row to sheet
        sheet.append_row(row_data)
        print(f"Complaint saved to sheets: {complaint_data.get('complaint_id')}")
        return True
        
    except Exception as e:
        print(f"Error saving to sheets: {e}")
        return False

# --- 5. Flask Routes ---
@app.route('/')
def index():
    """Serve the main HTML page"""
    return send_from_directory('static', 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    """Serve static files"""
    return send_from_directory('static', filename)

@app.route('/chat', methods=['POST'])
@cross_origin()
def chat():
    """Handle chat messages"""
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()
        session_id = data.get('session_id') or str(uuid.uuid4())
        
        if not user_message:
            return jsonify({
                'response': 'Please enter a message.',
                'session_id': session_id
            })
        
        # Get response from Dialogflow
        bot_response = get_dialogflow_response(user_message, session_id)
        
        return jsonify({
            'response': bot_response,
            'session_id': session_id
        })
        
    except Exception as e:
        print(f"Error in chat endpoint: {e}")
        return jsonify({
            'response': 'I encountered an error processing your message. Please try again.',
            'session_id': session_id if 'session_id' in locals() else str(uuid.uuid4())
        }), 503

@app.route('/webhook', methods=['POST'])
@cross_origin()
def webhook():
    """Handle Dialogflow webhook requests"""
    try:
        req = request.get_json()
        
        # Extract intent and parameters
        intent_name = req.get('queryResult', {}).get('intent', {}).get('displayName', '')
        parameters = req.get('queryResult', {}).get('parameters', {})
        
        print(f"Webhook received intent: {intent_name}")
        print(f"Parameters: {parameters}")
        
        # Handle complaint submission
        if intent_name == "SubmitComplaint" or "complaint" in intent_name.lower():
            # Generate complaint ID
            complaint_id = f"CYB{random.randint(100000, 999999)}"
            
            # Prepare complaint data
            complaint_data = {
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'complaint_id': complaint_id,
                'name': parameters.get('person-name', ''),
                'email': parameters.get('email', ''),
                'phone': parameters.get('phone-number', ''),
                'crime_type': parameters.get('crime-type', ''),
                'description': parameters.get('description', ''),
                'amount_lost': parameters.get('amount', ''),
                'location': parameters.get('location', ''),
                'suspect_info': parameters.get('suspect-info', ''),
                'evidence': parameters.get('evidence', ''),
                'status': 'Submitted'
            }
            
            # Save to Google Sheets
            if save_to_sheets(complaint_data):
                response_text = f"Thank you! Your complaint has been registered successfully.\n\n" \
                              f"🔍 **Complaint ID:** {complaint_id}\n" \
                              f"📅 **Date:** {complaint_data['timestamp']}\n" \
                              f"📋 **Status:** Under Review\n\n" \
                              f"You will receive updates on your registered email address. " \
                              f"Please save your Complaint ID for future reference."
            else:
                response_text = f"Your complaint has been registered with ID: {complaint_id}. " \
                              f"However, there was an issue saving to our database. " \
                              f"Please contact support with this ID."
            
            return jsonify({
                'fulfillmentText': response_text
            })
        
        # Default response for other intents
        return jsonify({
            'fulfillmentText': 'I can help you report cybercrime incidents. Please provide details about what happened.'
        })
        
    except Exception as e:
        print(f"Webhook error: {e}")
        return jsonify({
            'fulfillmentText': 'I encountered an error processing your request. Please try again.'
        })

# --- 6. Run the App ---
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)