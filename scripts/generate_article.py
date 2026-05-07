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
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config.json"
CONTENT_DIR = BASE_DIR / "content" / "articles"
HISTORY_PATH = BASE_DIR / "content" / "history.json"


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
    """まだ生成していない業種×トピックの組み合わせを1つ選ぶ"""
    generated = set(history["generated"])
    for industry in config["industries"]:
        for topic in config["topics_per_industry"]:
            key = f"{industry}|{topic}"
            if key not in generated:
                return industry, topic, key
    return None, None, None


def generate_slug(industry, topic):
    """URLスラッグ生成"""
    raw = f"{industry}-{topic}"
    h = hashlib.md5(raw.encode()).hexdigest()[:8]
    return f"{h}"


def call_claude(prompt):
    """claude CLI を呼び出して結果を取得（stdinでプロンプト送信）"""
    # Windowsでは .cmd 拡張子が必要
    claude_cmd = "claude.cmd" if sys.platform == "win32" else "claude"
    # 入れ子セッション制約を回避するため環境変数をクリア
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)
    # プロンプトをstdinから渡す（コマンドライン長制限回避）
    # --setting-sources で空にしてCLAUDE.mdの影響を排除
    result = subprocess.run(
        [claude_cmd, "-p",
         "--system-prompt", "あなたはSEOライターです。指示されたMarkdown記事だけを出力してください。質問・確認・説明は一切禁止。",
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


def generate_article(industry, topic):
    """claude CLI で記事を生成"""
    prompt = f"""あなたはSEOライターです。以下の条件でMarkdown形式の記事を出力してください。質問や確認は一切せず、Markdown本文だけを即座に出力してください。

# {industry}の{topic}をAIで改善する方法

上記タイトルの記事を以下の要件で書いてください:
- タイトルはh1（# ）で始める（上記をそのまま使う）
- 1500〜2500文字程度
- h2見出しを3〜5個使う
- 具体的な悩み・課題から始めて、AI（主にChatGPT等の無料ツール）を使った解決策を提示
- 専門用語は避け、初心者にもわかりやすく「です・ます」調で
- 最後に「## まとめ」セクションを入れる
- 記事の途中（2番目のh2の後あたり）に「<!-- AFFILIATE -->」というHTMLコメントを1行だけ入れる
- 最終行に「DESC: 」で始まる80文字以内のmeta description要約を1行追加する

Markdown本文だけを出力。前置き・説明・質問は禁止。"""

    return call_claude(prompt)


def parse_article(raw_text):
    """生成テキストからタイトル・本文・descriptionを抽出"""
    lines = raw_text.strip().split("\n")

    # DESC行を探す
    desc = ""
    body_lines = []
    for line in lines:
        if line.startswith("DESC:"):
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
        desc = title

    return title, body, desc


def save_article(slug, title, body, desc, industry, topic):
    """記事をMarkdown+メタデータとして保存"""
    date_str = datetime.now().strftime("%Y-%m-%d")
    meta = {
        "slug": slug,
        "title": title,
        "description": desc,
        "industry": industry,
        "topic": topic,
        "date": date_str
    }

    # メタデータJSON
    meta_path = CONTENT_DIR / f"{slug}.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    # Markdown本文
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

        print(f"[{i+1}/{n}] 生成中: {industry} × {topic}")
        slug = generate_slug(industry, topic)
        raw = generate_article(industry, topic)
        title, body, desc = parse_article(raw)
        meta = save_article(slug, title, body, desc, industry, topic)

        history["generated"].append(key)
        save_history(history)

        print(f"  -> 保存完了: {slug} ({title})")

    print(f"完了。現在の記事数: {total + n}")


if __name__ == "__main__":
    main()
