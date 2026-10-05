import os
import sys
from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

load_dotenv()

MAX_RESULTS = 5


def get_api_key():
    key = os.getenv('YOUTUBE_API_KEY')
    if not key:
        print('エラー: YOUTUBE_API_KEY が .env に設定されていません。')
        sys.exit(1)
    return key


def search_videos(keyword, max_results=MAX_RESULTS):
    api_key = get_api_key()

    try:
        youtube = build('youtube', 'v3', developerKey=api_key)
        response = youtube.search().list(
            q=keyword,
            part='snippet',
            type='video',
            maxResults=max_results,
        ).execute()
    except HttpError as e:
        status = e.resp.status
        if status == 400:
            print('エラー: APIキーが無効です。.env の YOUTUBE_API_KEY を確認してください。')
        elif status == 403:
            reason = ''
            try:
                reason = e.error_details[0].get('reason', '')
            except Exception:
                pass
            if reason == 'quotaExceeded':
                print('エラー: YouTube Data API の利用制限（クォータ）に達しました。明日以降に再試行してください。')
            else:
                print('エラー: APIアクセスが拒否されました。YouTube Data API v3 が有効か確認してください。')
        else:
            print(f'エラー: API通信に失敗しました。(HTTP {status})\n詳細: {e}')
        sys.exit(1)
    except Exception as e:
        print(f'エラー: API通信に失敗しました。\n詳細: {e}')
        sys.exit(1)

    items = response.get('items', [])
    if not items:
        print(f'「{keyword}」の検索結果が0件でした。')
        sys.exit(0)

    return items


def main():
    try:
        keyword = input('検索キーワードを入力してください：').strip()
    except (KeyboardInterrupt, EOFError):
        print('\n中止しました。')
        sys.exit(0)

    if not keyword:
        print('エラー: キーワードを入力してください。')
        sys.exit(1)

    print(f'\n「{keyword}」を検索中...\n')
    items = search_videos(keyword)

    print(f'検索結果（上位{len(items)}件）\n' + '─' * 40)
    for i, item in enumerate(items, 1):
        title = item['snippet']['title']
        video_id = item['id']['videoId']
        url = f'https://www.youtube.com/watch?v={video_id}'
        print(f'{i}. {title}')
        print(f'   {url}\n')


if __name__ == '__main__':
    main()
