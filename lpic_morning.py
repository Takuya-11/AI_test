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

# ── 固定出題スケジュール ────────────────────────────────────
# new/review: (開始番号, 終了番号)  ※問題番号は1始まりの整数
# review_range: その範囲を全部復習
# weak_points: 履歴から不正解率の高い問題を抽出
# random_all:  全363問からランダム
SCHEDULE: dict[str, dict] = {
    # Phase 1: 新規20問 + 復習20問（順番通り）
    "2026-10-08": {"new": (1,   20),  "review": None},
    "2026-10-09": {"new": (21,  40),  "review": (1,   20)},
    "2026-10-10": {"new": (41,  60),  "review": (21,  40)},
    "2026-10-11": {"new": (61,  80),  "review": (1,   20)},
    "2026-10-12": {"new": (81,  100), "review": (21,  40)},
    "2026-10-13": {"new": (101, 120), "review": (41,  60)},
    "2026-10-14": {"new": (121, 140), "review": (61,  80)},
    "2026-10-15": {"new": (141, 160), "review": (81,  100)},
    "2026-10-16": {"new": (161, 180), "review": (101, 120)},
    "2026-10-17": {"new": (181, 200), "review": (121, 140)},
    "2026-10-18": {"new": (201, 220), "review": (141, 160)},
    "2026-10-19": {"new": (221, 240), "review": (161, 180)},
    "2026-10-20": {"new": (241, 260), "review": (181, 200)},
    "2026-10-21": {"new": (261, 280), "review": (201, 220)},
    "2026-10-22": {"new": (281, 300), "review": (221, 240)},
    "2026-10-23": {"new": (301, 320), "review": (241, 260)},
    "2026-10-24": {"new": (321, 340), "review": (261, 280)},
    "2026-10-25": {"new": (341, 363), "review": (281, 300)},

    # Phase 2: 範囲復習（60問/日）
    "2026-10-26": {"review_range": (301, 363)},
    "2026-10-27": {"review_range": (1,   60)},
    "2026-10-28": {"review_range": (61,  120)},
    "2026-10-29": {"review_range": (121, 180)},
    "2026-10-30": {"review_range": (181, 240)},
    "2026-10-31": {"review_range": (241, 300)},
    "2026-11-01": {"review_range": (301, 363)},

    # Phase 3: 苦手・仕上げ
    "2026-11-02": {"weak_points": True, "count": 40},  # 苦手抽出チェック
    "2026-11-03": {"weak_points": True, "count": 40},
    "2026-11-04": {"weak_points": True, "count": 40},
    "2026-11-05": {"random_all": True,  "count": 60},  # ランダムチェック
    "2026-11-06": {"weak_points": True, "count": 40},
    "2026-11-07": {"weak_points": True, "count": 40},
}


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


def select_questions(questions: list[dict], history: dict, today: date) -> tuple[list[dict], int, int, str]:
    """スケジュールに従って今日の問題を選択。(selected, new_count, review_count, label) を返す"""
    import random
    q_map = {int(q["id"]): q for q in questions}
    today_str = today.isoformat()

    def by_range(start: int, end: int) -> list[dict]:
        return [q_map[n] for n in range(start, end + 1) if n in q_map]

    plan = SCHEDULE.get(today_str)

    if plan is None:
        # スケジュール外の日: 弱点問題20問
        return _select_weak_or_random(questions, history, 20), 0, 20, "スケジュール外（弱点優先）"

    if "review_range" in plan:
        s, e = plan["review_range"]
        selected = by_range(s, e)
        return selected, 0, len(selected), f"復習 {s}～{e}問"

    if "weak_points" in plan:
        count = plan.get("count", 40)
        selected = _select_weak(questions, history, count)
        return selected, 0, len(selected), f"苦手問題（上位{count}問）"

    if "random_all" in plan:
        count = plan.get("count", 60)
        selected = random.sample(questions, min(count, len(questions)))
        return selected, 0, len(selected), f"ランダム全問チェック（{count}問）"

    # Phase 1: new + review
    new_range = plan.get("new")
    review_range = plan.get("review")

    new_qs = by_range(*new_range) if new_range else []
    review_qs = by_range(*review_range) if review_range else []

    selected = new_qs + review_qs
    label = f"新規 {new_range[0]}～{new_range[1]}問"
    if review_range:
        label += f"  復習 {review_range[0]}～{review_range[1]}問"
    return selected, len(new_qs), len(review_qs), label


def _select_weak(questions: list[dict], history: dict, count: int) -> list[dict]:
    """不正解率の高い問題を上位countまで返す"""
    scored = []
    for q in questions:
        h = history.get(q["id"])
        if h and h["times_wrong"] > 0:
            wrong_rate = h["times_wrong"] / max(h["times_shown"], 1)
            scored.append((wrong_rate, h["times_wrong"], q))
    scored.sort(key=lambda x: (-x[0], -x[1]))
    result = [q for _, _, q in scored[:count]]
    if len(result) < count:
        # 不足分は未出題を順番に補充
        seen_ids = {q["id"] for q in result}
        for q in questions:
            if q["id"] not in seen_ids and q["id"] not in history:
                result.append(q)
                if len(result) >= count:
                    break
    return result


def _select_weak_or_random(questions: list[dict], history: dict, count: int) -> list[dict]:
    weak = _select_weak(questions, history, count)
    if len(weak) >= count:
        return weak
    import random
    remaining = [q for q in questions if q["id"] not in {w["id"] for w in weak}]
    weak += random.sample(remaining, min(count - len(weak), len(remaining)))
    return weak


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
    coverable = days_remaining * 40 >= unseen

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
    lsof_path = "/usr/sbin/lsof" if os.path.exists("/usr/sbin/lsof") else "lsof"
    result = subprocess.run([lsof_path, "-ti", f":{PORT}"], capture_output=True, text=True)
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


def send_line_notification(quiz_url: str, new_count: int, review_count: int, coverage: dict, label: str = "") -> None:
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

    total_q = new_count + review_count
    new_line = f"🆕 新規：{new_count}問\n" if new_count > 0 else ""
    review_line = f"🔁 復習：{review_count}問\n" if review_count > 0 else ""

    text = (
        f"📚 LPIC学習の時間です！\n"
        f"━━━━━━━━━━━━━━\n"
        f"📝 {label}\n"
        f"問題数：計{total_q}問\n"
        f"{new_line}{review_line}"
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

    selected, new_count, review_count, label = select_questions(questions, history, today)
    print(f"今日の選択: {label}  計{len(selected)}問")

    save_session(selected, history, new_count, review_count, today)
    print(f"セッション保存完了: {SESSION_PATH}")

    coverage = calc_coverage(questions, history, today)

    start_server()
    quiz_url = get_ngrok_url()
    print(f"クイズURL（公開）: {quiz_url}")

    send_line_notification(quiz_url, new_count, review_count, coverage, label)
    print("完了。")


if __name__ == "__main__":
    main()
