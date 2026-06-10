"""X(旧Twitter)自動投稿モジュール（お困り解決帳版）

genai-gakusyu / hourei-search と同方式（X API v2 + OAuth 1.0a）。
run_daily.bat の末尾から呼ばれ、1日1本だけ投稿する。

工夫している点:
- 1日1本ガード: content/x_state.json の last_posted_date で当日二重投稿を防ぐ
  （8:00 / 17:00 の2回実行されても投稿は1本）
- GitHub Pages の反映遅延対策: URLが実際に200を返す最新の未投稿記事を選ぶ。
  push直後の記事はまだ404なので、自然に「前回生成分」が投稿される
- 画像は添付しない: 記事個別画像が無いため、OGPリンクカードを出す方がクリック面積が大きい

必要な環境変数（auto-blog/.env に記載）:
  X_API_KEY / X_API_SECRET / X_ACCESS_TOKEN / X_ACCESS_TOKEN_SECRET

使い方:
  py scripts/x_poster.py verify       認証確認（投稿しない）
  py scripts/x_poster.py post-daily   1日1本の自動投稿（run_daily.batが呼ぶ）
  py scripts/x_poster.py "テスト文"    単発テスト投稿
"""

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import subprocess
import sys
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

import requests
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SITE = "https://okomari.smilefactory-rakuai.com"
ARTICLES_DIR = BASE_DIR / "content" / "articles"
STATE_PATH = BASE_DIR / "content" / "x_state.json"
JST = timezone(timedelta(hours=9))

TWEET_URL = "https://api.twitter.com/2/tweets"


def _credentials():
    keys = ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET")
    values = [os.environ.get(k, "").strip() for k in keys]
    if not all(values):
        missing = [k for k, v in zip(keys, values) if not v]
        raise RuntimeError(f"X APIキー未設定: {', '.join(missing)} を .env に追加してください")
    return values


def _pct(s: str) -> str:
    return quote(str(s), safe="-._~")


def _oauth1_header(method: str, url: str) -> str:
    api_key, api_secret, access_token, token_secret = _credentials()
    oauth = {
        "oauth_consumer_key": api_key,
        "oauth_nonce": secrets.token_hex(16),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": access_token,
        "oauth_version": "1.0",
    }
    param_str = "&".join(f"{_pct(k)}={_pct(v)}" for k, v in sorted(oauth.items()))
    base = "&".join([method.upper(), _pct(url), _pct(param_str)])
    signing_key = f"{_pct(api_secret)}&{_pct(token_secret)}".encode()
    digest = hmac.new(signing_key, base.encode(), hashlib.sha1).digest()
    oauth["oauth_signature"] = base64.b64encode(digest).decode()
    header = ", ".join(f'{_pct(k)}="{_pct(v)}"' for k, v in sorted(oauth.items()))
    return f"OAuth {header}"


def post_tweet(text: str) -> str:
    res = requests.post(
        TWEET_URL,
        headers={
            "Authorization": _oauth1_header("POST", TWEET_URL),
            "Content-Type": "application/json",
        },
        data=json.dumps({"text": text}, ensure_ascii=False).encode("utf-8"),
        timeout=60,
    )
    if res.status_code >= 300:
        raise RuntimeError(f"tweet失敗 {res.status_code}: {res.text[:300]}")
    return res.json()["data"]["id"]


def verify_credentials() -> dict:
    url = "https://api.twitter.com/2/users/me"
    res = requests.get(url, headers={"Authorization": _oauth1_header("GET", url)}, timeout=30)
    if res.status_code >= 300:
        raise RuntimeError(f"認証失敗 {res.status_code}: {res.text[:300]}")
    return res.json()["data"]


def _tweet_weight(text: str, url: str = None) -> int:
    if url:
        text = text.replace(url, "")
    w = sum(2 if unicodedata.east_asian_width(c) in "WFA" else 1 for c in text)
    return w + (23 if url else 0)


def _hashtags(meta: dict) -> str:
    """業種からタグを組み立てる（中黒・スラッシュはタグを分断するため分割）"""
    parts = []
    for piece in re.split(r"[・/／\s]+", (meta.get("industry") or "").strip()):
        if piece and len(piece) <= 8:
            parts.append(f"#{piece}")
        if len(parts) >= 2:
            break
    parts += ["#AI活用", "#業務効率化", "#中小企業"]
    seen = []
    for p in parts:
        if p not in seen:
            seen.append(p)
    return " ".join(seen[:5])


def write_hook(meta: dict, body_md: str) -> str:
    """投稿フック文をClaude CLIで生成。失敗時は空文字（定型文にフォールバック）"""
    system = ("あなたは中小事業者向けAI活用メディアのSNS担当です。"
              "指定されたフック文だけを出力してください。前置き・説明・引用符は不要です。")
    prompt = f"""X(Twitter)投稿の冒頭に置くフック文を1つ作ってください。

記事タイトル: {meta['title']}
業種: {meta.get('industry', '')} / テーマ: {meta.get('topic', '')}
記事の説明: {meta.get('description', '')}
記事本文の冒頭: {body_md[:500]}

最重要ルール:
- 記事の中身から「具体的なネタ」を1つ拾って必ず入れること。
  具体的なネタ = 削減時間などの数字、具体的な作業名、あるあるな困りごとの場面 など
- 中身に触れない一般論だけのフック（「業務効率化しませんか」だけ等）は禁止

良い例:
- 「口コミ返信に毎晩30分。下書きはAIに任せて、最後のひと言だけ自分で書く方法です」
- 「『予約の電話でランチの手が止まる』を無料ツールでなくした実例です」

条件:
- 読者は{meta.get('industry', '小さなお店')}の店主・事業主。その人に話しかける文体で
- 1〜2文、合計全角55字以内
- 絵文字は0〜1個まで。ハッシュタグ・URL・記事タイトルの言い換え反復は入れない
- 誇大表現（絶対儲かる、必ず削減できる等）は禁止

フック文のみを出力:"""
    claude_cmd = "claude.cmd" if sys.platform == "win32" else "claude"
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)
    try:
        result = subprocess.run(
            [claude_cmd, "-p", "--system-prompt", system, "--model", "claude-opus-4-7"],
            input=prompt, capture_output=True, text=True, encoding="utf-8",
            timeout=600, shell=(sys.platform == "win32"), env=env,
        )
        if result.returncode != 0:
            print(f"[WARN] フック生成失敗（定型文を使用）: {result.stderr[:200]}")
            return ""
        hook = result.stdout.strip().splitlines()[0].strip()
        return hook if 0 < len(hook) <= 70 else ""
    except Exception as e:
        print(f"[WARN] フック生成失敗（定型文を使用）: {e}")
        return ""


def compose_post(meta: dict, hook: str = None) -> str:
    title = meta["title"]
    url = f"{SITE}/articles/{meta['slug']}.html"
    tags = _hashtags(meta)
    hook = (hook or "").strip().replace("\n", " ")
    if hook:
        text = f"{title}\n\n{hook}\n{url}\n\n{tags}"
        if _tweet_weight(text, url) <= 280:
            return text
    return f"{title}\n\nAIでの解決手順をプロンプト例つきでまとめました。\n{url}\n\n{tags}"


def _load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {"last_posted_date": "", "posted_slugs": []}


def post_daily() -> int:
    """1日1本だけ、URLが公開済みの最新未投稿記事を投稿する"""
    state = _load_state()
    today = datetime.now(JST).strftime("%Y-%m-%d")
    if state.get("last_posted_date") == today:
        print(f"X投稿スキップ: 本日分は投稿済み（{today}）")
        return 0

    posted = set(state.get("posted_slugs", []))
    metas = []
    for p in ARTICLES_DIR.glob("*.json"):
        try:
            m = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if m.get("slug") and m["slug"] not in posted:
            metas.append(m)
    # 新しい順（同日内は順不同で可）
    metas.sort(key=lambda m: m.get("date", ""), reverse=True)

    for meta in metas[:5]:  # 念のため先頭5件まで生存確認を試す
        url = f"{SITE}/articles/{meta['slug']}.html"
        try:
            if requests.get(url, timeout=15).status_code != 200:
                print(f"未公開のためスキップ: {url}")
                continue
        except requests.RequestException:
            continue
        md_path = ARTICLES_DIR / f"{meta['slug']}.md"
        body_md = md_path.read_text(encoding="utf-8") if md_path.exists() else ""
        hook = write_hook(meta, body_md)
        text = compose_post(meta, hook)
        tweet_id = post_tweet(text)
        print(f"X投稿成功: {meta['title'][:40]} https://x.com/i/status/{tweet_id}")
        state["last_posted_date"] = today
        state.setdefault("posted_slugs", []).append(meta["slug"])
        STATE_PATH.write_text(
            json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return 0

    print("X投稿対象なし（公開済みの未投稿記事が見つからない）")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    if sys.argv[1] == "verify":
        me = verify_credentials()
        print(f"認証OK: @{me.get('username')}（{me.get('name')}）として投稿できます")
        sys.exit(0)
    if sys.argv[1] == "post-daily":
        sys.exit(post_daily())
    print(f"投稿成功: https://x.com/i/status/{post_tweet(sys.argv[1])}")
