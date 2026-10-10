#!/usr/bin/env python3
"""
楽天市場スクレイピング・Google Sheets保存スクリプト（個人学習目的）
※楽天市場の利用規約により商用利用は禁止されています。

使い方:
    python3 ec_to_sheets.py "Nintendo Switch"
    python3 ec_to_sheets.py "コーヒーメーカー" --hits 10
"""

import sys
import os
import time
import argparse
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request as GoogleAuthRequest
from googleapiclient.discovery import build

load_dotenv()

RAKUTEN_SEARCH_URL = "https://search.rakuten.co.jp/search/mall/{keyword}/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

SHEET_NAME = "楽天商品情報"
SHEET_HEADERS = ["取得日時", "商品コード", "商品名", "価格(円)", "ショップ名", "商品URL"]
JST = timezone(timedelta(hours=9))

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/meetings.space.created",
]
TOKEN_PATH = "token.json"
CREDENTIALS_PATH = "credentials.json"


# ===== スクレイピング =====

def scrape_rakuten(keyword: str, hits: int) -> list[dict]:
    url = RAKUTEN_SEARCH_URL.format(keyword=requests.utils.quote(keyword))
    print(f"  URL: {url}")

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        raise RuntimeError("タイムアウト（15秒）")
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"接続エラー: {e}")

    soup = BeautifulSoup(resp.text, "lxml")
    items = soup.select("div.searchresultitem")

    if not items:
        return []

    results = []
    for item in items[:hits]:
        # 商品名: img の alt 属性
        img = item.select_one("img")
        name = img["alt"].strip() if img and img.get("alt") else "取得不可"

        # URL
        link = item.select_one('a[href*="item.rakuten"]')
        url_product = link["href"].split("?")[0] if link else "取得不可"

        # 商品コード: URLから抽出（shop/item_id 形式）
        item_code = "/".join(url_product.rstrip("/").split("/")[-2:]) if url_product != "取得不可" else "取得不可"

        # 価格: data-track-price 属性
        price_raw = item.get("data-track-price", "")
        price = str(int(price_raw)) if price_raw.isdigit() else "取得不可"

        # ショップ名
        shop_el = item.select_one("div.merchant")
        shop = shop_el.get_text(strip=True) if shop_el else "取得不可"

        results.append({
            "name": name,
            "price": price,
            "shop": shop,
            "url": url_product,
            "code": item_code,
        })

    return results


# ===== Google Sheets =====

def _get_credentials() -> Credentials:
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(GoogleAuthRequest())
        else:
            if not os.path.exists(CREDENTIALS_PATH):
                raise FileNotFoundError(f"{CREDENTIALS_PATH} が見つかりません")
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())
    return creds


def _get_service():
    return build("sheets", "v4", credentials=_get_credentials())


def _get_or_create_spreadsheet(service) -> str:
    sheet_id = os.getenv("EC_SHEETS_ID", "").strip()
    if sheet_id:
        return sheet_id

    spreadsheet = service.spreadsheets().create(body={
        "properties": {"title": "楽天商品情報"},
        "sheets": [{"properties": {"title": SHEET_NAME}}],
    }).execute()
    sheet_id = spreadsheet["spreadsheetId"]

    service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=f"{SHEET_NAME}!A1",
        valueInputOption="RAW",
        body={"values": [SHEET_HEADERS]},
    ).execute()

    with open(".env", "a") as f:
        f.write(f"\nEC_SHEETS_ID={sheet_id}\n")
    print(f"スプレッドシート新規作成: https://docs.google.com/spreadsheets/d/{sheet_id}")
    return sheet_id


def _ensure_sheet_headers(service, sheet_id: str) -> None:
    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=f"{SHEET_NAME}!A1:F1",
    ).execute()

    if not result.get("values"):
        try:
            service.spreadsheets().batchUpdate(
                spreadsheetId=sheet_id,
                body={"requests": [{"addSheet": {"properties": {"title": SHEET_NAME}}}]},
            ).execute()
        except Exception:
            pass
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f"{SHEET_NAME}!A1",
            valueInputOption="RAW",
            body={"values": [SHEET_HEADERS]},
        ).execute()


def _append_rows(service, sheet_id: str, rows: list) -> None:
    service.spreadsheets().values().append(
        spreadsheetId=sheet_id,
        range=f"{SHEET_NAME}!A:F",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": rows},
    ).execute()


# ===== メイン =====

def main() -> None:
    parser = argparse.ArgumentParser(
        description="楽天市場の商品情報をスクレイピングしてGoogle Sheetsに保存する（個人学習目的）"
    )
    parser.add_argument("keyword", nargs="+", help="検索キーワード")
    parser.add_argument("--hits", type=int, default=5, metavar="N",
                        help="取得件数（デフォルト: 5）")
    args = parser.parse_args()

    keyword = " ".join(args.keyword)
    hits = max(1, args.hits)

    print(f"検索キーワード: 「{keyword}」  取得件数: {hits}件")

    # ---- スクレイピング ----
    print("楽天市場を検索中...")
    try:
        items = scrape_rakuten(keyword, hits)
    except RuntimeError as e:
        print(f"\nエラー: {e}")
        sys.exit(1)

    if not items:
        print("検索結果が0件でした（キーワードを変えてみてください）")
        sys.exit(0)

    print(f"{len(items)}件取得しました\n")

    fetched_at = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")

    rows = []
    for i, item in enumerate(items, 1):
        row = [
            fetched_at,
            item["code"],
            item["name"],
            item["price"],
            item["shop"],
            item["url"],
        ]
        rows.append(row)
        title_preview = item["name"][:45] + ("..." if len(item["name"]) > 45 else "")
        print(f"  {i}. {title_preview}")
        print(f"     価格={item['price']}円  店={item['shop']}")

    # ---- Google Sheets ----
    print("\nGoogle Sheetsに保存中...")
    try:
        service = _get_service()
        sheet_id = _get_or_create_spreadsheet(service)
        _ensure_sheet_headers(service, sheet_id)
        _append_rows(service, sheet_id, rows)
    except FileNotFoundError as e:
        print(f"\n認証エラー: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nGoogle Sheetsエラー: {e}")
        sys.exit(1)

    print(f"{len(rows)}件をシートに追記しました")
    print(f"スプレッドシート: https://docs.google.com/spreadsheets/d/{sheet_id}")


if __name__ == "__main__":
    main()
