"""
楽天ブックスAPIから各記事に合った書籍を検索してキャッシュする。
titleパラメータで書名検索し、記事テーマに関連する本を自動選択。
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


def search_books(app_id, access_key, aff_id, title_keyword, hits=2):
    """楽天ブックスAPIでタイトル検索"""
    encoded = urllib.parse.quote(title_keyword)
    url = (
        f"https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404"
        f"?applicationId={app_id}"
        f"&accessKey={access_key}"
        f"&affiliateId={aff_id}"
        f"&title={encoded}"
        f"&hits={hits}"
        f"&sort=sales"
    )

    req = urllib.request.Request(url, headers={
        "Referer": "https://okomari.smilefactory-rakuai.com/",
        "Origin": "https://okomari.smilefactory-rakuai.com",
    })

    with urllib.request.urlopen(req, timeout=15) as res:
        data = json.loads(res.read())

    results = []
    for item_wrap in data.get("Items", []):
        item = item_wrap["Item"]
        results.append({
            "title": item.get("title", ""),
            "author": item.get("author", ""),
            "price": item.get("itemPrice", 0),
            "review_count": item.get("reviewCount", 0),
            "image_url": item.get("largeImageUrl", ""),
            "affiliate_url": item.get("affiliateUrl", ""),
        })
    return results


def get_search_queries(industry, topic):
    """業種×トピックから検索キーワード候補を優先順で返す"""
    # トピック別の書名キーワード
    topic_map = {
        "予約管理の効率化": ["予約管理", "業務効率化"],
        "顧客対応の自動化": ["顧客対応", "接客"],
        "SNS投稿の作成": ["SNS 集客", "SNS マーケティング"],
        "売上データの分析": ["データ分析 ビジネス", "売上分析"],
        "スタッフ教育の効率化": ["人材育成", "スタッフ教育"],
        "在庫管理の改善": ["在庫管理", "業務改善"],
        "経理作業の時短": ["経理 効率化", "AI 経理"],
        "集客・マーケティング": ["集客 マーケティング", "Web集客"],
        "口コミ対応": ["口コミ 集客", "レビュー対策"],
        "業務マニュアル作成": ["業務マニュアル", "マニュアル作成"],
    }

    queries = []
    # 1. 業種名 + トピック関連（最も具体的）
    queries.append(f"{industry} {topic.split('の')[0]}")
    # 2. 業種名 + 経営
    queries.append(f"{industry} 経営")
    # 3. トピック系キーワード
    queries.extend(topic_map.get(topic, [topic.split("の")[0]]))
    # 4. AI系フォールバック
    queries.append("AI 業務効率化")
    queries.append("ChatGPT")

    return queries


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

    new_count = 0
    for article in articles:
        slug = article["slug"]
        if slug in cache["books"]:
            print(f"キャッシュ済み: {article['industry']} x {article['topic']}")
            continue

        queries = get_search_queries(article["industry"], article["topic"])
        found = False

        for query in queries:
            time.sleep(2)  # レート制限回避
            print(f"検索中: [{article['industry']} x {article['topic']}] -> \"{query}\"")

            try:
                results = search_books(app_id, access_key, aff_id, query, hits=1)
                if results:
                    book = results[0]
                    cache["books"][slug] = book
                    print(f"  -> {book['title']} ({book['price']}円)")
                    new_count += 1
                    found = True
                    break
            except Exception as e:
                print(f"  -> エラー: {e}")
                continue

        if not found:
            print(f"  -> 全クエリで該当なし（スキップ）")

    cache["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

    print(f"\n更新完了: 新規{new_count}件 / 全{len(cache['books'])}件キャッシュ済み")


if __name__ == "__main__":
    main()
