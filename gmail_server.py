import os
import sys
import base64
from email.mime.text import MIMEText
from flask import Flask, request, jsonify
from flask_cors import CORS
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    'https://www.googleapis.com/auth/drive.file',
    'https://www.googleapis.com/auth/documents',
    'https://www.googleapis.com/auth/meetings.space.created',
    'https://www.googleapis.com/auth/gmail.send',
]

CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token.json'

app = Flask(__name__)
CORS(app)


def get_gmail_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'w') as f:
            f.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)


@app.route('/api/send-email', methods=['POST'])
def send_email():
    try:
        data = request.get_json()
        to      = data.get('to', '').strip()
        subject = data.get('subject', '').strip()
        body    = data.get('body', '').strip()

        if not to or not subject or not body:
            return jsonify({'error': '宛先・件名・本文は必須です。'}), 400

        service = get_gmail_service()
        message = MIMEText(body)
        message['to'] = to
        message['subject'] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

        result = service.users().messages().send(
            userId='me',
            body={'raw': raw}
        ).execute()

        return jsonify({'message_id': result['id'], 'to': to, 'subject': subject})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(port=5001, debug=True)
