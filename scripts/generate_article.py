"""
記事自動生成スクリプト
claude CLI を呼び出して業種別AI活用記事を生成し、Markdownとして保存する。
最新ニュースを取得して記事に反映させる。
"""
import json
import os
import subprocess
import sys
import re
import hashlib
import random
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

# Windows環境でのUTF-8出力を強制
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config.json"
CONTENT_DIR = BASE_DIR / "content" / "articles"
HISTORY_PATH = BASE_DIR / "content" / "history.json"

# タイトルパターン（お困りごと検索キーワードで流入させる）
TITLE_PATTERNS = [
    "{industry} {topic} 大変 → AIで解決した方法を全手順つきで紹介",
    "{industry} {topic} 悩み｜無料AIツールで月10時間削減できた話",
    "{industry} {topic} 効率化｜ChatGPTを使った具体的なやり方",
    "{industry} {topic} つらい・終わらない → AI導入で変わった実例",
    "{industry} {topic} 人手不足で回らない → AIに任せたら楽になった話",
    "{industry} {topic} やり方がわからない｜初心者でもできるAI活用術",
    "{industry} {topic} 時間がかかりすぎる → ChatGPTで解決する方法",
    "{industry} {topic} 改善したい｜今日から始められるAI活用3ステップ",
]


def fetch_news(industry, topic, max_items=5):
    """Google News RSSからAI関連の最新ニュースを取得"""
    queries = [
        f"{industry} AI 活用",
        f"AI {topic}",
        "AI ビジネス活用 中小企業",
    ]
    all_news = []
    for q in queries:
        try:
            encoded = urllib.parse.quote(q)
            url = f"https://news.google.com/rss/search?q={encoded}&hl=ja&gl=JP&ceid=JP:ja"
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; AutoBlogBot/1.0)"
            })
            with urllib.request.urlopen(req, timeout=10) as res:
                xml_data = res.read().decode("utf-8")
            root = ET.fromstring(xml_data)
            for item in root.findall(".//item")[:3]:
                title = item.findtext("title", "")
                pub_date = item.findtext("pubDate", "")
                if title and title not in [n["title"] for n in all_news]:
                    all_news.append({"title": title, "date": pub_date})
        except Exception as e:
            print(f"  ニュース取得エラー ({q}): {e}")
            continue
    return all_news[:max_items]


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_history():
    if HISTORY_PATH.exists():
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"generated": []}


def save_history(history):
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def pick_next_topic(config, history):
    """業種×トピックの両方をバランスよく選ぶ"""
    generated = set(history["generated"])
    topics = config["topics_per_industry"]
    industries = config["industries"]

    # 業種ごと・トピックごとの生成済み数をカウント
    ind_counts = {}
    topic_counts = {}
    for key in generated:
        parts = key.split("|")
        if len(parts) == 2:
            ind_counts[parts[0]] = ind_counts.get(parts[0], 0) + 1
            topic_counts[parts[1]] = topic_counts.get(parts[1], 0) + 1

    # 未生成の組み合わせを全列挙し、業種+トピックの合計カウントでソート
    candidates = []
    for industry in industries:
        for topic in topics:
            key = f"{industry}|{topic}"
            if key not in generated:
                score = ind_counts.get(industry, 0) + topic_counts.get(topic, 0)
                candidates.append((score, industry, topic, key))

    if not candidates:
        return None, None, None

    # スコアが同じもの（最小値）からランダムに選んで単調さを防ぐ
    candidates.sort(key=lambda x: x[0])
    min_score = candidates[0][0]
    best = [c for c in candidates if c[0] == min_score]
    chosen = random.choice(best)

    return chosen[1], chosen[2], chosen[3]


def generate_slug(industry, topic):
    """URLスラッグ生成"""
    raw = f"{industry}-{topic}"
    h = hashlib.md5(raw.encode()).hexdigest()[:8]
    return f"{h}"


def pick_title(industry, topic):
    """タイトルパターンをランダムに選択"""
    pattern = random.choice(TITLE_PATTERNS)
    return pattern.format(industry=industry, topic=topic)


def call_claude(prompt):
    """claude CLI を呼び出して結果を取得（stdinでプロンプト送信）"""
    claude_cmd = "claude.cmd" if sys.platform == "win32" else "claude"
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)
    result = subprocess.run(
        [claude_cmd, "-p",
         "--system-prompt", "あなたは中小企業向けAI活用の専門ライターです。実践的で具体的、読みやすいSEO記事をMarkdown形式で出力します。質問・確認・説明は一切せず、Markdown本文のみ出力してください。",
         "--model", "claude-opus-4-7"],
        input=prompt,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
        shell=(sys.platform == "win32"),
        env=env
    )
    if result.returncode != 0:
        print(f"claude CLI エラー: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return result.stdout.strip()


def generate_article(industry, topic, title, news_items=None):
    """claude CLI で記事を生成（最新ニュースを反映）"""
    # ニュース情報をプロンプトに組み込む
    news_section = ""
    if news_items:
        news_lines = "\n".join(f"- {n['title']}" for n in news_items)
        news_section = f"""
【最新トレンド情報】以下は直近のAI関連ニュースです。記事内で1〜2個を自然に引用し、「最近では〜」「2026年に入って〜」のような形で時事性を持たせてください。ただし、ニュースの丸写しではなく、{industry}の{topic}にどう関係するかの視点で触れてください。
{news_lines}
"""

    prompt = f"""以下のタイトルと条件でSEO記事をMarkdown形式で出力してください。Markdown本文だけを出力。前置き・説明・質問は絶対に禁止。

タイトル: {title}
業種: {industry}
テーマ: {topic}
執筆日: {datetime.now().strftime('%Y年%m月%d日')}
{news_section}
【最重要ルール：ペルソナドリブン】
この記事は「{industry}で{topic}に悩んでいる、たった1人の具体的な人物」に向けて書く。
まず以下のペルソナを自分で設定し、記事全体をその人の物語として構成すること。

ペルソナ設定（記事冒頭で自然に紹介する）:
- 名前（例：田中さん、佐藤さんなど日本人の姓）
- 年齢・性別
- {industry}での役割（オーナー／店長／スタッフ等）
- 店舗・事業の規模（従業員数、売上感）
- {topic}に関する「1つの具体的な困りごと」（これが記事全体の軸になる）
- その困りごとが発生する典型的な1日のシーン

【記事構成の要件】
1. タイトルはh1（# {title}）で始める
2. 4000〜5000文字（しっかり読み応えのある分量）
3. 冒頭リード文（4〜5行）: ペルソナの「ある1日」を描写し、読者に「自分のことだ」と思わせる。時事ネタにも軽く触れる
4. h2見出しを5〜6個。以下の流れで構成:
   - ペルソナの1日と、その困りごとの深掘り（感情面も描く）
   - なぜその問題が放置されがちなのか（業界構造・時間・心理の壁）
   - AI活用の解決策1（ペルソナが実際に試す物語として、ステップを具体的に）
   - AI活用の解決策2（別のアプローチ。ペルソナの状況に合わせて）
   - 導入後のビフォーアフター（数字で示す。1日・1週間・1ヶ月の変化）
   - まとめ：ペルソナからのひとこと（「やってみたら意外と簡単だった」的な締め）
5. 各セクション内でh3も使って読みやすくする

【内容の要件】
- 記事全体を通してペルソナの名前を繰り返し使い、物語として一貫させる
- ペルソナが実際にChatGPTに入力するプロンプト例を「」で4〜5個含める（業務に即した具体的なもの）
- ビフォーアフターの数字を明確に入れる（「月○時間→△時間に削減」「○円のコスト削減」等）
- 無料ツールとの組み合わせ（Googleフォーム、スプレッドシート、LINE公式、Canva等）を2つ以上提案
- 失敗談も1つ入れる（「最初はうまくいかなかった」→「こう工夫したら解決した」）
- 「です・ます」調。読者に語りかけるような親しみやすいトーン
- 2026年現在の最新情報を踏まえる

【書籍・ツール紹介の組み込み（重要）】
記事内で以下の2箇所に、ペルソナが実際に参考にした書籍やツールとして自然に紹介を入れる:

1. 解決策セクションの中で、ペルソナが「最初にAIの使い方を学ぶために読んだ本」として言及する
   例：「佐藤さんが最初に読んだのは、ChatGPTのビジネス活用について書かれた入門書でした。『この本に書いてあった通りにやったら、最初のプロンプトがうまくいった』と振り返ります」
   → この直後に「<!-- AFFILIATE -->」を1行入れる

2. まとめ・よくある質問の前に、ペルソナ目線で「もっと深く学びたい人向け」の紹介セクション
   → ここに「<!-- AFFILIATE2 -->」を1行入れる

【FAQ（よくある質問）セクション】
- まとめの前に「## よくある質問」セクションを入れる
- 同業者がよく持つ疑問を3つ、Q&A形式（### Q1: 〜）で答える
- 各回答は2〜3文で簡潔に
- Q&Aの中に1つは「初心者におすすめの本やツールはありますか？」を含め、書籍への誘導を自然に入れる

【SEO要件】
- 「<!-- AFFILIATE -->」を1箇所（解決策セクション内の書籍言及の直後）
- 「<!-- AFFILIATE2 -->」を1箇所（よくある質問の直前）
- 最終行に「DESC: 」で始まる60〜80文字のmeta description要約を追加

Markdown本文のみ出力してください。"""

    return call_claude(prompt)


def parse_article(raw_text):
    """生成テキストからタイトル・本文・descriptionを抽出"""
    lines = raw_text.strip().split("\n")

    # コードブロックの```を除去
    clean_lines = []
    in_code_block = False
    for line in lines:
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue
        if not in_code_block:
            clean_lines.append(line)

    # DESC行を探す
    desc = ""
    body_lines = []
    for line in clean_lines:
        if line.startswith("DESC:") or line.startswith("DESC: "):
            desc = line.replace("DESC:", "").strip()
        else:
            body_lines.append(line)

    body = "\n".join(body_lines).strip()

    # タイトル抽出
    title = ""
    for line in body_lines:
        if line.startswith("# "):
            title = line.replace("# ", "").strip()
            break

    if not title:
        title = "AI活用ガイド"
    if not desc:
        desc = title[:80]

    return title, body, desc


def save_article(slug, title, body, desc, industry, topic):
    """記事をMarkdown+メタデータとして保存"""
    date_str = datetime.now().strftime("%Y-%m-%d")

    # 読了時間を計算（日本語は400文字/分）
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

    n = config["generation"]["articles_per_run"]
    total = len(list(CONTENT_DIR.glob("*.md")))

    if total >= config["generation"]["max_articles"]:
        print("記事数上限に達しています。")
        return

    for i in range(n):
        industry, topic, key = pick_next_topic(config, history)
        if industry is None:
            print("全トピック生成済みです。")
            return

        title = pick_title(industry, topic)
        print(f"[{i+1}/{n}] 生成中: {industry} × {topic}")
        print(f"  タイトル: {title}")

        # 最新ニュースを取得
        print(f"  最新ニュースを取得中...")
        news_items = fetch_news(industry, topic)
        if news_items:
            print(f"  -> {len(news_items)}件のニュースを取得")
            for n_item in news_items[:3]:
                print(f"     - {n_item['title'][:60]}...")
        else:
            print(f"  -> ニュース取得なし（通常モードで生成）")

        slug = generate_slug(industry, topic)
        raw = generate_article(industry, topic, title, news_items)
        title, body, desc = parse_article(raw)
        meta = save_article(slug, title, body, desc, industry, topic)

        history["generated"].append(key)
        save_history(history)

        print(f"  -> 保存完了: {slug} ({meta['char_count']}文字, 約{meta['read_minutes']}分)")

    print(f"完了。現在の記事数: {total + n}")


if __name__ == "__main__":
    main()
