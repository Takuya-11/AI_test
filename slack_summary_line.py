"""
Slack の未読メッセージを Claude で要約して LINE に送信する。
実行: python3 slack_summary_line.py
オプション:
  --hours N   過去N時間のメッセージを対象（デフォルト: 72）
  --reset     処理済み記録をリセットして全件再取得
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import anthropic
import requests

load_dotenv()

PROCESSED_PATH = "processed_messages.json"
JST = timezone(timedelta(hours=9))
FETCH_HOURS = 72  # デフォルト: 過去72時間
LINE_API_URL = "https://api.line.me/v2/bot/message/push"


# ── 処理済みIDの管理 ─────────────────────────────────────────


def load_processed() -> set[str]:
    if not os.path.exists(PROCESSED_PATH):
        return set()
    with open(PROCESSED_PATH, encoding="utf-8") as f:
        return set(json.load(f))


def save_processed(ids: set[str]) -> None:
    with open(PROCESSED_PATH, "w", encoding="utf-8") as f:
        json.dump(sorted(ids), f, ensure_ascii=False, indent=2)


# ── Slack メッセージ取得 ─────────────────────────────────────


def fetch_messages(token: str, channel: str, hours: int = FETCH_HOURS) -> list[dict]:
    """指定チャンネルの過去 hours 時間のメッセージを取得する"""
    client = WebClient(token=token)
    oldest = (datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp()

    try:
        result = client.conversations_history(
            channel=channel,
            oldest=str(oldest),
            limit=200,
        )
    except SlackApiError as e:
        error = e.response.get("error", "")
        msgs = {
            "invalid_auth":      "SLACK_BOT_TOKEN が無効です。",
            "token_revoked":     "SLACK_BOT_TOKEN が無効化されています。",
            "missing_scope":     "スコープ不足: channels:history または groups:history を追加してください。",
            "channel_not_found": "SLACK_CHANNEL_ID が見つかりません。",
            "not_in_channel":    "Botがチャンネルにいません。/invite @BotName で招待してください。",
        }
        print(f"Slackエラー: {msgs.get(error, error)}")
        sys.exit(1)

    messages = result.get("messages", [])
    # サブタイプ（チャンネル参加通知など）のみ除外
    return [m for m in messages if not m.get("subtype")]


# ── Claude で要約 ────────────────────────────────────────────


def summarize(messages: list[dict]) -> str:
    """メッセージリストを Claude API で要約する"""
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("エラー: ANTHROPIC_API_KEY が設定されていません。")
        sys.exit(1)

    lines = []
    for m in reversed(messages):  # 古い順に並べ直す
        ts = float(m.get("ts", 0))
        dt = datetime.fromtimestamp(ts, tz=JST).strftime("%m/%d %H:%M")
        text = m.get("text", "").strip()
        user = m.get("user", "不明")
        if text:
            lines.append(f"[{dt}] {user}: {text}")

    conversation_text = "\n".join(lines)

    prompt = f"""以下はSlackチャンネルのメッセージです。
ビジネス上重要な情報を抽出し、日本語で簡潔にまとめてください。

まとめる観点:
- タスク・ToDo（誰が何をするか）
- 期限・締め切り
- 決定事項
- 重要な共有事項

形式:
📋 Slackまとめ（{datetime.now(JST).strftime("%m/%d %H:%M")}）
━━━━━━━━━━━━━━
（各観点ごとに箇条書き。該当なしの観点は省略）
━━━━━━━━━━━━━━
対象メッセージ数: {len(messages)}件

メッセージ:
{conversation_text}"""

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


# ── LINE 送信 ────────────────────────────────────────────────


def send_line(message: str) -> None:
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
    user_id = os.getenv("LINE_USER_ID", "")

    if not token or not user_id:
        print("エラー: LINE_CHANNEL_ACCESS_TOKEN または LINE_USER_ID が未設定です。")
        sys.exit(1)

    try:
        r = requests.post(
            LINE_API_URL,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"to": user_id, "messages": [{"type": "text", "text": message}]},
            timeout=10,
        )
    except requests.exceptions.RequestException as e:
        print(f"LINEネットワークエラー: {e}")
        sys.exit(1)

    if r.status_code == 200:
        print("LINE送信成功")
    elif r.status_code == 401:
        print("LINE送信エラー: Token が無効です。")
        sys.exit(1)
    else:
        print(f"LINE送信エラー: {r.status_code} {r.text}")
        sys.exit(1)


# ── メイン ────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Slack → Claude要約 → LINE通知")
    parser.add_argument("--hours", type=int, default=FETCH_HOURS,
                        help=f"過去N時間のメッセージを対象（デフォルト: {FETCH_HOURS}）")
    parser.add_argument("--reset", action="store_true",
                        help="処理済み記録をリセットして全件再取得")
    args = parser.parse_args()

    slack_token = os.getenv("SLACK_BOT_TOKEN", "")
    channel = os.getenv("SLACK_CHANNEL_ID", "")

    if not slack_token or not channel:
        print("エラー: SLACK_BOT_TOKEN または SLACK_CHANNEL_ID が未設定です。")
        sys.exit(1)

    if args.reset and os.path.exists(PROCESSED_PATH):
        os.remove(PROCESSED_PATH)
        print("処理済み記録をリセットしました。")

    print(f"Slackメッセージを取得中（過去{args.hours}時間）...")
    messages = fetch_messages(slack_token, channel, args.hours)
    print(f"{len(messages)}件取得")

    if not messages:
        print("メッセージが見つかりませんでした。--hours N で取得期間を広げてください。")
        return

    # 処理済みを除外
    processed = load_processed()
    new_messages = [m for m in messages if m.get("ts") not in processed]
    print(f"未処理: {len(new_messages)}件（処理済みを除く）")

    if not new_messages:
        print("すべて処理済みです。--reset で記録をリセットできます。")
        return

    print("Claude で要約中...")
    summary = summarize(new_messages)
    print("要約完了:\n" + summary)

    print("LINE に送信中...")
    send_line(summary)

    # 処理済みに追加
    new_ts = {m["ts"] for m in new_messages}
    save_processed(processed | new_ts)
    print(f"処理済みIDを保存しました（計{len(processed | new_ts)}件）")


if __name__ == "__main__":
    main()
