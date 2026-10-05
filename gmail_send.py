import os
import sys
import base64
from email.mime.text import MIMEText
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


def authenticate():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                print(f'エラー: {CREDENTIALS_FILE} が見つかりません。')
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'w') as f:
            f.write(creds.to_json())
    return creds


def send_email(service, to, subject, body):
    message = MIMEText(body)
    message['to'] = to
    message['subject'] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    result = service.users().messages().send(
        userId='me',
        body={'raw': raw}
    ).execute()
    return result


def main():
    # ---- 送信設定（ここを変更する） ----
    to      = 'taquya.itow@gmail.com'
    subject = 'Gmail API テスト'
    body    = 'これはGmail APIから送信したテストメールです。\nPythonから自動送信しました。'
    # -----------------------------------

    print('認証中...')
    creds = authenticate()
    service = build('gmail', 'v1', credentials=creds)

    print('メール送信中...')
    try:
        result = send_email(service, to, subject, body)
    except Exception as e:
        print(f'エラー: メール送信に失敗しました。\n詳細: {e}')
        sys.exit(1)

    print('\nメールを送信しました。')
    print(f'  宛先      : {to}')
    print(f'  件名      : {subject}')
    print(f'  Message ID: {result["id"]}')


if __name__ == '__main__':
    main()
