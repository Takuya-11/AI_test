"""
LINE公式アカウント Webhook サーバー — Googleカレンダー予定管理

起動前準備:
  1. python3 calendar_client.py        （Google Calendar 認証）
  2. .env に LINE_CHANNEL_SECRET を追加  （LINE Developers → チャンネル基本設定）
  3. ngrok http 5000                    （公開URL取得）
  4. LINE Developers → Webhook URL に https://xxxx.ngrok-free.app/webhook を設定

起動: python3 line_schedule.py

対応コマンド:
  [登録] 日付行 + 時刻行を複数行で送信
    10/10
    20:00-21:00 移動
    21:00-23:30 AI
    23:30-24:00 日報

  [一覧] 今日の予定 / 明日の予定 / 10/10の予定
  [削除] 10/10 20:00 移動 削除  /  20:00 移動 削除（当日）
"""
import base64
import hashlib
import hmac
import json
import os
import re
import sys
from datetime import date, datetime, time, timedelta

import requests
import zoneinfo
from dotenv import load_dotenv
from flask import Flask, abort, request

import calendar_client as cal

load_dotenv()

JST = zoneinfo.ZoneInfo("Asia/Tokyo")
LINE_REPLY_URL = "https://api.line.me/v2/bot/message/reply"
PORT = 8080

app = Flask(__name__)


# ── LINE署名検証 ──────────────────────────────────────────────

def verify_signature(body: bytes, signature: str) -> bool:
    secret = os.getenv("LINE_CHANNEL_SECRET", "")
    mac = hmac.new(secret.encode(), body, hashlib.sha256)
    return hmac.compare_digest(base64.b64encode(mac.digest()).decode(), signature)


def reply(reply_token: str, message: str) -> None:
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
    requests.post(
        LINE_REPLY_URL,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        json={"replyToken": reply_token, "messages": [{"type": "text", "text": message}]},
        timeout=10,
    )


# ── メッセージパース ───────────────────────────────────────────

DATE_PAT     = re.compile(r"^(\d{1,2})[/／](\d{1,2})$")
SCHEDULE_PAT = re.compile(r"^(\d{1,2}:\d{2})-(\d{1,2}:\d{2})\s*(.+)$")
LIST_DATE    = re.compile(r"(\d{1,2})[/／](\d{1,2})の予定")
DELETE_DATE  = re.compile(r"(\d{1,2})[/／](\d{1,2})\s+(\d{1,2}:\d{2})\s+(.+?)\s*削除")
DELETE_TODAY = re.compile(r"^(\d{1,2}:\d{2})\s+(.+?)\s*削除$")


def _parse_time(s: str) -> tuple[time, int]:
    """
    "24:00" → (time(0, 0), 1)  day_offset=1 = 翌日
    "23:30" → (time(23, 30), 0)
    """
    h, m = map(int, s.split(":"))
    if h >= 24:
        return time(h - 24, m), 1
    return time(h, m), 0


def _resolve_date(month: str, day: str) -> date | None:
    """月/日 → date（今年。過去日なら翌年）"""
    today = date.today()
    try:
        target = date(today.year, int(month), int(day))
    except ValueError:
        return None
    if target < today:
        try:
            target = date(today.year + 1, int(month), int(day))
        except ValueError:
            return None
    return target


def parse_schedules(text: str) -> tuple[list[dict], list[str]]:
    """
    テキストをパースして (登録済みリスト, エラーリスト) を返す。

    登録リストの各要素: {"summary": str, "start_dt": datetime, "end_dt": datetime}
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    current_date = date.today()
    parsed: list[dict] = []
    errors: list[str] = []

    for line in lines:
        # 日付行: 今日 / 明日
        if line in ("今日", "きょう"):
            current_date = date.today()
            continue
        if line in ("明日", "あした", "あす"):
            current_date = date.today() + timedelta(days=1)
            continue

        # 日付行: 10/10
        m = DATE_PAT.match(line)
        if m:
            d = _resolve_date(m.group(1), m.group(2))
            if d:
                current_date = d
            else:
                errors.append(f"日付の解析失敗: {line}")
            continue

        # 予定行: 20:00-21:00 タイトル
        m = SCHEDULE_PAT.match(line)
        if m:
            start_str, end_str, title = m.group(1), m.group(2), m.group(3).strip()
            try:
                start_t, _      = _parse_time(start_str)
                end_t,   offset = _parse_time(end_str)
            except ValueError:
                errors.append(f"時刻の解析失敗: {line}")
                continue

            parsed.append({
                "summary":  title,
                "start_dt": datetime.combine(current_date,                     start_t, tzinfo=JST),
                "end_dt":   datetime.combine(current_date + timedelta(days=offset), end_t, tzinfo=JST),
            })
            continue

        # どのパターンにも一致しない行は解析エラー
        errors.append(f"認識できない行: {line}")

    return parsed, errors


# ── メッセージハンドラ ─────────────────────────────────────────

def _fmt_list(events: list[dict], label: str) -> str:
    if not events:
        return f"📅 {label}の予定はありません。"
    lines = [f"📅 {label}の予定"]
    for e in events:
        lines.append(f"  {e['start']}-{e['end']} {e['summary']}")
    return "\n".join(lines)


def handle_message(text: str, reply_token: str) -> None:
    today = date.today()

    # 一覧: 今日の予定
    if "今日の予定" in text:
        events = cal.list_events(today)
        reply(reply_token, _fmt_list(events, f"{today.month}/{today.day}（今日）"))
        return

    # 一覧: 明日の予定
    if "明日の予定" in text:
        tomorrow = today + timedelta(days=1)
        events = cal.list_events(tomorrow)
        reply(reply_token, _fmt_list(events, f"{tomorrow.month}/{tomorrow.day}（明日）"))
        return

    # 一覧: MM/DDの予定
    m = LIST_DATE.search(text)
    if m:
        target = _resolve_date(m.group(1), m.group(2))
        if target:
            reply(reply_token, _fmt_list(cal.list_events(target), f"{target.month}/{target.day}"))
        else:
            reply(reply_token, "日付を認識できませんでした。")
        return

    # 削除: MM/DD HH:MM タイトル 削除
    m = DELETE_DATE.search(text)
    if m:
        target = _resolve_date(m.group(1), m.group(2))
        start_str, keyword = m.group(3), m.group(4)
        if not target:
            reply(reply_token, "日付を認識できませんでした。")
            return
        ev = cal.find_event(target, start_str, keyword)
        if ev:
            cal.delete_event(ev["id"])
            reply(reply_token, f"✅ 削除しました\n{target.month}/{target.day} {ev['start']} {ev['summary']}")
        else:
            reply(reply_token, f"❌ 予定が見つかりませんでした\n{target.month}/{target.day} {start_str} {keyword}")
        return

    # 削除: HH:MM タイトル 削除（当日）
    m = DELETE_TODAY.search(text)
    if m:
        start_str, keyword = m.group(1), m.group(2)
        ev = cal.find_event(today, start_str, keyword)
        if ev:
            cal.delete_event(ev["id"])
            reply(reply_token, f"✅ 削除しました\n{today.month}/{today.day} {ev['start']} {ev['summary']}")
        else:
            reply(reply_token, f"❌ 予定が見つかりませんでした\n{start_str} {keyword}")
        return

    # 予定登録（デフォルト）
    parsed, errors = parse_schedules(text)

    if not parsed and not errors:
        reply(reply_token, (
            "予定の形式が認識できませんでした。\n\n"
            "【登録例】\n"
            "10/10\n"
            "20:00-21:00 移動\n"
            "21:00-23:30 AI\n"
            "23:30-24:00 日報\n\n"
            "【一覧】今日の予定 / 明日の予定 / 10/10の予定\n"
            "【削除】10/10 20:00 移動 削除"
        ))
        return

    if not parsed:
        reply(reply_token, "❌ 登録できませんでした\n" + "\n".join(errors))
        return

    # 一括登録（失敗時はロールバック）
    created_ids: list[str] = []
    try:
        for item in parsed:
            eid = cal.create_event(item["summary"], item["start_dt"], item["end_dt"])
            created_ids.append(eid)
    except Exception as e:
        for eid in created_ids:
            try:
                cal.delete_event(eid)
            except Exception:
                pass
        reply(reply_token, f"❌ 登録に失敗しました（登録済み分もロールバック済み）\n詳細: {e}")
        return

    # 成功返信
    lines = [f"✅ {len(parsed)}件の予定を登録しました"]
    for item in parsed:
        s = item["start_dt"].strftime("%-m/%-d %H:%M")
        e = item["end_dt"].strftime("%H:%M")
        lines.append(f"  {s}-{e} {item['summary']}")
    if errors:
        lines.append("\n⚠️ 以下の行は解析できませんでした:")
        lines.extend(f"  {err}" for err in errors)
    reply(reply_token, "\n".join(lines))


# ── Webhook エンドポイント ─────────────────────────────────────

@app.route("/webhook", methods=["POST"])
def webhook():
    body = request.get_data()
    sig  = request.headers.get("X-Line-Signature", "")

    if not verify_signature(body, sig):
        abort(400)

    data = json.loads(body)
    for event in data.get("events", []):
        if event.get("type") != "message":
            continue
        msg = event.get("message", {})
        if msg.get("type") != "text":
            continue
        try:
            handle_message(msg["text"].strip(), event["replyToken"])
        except Exception as e:
            try:
                reply(event["replyToken"], f"❌ エラーが発生しました: {e}")
            except Exception:
                pass

    return "OK", 200


# ── 起動 ─────────────────────────────────────────────────────

if __name__ == "__main__":
    # 必須環境変数チェック
    missing = []
    if not os.getenv("LINE_CHANNEL_SECRET"):
        missing.append("LINE_CHANNEL_SECRET")
    if not os.getenv("LINE_CHANNEL_ACCESS_TOKEN"):
        missing.append("LINE_CHANNEL_ACCESS_TOKEN")
    if missing:
        print(f"エラー: .env に以下を設定してください: {', '.join(missing)}", file=sys.stderr)
        print("LINE_CHANNEL_SECRET は LINE Developers → チャンネル基本設定 で確認できます。", file=sys.stderr)
        sys.exit(1)

    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    local_ip = s.getsockname()[0]
    s.close()

    print(f"\n{'='*50}")
    print("LINE スケジュール Webhook サーバー起動中")
    print(f"{'='*50}")
    print(f"ローカル: http://{local_ip}:{PORT}/webhook")
    print(f"\n[ ngrok 手順 ]")
    print(f"  $ ngrok http {PORT}")
    print(f"  → https://xxxx.ngrok-free.app/webhook を")
    print(f"    LINE Developers の Webhook URL に設定")
    print(f"{'='*50}\n")

    app.run(host="0.0.0.0", port=PORT, debug=False)
