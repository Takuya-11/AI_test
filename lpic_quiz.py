"""
LPIC問題をLINEへ毎日20問送信するシステム
"""
import json
import os
import sys
import random
import requests
from datetime import date, timedelta
from dotenv import load_dotenv

load_dotenv()

QUESTIONS_PATH = "lpic_data/questions.json"
HISTORY_PATH = "lpic_data/history.json"
DAILY_COUNT = 20
QUESTIONS_PER_MSG = 5  # 1メッセージあたりの問題数（LINE上限5通に収める）

# 間隔（日数）: 初回→1日, 正解1回→3日, 正解2回→7日, 正解3回以上→14日
INTERVALS = {0: 1, 1: 3, 2: 7}
INTERVAL_MAX = 14
INTERVAL_WRONG = 1


# ---------- データ読み込み ----------

def load_questions() -> list[dict]:
    if not os.path.exists(QUESTIONS_PATH):
        print(f"エラー：{QUESTIONS_PATH} が見つかりません。先に lpic_parse.py を実行してください。")
        sys.exit(1)
    with open(QUESTIONS_PATH, encoding="utf-8") as f:
        questions = json.load(f)
    if len(questions) < DAILY_COUNT:
        print(f"エラー：問題数が{DAILY_COUNT}問未満です（{len(questions)}問）。")
        sys.exit(1)
    return questions


def load_history() -> dict:
    if not os.path.exists(HISTORY_PATH):
        return {"questions": {}, "sessions": []}
    with open(HISTORY_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_history(history: dict) -> None:
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


# ---------- 出題選択ロジック ----------

def select_questions(questions: list[dict], history: dict, today: date) -> list[dict]:
    today_str = today.isoformat()
    q_history = history["questions"]
    q_map = {q["id"]: q for q in questions}

    new_qs = []        # 未出題
    due_qs = []        # 復習期限が今日以前
    not_due_qs = []    # 復習期限が未来

    for q in questions:
        qid = q["id"]
        if qid not in q_history:
            new_qs.append(q)
        else:
            h = q_history[qid]
            next_review = date.fromisoformat(h["next_review"])
            overdue_days = (today - next_review).days
            if overdue_days >= 0:
                # 間違い率が高いほど優先
                shown = h["times_shown"]
                wrong = h["times_wrong"]
                wrong_rate = wrong / shown if shown > 0 else 0
                priority = overdue_days * 10 + wrong_rate * 100
                due_qs.append((priority, q))
            else:
                not_due_qs.append((next_review, q))

    # 復習は優先度降順
    due_qs.sort(key=lambda x: -x[0])
    due_qs = [q for _, q in due_qs]

    # not_due は次回期日が近い順
    not_due_qs.sort(key=lambda x: x[0])
    not_due_qs = [q for _, q in not_due_qs]

    # 配分: 新規14問 + 復習6問（ただし在庫に合わせて調整）
    new_target = min(14, len(new_qs))
    review_target = min(DAILY_COUNT - new_target, len(due_qs))
    new_target = DAILY_COUNT - review_target

    selected = random.sample(new_qs, min(new_target, len(new_qs)))
    selected += due_qs[:review_target]

    # 不足分をnot_dueで補充
    if len(selected) < DAILY_COUNT:
        remaining = not_due_qs[:DAILY_COUNT - len(selected)]
        selected += remaining

    # ちょうど20問になるよう調整
    selected = selected[:DAILY_COUNT]

    # ランダムシャッフル
    random.shuffle(selected)
    return selected


# ---------- 履歴更新 ----------

def update_history(history: dict, selected: list[dict], today: date) -> None:
    today_str = today.isoformat()
    q_history = history["questions"]

    for q in selected:
        qid = q["id"]
        if qid not in q_history:
            q_history[qid] = {
                "first_seen": today_str,
                "last_seen": today_str,
                "times_shown": 1,
                "times_correct": 0,
                "times_wrong": 0,
                "next_review": (today + timedelta(days=INTERVALS.get(0, 3))).isoformat(),
                "interval_days": INTERVALS.get(0, 3),
            }
        else:
            h = q_history[qid]
            h["last_seen"] = today_str
            h["times_shown"] += 1
            # 次回復習日（正解・不正解が記録される前の状態では間隔をそのまま維持）
            h["next_review"] = (today + timedelta(days=h["interval_days"])).isoformat()

    history["sessions"].append({
        "date": today_str,
        "question_ids": [q["id"] for q in selected],
    })


# ---------- LINEフォーマット ----------

def format_tag(q: dict, history: dict) -> str:
    qid = q["id"]
    if qid not in history["questions"]:
        return "🆕"
    h = history["questions"][qid]
    if h["times_wrong"] > 0 and h["times_correct"] == 0:
        return "❌"
    if h["times_wrong"] > h["times_correct"]:
        return "⚠️"
    return "🔁"


def format_question_block(idx: int, q: dict, history: dict) -> str:
    tag = format_tag(q, history)
    lines = [f"Q{idx} [{q['id']}] {tag}"]
    lines.append(q["question"])
    if q["choices"]:
        lines.append("")
        for label, text in q["choices"].items():
            lines.append(f"{label}. {text}")
    return "\n".join(lines)


def build_messages(selected: list[dict], history: dict, today: date) -> list[str]:
    today_str = today.strftime("%Y-%m-%d")
    new_count = sum(1 for q in selected if q["id"] not in history["questions"])

    # ヘッダー（1通目）
    header = (
        f"📚 LPIC 今日の20問\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"📅 {today_str}\n"
        f"🆕 新規：{new_count}問  🔁 復習：{DAILY_COUNT - new_count}問\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"5問ずつ4回に分けてお届けします。\n"
        f"各ブロック末尾に答えを記載しています。"
    )
    messages = [header]

    # 5問ずつ4ブロック
    for block_idx in range(0, DAILY_COUNT, QUESTIONS_PER_MSG):
        block = selected[block_idx:block_idx + QUESTIONS_PER_MSG]
        start_num = block_idx + 1
        end_num = block_idx + len(block)

        lines = [f"━━ Q{start_num}〜Q{end_num} ━━"]
        for i, q in enumerate(block):
            lines.append("")
            lines.append(format_question_block(start_num + i, q, history))

        # 答え
        lines.append("")
        lines.append("┈┈┈┈ 答え ┈┈┈┈")
        answers = []
        for i, q in enumerate(block):
            ans = "、".join(q["answer"])
            answers.append(f"Q{start_num + i}→{ans}")
        lines.append("  ".join(answers))

        messages.append("\n".join(lines))

    return messages


# ---------- LINE送信 ----------

def send_line_messages(messages: list[str]) -> None:
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    user_id = os.getenv("LINE_USER_ID")

    if not token or "ここに" in token:
        print("エラー：LINE_CHANNEL_ACCESS_TOKEN が未設定です。")
        sys.exit(1)
    if not user_id or "ここに" in user_id:
        print("エラー：LINE_USER_ID が未設定です。")
        sys.exit(1)

    # LINE Push APIは1リクエストで最大5通
    payload = {
        "to": user_id,
        "messages": [{"type": "text", "text": m} for m in messages[:5]],
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }

    try:
        r = requests.post(
            "https://api.line.me/v2/bot/message/push",
            headers=headers,
            json=payload,
            timeout=15,
        )
    except requests.exceptions.RequestException as e:
        print(f"エラー：LINE APIへの接続に失敗しました。\n詳細：{e}")
        sys.exit(1)

    if r.status_code == 200:
        print("=" * 30)
        print("LINEへの送信に成功しました！")
        print("=" * 30)
    elif r.status_code == 401:
        print("エラー：Channel Access Tokenが無効です。")
        sys.exit(1)
    elif r.status_code == 400:
        print(f"エラー：リクエストが不正です。\n詳細：{r.json().get('message','')}")
        sys.exit(1)
    else:
        print(f"エラー：送信失敗（ステータス：{r.status_code}）\n詳細：{r.json()}")
        sys.exit(1)


# ---------- メイン ----------

def main():
    today = date.today()

    print("問題を読み込み中...")
    questions = load_questions()
    history = load_history()

    print("今日の20問を選択中...")
    selected = select_questions(questions, history, today)

    # 統計
    new_count = sum(1 for q in selected if q["id"] not in history["questions"])
    review_count = DAILY_COUNT - new_count
    print(f"  新規：{new_count}問  復習：{review_count}問")

    # 選択内容をプレビュー
    print("\n--- 今日の出題リスト ---")
    for i, q in enumerate(selected, 1):
        tag = "🆕" if q["id"] not in history["questions"] else "🔁"
        print(f"  {i:2d}. No.{q['id']} {tag} {q['question'][:40]}...")

    # 確認
    try:
        confirm = input("\nLINEに送信しますか？ [y/N]: ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print("\n中止しました。")
        sys.exit(0)

    if confirm != "y":
        print("送信をキャンセルしました。")
        sys.exit(0)

    # 履歴更新
    update_history(history, selected, today)

    # メッセージ構築・送信
    messages = build_messages(selected, history, today)
    print("\nLINEに送信中...")
    send_line_messages(messages)

    # 履歴保存
    save_history(history)
    print(f"出題履歴を保存しました。（{HISTORY_PATH}）")

    # 残問数
    unseen = sum(1 for q in questions if q["id"] not in history["questions"])
    print(f"\n未出題の残り：{unseen}問 / {len(questions)}問")


if __name__ == "__main__":
    main()
