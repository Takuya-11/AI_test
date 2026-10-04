import random


def get_valid_guess():
    while True:
        user_input = input("数字を入力してください (1〜100): ").strip()

        if not user_input:
            print("エラー: 数字を入力してください。")
            continue

        try:
            guess = int(user_input)
        except ValueError:
            print("エラー: 1〜100の整数を入力してください。")
            continue

        if guess < 1 or guess > 100:
            print("エラー: 1〜100の範囲で入力してください。")
            continue

        return guess


def play_game():
    secret_number = random.randint(1, 100)
    attempts = 0

    print("\n=== 数字当てゲーム ===")
    print("1〜100の中からコンピューターが選んだ数字を当ててください！")

    while True:
        guess = get_valid_guess()
        attempts += 1

        if guess < secret_number:
            print("もっと大きい！")
        elif guess > secret_number:
            print("もっと小さい！")
        else:
            print(f"\n正解！ {secret_number} です！")
            print(f"{attempts}回で当てました！")
            break


def ask_play_again():
    while True:
        answer = input("\nもう一度遊びますか？ (y/n): ").strip().lower()
        if answer in ("y", "n"):
            return answer == "y"
        print("y か n を入力してください。")


def main():
    while True:
        play_game()
        if not ask_play_again():
            print("ゲームを終了します。ありがとうございました！")
            break


if __name__ == "__main__":
    main()
