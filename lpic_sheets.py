"""
Google Sheetsで学習履歴を管理するヘルパー
"""
import os
import json
from datetime import date, timedelta
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/meetings.space.created",
]
TOKEN_PATH = "token.json"
CREDENTIALS_PATH = "credentials.json"

SHEET_HISTORY = "history"
SHEET_SESSIONS = "sessions"
SHEET_ANSWERS = "answers"

HISTORY_HEADERS = [
    "question_id", "first_seen", "last_seen",
    "times_shown", "times_correct", "times_wrong",
    "next_review", "interval_days",
]
SESSION_HEADERS = ["date", "question_ids", "new_count", "review_count", "correct_count", "wrong_count"]
ANSWER_HEADERS = ["date", "time", "question_id", "user_answer", "correct_answer", "is_correct"]


def get_credentials() -> Credentials:
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())
    return creds


def get_service():
    return build("sheets", "v4", credentials=get_credentials())


def get_or_create_spreadsheet(service) -> str:
    """環境変数からSpreadsheet IDを取得、なければ新規作成"""
    from dotenv import load_dotenv
    load_dotenv()
    sheet_id = os.getenv("LPIC_SHEETS_ID", "")
    if sheet_id:
        return sheet_id

    # 新規作成
    spreadsheet = service.spreadsheets().create(body={
        "properties": {"title": "LPIC学習履歴"},
        "sheets": [
            {"properties": {"title": SHEET_HISTORY}},
            {"properties": {"title": SHEET_SESSIONS}},
            {"properties": {"title": SHEET_ANSWERS}},
        ],
    }).execute()
    sheet_id = spreadsheet["spreadsheetId"]

    # ヘッダー行を挿入
    _write(service, sheet_id, f"{SHEET_HISTORY}!A1", [HISTORY_HEADERS])
    _write(service, sheet_id, f"{SHEET_SESSIONS}!A1", [SESSION_HEADERS])
    _write(service, sheet_id, f"{SHEET_ANSWERS}!A1", [ANSWER_HEADERS])

    # .env に書き込み
    _append_env("LPIC_SHEETS_ID", sheet_id)
    print(f"Google Sheets 作成完了: https://docs.google.com/spreadsheets/d/{sheet_id}")
    return sheet_id


def _append_env(key: str, value: str) -> None:
    env_path = ".env"
    with open(env_path, "a") as f:
        f.write(f"\n{key}={value}\n")


def _write(service, sheet_id: str, range_: str, values: list) -> None:
    service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=range_,
        valueInputOption="RAW",
        body={"values": values},
    ).execute()


def _append(service, sheet_id: str, range_: str, values: list) -> None:
    service.spreadsheets().values().append(
        spreadsheetId=sheet_id,
        range=range_,
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": values},
    ).execute()


def _read(service, sheet_id: str, range_: str) -> list:
    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id, range=range_
    ).execute()
    return result.get("values", [])


# ---------- 公開API ----------

def load_history_from_sheets() -> dict:
    """Sheetsから学習履歴をdictとして返す"""
    service = get_service()
    sheet_id = get_or_create_spreadsheet(service)

    rows = _read(service, sheet_id, f"{SHEET_HISTORY}!A:H")
    if not rows or len(rows) < 2:
        return {}

    history = {}
    for row in rows[1:]:  # ヘッダーをスキップ
        if len(row) < 8:
            continue
        qid = row[0]
        history[qid] = {
            "first_seen": row[1],
            "last_seen": row[2],
            "times_shown": int(row[3]),
            "times_correct": int(row[4]),
            "times_wrong": int(row[5]),
            "next_review": row[6],
            "interval_days": int(row[7]),
        }
    return history


def save_session_to_sheets(session_date: str, selected_ids: list,
                            new_count: int, review_count: int,
                            correct_count: int = 0, wrong_count: int = 0) -> None:
    service = get_service()
    sheet_id = get_or_create_spreadsheet(service)
    _append(service, sheet_id, f"{SHEET_SESSIONS}!A:F", [[
        session_date, ",".join(selected_ids),
        new_count, review_count, correct_count, wrong_count,
    ]])


def save_answers_to_sheets(answers: list[dict]) -> None:
    """answers: [{date, time, question_id, user_answer, correct_answer, is_correct}]"""
    service = get_service()
    sheet_id = get_or_create_spreadsheet(service)
    rows = [
        [a["date"], a["time"], a["question_id"],
         a["user_answer"], a["correct_answer"], a["is_correct"]]
        for a in answers
    ]
    _append(service, sheet_id, f"{SHEET_ANSWERS}!A:F", rows)


def update_history_in_sheets(history_updates: dict) -> None:
    """history_updates: {question_id: {学習履歴フィールド}}"""
    service = get_service()
    sheet_id = get_or_create_spreadsheet(service)

    # 現在のデータを読み込み
    rows = _read(service, sheet_id, f"{SHEET_HISTORY}!A:H")
    existing_ids = {}
    if rows and len(rows) > 1:
        for i, row in enumerate(rows[1:], start=2):  # 行番号（1始まり）
            if row:
                existing_ids[row[0]] = i

    new_rows = []
    update_requests = []

    for qid, h in history_updates.items():
        row_data = [
            qid, h["first_seen"], h["last_seen"],
            h["times_shown"], h["times_correct"], h["times_wrong"],
            h["next_review"], h["interval_days"],
        ]
        if qid in existing_ids:
            row_num = existing_ids[qid]
            update_requests.append({
                "range": f"{SHEET_HISTORY}!A{row_num}:H{row_num}",
                "values": [row_data],
            })
        else:
            new_rows.append(row_data)

    # バッチ更新
    if update_requests:
        service.spreadsheets().values().batchUpdate(
            spreadsheetId=sheet_id,
            body={"valueInputOption": "RAW", "data": update_requests},
        ).execute()

    if new_rows:
        _append(service, sheet_id, f"{SHEET_HISTORY}!A:H", new_rows)
