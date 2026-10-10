"""
Google Calendar API クライアント
初回実行: python3 calendar_client.py  （ブラウザで認証）
"""
import os
import sys
from datetime import date, datetime, time, timedelta
import zoneinfo

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/calendar"]
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "calendar_token.json"
CALENDAR_ID = "primary"
JST = zoneinfo.ZoneInfo("Asia/Tokyo")


def authenticate() -> Credentials:
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                print(f"エラー: {CREDENTIALS_FILE} が見つかりません。", file=sys.stderr)
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return creds


def _service():
    return build("calendar", "v3", credentials=authenticate())


def create_event(summary: str, start_dt: datetime, end_dt: datetime) -> str:
    """予定を作成してイベントIDを返す"""
    body = {
        "summary": summary,
        "start": {"dateTime": start_dt.isoformat(), "timeZone": "Asia/Tokyo"},
        "end":   {"dateTime": end_dt.isoformat(),   "timeZone": "Asia/Tokyo"},
    }
    ev = _service().events().insert(calendarId=CALENDAR_ID, body=body).execute()
    return ev["id"]


def list_events(target: date) -> list[dict]:
    """指定日の予定一覧 [{id, summary, start, end}, ...]"""
    day_start = datetime.combine(target,                    time(0, 0), tzinfo=JST)
    day_end   = datetime.combine(target + timedelta(days=1), time(0, 0), tzinfo=JST)

    result = _service().events().list(
        calendarId=CALENDAR_ID,
        timeMin=day_start.isoformat(),
        timeMax=day_end.isoformat(),
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    out = []
    for e in result.get("items", []):
        raw_s = e["start"].get("dateTime", e["start"].get("date"))
        raw_e = e["end"].get("dateTime",   e["end"].get("date"))
        try:
            s  = datetime.fromisoformat(raw_s).astimezone(JST).strftime("%H:%M")
            en = datetime.fromisoformat(raw_e).astimezone(JST).strftime("%H:%M")
        except Exception:
            s, en = raw_s, raw_e
        out.append({
            "id": e["id"],
            "summary": e.get("summary", "（タイトルなし）"),
            "start": s,
            "end": en,
        })
    return out


def delete_event(event_id: str) -> None:
    _service().events().delete(calendarId=CALENDAR_ID, eventId=event_id).execute()


def find_event(target: date, start_str: str, keyword: str = "") -> dict | None:
    """開始時刻（HH:MM）とキーワードで予定を検索して最初のマッチを返す"""
    for e in list_events(target):
        if e["start"] == start_str and (not keyword or keyword in e["summary"]):
            return e
    return None


if __name__ == "__main__":
    print("Google Calendar 認証中...")
    authenticate()
    today = date.today()
    events = list_events(today)
    print(f"\n今日（{today}）の予定:")
    if events:
        for e in events:
            print(f"  {e['start']}-{e['end']} {e['summary']}")
    else:
        print("  （なし）")
    print("\n認証・接続テスト完了。")
