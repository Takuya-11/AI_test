import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

LINE_API_URL = "https://api.line.me/v2/bot/message/push"

DEFAULT_MESSAGE = "こんにちは！PythonからLINEを送っています。\nこれはLINE Messaging APIからのテストメッセージです！"


def send_line_message(message: str) -> None:
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    user_id = os.getenv("LINE_USER_ID")

    if not token or token == "ここにChannel Access Tokenを入れる":
        print("エラー：LINE_CHANNEL_ACCESS_TOKEN が設定されていません。")
        print(".env に Channel Access Token を設定してください。")
        sys.exit(1)

    if not user_id or user_id == "ここにUser IDを入れる":
        print("エラー：LINE_USER_ID が設定されていません。")
        print(".env に送信先の User ID を設定してください。")
        sys.exit(1)

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    payload = {
        "to": user_id,
        "messages": [{"type": "text", "text": message}],
    }

    try:
        response = requests.post(LINE_API_URL, headers=headers, json=payload, timeout=10)
    except requests.exceptions.ConnectionError:
        print("エラー：LINE Messaging API へ接続できませんでした。ネットワークを確認してください。")
        sys.exit(1)
    except requests.exceptions.Timeout:
        print("エラー：LINE Messaging API への接続がタイムアウトしました。")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"エラー：通信中に問題が発生しました。\n詳細：{e}")
        sys.exit(1)

    if response.status_code == 200:
        print("=" * 30)
        print("LINEへの送信に成功しました！")
        print("=" * 30)
        print("メッセージ：")
        print(message)
    elif response.status_code == 401:
        print("エラー：Channel Access Token が無効です。LINE Developers で確認してください。")
        sys.exit(1)
    elif response.status_code == 400:
        data = response.json()
        detail = data.get("message", "不明なエラー")
        if "userId" in detail.lower() or "to" in detail.lower():
            print(f"エラー：User ID が間違っています。LINE Developers で送信先 User ID を確認してください。")
        else:
            print(f"エラー：リクエストが不正です。\n詳細：{detail}")
        sys.exit(1)
    else:
        data = response.json()
        print(f"エラー：メッセージ送信に失敗しました（ステータス：{response.status_code}）")
        print(f"詳細：{data.get('message', '不明なエラー')}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        message = " ".join(sys.argv[1:])
    else:
        try:
            message = input("送信するメッセージを入力してください（空でEnterで既定のメッセージ）：").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n中止しました。")
            sys.exit(0)
        if not message:
            message = DEFAULT_MESSAGE

    print("\nLINEに送信中...\n")
    send_line_message(message)
