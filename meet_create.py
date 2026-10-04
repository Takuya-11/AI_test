import os
import sys
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.apps import meet_v2

# Drive + Docs + Meet のスコープ
SCOPES = [
    'https://www.googleapis.com/auth/drive.file',
    'https://www.googleapis.com/auth/documents',
    'https://www.googleapis.com/auth/meetings.space.created',
]

CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token.json'


def authenticate():
    """OAuth 2.0 認証を行い、認証済みの credentials を返す。"""
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


def create_meeting(creds):
    """Google Meet の会議スペースを作成し、参加URLを返す。"""
    client = meet_v2.SpacesServiceClient(credentials=creds)
    response = client.create_space(request=meet_v2.CreateSpaceRequest())
    return response


def main():
    print('認証中...')
    creds = authenticate()

    print('会議スペースを作成中...')
    try:
        space = create_meeting(creds)
    except Exception as e:
        print(f'エラー: 会議スペースの作成に失敗しました。\n詳細: {e}')
        print('\n確認事項：')
        print('  - Google Cloud Console で「Google Meet API」が有効になっているか')
        print('  - OAuthスコープが正しいか')
        sys.exit(1)

    print('\n会議を作成しました。')
    print(f'  Meet URL  : {space.meeting_uri}')
    print(f'  スペース名 : {space.name}')
    print(f'  会議コード : {space.meeting_code}')


if __name__ == '__main__':
    main()
