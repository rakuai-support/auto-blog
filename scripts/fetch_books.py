"""
楽天ブックスAPIから各記事に合った書籍を検索してキャッシュする。
タイトル検索で狭く探し、見つからない場合は総合検索のkeyword検索で広く拾う。
"""
import json
import os
import time
import urllib.error
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
CONTENT_DIR = BASE_DIR / "content" / "articles"
CACHE_PATH = BASE_DIR / "content" / "books_cache.json"
ENV_PATH = BASE_DIR / ".env"
REQUEST_HEADERS = {
    "Referer": "https://okomari.smilefactory-rakuai.com/",
    "Origin": "https://okomari.smilefactory-rakuai.com",
}
BLOCKED_STATUS_CODES = {403, 429}


class ApiBlockedError(Exception):
    """楽天API側でリクエストが拒否された場合に、今回の書籍更新を早く諦めるための例外"""


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


def request_json(url):
    req = urllib.request.Request(url, headers=REQUEST_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            return json.loads(res.read())
    except urllib.error.HTTPError as e:
        if e.code in BLOCKED_STATUS_CODES:
            raise ApiBlockedError(f"HTTP Error {e.code}: {e.reason}") from e
        raise


def build_url(endpoint, params):
    query = urllib.parse.urlencode(params)
    return f"https://openapi.rakuten.co.jp/services/api/{endpoint}/20170404?{query}"


def normalize_book(item):
    return {
        "title": item.get("title", ""),
        "author": item.get("author", ""),
        "price": item.get("itemPrice", 0),
        "review_count": item.get("reviewCount", 0),
        "review_average": item.get("reviewAverage", 0),
        "image_url": item.get("largeImageUrl") or item.get("mediumImageUrl") or item.get("smallImageUrl") or "",
        "affiliate_url": item.get("affiliateUrl") or item.get("itemUrl", ""),
    }


def parse_items(data):
    results = []
    for item_wrap in data.get("Items", []):
        item = item_wrap.get("Item", item_wrap)
        book = normalize_book(item)
        if book["title"] and book["affiliate_url"]:
            results.append(book)
    return results


def search_book_title(app_id, access_key, aff_id, title_keyword, hits=3):
    """楽天ブックス書籍検索APIでタイトルを狭く検索"""
    url = build_url("BooksBook/Search", {
        "applicationId": app_id,
        "accessKey": access_key,
        "affiliateId": aff_id,
        "title": title_keyword,
        "hits": hits,
        "sort": "sales",
    })
    return parse_items(request_json(url))


def search_books_total(app_id, access_key, aff_id, keyword, hits=8, or_flag=0):
    """楽天ブックス総合検索APIでキーワードを広く検索"""
    url = build_url("BooksTotal/Search", {
        "applicationId": app_id,
        "accessKey": access_key,
        "affiliateId": aff_id,
        "keyword": keyword,
        "hits": hits,
        "sort": "sales",
        "field": 0,
        "orFlag": or_flag,
    })
    return parse_items(request_json(url))


def score_book(book, industry, topic):
    text = f"{book.get('title', '')} {book.get('author', '')}".lower()
    score = 0

    topic_terms = [topic, topic.split("の")[0], topic.replace("・", " ")]
    for term in topic_terms:
        if term and term.lower() in text:
            score += 4

    if industry and industry.lower() in text:
        score += 3

    for term in ["ai", "chatgpt", "生成ai", "業務効率", "仕事術", "ビジネス"]:
        if term in text:
            score += 3

    if book.get("image_url"):
        score += 2
    if book.get("review_count"):
        score += min(3, int(book.get("review_count", 0)))

    return score


def choose_best_book(results, industry, topic):
    with_images = [book for book in results if book.get("image_url")]
    candidates = with_images or results
    if not candidates:
        return None

    return max(candidates, key=lambda book: score_book(book, industry, topic))


def search_books(app_id, access_key, aff_id, query, industry, topic):
    """タイトル検索から総合検索へ段階的に広げる"""
    results = []

    try:
        results.extend(search_book_title(app_id, access_key, aff_id, query, hits=3))
    except ApiBlockedError:
        raise
    except Exception as e:
        print(f"  -> タイトル検索エラー: {e}")

    if results:
        return choose_best_book(results, industry, topic)

    for or_flag in [0, 1]:
        try:
            results.extend(search_books_total(app_id, access_key, aff_id, query, hits=8, or_flag=or_flag))
        except ApiBlockedError:
            raise
        except Exception as e:
            print(f"  -> 総合検索エラー: {e}")
        if results:
            return choose_best_book(results, industry, topic)

    return None


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
    # 4. AI系フォールバック（どの記事でも画像付き書籍に落とす）
    queries.append("AI 業務効率化")
    queries.append("生成AI ビジネス")
    queries.append("ChatGPT ビジネス")
    queries.append("ChatGPT 仕事術")

    unique = []
    for query in queries:
        if query not in unique:
            unique.append(query)
    return unique


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

    max_new_books = int(env.get("FETCH_BOOKS_MAX_NEW", os.environ.get("FETCH_BOOKS_MAX_NEW", "3")))
    new_count = 0
    for article in articles:
        if new_count >= max_new_books:
            print(f"今回の書籍取得上限に達しました: 新規{new_count}件")
            break

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
                book = search_books(app_id, access_key, aff_id, query, article["industry"], article["topic"])
                if book:
                    cache["books"][slug] = book
                    print(f"  -> {book['title']} ({book['price']}円)")
                    new_count += 1
                    found = True
                    break
            except ApiBlockedError as e:
                print(f"  -> 楽天APIがリクエストを拒否しました: {e}")
                print("  -> 今回の書籍キャッシュ更新はスキップします")
                found = True
                break
            except Exception as e:
                print(f"  -> エラー: {e}")
                continue

        if found and slug not in cache["books"]:
            break

        if not found:
            print(f"  -> 全クエリで該当なし（スキップ）")

    cache["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

    print(f"\n更新完了: 新規{new_count}件 / 全{len(cache['books'])}件キャッシュ済み")


if __name__ == "__main__":
    main()
