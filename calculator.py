def calculate(a, op, b):
    if op == '+':
        return a + b
    elif op == '-':
        return a - b
    elif op == '*':
        return a * b
    elif op == '/':
        if b == 0:
            raise ValueError("0 で割ることはできません")
        return a / b
    else:
        raise ValueError(f"未対応の演算子: {op}")


def main():
    print("=== 簡易計算機 ===")

    try:
        a = float(input("1つ目の数値: "))
        op = input("演算子 (+ - * /): ").strip()
        b = float(input("2つ目の数値: "))

        result = calculate(a, op, b)

        # 整数で割り切れる場合は整数表示
        if result == int(result):
            print(f"結果: {a} {op} {b} = {int(result)}")
        else:
            print(f"結果: {a} {op} {b} = {result}")

    except ValueError as e:
        print(f"エラー: {e}")
    except EOFError:
        print("入力がキャンセルされました")


if __name__ == "__main__":
    main()
