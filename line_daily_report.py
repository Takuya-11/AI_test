"""
毎日21:00にLINEへ日報フォーマットを自動送信するスクリプト。
launchd または手動実行どちらでも動作する。
"""
import os
import sys
import logging
from datetime import datetime
import zoneinfo
import requests
from dotenv import load_dotenv

load_dotenv()

# ── ログ設定 ─────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("line_daily_report.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

JST = zoneinfo.ZoneInfo("Asia/Tokyo")
LINE_API_URL = "https://api.line.me/v2/bot/message/push"


def build_message() -> str:
    """当日の日付（日本時間）を取得して日報フォーマットを生成する"""
    now = datetime.now(JST)
    date_str = f"{now.year}年{now.month}月{now.day}日"

    return f"""{date_str}日報

・今日の主な出来事:

・感謝3つ:

・学んだこと:

・できたことや改善点:

・自分に対するポジティブな言葉:

・明日の目標:

・今日の一言:

━━━━━━━━━━━━━━
🔴 緊急度：高 × 重要度：高
今すぐ対応するもの
・本業

🟡 緊急度：低 × 重要度：高
・日報
・青木社長の動画
・英語学習

🟢 緊急度：高 × 重要度：低
・メール返信

⚪ 緊急度：低 × 重要度：低
・SNS確認"""


def get_env() -> tuple[str, str]:
    """環境変数からToken・User IDを取得してバリデーションする"""
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
    user_id = os.getenv("LINE_USER_ID", "")

    if not token or "ここに" in token:
        log.error("LINE_CHANNEL_ACCESS_TOKENが設定されていません")
        sys.exit(1)

    if not user_id or "ここに" in user_id:
        log.error("LINE_USER_IDが設定されていません")
        sys.exit(1)

    return token, user_id


def send(token: str, user_id: str, message: str) -> None:
    """LINE Push MessageAPIへ送信し、結果をログに記録する"""
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
        log.error("ネットワークエラー：LINE APIに接続できませんでした")
        sys.exit(1)
    except requests.exceptions.Timeout:
        log.error("ネットワークエラー：LINE APIへの接続がタイムアウトしました")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        log.error("ネットワークエラー：%s", e)
        sys.exit(1)

    if response.status_code == 200:
        log.info("送信成功 ステータス:%d", response.status_code)
    elif response.status_code == 401:
        log.error("送信失敗 ステータス:401 — TokenGが無効の可能性があります。LINE DevelopersでTokenを確認してください")
        sys.exit(1)
    elif response.status_code == 400:
        detail = response.json().get("message", "不明")
        log.error("送信失敗 ステータス:400 — User IDまたはリクエスト内容を確認してください。詳細: %s", detail)
        sys.exit(1)
    else:
        log.error("送信失敗 ステータス:%d — %s", response.status_code, response.text)
        sys.exit(1)


def main() -> None:
    log.info("日報送信を開始します")

    token, user_id = get_env()
    message = build_message()

    log.info("送信メッセージ:\n%s", message)
    send(token, user_id, message)

    log.info("日報送信が完了しました")


if __name__ == "__main__":
    main()
