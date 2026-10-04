import os
import sys
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# アクセス権限（Google Driveへのファイルアップロード）
SCOPES = ['https://www.googleapis.com/auth/drive.file']

CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token.json'


def authenticate():
    """OAuth 2.0 認証を行い、認証済みサービスを返す。"""
    creds = None

    # 既存トークンを読み込む
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    # トークンがない or 期限切れの場合は再認証
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                print(f'エラー: {CREDENTIALS_FILE} が見つかりません。')
                print('Google Cloud Console から OAuth 2.0 クライアントIDをダウンロードして')
                print(f'{CREDENTIALS_FILE} として保存してください。')
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        # トークンを保存（次回から再認証不要）
        with open(TOKEN_FILE, 'w') as f:
            f.write(creds.to_json())

    return build('drive', 'v3', credentials=creds)


def upload_file(service, file_path):
    """指定したローカルファイルを Google Drive へアップロードする。"""
    if not os.path.exists(file_path):
        print(f'エラー: ファイルが見つかりません → {file_path}')
        sys.exit(1)

    file_name = os.path.basename(file_path)
    media = MediaFileUpload(file_path, resumable=True)

    print(f'アップロード中: {file_name} ...')

    file_metadata = {'name': file_name}
    result = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id, name, webViewLink'
    ).execute()

    print('アップロード成功！')
    print(f'  ファイル名 : {result["name"]}')
    print(f'  ファイルID : {result["id"]}')
    print(f'  Drive URL  : {result.get("webViewLink", "（共有リンクなし）")}')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('使い方: python3 drive_upload.py <アップロードするファイルのパス>')
        print('例    : python3 drive_upload.py scores.csv')
        sys.exit(1)

    target_file = sys.argv[1]

    service = authenticate()
    upload_file(service, target_file)
