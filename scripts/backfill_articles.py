"""
過去日付で記事をバックフィル生成するスクリプト
指定した日付範囲で1日2記事ずつ生成する
"""
import json
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_article import (
    load_config, load_history, save_history,
    pick_next_topic, pick_title, fetch_news,
    generate_slug, generate_article, parse_article,
    save_article, CONTENT_DIR
)


def save_article_with_date(slug, title, body, desc, industry, topic, date_str):
    """日付を指定して記事を保存"""
    char_count = len(body)
    read_minutes = max(1, round(char_count / 400))

    meta = {
        "slug": slug,
        "title": title,
        "description": desc,
        "industry": industry,
        "topic": topic,
        "date": date_str,
        "read_minutes": read_minutes,
        "char_count": char_count
    }

    meta_path = CONTENT_DIR / f"{slug}.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    md_path = CONTENT_DIR / f"{slug}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(body)

    return meta


def main():
    config = load_config()
    history = load_history()

    # 過去7日分、1日2記事 = 14記事
    articles_per_day = 2
    days_back = 7
    today = datetime.now()

    total_generated = 0

    for day_offset in range(days_back, 0, -1):
        target_date = today - timedelta(days=day_offset)
        date_str = target_date.strftime("%Y-%m-%d")

        for i in range(articles_per_day):
            industry, topic, key = pick_next_topic(config, history)
            if industry is None:
                print("全トピック生成済みです。")
                return

            title = pick_title(industry, topic)
            slug = generate_slug(industry, topic)

            print(f"[{date_str} #{i+1}] {industry} x {topic}")
            print(f"  タイトル: {title}")

            news_items = fetch_news(industry, topic)
            if news_items:
                print(f"  -> ニュース{len(news_items)}件取得")

            raw = generate_article(industry, topic, title, news_items)
            title, body, desc = parse_article(raw)
            meta = save_article_with_date(slug, title, body, desc, industry, topic, date_str)

            history["generated"].append(key)
            save_history(history)

            total_generated += 1
            print(f"  -> 完了: {meta['char_count']}文字 (日付: {date_str})\n")

            time.sleep(3)

    print(f"バックフィル完了: {total_generated}記事生成")


if __name__ == "__main__":
    main()
