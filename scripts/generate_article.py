"""
記事自動生成スクリプト
claude CLI を呼び出して業種別AI活用記事を生成し、Markdownとして保存する。
"""
import json
import os
import subprocess
import sys
import re
import hashlib
import random
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config.json"
CONTENT_DIR = BASE_DIR / "content" / "articles"
HISTORY_PATH = BASE_DIR / "content" / "history.json"

# タイトルパターン（単調さを排除）
TITLE_PATTERNS = [
    "{industry}の{topic}、AIで驚くほど楽になる方法",
    "【{industry}向け】{topic}にAIを使ったら何が変わる？",
    "{industry}オーナー必見！{topic}をAIに任せる具体的な手順",
    "「{topic}が大変…」{industry}のよくある悩みをAIで解決",
    "{industry}の{topic}を今日からAIで効率化する3つのステップ",
    "プロが教える！{industry}の{topic}にChatGPTを活用する方法",
    "{industry}で{topic}に困っていませんか？無料AIツールで即改善",
    "月10時間削減！{industry}の{topic}をAIで自動化した事例",
]


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
    """業種をバラけさせて選ぶ（同じ業種が連続しない）"""
    generated = set(history["generated"])
    topics = config["topics_per_industry"]
    industries = config["industries"]

    # 業種ごとの生成済みトピック数をカウント
    counts = {}
    for key in generated:
        ind = key.split("|")[0]
        counts[ind] = counts.get(ind, 0) + 1

    # 最も記事が少ない業種から優先的に選ぶ
    sorted_industries = sorted(industries, key=lambda i: counts.get(i, 0))

    for industry in sorted_industries:
        for topic in topics:
            key = f"{industry}|{topic}"
            if key not in generated:
                return industry, topic, key

    return None, None, None


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
         "--model", "claude-sonnet-4-6"],
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


def generate_article(industry, topic, title):
    """claude CLI で記事を生成"""
    prompt = f"""以下のタイトルと条件でSEO記事をMarkdown形式で出力してください。Markdown本文だけを出力。前置き・説明・質問は絶対に禁止。

タイトル: {title}
業種: {industry}
テーマ: {topic}

【記事構成の要件】
1. タイトルはh1（# {title}）で始める
2. 2000〜3000文字
3. 冒頭にリード文（3〜4行）: 読者の悩みに共感し、この記事を読むメリットを伝える
4. h2見出しを4〜5個。以下の流れで構成:
   - 現状の課題（具体的なシーンを描写）
   - AI活用の解決策1（手順をステップで）
   - AI活用の解決策2（別のアプローチ）
   - 実践のコツ・注意点
   - まとめ
5. 各セクション内でh3も適宜使って読みやすく

【内容の要件】
- {industry}の現場で実際にありそうな具体的シーンを描く（「例えば〜」で始まる事例）
- ChatGPTへの具体的なプロンプト例を「」で2〜3個含める
- 数字を入れる（「月○時間の削減」「○%の改善」など想定値でOK）
- Googleフォーム、スプレッドシート、LINE公式アカウントなど無料ツールとの組み合わせも提案
- 「です・ます」調。親しみやすく、押し付けがましくなく

【SEO要件】
- 記事の途中（2番目のh2の後）に「<!-- AFFILIATE -->」を1行入れる
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
        slug = generate_slug(industry, topic)
        raw = generate_article(industry, topic, title)
        title, body, desc = parse_article(raw)
        meta = save_article(slug, title, body, desc, industry, topic)

        history["generated"].append(key)
        save_history(history)

        print(f"  -> 保存完了: {slug} ({meta['char_count']}文字, 約{meta['read_minutes']}分)")

    print(f"完了。現在の記事数: {total + n}")


if __name__ == "__main__":
    main()
