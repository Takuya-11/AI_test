"""
LPICクイズWebサーバー（Flask）
iPhone Safari → http://[MacのIP]:8080 でアクセス
"""
import json
import os
import socket
import subprocess
import sys
from datetime import datetime
from flask import Flask, render_template, jsonify, request

app = Flask(__name__)

SESSION_PATH = "lpic_data/today_session.json"
PORT = 3000


def load_session() -> dict | None:
    if not os.path.exists(SESSION_PATH):
        return None
    with open(SESSION_PATH, encoding="utf-8") as f:
        return json.load(f)


def get_local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]
    s.close()
    return ip


@app.route("/")
def index():
    session = load_session()
    if not session:
        return "<h2>今日のセッションがまだ準備されていません。<br>lpic_morning.py を実行してください。</h2>", 404
    return render_template("quiz.html",
                           date=session["date"],
                           total=len(session["questions"]))


@app.route("/api/session")
def api_session():
    session = load_session()
    if not session:
        return jsonify({"error": "セッションがありません"}), 404
    return jsonify(session)


@app.route("/api/submit", methods=["POST"])
def api_submit():
    data = request.get_json()
    if not data:
        return jsonify({"error": "データがありません"}), 400

    answers = data.get("answers", [])
    session = load_session()
    if not session:
        return jsonify({"error": "セッションがありません"}), 404

    # 結果集計
    correct = sum(1 for a in answers if a.get("is_correct"))
    wrong = len(answers) - correct

    # Sheetsへ保存
    try:
        from lpic_sheets import save_answers_to_sheets, update_history_in_sheets, save_session_to_sheets
        from lpic_quiz import INTERVALS, INTERVAL_WRONG, INTERVAL_MAX
        from datetime import date, timedelta

        today = date.today()
        today_str = today.isoformat()

        # 回答記録
        answer_records = []
        for a in answers:
            answer_records.append({
                "date": today_str,
                "time": datetime.now().strftime("%H:%M:%S"),
                "question_id": a["question_id"],
                "user_answer": str(a.get("user_answer", "")),
                "correct_answer": str(a.get("correct_answer", "")),
                "is_correct": "1" if a.get("is_correct") else "0",
            })
        save_answers_to_sheets(answer_records)

        # 履歴更新
        history_updates = {}
        for a in answers:
            qid = a["question_id"]
            h = session["history_snapshot"].get(qid, None)
            is_correct = a.get("is_correct", False)

            if h is None:
                # 初回
                interval = INTERVALS.get(0, 1)
                history_updates[qid] = {
                    "first_seen": today_str,
                    "last_seen": today_str,
                    "times_shown": 1,
                    "times_correct": 1 if is_correct else 0,
                    "times_wrong": 0 if is_correct else 1,
                    "next_review": (today + timedelta(days=interval)).isoformat(),
                    "interval_days": interval,
                }
            else:
                times_correct = h["times_correct"] + (1 if is_correct else 0)
                times_wrong = h["times_wrong"] + (0 if is_correct else 1)
                if is_correct:
                    interval = min(h["interval_days"] * 2, INTERVAL_MAX)
                else:
                    interval = INTERVAL_WRONG
                history_updates[qid] = {
                    "first_seen": h["first_seen"],
                    "last_seen": today_str,
                    "times_shown": h["times_shown"] + 1,
                    "times_correct": times_correct,
                    "times_wrong": times_wrong,
                    "next_review": (today + timedelta(days=interval)).isoformat(),
                    "interval_days": interval,
                }
        update_history_in_sheets(history_updates)

        # セッション記録
        save_session_to_sheets(
            today_str,
            [a["question_id"] for a in answers],
            session.get("new_count", 0),
            session.get("review_count", 0),
            correct, wrong,
        )

        # LINE完了通知
        _send_completion_line(correct, wrong, session, history_updates)

    except Exception as e:
        print(f"Sheets保存エラー: {e}")

    return jsonify({
        "correct": correct,
        "wrong": wrong,
        "total": len(answers),
        "accuracy": round(correct / max(len(answers), 1) * 100, 1),
    })


def _send_completion_line(correct: int, wrong: int, session: dict, history_updates: dict) -> None:
    import os, requests
    from dotenv import load_dotenv
    load_dotenv()
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
    user_id = os.getenv("LINE_USER_ID", "")
    if not token or not user_id or "ここに" in token:
        return

    total = correct + wrong
    accuracy = round(correct / max(total, 1) * 100)
    streak_emoji = "🔥" if accuracy >= 80 else "📚" if accuracy >= 60 else "💪"

    # 苦手問題（間違えた問題）
    wrong_ids = [
        a["question_id"]
        for a in session.get("questions", [])
        if history_updates.get(a["id"], {}).get("times_wrong", 0) > 0
           and not any(True for _ in [1])  # placeholder
    ]

    text = (
        f"🎉 今日のLPIC学習 完了！\n"
        f"━━━━━━━━━━━━━━\n"
        f"{streak_emoji} 正解：{correct}/{total}問（{accuracy}%）\n"
        f"❌ 不正解：{wrong}問\n"
        f"━━━━━━━━━━━━━━\n"
        f"お疲れさまでした！\n"
        f"間違えた問題は明日優先的に出題されます。"
    )

    requests.post(
        "https://api.line.me/v2/bot/message/push",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"to": user_id, "messages": [{"type": "text", "text": text}]},
        timeout=10,
    )


@app.route("/result")
def result():
    return render_template("result.html")


if __name__ == "__main__":
    ip = get_local_ip()
    print(f"\n{'='*40}")
    print(f"LPICクイズサーバー起動中")
    print(f"{'='*40}")
    print(f"iPhone でアクセス：http://{ip}:{PORT}")
    print(f"{'='*40}\n")
    app.run(host="0.0.0.0", port=PORT, debug=False)
