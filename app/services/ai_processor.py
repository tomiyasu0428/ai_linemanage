import os
import json
import datetime
import google.generativeai as genai

from app.services.google_calendar import (
    register_calendar_event,
    get_calendar_events,
    delete_calendar_event,
    update_calendar_event
)

gemini_api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=gemini_api_key)

CALENDAR_PROMPT = """
あなたは日本語のテキストから予定情報を抽出するAIアシスタントです。
以下のユーザーの入力から予定に関する情報を抽出し、JSONフォーマットで出力してください。

ユーザー入力: {user_message}

以下の形式でJSON出力してください:
```
{
  "action": "create/read/update/delete", // 予定の作成/読み取り/更新/削除
  "datetime_start": "YYYY-MM-DDTHH:MM:SS+09:00", // 日本時間のISO形式
  "datetime_end": "YYYY-MM-DDTHH:MM:SS+09:00", // 日本時間のISO形式
  "title": "予定のタイトル",
  "location": "場所",
  "description": "詳細説明"
}
```

特定の時間が指定されていない場合は、以下のデフォルト値を使用:
- 「今日」: 現在の日付
- 「明日」: 現在の日付+1日
- 時間が指定されていない場合: 
  * 作成/更新の場合は、開始時間=現在時刻から1時間後の正時、終了時間=開始時間+1時間
  * 読み取り/削除の場合は、開始時間=当日0時、終了時間=当日23:59

読み取り操作の場合:
- 「今日の予定」「今日何がある？」などの場合は、当日の全予定を返す
- 「明日の予定」などの場合は、指定された日の全予定を返す
- 「今週の予定」の場合は、今週の全予定を返す

更新/削除操作の場合:
- まず特定の予定を特定できる情報（タイトル、日時など）が必要
- 「明日の会議をキャンセル」のような場合、タイトルに「会議」を含む明日の予定を探す

出力は必ずJSON形式のみにしてください。説明文は不要です。
"""

def process_user_message(user_id: str, user_message: str) -> str:
    """ユーザーのメッセージを処理し、適切な応答を返す"""
    try:
        formatted_prompt = CALENDAR_PROMPT.format(user_message=user_message)
        
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(formatted_prompt)
        
        response_text = response.text
        start_idx = response_text.find('{')
        end_idx = response_text.rfind('}') + 1
        if start_idx >= 0 and end_idx > start_idx:
            json_str = response_text[start_idx:end_idx]
            parsed_data = json.loads(json_str)
        else:
            return "予定情報の抽出に失敗しました。もう少し詳しく教えていただけますか？"
        
        action = parsed_data.get("action", "")
        
        if action == "create":
            event_id = register_calendar_event(
                user_id=user_id,
                start_time=parsed_data.get("datetime_start"),
                end_time=parsed_data.get("datetime_end"),
                title=parsed_data.get("title"),
                location=parsed_data.get("location", ""),
                description=parsed_data.get("description", "")
            )
            return f"予定「{parsed_data.get('title')}」を登録しました。"
            
        elif action == "read":
            events = get_calendar_events(
                user_id=user_id,
                start_time=parsed_data.get("datetime_start"),
                end_time=parsed_data.get("datetime_end")
            )
            
            if not events:
                return "指定された期間の予定はありません。"
            
            events_text = "以下の予定が見つかりました：\n"
            for i, event in enumerate(events, 1):
                events_text += f"{i}. {event['summary']} ({event['start']['dateTime']}〜{event['end']['dateTime']})\n"
            return events_text
            
        elif action == "update":
            success = update_calendar_event(
                user_id=user_id,
                event_query={
                    "title": parsed_data.get("title"),
                    "start_time": parsed_data.get("datetime_start")
                },
                updated_data={
                    "title": parsed_data.get("title"),
                    "start_time": parsed_data.get("datetime_start"),
                    "end_time": parsed_data.get("datetime_end"),
                    "location": parsed_data.get("location", ""),
                    "description": parsed_data.get("description", "")
                }
            )
            
            if success:
                return f"予定「{parsed_data.get('title')}」を更新しました。"
            else:
                return "予定の更新に失敗しました。該当する予定が見つからないか、複数の候補があります。"
            
        elif action == "delete":
            success = delete_calendar_event(
                user_id=user_id,
                event_query={
                    "title": parsed_data.get("title"),
                    "start_time": parsed_data.get("datetime_start")
                }
            )
            
            if success:
                return f"予定「{parsed_data.get('title')}」を削除しました。"
            else:
                return "予定の削除に失敗しました。該当する予定が見つからないか、複数の候補があります。"
            
        else:
            return "予定の操作種別（作成/参照/更新/削除）が特定できませんでした。もう少し詳しく教えていただけますか？"
            
    except Exception as e:
        print(f"Error processing message: {e}")
        return "申し訳ありません。メッセージ処理中にエラーが発生しました。後でもう一度お試しください。"
