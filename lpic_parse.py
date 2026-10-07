"""
PDFからLPIC問題を抽出してJSONに保存する（初回1回のみ実行）
"""
import re
import json
import sys
import pdfplumber

PDF_PATH = "LPIC 201-450_問題集_V03 (1).pdf"
OUTPUT_PATH = "lpic_data/questions.json"


def extract_text(pdf_path: str) -> str:
    with pdfplumber.open(pdf_path) as pdf:
        pages = []
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                # ページ番号行を除去
                t = re.sub(r'\n\d+ / \d+\s*$', '', t.strip())
                pages.append(t)
    return "\n".join(pages)


def parse_questions(text: str) -> list[dict]:
    # No.NNN で分割
    blocks = re.split(r'(?=No\.\d{3})', text)
    questions = []

    for block in blocks:
        block = block.strip()
        if not re.match(r'^No\.\d{3}', block):
            continue

        # 問題番号
        m = re.match(r'^No\.(\d{3})', block)
        if not m:
            continue
        num = m.group(1)
        rest = block[len(m.group(0)):].strip()

        # 答えを分離
        answer_match = re.search(r'答え[：:]\s*(.+?)(?:\n|$)', rest)
        if not answer_match:
            continue
        answer_raw = answer_match.group(1).strip()
        answer_pos = answer_match.start()
        body = rest[:answer_pos].strip()

        # 答えをパース（A,C → ["A","C"] / sync → ["sync"]）
        answers = [a.strip() for a in re.split(r'[,、]', answer_raw) if a.strip()]

        # 選択肢を抽出
        choice_pattern = re.compile(r'^([A-E])[.\．]\s+(.+)', re.MULTILINE)
        choices = {}
        choice_matches = list(choice_pattern.finditer(body))

        if choice_matches:
            # 問題文は最初の選択肢の前まで
            q_text = body[:choice_matches[0].start()].strip()
            for i, cm in enumerate(choice_matches):
                label = cm.group(1)
                # 次の選択肢の直前まで
                end = choice_matches[i + 1].start() if i + 1 < len(choice_matches) else len(body)
                choice_text = body[cm.start():end]
                # ラベル部分を除いたテキスト
                choice_text = re.sub(r'^[A-E][.\．]\s+', '', choice_text).strip()
                choices[label] = choice_text
            q_type = "multiple_choice"
        else:
            q_text = body.strip()
            q_type = "fill_in"

        # 複数選択かどうか
        multi = "2つ選択" in q_text or "3つ選択" in q_text or len(answers) > 1

        questions.append({
            "id": num,
            "type": q_type,
            "multi_answer": multi,
            "question": q_text,
            "choices": choices,
            "answer": answers,
        })

    return questions


def main():
    print(f"PDFを読み込み中: {PDF_PATH}")
    try:
        text = extract_text(PDF_PATH)
    except FileNotFoundError:
        print(f"エラー：{PDF_PATH} が見つかりません。")
        sys.exit(1)

    print("問題を解析中...")
    questions = parse_questions(text)

    if not questions:
        print("エラー：問題を抽出できませんでした。")
        sys.exit(1)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(questions, f, ensure_ascii=False, indent=2)

    print(f"完了：{len(questions)}問を {OUTPUT_PATH} に保存しました。")

    # サンプル表示
    for q in questions[:2]:
        print(f"\n--- No.{q['id']} ---")
        print(f"問題：{q['question'][:60]}...")
        if q['choices']:
            for k, v in q['choices'].items():
                print(f"  {k}. {v[:40]}")
        print(f"答え：{q['answer']}")


if __name__ == "__main__":
    main()
