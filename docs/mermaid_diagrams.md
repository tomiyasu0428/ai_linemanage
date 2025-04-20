# AI予定管理アプリのファイル構造と処理フロー

## ファイル構造図

```mermaid
graph TD
    Root["AI予定管理/"] --> App["app/"]
    Root --> Tests["tests/"]
    Root --> Config[".env, .env.example, .gitignore"]
    Root --> PyProject["pyproject.toml"]
    Root --> README["README.md"]
    Root --> RunPy["run.py"]
    
    App --> Main["main.py"]
    App --> Routers["routers/"]
    App --> Services["services/"]
    App --> Utils["utils/"]
    
    Routers --> LineRouter["line.py"]
    Routers --> GoogleAuthRouter["google_auth.py"]
    
    Services --> AIProcessor["ai_processor.py<br>(LangChain Agent)"]
    Services --> Database["database.py"]
    Services --> GoogleCalendar["google_calendar.py"]
    Services --> GroupScheduler["group_scheduler.py"]
    
    Tests --> TestLineWebhook["test_line_webhook.py"]
    
    style Root fill:#f9f,stroke:#333,stroke-width:2px
    style App fill:#bbf,stroke:#333,stroke-width:1px
    style Routers fill:#ddf,stroke:#333,stroke-width:1px
    style Services fill:#ddf,stroke:#333,stroke-width:1px
    style Tests fill:#bbf,stroke:#333,stroke-width:1px
    style AIProcessor fill:#ffd700,stroke:#333,stroke-width:2px
```

## 処理フロー図

### 1. 個人予定管理の処理フロー（LangChain AIエージェント使用）

```mermaid
sequenceDiagram
    participant User as ユーザー
    participant LINE as LINE Bot
    participant Server as FastAPIサーバー
    participant Agent as LangChain AIエージェント
    participant Tools as ツール群
    participant Google as Googleカレンダー
    
    User->>LINE: メッセージ送信<br>「明日の10時から会議」
    LINE->>Server: Webhookリクエスト
    Server->>Server: 署名検証
    
    alt ユーザー未認証
        Server->>User: 認証リンク送信
        User->>Google: OAuth認証
        Google-->>Server: 認証コード
        Server->>Google: トークン取得
        Google-->>Server: アクセストークン
        Server->>Server: トークン保存
    end
    
    Server->>Agent: メッセージ解析リクエスト
    
    Agent->>Agent: 意図理解
    
    alt 日時解析が必要
        Agent->>Tools: parse_datetime呼び出し
        Tools-->>Agent: ISO形式の日時
    end
    
    alt 予定作成
        Agent->>Tools: create_calendar_event呼び出し
        Tools->>Google: カレンダーイベント作成
        Google-->>Tools: イベントID
        Tools-->>Agent: 作成結果
        Agent-->>Server: 「予定を登録しました」
        Server->>User: 「予定を登録しました」
    else 予定確認
        Agent->>Tools: read_calendar_events呼び出し
        Tools->>Google: カレンダーイベント取得
        Google-->>Tools: イベントリスト
        Tools-->>Agent: イベントリスト
        Agent-->>Server: 「以下の予定があります...」
        Server->>User: 「以下の予定があります...」
    else 予定更新
        Agent->>Tools: update_calendar_event呼び出し
        Tools->>Google: カレンダーイベント更新
        Google-->>Tools: 更新結果
        Tools-->>Agent: 更新結果
        Agent-->>Server: 「予定を更新しました」
        Server->>User: 「予定を更新しました」
    else 予定削除
        Agent->>Tools: delete_calendar_event呼び出し
        Tools->>Google: カレンダーイベント削除
        Google-->>Tools: 削除結果
        Tools-->>Agent: 削除結果
        Agent-->>Server: 「予定を削除しました」
        Server->>User: 「予定を削除しました」
    end
```

### 2. グループ日程調整の処理フロー

```mermaid
sequenceDiagram
    participant Users as グループメンバー
    participant LINE as LINE Bot
    participant Server as FastAPIサーバー
    participant Agent as LangChain AIエージェント
    participant Google as Googleカレンダー
    
    Users->>LINE: 「日程調整 プロジェクト会議」
    LINE->>Server: Webhookリクエスト
    Server->>Server: グループメッセージ処理
    Server->>Agent: 意図解析
    Agent-->>Server: 「グループ日程調整」と判定
    
    alt メンバー未認証
        Server->>Users: 認証リンク送信
        Users->>Google: OAuth認証
        Google-->>Server: 認証コード
        Server->>Google: トークン取得
        Google-->>Server: アクセストークン
        Server->>Server: トークン保存
    end
    
    Server->>Google: 全メンバーの予定取得
    Google-->>Server: 各メンバーの予定
    Server->>Server: 空き時間検索
    Server->>LINE: 候補日時の投票メッセージ<br>(Flex Message)
    LINE->>Users: 投票UI表示
    
    loop 投票プロセス
        Users->>LINE: 候補日時に投票
        LINE->>Server: Postbackイベント
        Server->>Server: 投票を記録
    end
    
    Users->>LINE: 「投票締め切り」
    LINE->>Server: Postbackイベント
    Server->>Server: 投票集計
    Server->>Google: 全メンバーのカレンダーに<br>イベント登録
    Google-->>Server: 登録結果
    Server->>LINE: 確定メッセージ
    LINE->>Users: 「日程が確定しました」
```

### 3. LangChain AIエージェントのアーキテクチャ

```mermaid
graph TD
    UserInput["ユーザー入力<br>（自然言語）"] --> Agent["LangChain AIエージェント<br>(app/services/ai_processor.py)"]
    
    Agent --> Memory["会話履歴メモリ<br>(ConversationBufferMemory)"]
    Memory --> Agent
    
    Agent --> Tools["ツール群"]
    
    Tools --> CreateEvent["create_calendar_event<br>予定作成ツール"]
    Tools --> ReadEvents["read_calendar_events<br>予定確認ツール"]
    Tools --> UpdateEvent["update_calendar_event<br>予定更新ツール"]
    Tools --> DeleteEvent["delete_calendar_event<br>予定削除ツール"]
    Tools --> ParseDateTime["parse_datetime<br>日時解析ツール"]
    
    CreateEvent --> GoogleCalendar["Googleカレンダー<br>API"]
    ReadEvents --> GoogleCalendar
    UpdateEvent --> GoogleCalendar
    DeleteEvent --> GoogleCalendar
    
    Agent --> Response["応答<br>（自然言語）"]
    
    style Agent fill:#ffd700,stroke:#333,stroke-width:2px
    style Tools fill:#9f6,stroke:#333,stroke-width:2px
    style Memory fill:#f96,stroke:#333,stroke-width:2px
    style GoogleCalendar fill:#96f,stroke:#333,stroke-width:2px
```

## LangChain AIエージェントの説明

### 1. AIエージェントの概要

LangChainを使用したAIエージェントは、ユーザーの自然言語入力を理解し、適切なツールを選択・実行して予定管理タスクを完了させる中心的なコンポーネントです。このエージェントは以下の特徴を持ちます：

- **自然言語理解**: ユーザーの入力から意図（予定の作成/確認/更新/削除）を抽出
- **ツール選択**: 適切なツールを選んで実行する能力
- **会話履歴**: 過去のやり取りを記憶し、文脈を理解
- **構造化出力**: 自然言語入力から構造化データへの変換

### 2. 主要コンポーネント

1. **LLM (Large Language Model)**
   - Google Gemini Pro APIを使用
   - 自然言語理解と生成を担当

2. **ツール群**
   - `create_calendar_event`: 予定作成ツール
   - `read_calendar_events`: 予定確認ツール
   - `update_calendar_event`: 予定更新ツール
   - `delete_calendar_event`: 予定削除ツール
   - `parse_datetime`: 自然言語の日時表現をISO形式に変換するツール

3. **プロンプトテンプレート**
   - エージェントの役割と使用可能なツールを定義
   - 日本語での応答を指示

4. **会話メモリ**
   - `ConversationBufferMemory`を使用
   - 過去の会話履歴を保持し、文脈理解を可能に

### 3. 処理フロー

1. ユーザーがLINE Botにメッセージを送信
2. FastAPIサーバーがWebhookを受け取り、AIエージェントに処理を依頼
3. AIエージェントがメッセージを解析し、意図を理解
4. 必要に応じて日時解析ツールを使用
5. 意図に基づいて適切なカレンダーツールを選択・実行
6. 実行結果を自然言語で整形し、ユーザーに返信

### 4. 技術的詳細

- **AgentExecutor**: ツール選択と実行を管理
- **StructuredTool**: 型付きの関数をツールとして定義
- **ChatPromptTemplate**: エージェントの指示を定義
- **ConversationBufferMemory**: 会話履歴の管理

### 5. 利点

- **柔軟な自然言語理解**: 様々な表現方法に対応
- **文脈理解**: 会話の流れを理解し、適切に応答
- **拡張性**: 新しいツールの追加が容易
- **モジュール性**: 各コンポーネントが明確に分離され、保守性が高い

LangChainを使用したAIエージェントの導入により、ユーザーはより自然な会話形式でカレンダー操作が可能になり、アプリケーションの使いやすさと機能性が大幅に向上しました。
