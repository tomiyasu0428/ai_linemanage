# AI予定管理秘書アプリ

LINEを通じてGoogleカレンダーを操作できるAI秘書アプリケーションです。自然言語でスケジュール管理ができ、グループでの日程調整も可能です。

## 機能

### MVP機能
- 個人予定の自然言語による登録・確認・変更・削除 (F-1)
- Googleアカウント認証 (OAuth 2.0) (F-2)
- グループ空き時間検索（基本ロジック）(F-3)
- 候補日提示と簡易投票機能 (LINE Flex Message) (F-4)
- 投票結果に基づくカレンダー自動登録 (F-5)

## 技術スタック

- **バックエンド**: FastAPI (Python)
- **AI / NLP**: Google Gemini API + LangChain
- **外部API**: LINE Messaging API, Google Calendar API
- **データベース**: インメモリDB (本番環境ではFirestore推奨)

## セットアップ手順

### 1. 環境構築

```bash
# リポジトリのクローン
git clone https://github.com/yourusername/ai-scheduler.git
cd ai-scheduler

# 仮想環境の作成と有効化
python -m venv venv
source venv/bin/activate  # Mac/Linux
# venv\Scripts\activate  # Windows

# 依存関係のインストール
pip install poetry
poetry install
```

### 2. 環境変数の設定

`.env.example`ファイルを`.env`にコピーし、必要な環境変数を設定します：

```
LINE_CHANNEL_ACCESS_TOKEN="your_line_channel_access_token"
LINE_CHANNEL_SECRET="your_line_channel_secret"
GOOGLE_CLIENT_ID="your_google_client_id"
GOOGLE_CLIENT_SECRET="your_google_client_secret"
GOOGLE_PROJECT_ID="your_google_project_id"
GEMINI_API_KEY="your_gemini_api_key"
SECRET_KEY="your_secret_key"
APP_BASE_URL="https://your-app-url.com"
```

### 3. アプリケーションの起動

```bash
# 開発サーバーの起動
python run.py
```

### 4. LINE Webhook URLの設定

1. ngrokなどを使用してローカルサーバーを公開
   ```bash
   ngrok http 8000
   ```

2. LINE Developersコンソールで、Webhook URLを設定
   - URL: `https://your-ngrok-url.ngrok.io/line/callback`
   - Webhookの利用: ON

## 使用方法

### 個人予定管理

LINEで以下のようなメッセージを送信することで、予定の管理ができます：

- 予定登録: 「明日の10時から12時まで会議」
- 予定確認: 「今日の予定を教えて」
- 予定変更: 「明日の会議を13時から15時に変更して」
- 予定削除: 「明日の会議をキャンセル」

### グループ日程調整

LINEグループで以下のコマンドを使用して、グループでの日程調整ができます：

1. 「日程調整 イベント名」と入力
2. ボットが候補日時を提示
3. メンバーが投票
4. 投票締め切り後、最も多く投票された日時が全員のカレンダーに自動登録

## プロジェクト構造

```
AI予定管理/
├── app/
│   ├── main.py              # FastAPIアプリケーションのエントリーポイント
│   ├── routers/
│   │   ├── line.py          # LINE Webhookハンドラー
│   │   └── google_auth.py   # Google OAuth認証ハンドラー
│   └── services/
│       ├── ai_processor.py  # 自然言語処理サービス
│       ├── database.py      # データベース操作サービス
│       ├── google_calendar.py # Googleカレンダー連携サービス
│       └── group_scheduler.py # グループ日程調整サービス
├── tests/
│   └── test_line_webhook.py # LINE Webhookテスト
├── .env                     # 環境変数（非公開）
├── .env.example             # 環境変数テンプレート
├── .gitignore               # Gitの除外ファイル設定
├── pyproject.toml           # Poetryの依存関係定義
└── run.py                   # アプリケーション起動スクリプト
```

## 将来の拡張予定

- 音声入力対応 (F-8)
- PDFからの予定読み取り (F-9)
- カスタムリマインド機能 (F-7)
- Slack / Teams 連携プラグイン (F-10)
- 管理ダッシュボード (F-11)
- 未回答者へのリマインド強化 (F-6)
