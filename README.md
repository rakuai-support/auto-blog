# 小さなお店のための業種別AIお困り解決帳 - 自動ブログシステム

飲食店・美容室・士業・工務店などの「困った」をAIで減らす具体策を **完全自動** で生成・公開する静的サイトシステム。

**公開URL**: https://okomari.smilefactory-rakuai.com/

## 概要

毎日2回（8:00 / 17:00）Windowsタスクスケジューラが起動し、以下を自動実行する:

1. **最新ニュース取得** - Google News RSSからAI関連ニュースを収集
2. **記事生成** - Claude CLI（claude-opus-4-7）でニュースを反映したSEO記事をMarkdown生成
3. **書籍情報取得** - 楽天ブックスAPIで記事テーマに合った書籍を検索・キャッシュ
4. **サイトビルド** - Markdown → HTML変換、目次・構造化データ・アフィリエイトカード付与
5. **デプロイ** - git push → GitHub Actions → GitHub Pages自動公開
6. **メール通知** - 成功・失敗どちらの場合もSMTPで管理者へ結果を通知

人間の介入なしで記事が増え続け、アフィリエイト収益を生む仕組み。

## 記事マトリックス

20業種 × 10テーマ = **最大200記事**（config.jsonの上限設定: 300記事）

### 対象業種（20）
飲食店 / 美容室 / 整骨院・整体院 / 歯科医院 / 不動産業 / 税理士事務所 / 司法書士事務所 / 工務店・リフォーム業 / 自動車整備業 / クリーニング店 / 学習塾 / 保育園・幼稚園 / 介護施設 / 花屋 / 写真スタジオ / 印刷会社 / 運送業 / 農業 / ペットショップ・動物病院 / 旅館・民宿

### テーマ（10）
予約管理の効率化 / 顧客対応の自動化 / SNS投稿の作成 / 売上データの分析 / スタッフ教育の効率化 / 在庫管理の改善 / 経理作業の時短 / 集客・マーケティング / 口コミ対応 / 業務マニュアル作成

## プロジェクト構成

```
auto-blog/
├── config.json                  # サイト設定・業種/テーマ一覧・アフィリエイト情報
├── .env                         # APIキー（gitignore対象）
├── scripts/
│   ├── generate_article.py      # 記事生成（Claude CLI + ニュース取得）
│   ├── fetch_books.py           # 楽天ブックスAPI書籍検索・キャッシュ
│   ├── build_site.py            # 静的サイトビルダー（Markdown→HTML）
│   ├── run_daily.bat            # 毎日の自動実行バッチ
│   ├── send_notification.ps1    # SMTPメール通知（成功/失敗）
│   ├── setup_scheduler.bat      # タスクスケジューラ登録用
│   └── task_definition.xml      # タスクスケジューラ定義（8:00 / 17:00）
├── templates/
│   └── base.html                # HTMLテンプレート（OGP・構造化データ付き）
├── content/
│   ├── articles/                # 記事データ（.md + .json メタデータ）
│   ├── books_cache.json         # 楽天API書籍キャッシュ
│   └── history.json             # 生成済みトピック管理
├── public/                      # ビルド出力（GitHub Pagesで公開）
│   ├── index.html               # トップページ（カテゴリフィルター付き）
│   ├── articles/                # 各記事HTML
│   ├── style.css                # サイトCSS
│   ├── robots.txt               # クローラー設定
│   ├── sitemap.xml              # サイトマップ（changefreq付き）
│   ├── ogp.png                  # OGP共通画像（1200x630）
│   └── googlea0af38cf627c9297.html  # Search Console認証
├── .github/workflows/
│   └── deploy.yml               # GitHub Actions デプロイ設定
└── logs/                        # 実行ログ（gitignore対象）
```

## セットアップ

### 前提条件

- Windows 11
- Python 3.x（`py` コマンドで実行可能）
- Claude CLI（`claude.cmd`）インストール済み
- Gitリポジトリ初期化済み + GitHubリモート設定済み

### 1. 環境変数の設定

`.env` ファイルをプロジェクトルートに作成:

```
RAKUTEN_APP_ID=（楽天APIアプリID）
RAKUTEN_ACCESS_KEY=（楽天APIアクセスキー）
RAKUTEN_AFFILIATE_ID=（楽天アフィリエイトID）
```

楽天API新ポータル（https://webservice.rakuten.co.jp/）でアプリ登録が必要。
`Referer` ヘッダーに登録ドメイン（`https://okomari.smilefactory-rakuai.com/`）を設定。

メール通知を使う場合は、同じ `.env` にSMTP設定を追加する:

```
NOTIFY_EMAIL_TO=admin@smilefactory-rakuai.com
NOTIFY_EMAIL_FROM=admin@smilefactory-rakuai.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=admin@smilefactory-rakuai.com
SMTP_PASS=（SMTPパスワードまたはアプリパスワード）
SMTP_ENABLE_SSL=true
```

`SMTP_PASS` はGitに入れず、ローカルの `.env` のみに保存する。
Gmail / Google Workspace の場合、`SMTP_PASS` には通常のGoogleログインパスワードではなく、Googleアカウントで発行したアプリパスワードを設定する。

### 2. GitHub Pages の有効化

リポジトリ Settings → Pages → Source: GitHub Actions

### 3. タスクスケジューラの登録

管理者権限のコマンドプロンプトで:

```cmd
scripts\setup_scheduler.bat
```

毎日8:00と17:00に `scripts\run_daily.bat` が実行される。

### 4. メール通知

`scripts\run_daily.bat` は各処理の終了コードを確認し、成功・失敗どちらの場合も `scripts\send_notification.ps1` からSMTPメールを送信する。

通常運用では、8:00と17:00の自動実行ごとに成功通知が届くため、1日2通届く。失敗時は失敗箇所をメッセージに含めて通知する。

通知件名の例:

```
[auto-blog] SUCCESS daily run 2026-05-11 08:05:00
[auto-blog] FAILURE daily run 2026-05-11 17:03:00
```

失敗通知の主なメッセージ:

- `ERROR: generate`
- `ERROR: fetch_books`
- `ERROR: build_site`
- `ERROR: git add`
- `ERROR: git commit`
- `ERROR: git push`

通知メールには、リポジトリパス、ブランチ、コミット、`logs\daily.log` の末尾が含まれる。SMTP設定が未設定、または通知送信だけが失敗した場合でも、記事生成・ビルド・pushの本処理は通知エラーで停止しない。

## 各スクリプトの詳細

### generate_article.py

- `pick_next_topic()`: 業種バランスを考慮して次のトピックを選択（記事数が少ない業種を優先）
- `fetch_news()`: Google News RSSから業種×トピック関連のAIニュースを最大5件取得
- `call_claude()`: Claude CLI（claude-opus-4-7）を呼び出し、ニュースを反映したSEO記事を生成
- `pick_title()`: 8パターンのタイトルテンプレートからランダム選択
- 出力: `content/articles/{slug}.md` + `{slug}.json`

### fetch_books.py

- 楽天ブックスAPI（BooksBook/Search）でタイトル検索
- 業種×トピックから優先度付きの検索クエリを生成（具体→汎用のフォールバック）
- 2秒間隔でリクエスト（レート制限対策）
- 結果を `content/books_cache.json` にキャッシュ

### build_site.py

- 簡易Markdownパーサー（外部ライブラリ不要）
- 目次自動生成（h2見出しから）
- アフィリエイトカード挿入（書籍画像 + 文脈紹介文）
- 関連記事（同業種/同テーマから最大4件）
- JSON-LD構造化データ
- サイトマップ自動生成

### run_daily.bat

- `generate_article.py` → `fetch_books.py` → `build_site.py` → `git add` → `git commit` → `git push` の順に実行
- `GIT_TERMINAL_PROMPT=0` を設定し、GitHub認証で対話入力待ちになって止まることを防止
- 各ステップの失敗を `logs\daily.log` に記録し、失敗通知を送信
- 差分がない場合は `NO CHANGES` として成功通知を送信

### send_notification.ps1

- `.env` からSMTP設定を読み込み、成功・失敗通知を送信
- `NOTIFY_EMAIL_TO` はカンマまたはセミコロン区切りで複数宛先に対応
- SMTP設定が未設定の場合は通知をスキップし、ログに理由を出力
- 通知失敗時も終了コードは0にして、本処理の成否を通知処理で上書きしない

## 収益化の仕組み

| 収益源 | 状態 | 内容 |
|--------|------|------|
| 楽天アフィリエイト | 稼働中 | 記事内の書籍紹介カード（楽天ブックスAPI連携） |
| 楽天トラベル | 稼働中 | 旅館・民宿記事向け |
| Google AdSense | 準備中 | 30記事到達後に申請予定 |
| CTA（自社サービス） | 稼働中 | 各記事下部に「かわさき楽AIサポート」への無料相談リンク |

## SEO対策

- [x] Google Search Console 登録済み
- [x] sitemap.xml 自動生成・送信
- [x] robots.txt 設定
- [x] JSON-LD 構造化データ（Article スキーマ）
- [x] OGP / Twitter Card メタタグ（og:image / twitter:image 設定済み）
- [x] canonical URL
- [x] パンくずリスト
- [x] レスポンシブ対応
- [x] 目次（内部リンク）
- [x] 最新ニュースを反映した時事性のある記事内容

## 技術的な特徴

- **外部ライブラリ依存ゼロ**: Python標準ライブラリのみで動作（urllib, json, xml, hashlib等）
- **フレームワーク不要**: 静的HTML生成のため、ビルドツールやJSフレームワーク不要
- **増分生成**: 生成済みトピックを `history.json` で管理し、重複を防止
- **書籍キャッシュ**: API呼び出しを最小限に抑え、一度取得した書籍情報を再利用
- **業種バランス**: 同じ業種に偏らないよう、記事数が少ない業種から優先的に生成

## 運営

**株式会社スマイルファクトリー**（かわさき楽AIサポート）
https://www.smilefactory-rakuai.com/
