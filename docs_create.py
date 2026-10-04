import os
import sys
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Drive + Docs 両方のスコープ
SCOPES = [
    'https://www.googleapis.com/auth/drive.file',
    'https://www.googleapis.com/auth/documents',
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
                print('Google Cloud Console から OAuth 2.0 クライアントIDをダウンロードして')
                print(f'{CREDENTIALS_FILE} として保存してください。')
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, 'w') as f:
            f.write(creds.to_json())

    return creds


def create_document(docs_service, title):
    """指定タイトルで新しい Google ドキュメントを作成し、ドキュメントIDを返す。"""
    doc = docs_service.documents().create(body={'title': title}).execute()
    return doc['documentId']


def insert_text(docs_service, doc_id, text):
    """ドキュメントにテキストを挿入する。"""
    requests = [
        {
            'insertText': {
                'location': {'index': 1},
                'text': text,
            }
        }
    ]
    docs_service.documents().batchUpdate(
        documentId=doc_id,
        body={'requests': requests}
    ).execute()


def main():
    # ---- 設定（ここを変えると好きなタイトル・テキストにできる） ----
    title = 'APIテストドキュメント'
    text  = '私はClaude codeを使いこなしていく逸材です。\nこちらの文章はClaude codeによって生成されました。\nこれからもこのような文章を生成していきます。\n私の記事たくさん読んでください。'
    # ---------------------------------------------------------------

    print('認証中...')
    creds = authenticate()

    docs_service = build('docs', 'v1', credentials=creds)

    print(f'ドキュメント作成中: 「{title}」')
    try:
        doc_id = create_document(docs_service, title)
    except Exception as e:
        print(f'エラー: ドキュメント作成に失敗しました。\n詳細: {e}')
        sys.exit(1)

    print('テキスト挿入中...')
    try:
        insert_text(docs_service, doc_id, text)
    except Exception as e:
        print(f'エラー: テキスト挿入に失敗しました。\n詳細: {e}')
        sys.exit(1)

    print('\n完了！')
    print(f'  タイトル : {title}')
    print(f'  ドキュメントID : {doc_id}')
    print(f'  URL : https://docs.google.com/document/d/{doc_id}/edit')


if __name__ == '__main__':
    main()
