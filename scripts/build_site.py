"""
静的サイトビルドスクリプト v3
目次自動生成、構造化データ（Article/FAQ/HowTo）、関連記事、内部リンク、
SaaSアフィリエイト、カテゴリフィルター、sitemap ping対応
"""
import json
import re
import html
import urllib.request
import urllib.parse
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


def build_analytics_tag(config):
    """GA4 measurement IDが設定されている場合にGoogle tagを生成する"""
    measurement_id = config.get("analytics", {}).get("ga4_measurement_id", "").strip()
    if not measurement_id:
        return ""

    safe_id = html.escape(measurement_id)
    return f"""<!-- Google tag (gtag.js) -->
  <script async src="https://www.googletagmanager.com/gtag/js?id={safe_id}"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag('js', new Date());
    gtag('config', '{safe_id}');
  </script>"""


def split_table_row(row):
    """Markdown table rowをセル配列に分解する"""
    return [cell.strip() for cell in row.strip().strip("|").split("|")]


def is_table_row(line):
    """Markdown table rowらしい行か判定する"""
    stripped = line.strip()
    return stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 2


def is_table_separator(line):
    """Markdown tableの区切り行（|---|---|）か判定する"""
    if not is_table_row(line):
        return False
    cells = split_table_row(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell.strip()) for cell in cells)


def build_table_html(header_row, body_rows):
    """Markdown tableをHTML tableに変換する"""
    headers = split_table_row(header_row)
    thead = "".join(f"<th>{inline_format(cell)}</th>" for cell in headers)
    rows = []
    for row in body_rows:
        cells = split_table_row(row)
        if len(cells) < len(headers):
            cells += [""] * (len(headers) - len(cells))
        cells = cells[:len(headers)]
        rows.append("<tr>" + "".join(f"<td>{inline_format(cell)}</td>" for cell in cells) + "</tr>")

    return f"""<div class="table-wrap">
<table>
  <thead><tr>{thead}</tr></thead>
  <tbody>{"".join(rows)}</tbody>
</table>
</div>"""


def md_to_html(md_text):
    """簡易Markdownパーサー（外部依存なし）"""
    lines = md_text.split("\n")
    result = []
    in_list = False
    list_type = None
    h2_count = 0

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            if in_list:
                result.append(f"</{list_type}>")
                in_list = False
            result.append("")
            i += 1
            continue

        # 水平線（---）はスキップ
        if stripped == "---":
            i += 1
            continue

        # アフィリエイトタグ
        affiliate_markers = ["<!-- AFFILIATE -->", "<!-- AFFILIATE2 -->"]
        matched_marker = next((marker for marker in affiliate_markers if marker in stripped), None)
        if matched_marker:
            if in_list:
                result.append(f"</{list_type}>")
                in_list = False
            before = stripped.replace(matched_marker, "").strip()
            if before:
                result.append(f"<p>{inline_format(before)}</p>")
            result.append(matched_marker)
            i += 1
            continue

        # Markdown table
        if i + 1 < len(lines) and is_table_row(stripped) and is_table_separator(lines[i + 1].strip()):
            if in_list:
                result.append(f"</{list_type}>")
                in_list = False
            body_rows = []
            i += 2
            while i < len(lines) and is_table_row(lines[i].strip()):
                body_rows.append(lines[i].strip())
                i += 1
            result.append(build_table_html(stripped, body_rows))
            continue

        # 見出し
        if stripped.startswith("### "):
            if in_list:
                result.append(f"</{list_type}>")
                in_list = False
            text = stripped[4:]
            result.append(f"<h3>{inline_format(text)}</h3>")
            i += 1
            continue
        if stripped.startswith("## "):
            if in_list:
                result.append(f"</{list_type}>")
                in_list = False
            h2_count += 1
            text = stripped[3:]
            anchor = f"section-{h2_count}"
            result.append(f'<h2 id="{anchor}">{inline_format(text)}</h2>')
            i += 1
            continue
        if stripped.startswith("# "):
            if in_list:
                result.append(f"</{list_type}>")
                in_list = False
            result.append(f"<h1>{inline_format(stripped[2:])}</h1>")
            i += 1
            continue

        # リスト
        if stripped.startswith("- ") or stripped.startswith("* "):
            if not in_list:
                result.append("<ul>")
                in_list = True
                list_type = "ul"
            result.append(f"<li>{inline_format(stripped[2:])}</li>")
            i += 1
            continue

        if re.match(r"^\d+\. ", stripped):
            if not in_list:
                result.append("<ol>")
                in_list = True
                list_type = "ol"
            content = re.sub(r"^\d+\. ", "", stripped)
            result.append(f"<li>{inline_format(content)}</li>")
            i += 1
            continue

        # 通常段落
        if in_list:
            result.append(f"</{list_type}>")
            in_list = False
        result.append(f"<p>{inline_format(stripped)}</p>")
        i += 1

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

    result = html_text.replace("<!-- AFFILIATE -->", card_html)

    # 2つ目のアフィリエイト枠（まとめ前）
    if "<!-- AFFILIATE2 -->" in result:
        # 別の訴求文でカードを生成
        if book and book.get("image_url"):
            aff_url = book.get("affiliate_url", "#")
            card2_html = f"""<div class="aff-section">
  <p class="aff-section-intro">この記事の内容をもっと体系的に学びたい方へ。実践的な一冊をご紹介します。</p>
  <div class="aff-card">
    <div class="aff-card-inner">
      <div class="aff-book-img">
        <img src="{html.escape(book['image_url'])}" alt="{html.escape(book['title'])}" loading="lazy">
      </div>
      <div class="aff-content">
        <span class="aff-badge">おすすめ</span>
        <p class="aff-book-title">{html.escape(book['title'])}</p>
        <p class="aff-book-meta">{html.escape(book.get('author', ''))} / {book.get('price', '')}円（税込）</p>
        {review_html}
        <a href="{html.escape(aff_url)}" target="_blank" rel="nofollow" class="aff-btn">
          楽天ブックスで詳細を見る
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="aff-arrow"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
        </a>
      </div>
    </div>
  </div>
</div>"""
        else:
            search_q = quote(f"{industry} {topic} AI 入門")
            url2 = aff.get("base_url", "").replace("{query}", search_q)
            card2_html = f"""<div class="aff-section">
  <p class="aff-section-intro">「もっと詳しく知りたい」と思った方へ。AI活用の入門書から実践書まで、あなたに合った一冊が見つかるかもしれません。</p>
  <div class="aff-card">
    <div class="aff-card-inner" style="padding:1.25rem 1.5rem">
      <div class="aff-content">
        <span class="aff-badge">もっと学ぶ</span>
        <p class="aff-book-title">{html.escape(industry)}×AI活用の関連書籍</p>
        <p class="aff-book-meta">初心者向けから実践レベルまで幅広く揃っています</p>
        <a href="{url2}" target="_blank" rel="nofollow" class="aff-btn">
          楽天ブックスで探す
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="aff-arrow"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
        </a>
      </div>
    </div>
  </div>
</div>"""
        result = result.replace("<!-- AFFILIATE2 -->", card2_html)

    return result


def insert_saas_cards(html_text, config):
    """<!-- TOOL:ツール名 --> タグをSaaSカードに置換"""
    saas_list = config.get("saas_affiliate", [])
    if not saas_list:
        return html_text

    for saas in saas_list:
        tag = f"<!-- TOOL:{saas['service']} -->"
        if tag in html_text:
            card = f"""<div class="saas-card">
  <div class="saas-card-inner">
    <div class="saas-content">
      <span class="saas-badge">{html.escape(saas['badge'])}</span>
      <p class="saas-name">{html.escape(saas['service'])}</p>
      <p class="saas-desc">{html.escape(saas['description'])}</p>
      <a href="{html.escape(saas['url'])}" target="_blank" rel="nofollow noopener" class="saas-btn">
        {html.escape(saas['cta_text'])}
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="aff-arrow"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
      </a>
    </div>
  </div>
</div>"""
            html_text = html_text.replace(tag, card)

    # マッチしなかったタグを除去
    html_text = re.sub(r"<!-- TOOL:.+? -->", "", html_text)
    return html_text


def insert_own_services(html_text, config, meta):
    """記事本文中にサービスへの言及を自然に挿入する"""
    services = config.get("own_services", [])
    if not services:
        return html_text

    industry = meta.get("industry", "")
    topic = meta.get("topic", "")
    inserted = 0

    # --- 1. 本文中のキーワードに応じたインライン挿入 ---
    inline_rules = [
        {
            "triggers": ["メニュー", "チラシ", "価格表", "印刷"],
            "service_id": "menuprint",
            "text": 'ちなみに、スマホだけでメニュー表を作れる<a href="{url}" target="_blank" rel="noopener">MenuPrint</a>のようなサービスを使えば、デザインの手間もほぼゼロにできます。'
        },
        {
            "triggers": ["集客", "検索", "見つけてもらえ", "認知", "口コミ"],
            "service_id": "aio-shindan",
            "text": '最近はAIが検索結果を要約して表示する時代です。自分のお店がAIに紹介されるかどうか、<a href="{url}" target="_blank" rel="noopener">AIOスコア診断</a>で無料チェックしてみるのもおすすめです。'
        },
        {
            "triggers": ["外国人", "インバウンド", "多言語", "翻訳", "観光客"],
            "service_id": "omotenashi-qr",
            "text": '多言語対応には、日本語を入力するだけで15言語のAI音声動画を作れる<a href="{url}" target="_blank" rel="noopener">おもてなしQRメーカー</a>という選択肢もあります。'
        },
    ]

    svc_map = {s["id"]: s for s in services}

    for rule in inline_rules:
        if inserted >= 2:
            break
        svc = svc_map.get(rule["service_id"])
        if not svc:
            continue

        # 記事内にトリガーワードがあるか確認
        has_trigger = any(t in html_text for t in rule["triggers"])
        # 業種・テーマにキーワードが含まれるか確認
        has_keyword = any(k in industry or k in topic for k in svc.get("keywords", []))

        if has_trigger or has_keyword:
            mention = f'<p class="service-mention">{rule["text"].format(url=html.escape(svc["url"]))}</p>'
            # 最後から3番目のh2の前に挿入（記事中盤あたり）
            h2_positions = [m.start() for m in re.finditer(r'<h2 id="section-', html_text)]
            if len(h2_positions) >= 3:
                insert_pos = h2_positions[-3]
                html_text = html_text[:insert_pos] + mention + "\n" + html_text[insert_pos:]
                inserted += 1

    # --- 2. FAQ内の「おすすめツール」回答にAIO診断を追加 ---
    aio_svc = svc_map.get("aio-shindan")
    if aio_svc and "おすすめ" in html_text and inserted < 3:
        aio_mention = f'また、AIにお店が紹介されるかを確認できる<a href="{html.escape(aio_svc["url"])}" target="_blank" rel="noopener">AIOスコア診断（無料）</a>も試してみてください。'
        # 「楽天ブックス」等の書籍紹介文の後に追加
        html_text = html_text.replace(
            "現場ですぐ使えるようになります。</p>",
            f"現場ですぐ使えるようになります。{aio_mention}</p>"
        )

    return html_text


def insert_inline_links(html_text, current_meta, all_meta):
    """記事本文中に関連記事への内部リンクを自然に挿入"""
    same_industry = [m for m in all_meta
                     if m["industry"] == current_meta["industry"]
                     and m["slug"] != current_meta["slug"]]
    same_topic = [m for m in all_meta
                  if m["topic"] == current_meta["topic"]
                  and m["slug"] != current_meta["slug"]]

    links_added = 0
    # 同業種の記事へのリンク（最大2つ）
    for m in same_industry[:2]:
        topic_escaped = html.escape(m["topic"])
        link = f'<a href="{m["slug"]}.html" class="inline-link">{html.escape(m["industry"])}の{topic_escaped}</a>'
        # まとめセクションの前に挿入
        marker = '<h2 id="section-'
        # 最後から2番目のh2の前にリンクを挿入
        positions = [i for i, c in enumerate(html_text) if html_text[i:i+len(marker)] == marker]
        if len(positions) >= 3 and links_added == 0:
            insert_pos = positions[-2]
            link_block = f'<p class="inline-related">あわせて読みたい: {link}の記事もおすすめです。</p>\n'
            html_text = html_text[:insert_pos] + link_block + html_text[insert_pos:]
            links_added += 1
            break

    return html_text


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


def extract_faq(md_text):
    """MarkdownからFAQ（Q&A）を抽出"""
    faqs = []
    lines = md_text.split("\n")
    current_q = None
    current_a_lines = []
    in_faq = False

    for line in lines:
        stripped = line.strip()
        # 「よくある質問」セクション開始
        if stripped.startswith("## ") and "よくある質問" in stripped:
            in_faq = True
            continue
        # FAQ後の次のh2で終了
        if in_faq and stripped.startswith("## "):
            if current_q and current_a_lines:
                faqs.append({"q": current_q, "a": " ".join(current_a_lines).strip()})
            break
        if not in_faq:
            continue
        if stripped in ["<!-- AFFILIATE -->", "<!-- AFFILIATE2 -->", "---"]:
            continue
        # Q行を検出
        if stripped.startswith("### ") and ("Q" in stripped or "質問" in stripped):
            if current_q and current_a_lines:
                faqs.append({"q": current_q, "a": " ".join(current_a_lines).strip()})
            current_q = re.sub(r"^###\s*(Q\d*[:：]?\s*)", "", stripped).strip()
            current_a_lines = []
        elif current_q and stripped:
            answer_line = re.sub(r"<!--\s*AFFILIATE2?\s*-->", "", stripped).strip()
            if answer_line:
                current_a_lines.append(answer_line)

    if current_q and current_a_lines:
        faqs.append({"q": current_q, "a": " ".join(current_a_lines).strip()})

    seen_questions = set()
    unique_faqs = []
    for faq in faqs:
        if faq["q"] in seen_questions:
            continue
        seen_questions.add(faq["q"])
        unique_faqs.append(faq)

    return unique_faqs


def extract_howto_steps(md_text):
    """Markdownからステップ手順を抽出（HowToスキーマ用）"""
    steps = []
    lines = md_text.split("\n")
    in_solution = False

    for line in lines:
        stripped = line.strip()
        # 解決策セクションを探す
        if stripped.startswith("## ") and ("解決" in stripped or "方法" in stripped or "ステップ" in stripped):
            in_solution = True
            continue
        if in_solution and stripped.startswith("## "):
            break
        # h3のステップ見出しを抽出
        if in_solution and stripped.startswith("### ") and ("ステップ" in stripped or "Step" in stripped.lower()):
            step_text = re.sub(r"^###\s*(ステップ\d*[:：]?\s*|Step\s*\d*[:：]?\s*)", "", stripped).strip()
            if step_text:
                steps.append(step_text)
        # 番号付きリストも抽出
        if in_solution and re.match(r"^\d+\.\s", stripped):
            step_text = re.sub(r"^\d+\.\s*", "", stripped).strip()
            if step_text and len(step_text) > 5:
                steps.append(step_text)

    # 重複除去しつつ順序保持
    seen = set()
    unique = []
    for s in steps:
        if s not in seen:
            seen.add(s)
            unique.append(s)
    return unique[:8]


def build_structured_data(meta, config, md_text=""):
    """JSON-LD構造化データを生成（Article + FAQ + HowTo）"""
    scripts = []

    # Article スキーマ
    article_data = {
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
    scripts.append(f'<script type="application/ld+json">{json.dumps(article_data, ensure_ascii=False)}</script>')

    # FAQ スキーマ
    faqs = extract_faq(md_text)
    if faqs:
        faq_data = {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": faq["q"],
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": faq["a"]
                    }
                }
                for faq in faqs
            ]
        }
        scripts.append(f'<script type="application/ld+json">{json.dumps(faq_data, ensure_ascii=False)}</script>')

    # HowTo スキーマ
    howto_steps = extract_howto_steps(md_text)
    if len(howto_steps) >= 2:
        howto_data = {
            "@context": "https://schema.org",
            "@type": "HowTo",
            "name": f'{meta.get("industry", "")}の{meta.get("topic", "")}をAIで効率化する方法',
            "description": meta["description"],
            "step": [
                {
                    "@type": "HowToStep",
                    "name": step,
                    "text": step
                }
                for step in howto_steps
            ]
        }
        scripts.append(f'<script type="application/ld+json">{json.dumps(howto_data, ensure_ascii=False)}</script>')

    return "\n".join(scripts)


def build_article(meta, md_text, template, config, all_meta, books_cache=None):
    """1記事分のHTMLを生成"""
    site_name = config["site"]["title"]
    site_description = config["site"]["description"]
    article_html = md_to_html(md_text)
    article_html = insert_affiliate(article_html, config, meta=meta, books_cache=books_cache)
    article_html = insert_saas_cards(article_html, config)
    article_html = insert_inline_links(article_html, meta, all_meta)
    article_html = insert_own_services(article_html, config, meta)

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
    topic_name = html.escape(meta.get("topic", ""))
    cta = f"""<div class="cta-box">
  <p class="cta-title">「うちも{topic_name}をどうにかしたい」と思った{ind_name}の方へ</p>
  <p>この記事で紹介した方法は、どなたでも今日から始められます。「でも一人だと不安…」という方は、かわさき楽AIサポートにご相談ください。無料ツール中心で、あなたの業務に合ったAI活用を一緒に考えます。</p>
  <a href="https://www.smilefactory-rakuai.com/" target="_blank" rel="noopener" class="cta-btn">初回無料で相談してみる</a>
</div>"""

    # 注意書き
    disclaimer = """<div class="disclaimer">
  <p>※本記事に登場する人物・店舗名は架空のものであり、実在の個人・団体とは関係ありません。事例は同業種でよくあるお悩みをもとに構成したフィクションです。効果や数値はあくまで想定であり、成果を保証するものではありません。</p>
</div>"""

    content = f"<article>\n{header_meta}\n{article_html}\n{disclaimer}\n{cta}\n{related}\n</article>"

    # パンくずリスト
    breadcrumb = f'<div class="breadcrumb"><a href="../index.html">トップ</a><span>&gt;</span><span>{html.escape(meta.get("industry", ""))}</span><span>&gt;</span><span>{html.escape(meta["title"][:30])}...</span></div>'

    # 構造化データ（FAQ含む）
    structured = build_structured_data(meta, config, md_text)

    page_title = f'{meta["title"]} | {site_name}'
    page = template.replace("{{html_title}}", html.escape(page_title))
    page = page.replace("{{site_name}}", html.escape(site_name))
    page = page.replace("{{site_description}}", html.escape(site_description))
    page = page.replace("{{meta_description}}", html.escape(meta["description"]))
    page = page.replace("{{canonical_url}}", f'{config["site"]["url"]}/articles/{meta["slug"]}.html')
    page = page.replace("{{root_path}}", "../")
    page = page.replace("{{og_type}}", "article")
    page = page.replace("{{breadcrumb}}", breadcrumb)
    page = page.replace("{{structured_data}}", structured)
    page = page.replace("{{analytics_tag}}", build_analytics_tag(config))
    page = page.replace("{{content}}", content)

    return page


def build_index(all_meta, template, config):
    """トップページ（記事一覧 + カテゴリフィルター）"""
    site_name = config["site"]["title"]
    site_description = config["site"]["description"]
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
  <h1>{html.escape(site_name)}</h1>
  <p class="hero-sub">{html.escape(site_description)}</p>
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

    page = template.replace("{{html_title}}", html.escape(site_name))
    page = page.replace("{{site_name}}", html.escape(site_name))
    page = page.replace("{{site_description}}", html.escape(site_description))
    page = page.replace("{{meta_description}}", html.escape(site_description))
    page = page.replace("{{canonical_url}}", config["site"]["url"])
    page = page.replace("{{root_path}}", "")
    page = page.replace("{{og_type}}", "website")
    page = page.replace("{{breadcrumb}}", "")
    page = page.replace("{{structured_data}}", "")
    page = page.replace("{{analytics_tag}}", build_analytics_tag(config))
    page = page.replace("{{content}}", content)

    return page


def build_privacy_page(template, config):
    """プライバシーポリシーページ"""
    site_name = config["site"]["title"]
    site_description = config["site"]["description"]
    site_url = config["site"]["url"]
    updated = datetime.now().strftime("%Y-%m-%d")

    content = f"""<article class="policy-page">
  <h1>プライバシーポリシー</h1>
  <p>本プライバシーポリシーは、「{html.escape(site_name)}」（以下、「当サイト」）における個人情報および利用者情報の取り扱いについて定めるものです。</p>

  <h2>アクセス解析ツールについて</h2>
  <p>当サイトでは、サイトの利用状況を把握し、コンテンツ改善に役立てるため、Google LLC が提供する Google Analytics を利用しています。</p>
  <p>Google Analytics は Cookie などを使用して、訪問ページ、滞在時間、利用環境などのトラフィックデータを収集します。これらのデータは匿名で収集されており、個人を特定するものではありません。</p>
  <p>Google Analytics によるデータの収集および処理の仕組みについては、Google の説明ページをご確認ください。</p>
  <p><a href="https://policies.google.com/technologies/partner-sites?hl=ja" target="_blank" rel="noopener">Google のサービスを使用するサイトやアプリから収集した情報の Google による使用</a></p>

  <h2>Cookieの利用について</h2>
  <p>当サイトでは、Google Analytics によるアクセス解析のために Cookie を使用する場合があります。Cookie は利用者のブラウザに保存される情報であり、氏名、住所、メールアドレスなど個人を直接特定する情報は含まれません。</p>
  <p>Cookie の利用を望まない場合、利用者はブラウザの設定により Cookie を無効化できます。ただし、Cookie を無効化した場合、一部の機能が正しく動作しないことがあります。</p>

  <h2>広告・アフィリエイトについて</h2>
  <p>当サイトでは、第三者配信の広告サービスおよびアフィリエイトプログラムを利用する場合があります。商品・サービスの購入や申し込みに関する最終的な判断は、リンク先の公式情報をご確認ください。</p>

  <h2>免責事項</h2>
  <p>当サイトに掲載する情報は、できる限り正確な内容となるよう努めていますが、正確性・安全性・最新性を保証するものではありません。当サイトの情報に基づいて生じた損害等について、当サイトは責任を負いかねます。</p>

  <h2>著作権について</h2>
  <p>当サイトに掲載している文章・画像等の著作物を、無断で転載・利用することを禁止します。引用する場合は、引用元を明示し、著作権法上認められた範囲で行ってください。</p>

  <h2>お問い合わせ</h2>
  <p>当サイトに関するお問い合わせは、運営元の <a href="https://www.smilefactory-rakuai.com/" target="_blank" rel="noopener">かわさき楽AIサポート</a> までお願いいたします。</p>

  <h2>改定について</h2>
  <p>当サイトは、必要に応じて本プライバシーポリシーを変更することがあります。変更後の内容は、当ページに掲載した時点で有効となります。</p>
  <p class="policy-updated">最終更新日: {updated}</p>
</article>"""

    page = template.replace("{{html_title}}", html.escape(f"プライバシーポリシー | {site_name}"))
    page = page.replace("{{site_name}}", html.escape(site_name))
    page = page.replace("{{site_description}}", html.escape(site_description))
    page = page.replace("{{meta_description}}", html.escape(f"{site_name}のプライバシーポリシーです。"))
    page = page.replace("{{canonical_url}}", f"{site_url}/privacy.html")
    page = page.replace("{{root_path}}", "")
    page = page.replace("{{og_type}}", "website")
    page = page.replace("{{breadcrumb}}", '<div class="breadcrumb"><a href="index.html">トップ</a><span>&gt;</span><span>プライバシーポリシー</span></div>')
    page = page.replace("{{structured_data}}", "")
    page = page.replace("{{analytics_tag}}", build_analytics_tag(config))
    page = page.replace("{{content}}", content)

    return page


def build_sitemap(all_meta, config):
    """sitemap.xml"""
    urls = [f"""
  <url>
    <loc>{config['site']['url']}/index.html</loc>
    <lastmod>{datetime.now().strftime('%Y-%m-%d')}</lastmod>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>"""]

    urls.append(f"""
  <url>
    <loc>{config['site']['url']}/privacy.html</loc>
    <lastmod>{datetime.now().strftime('%Y-%m-%d')}</lastmod>
    <changefreq>yearly</changefreq>
    <priority>0.3</priority>
  </url>""")

    for meta in all_meta:
        urls.append(f"""
  <url>
    <loc>{config['site']['url']}/articles/{meta['slug']}.html</loc>
    <lastmod>{meta.get('date', datetime.now().strftime('%Y-%m-%d'))}</lastmod>
    <changefreq>monthly</changefreq>
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

    # プライバシーポリシー
    privacy_html = build_privacy_page(template, config)
    with open(PUBLIC_DIR / "privacy.html", "w", encoding="utf-8") as f:
        f.write(privacy_html)

    # サイトマップ
    sitemap = build_sitemap(all_meta, config)
    with open(PUBLIC_DIR / "sitemap.xml", "w", encoding="utf-8") as f:
        f.write(sitemap)

    print(f"\nビルド完了: {built}記事 → public/")

    # sitemap ping（Google / Bing）
    ping_sitemap(config)


def ping_sitemap(config):
    """IndexNow API（Bing/Yandex等）にURL更新を通知"""
    site_url = config["site"]["url"]
    # IndexNow用キーファイルが存在すれば通知
    key_path = Path(__file__).resolve().parent.parent / "public" / "indexnow-key.txt"
    if not key_path.exists():
        # キーを生成して保存
        import hashlib
        key = hashlib.md5(site_url.encode()).hexdigest()[:32]
        key_path.write_text(key, encoding="utf-8")
        # キー認証ファイルも作成
        verify_path = Path(__file__).resolve().parent.parent / "public" / f"{key}.txt"
        verify_path.write_text(key, encoding="utf-8")
        print(f"  IndexNow キー生成: {key}")

    key = key_path.read_text(encoding="utf-8").strip()
    sitemap_url = f"{site_url}/sitemap.xml"

    try:
        data = json.dumps({
            "host": "okomari.smilefactory-rakuai.com",
            "key": key,
            "keyLocation": f"{site_url}/{key}.txt",
            "urlList": [f"{site_url}/index.html", sitemap_url]
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://api.indexnow.org/indexnow",
            data=data,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as res:
            print(f"  IndexNow ping OK ({res.status})")
    except Exception as e:
        print(f"  IndexNow ping: {e}（初回は認証待ち）")


if __name__ == "__main__":
    main()
