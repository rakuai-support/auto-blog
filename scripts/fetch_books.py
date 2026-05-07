"""
楽天ブックスAPIから各記事に合った書籍を検索してキャッシュする。
記事の業種×トピックをキーワードにして、最適な本を自動選択する。
"""
import json
import os
import time
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
CONTENT_DIR = BASE_DIR / "content" / "articles"
CACHE_PATH = BASE_DIR / "content" / "books_cache.json"
ENV_PATH = BASE_DIR / ".env"


def load_env():
    env = {}
    if ENV_PATH.exists():
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    for key in ["RAKUTEN_APP_ID", "RAKUTEN_ACCESS_KEY", "RAKUTEN_AFFILIATE_ID"]:
        if key in os.environ:
            env[key] = os.environ[key]
    return env


def search_books(app_id, access_key, aff_id, keyword):
    """楽天ブックスAPIで書籍を1冊検索"""
    encoded_kw = urllib.parse.quote(keyword)
    url = (
        f"https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404"
        f"?applicationId={app_id}"
        f"&accessKey={access_key}"
        f"&affiliateId={aff_id}"
        f"&keyword={encoded_kw}"
        f"&hits=1"
        f"&sort=reviewCount"
    )

    req = urllib.request.Request(url, headers={
        "Referer": "https://rakuai-support.github.io/",
        "Origin": "https://rakuai-support.github.io",
    })

    with urllib.request.urlopen(req, timeout=15) as res:
        data = json.loads(res.read())

    items = data.get("Items", [])
    if not items:
        return None

    item = items[0]["Item"]
    return {
        "title": item.get("title", ""),
        "author": item.get("author", ""),
        "price": item.get("itemPrice", 0),
        "review_count": item.get("reviewCount", 0),
        "image_url": item.get("largeImageUrl", ""),
        "affiliate_url": item.get("affiliateUrl", ""),
    }


def build_search_keyword(industry, topic):
    """業種とトピックから検索キーワードを組み立てる"""
    # トピックからAI関連のキーワードを組み立て
    topic_keywords = {
        "予約管理の効率化": "予約管理 効率化",
        "顧客対応の自動化": "顧客対応 AI",
        "SNS投稿の作成": "SNS マーケティング",
        "売上データの分析": "データ分析 ビジネス",
        "スタッフ教育の効率化": "人材育成 教育",
        "在庫管理の改善": "在庫管理 効率化",
        "経理作業の時短": "経理 AI 効率化",
        "集客・マーケティング": "集客 マーケティング",
        "口コミ対応": "口コミ 集客",
        "業務マニュアル作成": "業務改善 マニュアル",
    }
    kw = topic_keywords.get(topic, topic)
    return f"{industry} {kw}"


def main():
    env = load_env()
    app_id = env.get("RAKUTEN_APP_ID", "")
    access_key = env.get("RAKUTEN_ACCESS_KEY", "")
    aff_id = env.get("RAKUTEN_AFFILIATE_ID", "")

    if not all([app_id, access_key, aff_id]):
        print("楽天APIキーが設定されていません。.envを確認してください。")
        return

    # 既存キャッシュを読み込む
    cache = {"updated": "", "books": {}}
    if CACHE_PATH.exists():
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            cache = json.load(f)

    # 全記事メタデータを読む
    articles = []
    for meta_path in sorted(CONTENT_DIR.glob("*.json")):
        with open(meta_path, "r", encoding="utf-8") as f:
            articles.append(json.load(f))

    # 記事ごとにキャッシュにない書籍を検索
    new_count = 0
    for article in articles:
        slug = article["slug"]
        if slug in cache["books"]:
            print(f"キャッシュ済み: {article['industry']} × {article['topic']}")
            continue

        keyword = build_search_keyword(article["industry"], article["topic"])
        print(f"検索中: {keyword}")

        time.sleep(2)  # レート制限回避

        try:
            book = search_books(app_id, access_key, aff_id, keyword)
            if book:
                cache["books"][slug] = book
                print(f"  -> {book['title']} ({book['price']}円)")
                new_count += 1
            else:
                # 見つからなかった場合、汎用キーワードで再検索
                fallback_kw = f"{article['industry']} AI 活用"
                print(f"  -> 該当なし。再検索: {fallback_kw}")
                time.sleep(2)
                book = search_books(app_id, access_key, aff_id, fallback_kw)
                if book:
                    cache["books"][slug] = book
                    print(f"  -> {book['title']} ({book['price']}円)")
                    new_count += 1
                else:
                    print(f"  -> 該当なし（スキップ）")
        except Exception as e:
            print(f"  -> エラー: {e}")

    cache["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

    print(f"\n更新完了: 新規{new_count}件 / 全{len(cache['books'])}件キャッシュ済み")


if __name__ == "__main__":
    main()
