"""
30日分の出題シミュレーション（実際には送信しない）
"""
import json
import random
import copy
from datetime import date, timedelta

from lpic_quiz import load_questions, select_questions, update_history, DAILY_COUNT

SIMULATE_DAYS = 30


def simulate():
    questions = load_questions()
    history = {"questions": {}, "sessions": []}
    total_questions = len(questions)

    print(f"総問題数：{total_questions}問")
    print(f"シミュレーション期間：{SIMULATE_DAYS}日間")
    print(f"1日の出題数：{DAILY_COUNT}問")
    print("=" * 50)

    start = date(2026, 10, 7)

    for day in range(SIMULATE_DAYS):
        today = start + timedelta(days=day)
        selected = select_questions(questions, history, today)

        # ランダムに正解・不正解を付ける（シミュレーション用）
        update_history(history, selected, today)

        # 一部を正解・不正解として記録（シミュレーション）
        for q in selected:
            qid = q["id"]
            h = history["questions"][qid]
            correct = random.random() > 0.35  # 65%正解率を想定
            if correct:
                h["times_correct"] += 1
                h["interval_days"] = min(h["interval_days"] * 2, 14)
            else:
                h["times_wrong"] += 1
                h["interval_days"] = 1
            h["next_review"] = (today + timedelta(days=h["interval_days"])).isoformat()

        new_count = sum(1 for q in selected if history["questions"][q["id"]]["times_shown"] == 1)
        review_count = DAILY_COUNT - new_count
        seen_total = len(history["questions"])

        print(f"Day {day+1:2d} ({today})  新規：{new_count:2d}問  復習：{review_count:2d}問  累計出題済：{seen_total:3d}問")

    print("=" * 50)
    seen_total = len(history["questions"])
    coverage = seen_total / total_questions * 100
    avg_shown = sum(h["times_shown"] for h in history["questions"].values()) / max(seen_total, 1)
    wrong_prone = [qid for qid, h in history["questions"].items() if h["times_wrong"] > h["times_correct"]]

    print(f"\n【30日間の結果】")
    print(f"  出題済み問題数    ：{seen_total} / {total_questions}問 （{coverage:.1f}%）")
    print(f"  平均出題回数      ：{avg_shown:.1f}回")
    print(f"  苦手問題（復習優先）：{len(wrong_prone)}問")
    print(f"  未出題           ：{total_questions - seen_total}問")

    if coverage >= 100:
        print("\n✅ 30日以内に全問網羅できています！")
    else:
        days_needed = int(total_questions / DAILY_COUNT * 1.2)
        print(f"\n⚠️ 全問網羅には約{days_needed}日かかる見込みです。")


if __name__ == "__main__":
    simulate()
