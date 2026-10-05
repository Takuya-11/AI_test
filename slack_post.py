import os
import sys
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

load_dotenv()

DEFAULT_MESSAGE = "Slack APIからのテストメッセージです！"


def get_env():
    token = os.getenv('SLACK_BOT_TOKEN', '')
    channel = os.getenv('SLACK_CHANNEL_ID', '')

    if not token or token == 'ここにBot Tokenを入れる':
        print('エラー: .env に SLACK_BOT_TOKEN が設定されていません。')
        sys.exit(1)
    if not channel or channel == 'ここにチャンネルIDを入れる':
        print('エラー: .env に SLACK_CHANNEL_ID が設定されていません。')
        sys.exit(1)

    return token, channel


def post_message(token, channel, message):
    client = WebClient(token=token)
    try:
        response = client.chat_postMessage(channel=channel, text=message)
    except SlackApiError as e:
        error = e.response.get('error', '')
        messages = {
            'invalid_auth':        'Bot Tokenが無効です。SLACK_BOT_TOKEN を確認してください。',
            'token_revoked':       'Bot Tokenが無効化されています。Slack Appで再発行してください。',
            'missing_scope':       'スコープが不足しています。Slack Appに chat:write スコープを追加してください。',
            'not_in_channel':      'Botがチャンネルにいません。チャンネルにBotを招待してください（/invite @BotName）。',
            'channel_not_found':   'チャンネルが見つかりません。SLACK_CHANNEL_ID を確認してください。',
            'is_archived':         'チャンネルがアーカイブされています。',
            'msg_too_long':        'メッセージが長すぎます。',
            'rate_limited':        'APIの利用制限に達しました。しばらく待ってから再試行してください。',
        }
        msg = messages.get(error, f'Slack APIエラー: {error}')
        print(f'エラー: {msg}')
        sys.exit(1)
    except Exception as e:
        print(f'エラー: Slack APIへの通信に失敗しました。\n詳細: {e}')
        sys.exit(1)

    return response


def main():
    token, channel = get_env()

    try:
        message = input(f'投稿するメッセージを入力してください（空でEnterで既定のメッセージ）：').strip()
    except (KeyboardInterrupt, EOFError):
        print('\n中止しました。')
        sys.exit(0)

    if not message:
        message = DEFAULT_MESSAGE

    print(f'\nチャンネル「{channel}」に投稿中...\n')
    response = post_message(token, channel, message)

    print('=' * 30)
    print('投稿に成功しました。')
    print('=' * 30)
    print(f'チャンネル  : {response["channel"]}')
    print(f'タイムスタンプ: {response["ts"]}')
    print(f'メッセージ  : {message}')


if __name__ == '__main__':
    main()
