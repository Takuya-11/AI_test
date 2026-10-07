"""
毎朝7:00に実行: 今日の20問を準備してLINEへ通知
launchd または 手動で実行する
"""
import json
import os
import socket
import subprocess
import sys
from datetime import date
from dotenv import load_dotenv
import requests

load_dotenv()

SESSION_PATH = "lpic_data/today_session.json"
QUESTIONS_PATH = "lpic_data/questions.json"
PORT = 3000
DAILY_COUNT = 20


def get_local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]
    s.close()
    return ip


def load_questions() -> list[dict]:
    with open(QUESTIONS_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_history_from_sheets() -> dict:
    """Google Sheetsから履歴を取得、失敗時はローカルJSONにフォールバック"""
    try:
        from lpic_sheets import load_history_from_sheets as sheets_load
        history = sheets_load()
        # ローカルにキャッシュ
        with open("lpic_data/history.json", "w", encoding="utf-8") as f:
            json.dump({"questions": history, "sessions": []}, f, ensure_ascii=False, indent=2)
        return history
    except Exception as e:
        print(f"Sheets読み込みエラー（ローカルフォールバック）: {e}")
        local_path = "lpic_data/history.json"
        if os.path.exists(local_path):
            with open(local_path, encoding="utf-8") as f:
                data = json.load(f)
            return data.get("questions", {})
        return {}


def select_questions(questions: list[dict], history: dict, today: date) -> tuple[list[dict], int, int]:
    """今日の問題を選択。(selected, new_count, review_count) を返す"""
    from lpic_quiz import select_questions as _select, DAILY_COUNT
    import random

    # lpic_quiz.select_questions はhistory全体のdictを期待
    history_wrapper = {"questions": history, "sessions": []}
    selected = _select(questions, history_wrapper, today)

    new_count = sum(1 for q in selected if q["id"] not in history)
    review_count = DAILY_COUNT - new_count
    return selected, new_count, review_count


def save_session(selected: list[dict], history: dict, new_count: int, review_count: int, today: date) -> None:
    session = {
        "date": today.isoformat(),
        "new_count": new_count,
        "review_count": review_count,
        "questions": selected,
        "history_snapshot": {
            q["id"]: history[q["id"]]
            for q in selected
            if q["id"] in history
        },
    }
    os.makedirs("lpic_data", exist_ok=True)
    with open(SESSION_PATH, "w", encoding="utf-8") as f:
        json.dump(session, f, ensure_ascii=False, indent=2)


def calc_coverage(questions: list[dict], history: dict, today: date) -> dict:
    total = len(questions)
    seen = len(history)
    unseen = total - seen
    days_remaining = max(1, 30 - (today - date(2026, 10, 7)).days)  # 10/7スタート想定
    needed_per_day = unseen / days_remaining if days_remaining > 0 else 0
    coverable = days_remaining * DAILY_COUNT >= unseen

    return {
        "total": total,
        "seen": seen,
        "unseen": unseen,
        "coverage_pct": round(seen / total * 100, 1),
        "days_remaining": days_remaining,
        "needed_per_day": round(needed_per_day, 1),
        "coverable_in_month": coverable,
    }


def start_server() -> None:
    """Flaskサーバーをバックグラウンドで起動（多重起動防止）"""
    result = subprocess.run(["lsof", "-ti", f":{PORT}"], capture_output=True, text=True)
    if result.stdout.strip():
        print(f"Flaskサーバーはすでに起動中 (port {PORT})")
        return

    venv_python = os.path.join(os.path.dirname(sys.executable), "python3")
    if not os.path.exists(venv_python):
        venv_python = sys.executable

    script_dir = os.path.dirname(os.path.abspath(__file__))
    subprocess.Popen(
        [venv_python, "lpic_server.py"],
        cwd=script_dir,
        stdout=open("lpic_data/server.log", "a"),
        stderr=subprocess.STDOUT,
    )
    import time; time.sleep(2)
    print(f"Flaskサーバーを起動しました (port {PORT})")


def get_ngrok_url() -> str:
    """起動中のngrokトンネルURLを取得する"""
    import urllib.request, json as _json, time

    # ngrokのローカルAPIからURLを取得
    for _ in range(5):
        try:
            with urllib.request.urlopen("http://localhost:4040/api/tunnels", timeout=3) as res:
                data = _json.loads(res.read())
            tunnels = data.get("tunnels", [])
            for t in tunnels:
                url = t.get("public_url", "")
                if url.startswith("https://"):
                    return url
                if url.startswith("http://"):
                    return url.replace("http://", "https://")
        except Exception:
            time.sleep(1)

    raise RuntimeError("ngrokが起動していません。先に以下を実行してください:\nngrok http --domain=glacier-sliceable-camping.ngrok-free.dev 3000 &")


def send_line_notification(quiz_url: str, new_count: int, review_count: int, coverage: dict) -> None:
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
    user_id = os.getenv("LINE_USER_ID", "")
    if not token or not user_id or "ここに" in token:
        print("LINE認証情報が未設定です。")
        return

    if coverage["coverable_in_month"]:
        plan_text = f"✅ このペースで1か月以内に全{coverage['total']}問網羅できます！"
    else:
        plan_text = (
            f"⚠️ 残り{coverage['unseen']}問を{coverage['days_remaining']}日で終えるには\n"
            f"   1日{coverage['needed_per_day']:.0f}問必要です。"
        )

    text = (
        f"📚 LPIC学習の時間です！\n"
        f"━━━━━━━━━━━━━━\n"
        f"🆕 新規問題：{new_count}問\n"
        f"🔁 復習問題：{review_count}問\n"
        f"━━━━━━━━━━━━━━\n"
        f"📊 進捗：{coverage['seen']}/{coverage['total']}問 ({coverage['coverage_pct']}%)\n"
        f"{plan_text}\n"
        f"━━━━━━━━━━━━━━\n"
        f"🚀 今日の問題をスタート\n"
        f"{quiz_url}"
    )

    r = requests.post(
        "https://api.line.me/v2/bot/message/push",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"to": user_id, "messages": [{"type": "text", "text": text}]},
        timeout=10,
    )
    if r.status_code == 200:
        print("LINE通知を送信しました。")
    else:
        print(f"LINE送信エラー: {r.status_code} {r.text}")


def main():
    today = date.today()
    print(f"[{today}] LPIC朝の準備を開始...")

    questions = load_questions()
    print(f"問題数: {len(questions)}問")

    print("Google Sheetsから学習履歴を読み込み中...")
    history = load_history_from_sheets()
    print(f"既出題数: {len(history)}問")

    selected, new_count, review_count = select_questions(questions, history, today)
    print(f"今日の選択: 新規{new_count}問 + 復習{review_count}問 = {len(selected)}問")

    save_session(selected, history, new_count, review_count, today)
    print(f"セッション保存完了: {SESSION_PATH}")

    coverage = calc_coverage(questions, history, today)

    start_server()
    quiz_url = get_ngrok_url()
    print(f"クイズURL（公開）: {quiz_url}")

    send_line_notification(quiz_url, new_count, review_count, coverage)
    print("完了。")


if __name__ == "__main__":
    main()
