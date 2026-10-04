import os
import sys
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

ACCOUNT_ID    = os.getenv('ZOOM_ACCOUNT_ID')
CLIENT_ID     = os.getenv('ZOOM_CLIENT_ID')
CLIENT_SECRET = os.getenv('ZOOM_CLIENT_SECRET')


def get_access_token():
    """Server-to-Server OAuth でアクセストークンを取得する。"""
    url = f'https://zoom.us/oauth/token?grant_type=account_credentials&account_id={ACCOUNT_ID}'
    response = requests.post(url, auth=(CLIENT_ID, CLIENT_SECRET))

    if response.status_code != 200:
        print(f'エラー: トークン取得失敗 ({response.status_code})')
        print(response.json())
        sys.exit(1)

    return response.json()['access_token']


def create_meeting(token):
    """Zoom APIでミーティングを作成する。"""
    start_time = (datetime.now() + timedelta(minutes=5)).strftime('%Y-%m-%dT%H:%M:%S')

    payload = {
        'topic': 'APIテストミーティング',
        'type': 2,                      # スケジュールミーティング
        'start_time': start_time,
        'duration': 60,
        'timezone': 'Asia/Tokyo',
        'settings': {
            'waiting_room': False,
        }
    }

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }

    response = requests.post('https://api.zoom.us/v2/users/me/meetings', json=payload, headers=headers)

    if response.status_code != 201:
        print(f'エラー: ミーティング作成失敗 ({response.status_code})')
        print(response.json())
        sys.exit(1)

    return response.json()


def main():
    if not all([ACCOUNT_ID, CLIENT_ID, CLIENT_SECRET]):
        print('エラー: .env ファイルに ZOOM_ACCOUNT_ID / ZOOM_CLIENT_ID / ZOOM_CLIENT_SECRET を設定してください。')
        sys.exit(1)

    print('アクセストークン取得中...')
    token = get_access_token()

    print('ミーティング作成中...')
    meeting = create_meeting(token)

    print('\nミーティングを作成しました！')
    print(f'  タイトル       : {meeting["topic"]}')
    print(f'  ミーティングID : {meeting["id"]}')
    print(f'  パスワード     : {meeting.get("password", "なし")}')
    print(f'  参加URL        : {meeting["join_url"]}')


if __name__ == '__main__':
    main()
