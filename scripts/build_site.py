"""
静的サイトビルドスクリプト v2
目次自動生成、構造化データ、関連記事、カテゴリフィルター対応
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
    h2_count = 0

    for line in lines:
        stripped = line.strip()

        if not stripped:
            if in_list:
                result.append(f"</{list_type}>")
                in_list = False
            result.append("")
            continue

        # 水平線（---）はスキップ
        if stripped == "---":
            continue

        # 見出し
        if stripped.startswith("### "):
            if in_list:
                result.append(f"</{list_type}>")
                in_list = False
            text = stripped[4:]
            result.append(f"<h3>{inline_format(text)}</h3>")
            continue
        if stripped.startswith("## "):
            if in_list:
                result.append(f"</{list_type}>")
                in_list = False
            h2_count += 1
            text = stripped[3:]
            anchor = f"section-{h2_count}"
            result.append(f'<h2 id="{anchor}">{inline_format(text)}</h2>')
            continue
        if stripped.startswith("# "):
            if in_list:
                result.append(f"</{list_type}>")
                in_list = False
            result.append(f"<h1>{inline_format(stripped[2:])}</h1>")
            continue

        # アフィリエイトタグ
        if "<!-- AFFILIATE -->" in stripped:
            result.append(stripped)
            continue

        # リスト
        if stripped.startswith("- ") or stripped.startswith("* "):
            if not in_list:
                result.append("<ul>")
                in_list = True
                list_type = "ul"
            result.append(f"<li>{inline_format(stripped[2:])}</li>")
            continue

        if re.match(r"^\d+\. ", stripped):
            if not in_list:
                result.append("<ol>")
                in_list = True
                list_type = "ol"
            content = re.sub(r"^\d+\. ", "", stripped)
            result.append(f"<li>{inline_format(content)}</li>")
            continue

        # 通常段落
        if in_list:
            result.append(f"</{list_type}>")
            in_list = False
        result.append(f"<p>{inline_format(stripped)}</p>")

    if in_list:
        result.append(f"</{list_type}>")

    return "\n".join(result)


def inline_format(text):
    """太字・リンク・コードのインライン変換"""
    text = html.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    text = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', text)
    return text


def extract_h2_headings(md_text):
    """Markdownからh2見出しを抽出（目次用）"""
    headings = []
    count = 0
    for line in md_text.split("\n"):
        if line.strip().startswith("## "):
            count += 1
            text = line.strip()[3:]
            headings.append({"id": f"section-{count}", "text": text})
    return headings


def build_toc(headings):
    """目次HTMLを生成"""
    if len(headings) < 2:
        return ""
    items = "\n".join(
        f'<li><a href="#{h["id"]}">{html.escape(h["text"])}</a></li>'
        for h in headings
    )
    return f"""<div class="toc">
  <div class="toc-title">この記事の内容</div>
  <ol>{items}</ol>
</div>"""


def build_affiliate_html(pick, config):
    """書籍画像付きのリッチなアフィリエイトカードを生成"""
    aff = config["affiliate"]
    from urllib.parse import quote

    # URLを組み立て
    if pick["search"] == "_travel":
        url = aff["travel_url"]
        tracking = aff.get("travel_img", aff["tracking_img"])
        # 旅館用は画像なしカード
        return f"""<div class="aff-card">
  <div class="aff-card-inner aff-travel">
    <div class="aff-travel-icon">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M2 4v16"/><path d="M2 8h18a2 2 0 0 1 2 2v10"/><path d="M2 17h20"/><path d="M6 8v-2a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v2"/></svg>
    </div>
    <div class="aff-content">
      <span class="aff-badge">RECOMMEND</span>
      <p class="aff-label">宿泊施設の集客改善に</p>
      <p class="aff-sub">楽天トラベルへの掲載で予約数アップ</p>
      <a href="{url}" target="_blank" rel="nofollow" class="aff-btn">楽天トラベルを見る <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="aff-arrow"><path d="M5 12h14M12 5l7 7-7 7"/></svg></a>
    </div>
  </div>
  <img border="0" width="1" height="1" src="{tracking}" alt="">
</div>"""

    query = quote(pick["search"], safe="")
    url = aff["base_url"].replace("{query}", query)
    tracking = aff["tracking_img"]

    book_title = html.escape(pick.get("book_title", ""))
    book_author = html.escape(pick.get("book_author", ""))
    book_price = html.escape(pick.get("book_price", ""))
    book_img = pick.get("book_img", "")

    return f"""<div class="aff-card">
  <div class="aff-card-inner">
    <div class="aff-book-img">
      <img src="{book_img}" alt="{book_title}" loading="lazy">
    </div>
    <div class="aff-content">
      <span class="aff-badge">PICK UP</span>
      <p class="aff-book-title">{book_title}</p>
      <p class="aff-book-meta">{book_author}　{book_price}（税込）</p>
      <div class="aff-stars">★★★★☆ おすすめ</div>
      <a href="{url}" target="_blank" rel="nofollow" class="aff-btn">
        楽天ブックスで見る
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="aff-arrow"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
      </a>
    </div>
  </div>
  <img border="0" width="1" height="1" src="{tracking}" alt="">
</div>"""


def load_books_cache():
    """書籍キャッシュを読み込む"""
    cache_path = Path(__file__).resolve().parent.parent / "content" / "books_cache.json"
    if cache_path.exists():
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"books": {}}


def build_review_html(review_count):
    """レビュー数に応じた表示を生成（0件でも自然に見せる）"""
    if review_count and review_count > 0:
        stars = min(5, max(1, review_count))
        return f'<div class="aff-review"><span class="aff-review-stars">{"★" * stars}{"☆" * (5 - stars)}</span><span class="aff-review-count">レビュー{review_count}件</span></div>'
    return '<div class="aff-review"><span class="aff-review-stars">★★★★☆</span><span class="aff-review-count">おすすめ書籍</span></div>'


def insert_affiliate(html_text, config, meta=None, books_cache=None):
    """アフィリエイトタグを書籍画像付きカードに置換（文脈付き）"""
    if books_cache is None:
        books_cache = {}

    industry = meta.get("industry", "AI") if meta else "AI"
    topic = meta.get("topic", "活用") if meta else "活用"

    # 記事に対応する書籍をキャッシュから取得
    book = None
    if meta and meta.get("slug") in books_cache.get("books", {}):
        book = books_cache["books"][meta["slug"]]

    if book and book.get("image_url"):
        aff_url = book.get("affiliate_url", "#")
        review_html = build_review_html(book.get("review_count", 0))
        card_html = f"""<div class="aff-section">
  <p class="aff-section-intro">{html.escape(industry)}の{html.escape(topic)}について、さらに詳しく学びたい方にはこちらの書籍がおすすめです。</p>
  <div class="aff-card">
    <div class="aff-card-inner">
      <div class="aff-book-img">
        <img src="{html.escape(book['image_url'])}" alt="{html.escape(book['title'])}" loading="lazy">
      </div>
      <div class="aff-content">
        <span class="aff-badge">Pick Up</span>
        <p class="aff-book-title">{html.escape(book['title'])}</p>
        <p class="aff-book-meta">{html.escape(book.get('author', ''))} / {book.get('price', '')}円（税込）</p>
        {review_html}
        <a href="{html.escape(aff_url)}" target="_blank" rel="nofollow" class="aff-btn">
          楽天ブックスで見る
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="aff-arrow"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
        </a>
      </div>
    </div>
  </div>
</div>"""
    else:
        from urllib.parse import quote
        search_q = quote(f"{industry} {topic} AI")
        aff = config.get("affiliate", {})
        url = aff.get("base_url", "").replace("{query}", search_q)
        card_html = f"""<div class="aff-section">
  <p class="aff-section-intro">{html.escape(industry)}の{html.escape(topic)}をさらに深く学べる書籍を探してみませんか？</p>
  <div class="aff-card">
    <div class="aff-card-inner" style="padding:1.25rem 1.5rem">
      <div class="aff-content">
        <span class="aff-badge">Recommend</span>
        <p class="aff-book-title">{html.escape(industry)}のAI活用に役立つ書籍</p>
        <p class="aff-book-meta">楽天ブックスで関連書籍を探せます</p>
        <a href="{url}" target="_blank" rel="nofollow" class="aff-btn">
          楽天ブックスで探す
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="aff-arrow"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
        </a>
      </div>
    </div>
  </div>
</div>"""

    return html_text.replace("<!-- AFFILIATE -->", card_html)


def build_related_articles(current_meta, all_meta):
    """同じ業種 or 同じトピックの関連記事を最大4件表示"""
    related = []
    for meta in all_meta:
        if meta["slug"] == current_meta["slug"]:
            continue
        if meta["industry"] == current_meta["industry"] or meta["topic"] == current_meta["topic"]:
            related.append(meta)
        if len(related) >= 4:
            break

    if not related:
        return ""

    items = []
    for m in related:
        items.append(f"""<li>
  <span class="tag">{html.escape(m['industry'])}</span>
  <a href="{m['slug']}.html">{html.escape(m['title'])}</a>
</li>""")

    return f"""<div class="related-articles">
  <h2>あわせて読みたい</h2>
  <ul class="related-list">{"".join(items)}</ul>
</div>"""


def build_structured_data(meta, config):
    """JSON-LD構造化データを生成"""
    data = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": meta["title"],
        "description": meta["description"],
        "datePublished": meta["date"],
        "dateModified": meta["date"],
        "author": {
            "@type": "Organization",
            "name": "かわさき楽AIサポート",
            "url": "https://www.smilefactory-rakuai.com/"
        },
        "publisher": {
            "@type": "Organization",
            "name": "株式会社スマイルファクトリー"
        },
        "mainEntityOfPage": {
            "@type": "WebPage",
            "@id": f'{config["site"]["url"]}/articles/{meta["slug"]}.html'
        }
    }
    return f'<script type="application/ld+json">{json.dumps(data, ensure_ascii=False)}</script>'


def build_article(meta, md_text, template, config, all_meta, books_cache=None):
    """1記事分のHTMLを生成"""
    article_html = md_to_html(md_text)
    article_html = insert_affiliate(article_html, config, meta=meta, books_cache=books_cache)

    # 目次を生成してh1の後に挿入
    headings = extract_h2_headings(md_text)
    toc = build_toc(headings)
    if toc:
        article_html = article_html.replace("</h1>", f"</h1>\n{toc}", 1)

    # 記事ヘッダーメタ
    read_min = meta.get("read_minutes", 3)
    header_meta = f'<div class="article-header-meta"><span class="tag">{html.escape(meta.get("industry", ""))}</span><span>{meta.get("date", "")}</span><span>約{read_min}分で読めます</span></div>'

    # 関連記事
    related = build_related_articles(meta, all_meta)

    # CTA
    ind_name = html.escape(meta.get("industry", ""))
    cta = f"""<div class="cta-box">
  <p class="cta-title">{ind_name}のAI活用、何から始めればいいかわからない方へ</p>
  <p>かわさき楽AIサポートでは、{ind_name}をはじめ中小企業・個人事業主の方に向けて、無料ツール中心のAI活用支援を行っています。初回相談は無料です。</p>
  <a href="https://www.smilefactory-rakuai.com/" target="_blank" rel="noopener" class="cta-btn">無料で相談してみる</a>
</div>"""

    content = f"<article>\n{header_meta}\n{article_html}\n{cta}\n{related}\n</article>"

    # パンくずリスト
    breadcrumb = f'<div class="breadcrumb"><a href="../index.html">トップ</a><span>&gt;</span><span>{html.escape(meta.get("industry", ""))}</span><span>&gt;</span><span>{html.escape(meta["title"][:30])}...</span></div>'

    # 構造化データ
    structured = build_structured_data(meta, config)

    page = template.replace("{{page_title}}", html.escape(meta["title"]))
    page = page.replace("{{meta_description}}", html.escape(meta["description"]))
    page = page.replace("{{canonical_url}}", f'{config["site"]["url"]}/articles/{meta["slug"]}.html')
    page = page.replace("{{root_path}}", "../")
    page = page.replace("{{og_type}}", "article")
    page = page.replace("{{breadcrumb}}", breadcrumb)
    page = page.replace("{{structured_data}}", structured)
    page = page.replace("{{content}}", content)

    return page


def build_index(all_meta, template, config):
    """トップページ（記事一覧 + カテゴリフィルター）"""
    sorted_meta = sorted(all_meta, key=lambda m: m.get("date", ""), reverse=True)

    # カテゴリ一覧（記事数付き）
    industries = sorted(set(m["industry"] for m in all_meta))
    ind_counts = {}
    for m in all_meta:
        ind_counts[m["industry"]] = ind_counts.get(m["industry"], 0) + 1

    cat_buttons = ['<button class="category-btn active" data-filter="all">すべて</button>']
    for ind in industries:
        escaped = html.escape(ind)
        count = ind_counts.get(ind, 0)
        cat_buttons.append(f'<button class="category-btn" data-filter="{escaped}">{escaped} <small>({count})</small></button>')

    # 業種数
    industry_count = len(industries)

    # 記事一覧
    items = []
    for meta in sorted_meta:
        read_min = meta.get("read_minutes", 3)
        items.append(f"""<li data-industry="{html.escape(meta.get('industry', ''))}">
  <a class="article-title" href="articles/{meta['slug']}.html">{html.escape(meta['title'])}</a>
  <div class="article-meta">
    <span class="tag">{html.escape(meta.get('industry', ''))}</span>
    <span>{meta.get('date', '')}</span>
    <span class="article-meta-dot"></span>
    <span class="read-time">約{read_min}分で読めます</span>
  </div>
  <div class="article-excerpt">{html.escape(meta['description'][:120])}</div>
</li>""")

    content = f"""<div class="hero">
  <h1>業種別AI活用ガイド</h1>
  <p class="hero-sub">ChatGPTなどの無料AIツールで、日々の業務をもっと楽に。</p>
  <div class="hero-stats">
    <div class="hero-stat"><span class="hero-stat-num">{len(all_meta)}</span><span class="hero-stat-label">記事</span></div>
    <div class="hero-stat"><span class="hero-stat-num">{industry_count}</span><span class="hero-stat-label">業種</span></div>
    <div class="hero-stat"><span class="hero-stat-num">10</span><span class="hero-stat-label">テーマ</span></div>
  </div>
</div>
<div class="category-filter">
{"".join(cat_buttons)}
</div>
<ul class="article-list">
{"".join(items)}
</ul>
<script>
document.querySelectorAll('.category-btn').forEach(function(btn) {{
  btn.addEventListener('click', function() {{
    var industry = this.getAttribute('data-filter');
    document.querySelectorAll('.category-btn').forEach(function(b) {{ b.classList.remove('active'); }});
    this.classList.add('active');
    document.querySelectorAll('.article-list li').forEach(function(li) {{
      if (industry === 'all' || li.getAttribute('data-industry') === industry) {{
        li.style.display = '';
      }} else {{
        li.style.display = 'none';
      }}
    }});
  }});
}});
</script>"""

    page = template.replace("{{page_title}}", "業種別AI活用ガイド")
    page = page.replace("{{meta_description}}", config["site"]["description"])
    page = page.replace("{{canonical_url}}", config["site"]["url"])
    page = page.replace("{{root_path}}", "")
    page = page.replace("{{og_type}}", "website")
    page = page.replace("{{breadcrumb}}", "")
    page = page.replace("{{structured_data}}", "")
    page = page.replace("{{content}}", content)

    return page


def build_sitemap(all_meta, config):
    """sitemap.xml"""
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

    # 書籍キャッシュを読み込む
    books_cache = load_books_cache()

    # 全記事メタデータを先に読み込む
    all_meta = []
    for meta_path in sorted(CONTENT_DIR.glob("*.json")):
        with open(meta_path, "r", encoding="utf-8") as f:
            all_meta.append(json.load(f))

    # 各記事をビルド
    built = 0
    for meta in all_meta:
        md_path = CONTENT_DIR / f"{meta['slug']}.md"
        if not md_path.exists():
            continue

        with open(md_path, "r", encoding="utf-8") as f:
            md_text = f.read()

        article_html = build_article(meta, md_text, template, config, all_meta, books_cache)
        out_path = ARTICLES_DIR / f"{meta['slug']}.html"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(article_html)

        built += 1
        print(f"  ビルド: {meta['slug']} ({meta['title']})")

    # インデックスページ
    index_html = build_index(all_meta, template, config)
    with open(PUBLIC_DIR / "index.html", "w", encoding="utf-8") as f:
        f.write(index_html)

    # サイトマップ
    sitemap = build_sitemap(all_meta, config)
    with open(PUBLIC_DIR / "sitemap.xml", "w", encoding="utf-8") as f:
        f.write(sitemap)

    print(f"\nビルド完了: {built}記事 → public/")


if __name__ == "__main__":
    main()
