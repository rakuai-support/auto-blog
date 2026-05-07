"""
静的サイトビルドスクリプト
content/articles/ のMarkdownからHTMLを生成し、public/ に配置する。
"""
import json
import re
import html
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
CONTENT_DIR = BASE_DIR / "content" / "articles"
PUBLIC_DIR = BASE_DIR / "public"
ARTICLES_DIR = PUBLIC_DIR / "articles"
TEMPLATE_DIR = BASE_DIR / "templates"
CONFIG_PATH = BASE_DIR / "config.json"


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_template():
    with open(TEMPLATE_DIR / "base.html", "r", encoding="utf-8") as f:
        return f.read()


def md_to_html(md_text):
    """簡易Markdownパーサー（外部依存なし）"""
    lines = md_text.split("\n")
    result = []
    in_list = False
    list_type = None

    for line in lines:
        stripped = line.strip()

        # 空行
        if not stripped:
            if in_list:
                result.append(f"</{list_type}>")
                in_list = False
            result.append("")
            continue

        # 見出し
        if stripped.startswith("### "):
            if in_list:
                result.append(f"</{list_type}>")
                in_list = False
            result.append(f"<h3>{html.escape(stripped[4:])}</h3>")
            continue
        if stripped.startswith("## "):
            if in_list:
                result.append(f"</{list_type}>")
                in_list = False
            result.append(f"<h2>{html.escape(stripped[3:])}</h2>")
            continue
        if stripped.startswith("# "):
            if in_list:
                result.append(f"</{list_type}>")
                in_list = False
            result.append(f"<h1>{html.escape(stripped[2:])}</h1>")
            continue

        # アフィリエイトタグはそのまま通す
        if "<!-- AFFILIATE -->" in stripped:
            result.append(stripped)
            continue

        # リスト
        if stripped.startswith("- ") or stripped.startswith("* "):
            if not in_list:
                result.append("<ul>")
                in_list = True
                list_type = "ul"
            content = stripped[2:]
            content = inline_format(content)
            result.append(f"<li>{content}</li>")
            continue

        if re.match(r"^\d+\. ", stripped):
            if not in_list:
                result.append("<ol>")
                in_list = True
                list_type = "ol"
            content = re.sub(r"^\d+\. ", "", stripped)
            content = inline_format(content)
            result.append(f"<li>{content}</li>")
            continue

        # 通常の段落
        if in_list:
            result.append(f"</{list_type}>")
            in_list = False
        content = inline_format(stripped)
        result.append(f"<p>{content}</p>")

    if in_list:
        result.append(f"</{list_type}>")

    return "\n".join(result)


def inline_format(text):
    """太字・リンクのインライン変換"""
    text = html.escape(text)
    # 太字 **text**
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    # リンク [text](url)
    text = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', text)
    return text


def insert_affiliate(html_text, config):
    """アフィリエイトタグを実際のリンクに置換"""
    if not config.get("affiliate", {}).get("links"):
        return html_text.replace("<!-- AFFILIATE -->", "")

    # 記事内容に合うリンクを選択（最初にマッチしたもの）
    link_html = config["affiliate"]["links"][0]["html"]
    for link in config["affiliate"]["links"]:
        if link["keyword"].lower() in html_text.lower():
            link_html = link["html"]
            break

    return html_text.replace("<!-- AFFILIATE -->", link_html)


def build_article(meta, md_text, template, config):
    """1記事分のHTMLを生成"""
    article_html = md_to_html(md_text)
    article_html = insert_affiliate(article_html, config)

    date_display = meta.get("date", "")
    header = f'<div class="article-meta">{date_display} | {html.escape(meta.get("industry", ""))}</div>'
    content = f"<article>\n{header}\n{article_html}\n</article>"

    page = template.replace("{{page_title}}", html.escape(meta["title"]))
    page = page.replace("{{meta_description}}", html.escape(meta["description"]))
    page = page.replace("{{canonical_url}}", f'{config["site"]["url"]}/articles/{meta["slug"]}.html')
    page = page.replace("{{root_path}}", "../")
    page = page.replace("{{content}}", content)

    return page


def build_index(all_meta, template, config):
    """トップページ（記事一覧）を生成"""
    # 日付で降順ソート
    sorted_meta = sorted(all_meta, key=lambda m: m.get("date", ""), reverse=True)

    items = []
    for meta in sorted_meta:
        items.append(f"""<li>
  <span class="tag">{html.escape(meta.get('industry', ''))}</span>
  <a href="articles/{meta['slug']}.html">{html.escape(meta['title'])}</a>
  <div class="article-meta">{meta.get('date', '')}</div>
  <div class="article-excerpt">{html.escape(meta['description'][:100])}</div>
</li>""")

    content = f"""<h1>AI活用ラボ - 業種別ガイド</h1>
<p>中小企業・個人事業主のための、すぐに使えるAI活用ガイド集です。</p>
<p>現在 <strong>{len(all_meta)}記事</strong> 公開中</p>
<ul class="article-list">
{"".join(items)}
</ul>"""

    page = template.replace("{{page_title}}", "トップ")
    page = page.replace("{{meta_description}}", config["site"]["description"])
    page = page.replace("{{canonical_url}}", config["site"]["url"])
    page = page.replace("{{root_path}}", "")
    page = page.replace("{{content}}", content)

    return page


def build_sitemap(all_meta, config):
    """sitemap.xml を生成"""
    urls = [f"""  <url>
    <loc>{config['site']['url']}/index.html</loc>
    <lastmod>{datetime.now().strftime('%Y-%m-%d')}</lastmod>
    <priority>1.0</priority>
  </url>"""]

    for meta in all_meta:
        urls.append(f"""  <url>
    <loc>{config['site']['url']}/articles/{meta['slug']}.html</loc>
    <lastmod>{meta.get('date', datetime.now().strftime('%Y-%m-%d'))}</lastmod>
    <priority>0.8</priority>
  </url>""")

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{"".join(urls)}
</urlset>"""


def main():
    config = load_config()
    template = load_template()
    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)

    # 全記事を処理
    all_meta = []
    for meta_path in sorted(CONTENT_DIR.glob("*.json")):
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        md_path = CONTENT_DIR / f"{meta['slug']}.md"
        if not md_path.exists():
            continue

        with open(md_path, "r", encoding="utf-8") as f:
            md_text = f.read()

        article_html = build_article(meta, md_text, template, config)
        out_path = ARTICLES_DIR / f"{meta['slug']}.html"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(article_html)

        all_meta.append(meta)
        print(f"  ビルド: {meta['slug']} ({meta['title']})")

    # インデックスページ
    index_html = build_index(all_meta, template, config)
    with open(PUBLIC_DIR / "index.html", "w", encoding="utf-8") as f:
        f.write(index_html)

    # サイトマップ
    sitemap = build_sitemap(all_meta, config)
    with open(PUBLIC_DIR / "sitemap.xml", "w", encoding="utf-8") as f:
        f.write(sitemap)

    print(f"\nビルド完了: {len(all_meta)}記事 → public/")


if __name__ == "__main__":
    main()
