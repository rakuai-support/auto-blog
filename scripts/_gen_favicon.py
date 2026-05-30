# 困AI favicon を生成・設置する一回限りのスクリプト。
# ・public/favicon.ico（青地＋白「困AI」）をルートに → 全ページが自動取得
# ・base.html / index.html / privacy.html に SVGデータURI favicon リンクを追加（genai方式・くっきり）
import os, re
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # auto-blog/
PUB = os.path.join(ROOT, "public")
BLUE = (53, 160, 217, 255)  # #35a0d9（サイトのブランド色）

# --- favicon.ico 生成 ---
def make_ico():
    S = 256
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, S - 1, S - 1], radius=int(S * 0.18), fill=BLUE)
    # 日本語太字フォント（Yu Gothic Bold）
    font_path = "C:/Windows/Fonts/YuGothB.ttc"
    if not os.path.exists(font_path):
        font_path = "C:/Windows/Fonts/meiryob.ttc"
    text = "困AI"
    # 幅に収まるフォントサイズを探索
    size = int(S * 0.5)
    while size > 10:
        font = ImageFont.truetype(font_path, size)
        bb = d.textbbox((0, 0), text, font=font)
        w, h = bb[2] - bb[0], bb[3] - bb[1]
        if w <= S * 0.84 and h <= S * 0.7:
            break
        size -= 4
    bb = d.textbbox((0, 0), text, font=font)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    x = (S - w) / 2 - bb[0]
    y = (S - h) / 2 - bb[1]
    d.text((x, y), text, font=font, fill=(255, 255, 255, 255))
    img.save(os.path.join(PUB, "favicon.ico"), sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128)])
    # PWA/SNS用に png も置いておく（任意）
    img.resize((512, 512), Image.LANCZOS).save(os.path.join(PUB, "icon-512.png"))
    img.resize((192, 192), Image.LANCZOS).save(os.path.join(PUB, "icon-192.png"))
    img.resize((180, 180), Image.LANCZOS).save(os.path.join(PUB, "apple-touch-icon.png"))
    print("generated favicon.ico / icon-192 / icon-512 / apple-touch-icon")

# --- HTML に favicon リンク挿入 ---
SVG = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'"
       "%3E%3Crect width='32' height='32' rx='4' fill='%2335a0d9'/%3E%3Ctext x='50%25' y='50%25' "
       "dominant-baseline='central' text-anchor='middle' font-family='sans-serif' font-size='11' "
       "font-weight='900' fill='white'%3E困AI%3C/text%3E%3C/svg%3E")
LINKS_HTML = (
    f'  <link rel="icon" type="image/svg+xml" href="{SVG}">\n'
    f'  <link rel="icon" type="image/x-icon" href="/favicon.ico" sizes="any">\n'
    f'  <link rel="apple-touch-icon" href="/apple-touch-icon.png">\n'
    f'  <meta name="theme-color" content="#35a0d9">\n'
)

def insert_links(path):
    with open(path, encoding="utf-8") as f:
        html = f.read()
    if "image/svg+xml" in html and "困AI" in html:
        return "skip(既設)"
    if "</head>" not in html:
        return "skip(headなし)"
    html = html.replace("</head>", LINKS_HTML + "</head>", 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return "ok"

# base.html はテンプレ（{{root_path}}使用）だが SVG/絶対パスなので問題なし
def insert_base():
    p = os.path.join(ROOT, "templates", "base.html")
    with open(p, encoding="utf-8") as f:
        html = f.read()
    if "image/svg+xml" in html:
        return "skip(既設)"
    html = html.replace("</head>", LINKS_HTML + "</head>", 1)
    with open(p, "w", encoding="utf-8") as f:
        f.write(html)
    return "ok"

make_ico()
print("base.html:", insert_base())
for name in ["index.html", "privacy.html"]:
    p = os.path.join(PUB, name)
    if os.path.exists(p):
        print(name, ":", insert_links(p))
