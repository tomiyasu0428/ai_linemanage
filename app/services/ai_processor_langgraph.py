import os
import json
import datetime
from typing import Dict, Any, List, Optional, TypedDict, Annotated, Sequence, Union, cast

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_experimental.graph_runner import GraphRunner
from langchain_experimental.graph_components import GraphState, StateGraph, END

from app.services.google_calendar import (
    register_calendar_event,
    get_calendar_events,
    delete_calendar_event,
    update_calendar_event
)
from app.services.database import (
    save_conversation_memory,
    get_conversation_memory,
    clear_expired_memories
)

gemini_api_key = os.getenv("GEMINI_API_KEY")
llm = ChatGoogleGenerativeAI(model="gemini-pro", google_api_key=gemini_api_key)

user_memories = {}

clear_expired_memories()

class AgentState(TypedDict):
    user_id: str
    messages: List[BaseMessage]
    current_input: str
    current_output: Optional[str]
    tool_calls: List[Dict[str, Any]]
    tool_results: List[Dict[str, Any]]
    error: Optional[str]

def create_calendar_event(
    user_id: str,
    start_time: str,
    end_time: str,
    title: str,
    location: str = "",
    description: str = ""
) -> str:
    """
    Googleカレンダーに予定を登録する
    
    Args:
        user_id: ユーザーID
        start_time: 開始時間（ISO形式）
        end_time: 終了時間（ISO形式）
        title: 予定のタイトル
        location: 場所（オプション）
        description: 詳細説明（オプション）
    
    Returns:
        登録結果のメッセージ
    """
    try:
        event_id = register_calendar_event(
            user_id=user_id,
            start_time=start_time,
            end_time=end_time,
            title=title,
            location=location,
            description=description
        )
        
        if event_id:
            return f"予定「{title}」を登録しました。"
        else:
            return "予定の登録に失敗しました。"
    except Exception as e:
        return f"予定の登録中にエラーが発生しました: {str(e)}"

def read_calendar_events(
    user_id: str,
    start_time: str,
    end_time: str
) -> str:
    """
    指定期間のカレンダー予定を取得する
    
    Args:
        user_id: ユーザーID
        start_time: 開始時間（ISO形式）
        end_time: 終了時間（ISO形式）
    
    Returns:
        予定リストのメッセージ
    """
    try:
        events = get_calendar_events(
            user_id=user_id,
            start_time=start_time,
            end_time=end_time
        )
        
        if not events:
            return "指定された期間の予定はありません。"
        
        events_text = "以下の予定が見つかりました：\n"
        for i, event in enumerate(events, 1):
            events_text += f"{i}. {event['summary']} ({event['start']['dateTime']}〜{event['end']['dateTime']})\n"
        return events_text
    except Exception as e:
        return f"予定の取得中にエラーが発生しました: {str(e)}"

def handle_ambiguous_events(
    events: List[Dict[str, Any]]
) -> str:
    """
    複数の候補がある場合に、ユーザーに選択肢を提示する
    
    Args:
        events: 候補となる予定のリスト
    
    Returns:
        選択肢を含むメッセージ
    """
    if not events:
        return "該当する予定が見つかりませんでした。"
    
    message = "複数の予定が見つかりました。どの予定について操作しますか？\n"
    for i, event in enumerate(events, 1):
        start_time = event.get('start', {}).get('dateTime', '不明')
        end_time = event.get('end', {}).get('dateTime', '不明')
        
        try:
            start_dt = datetime.datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            end_dt = datetime.datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            
            jst = datetime.timezone(datetime.timedelta(hours=9))
            start_dt = start_dt.astimezone(jst)
            end_dt = end_dt.astimezone(jst)
            
            formatted_start = start_dt.strftime("%Y年%m月%d日 %H:%M")
            formatted_end = end_dt.strftime("%H:%M")
            time_str = f"{formatted_start}〜{formatted_end}"
        except:
            time_str = f"{start_time}〜{end_time}"
        
        message += f"{i}. {event.get('summary', '無題')} ({time_str})\n"
    
    message += "\n番号で選択するか、より詳細な情報（タイトルと日時）を教えてください。"
    return message

def update_calendar_event_tool(
    user_id: str,
    title: str,
    start_time: str,
    end_time: str,
    location: str = "",
    description: str = ""
) -> str:
    """
    カレンダー予定を更新する
    
    Args:
        user_id: ユーザーID
        title: 予定のタイトル
        start_time: 開始時間（ISO形式）
        end_time: 終了時間（ISO形式）
        location: 場所（オプション）
        description: 詳細説明（オプション）
    
    Returns:
        更新結果のメッセージ
    """
    try:
        result = update_calendar_event(
            user_id=user_id,
            event_query={
                "title": title,
                "start_time": start_time
            },
            updated_data={
                "title": title,
                "start_time": start_time,
                "end_time": end_time,
                "location": location,
                "description": description
            }
        )
        
        if result is True:
            return f"予定「{title}」を更新しました。"
        elif isinstance(result, list):
            return handle_ambiguous_events(result)
        else:
            return "予定の更新に失敗しました。該当する予定が見つかりません。"
    except Exception as e:
        return f"予定の更新中にエラーが発生しました: {str(e)}"

def delete_calendar_event_tool(
    user_id: str,
    title: str,
    start_time: str
) -> str:
    """
    カレンダー予定を削除する
    
    Args:
        user_id: ユーザーID
        title: 予定のタイトル
        start_time: 開始時間（ISO形式）
    
    Returns:
        削除結果のメッセージ
    """
    try:
        result = delete_calendar_event(
            user_id=user_id,
            event_query={
                "title": title,
                "start_time": start_time
            }
        )
        
        if result is True:
            return f"予定「{title}」を削除しました。"
        elif isinstance(result, list):
            return handle_ambiguous_events(result)
        else:
            return "予定の削除に失敗しました。該当する予定が見つかりません。"
    except Exception as e:
        return f"予定の削除中にエラーが発生しました: {str(e)}"

def parse_datetime(
    date_text: str
) -> Dict[str, str]:
    """
    自然言語の日時表現をISO形式に変換する
    
    Args:
        date_text: 日時を表す自然言語テキスト（例：「明日の10時から12時まで」「来週の水曜日」）
    
    Returns:
        開始時間と終了時間のISO形式文字列を含む辞書
    """
    import re
    from datetime import datetime, timedelta, timezone, time
    
    jst = timezone(timedelta(hours=9))
    now = datetime.now(jst)
    
    weekday_dict = {
        "月曜": 0, "月曜日": 0, "月": 0,
        "火曜": 1, "火曜日": 1, "火": 1,
        "水曜": 2, "水曜日": 2, "水": 2,
        "木曜": 3, "木曜日": 3, "木": 3,
        "金曜": 4, "金曜日": 4, "金": 4,
        "土曜": 5, "土曜日": 5, "土": 5,
        "日曜": 6, "日曜日": 6, "日": 6
    }
    
    if "今日" in date_text:
        target_date = now.date()
    elif "明日" in date_text:
        target_date = (now + timedelta(days=1)).date()
    elif "明後日" in date_text:
        target_date = (now + timedelta(days=2)).date()
    elif "昨日" in date_text:
        target_date = (now - timedelta(days=1)).date()
    elif "一昨日" in date_text:
        target_date = (now - timedelta(days=2)).date()
    else:
        weekday_pattern = re.compile(r'(今週|来週|再来週)の(月曜日|火曜日|水曜日|木曜日|金曜日|土曜日|日曜日|月|火|水|木|金|土|日)')
        weekday_match = weekday_pattern.search(date_text)
        
        if weekday_match:
            week_ref = weekday_match.group(1)
            weekday = weekday_dict[weekday_match.group(2)]
            
            current_weekday = now.weekday()
            
            if week_ref == "今週":
                days_ahead = weekday - current_weekday
                if days_ahead < 0:  # 既に過ぎている場合は来週
                    days_ahead += 7
                target_date = (now + timedelta(days=days_ahead)).date()
            
            elif week_ref == "来週":
                days_ahead = weekday - current_weekday + 7
                target_date = (now + timedelta(days=days_ahead)).date()
            
            elif week_ref == "再来週":
                days_ahead = weekday - current_weekday + 14
                target_date = (now + timedelta(days=days_ahead)).date()
        
        elif "日後" in date_text or "日前" in date_text:
            days_pattern = re.compile(r'(\d+)日(後|前)')
            days_match = days_pattern.search(date_text)
            
            if days_match:
                days = int(days_match.group(1))
                if days_match.group(2) == "後":
                    target_date = (now + timedelta(days=days)).date()
                else:
                    target_date = (now - timedelta(days=days)).date()
            else:
                target_date = now.date()
        
        elif "来月" in date_text:
            next_month = now.month + 1
            next_year = now.year
            if next_month > 12:
                next_month = 1
                next_year += 1
            
            import calendar
            last_day = calendar.monthrange(next_year, next_month)[1]
            target_day = min(now.day, last_day)
            
            target_date = datetime(next_year, next_month, target_day).date()
        
        elif "月" in date_text and "日" in date_text:
            date_pattern = re.compile(r'(\d+)月(\d+)日')
            date_match = date_pattern.search(date_text)
            
            if date_match:
                month = int(date_match.group(1))
                day = int(date_match.group(2))
                
                year = now.year
                if month < now.month or (month == now.month and day < now.day):
                    year += 1
                
                try:
                    target_date = datetime(year, month, day).date()
                except ValueError:
                    target_date = now.date()
            else:
                target_date = now.date()
        
        else:
            target_date = now.date()
    
    start_hour, start_minute = 9, 0  # デフォルト値
    end_hour, end_minute = 10, 0  # デフォルト値
    duration_hours = 1  # デフォルトの所要時間
    
    time_pattern = re.compile(r'(\d{1,2})時(?:(\d{1,2})分)?から(\d{1,2})時(?:(\d{1,2})分)?まで')
    time_match = time_pattern.search(date_text)
    
    if time_match:
        start_hour = int(time_match.group(1))
        start_minute = int(time_match.group(2)) if time_match.group(2) else 0
        end_hour = int(time_match.group(3))
        end_minute = int(time_match.group(4)) if time_match.group(4) else 0
    
    elif "時から" in date_text:
        start_pattern = re.compile(r'(\d{1,2})時(?:(\d{1,2})分)?から')
        start_match = start_pattern.search(date_text)
        
        if start_match:
            start_hour = int(start_match.group(1))
            start_minute = int(start_match.group(2)) if start_match.group(2) else 0
            end_hour = start_hour + duration_hours
            end_minute = start_minute
    
    elif "午前" in date_text or "午後" in date_text:
        am_pm_pattern = re.compile(r'(午前|午後)(\d{1,2})時(?:(\d{1,2})分)?(?:から(?:(午前|午後))?(\d{1,2})時(?:(\d{1,2})分)?まで)?')
        am_pm_match = am_pm_pattern.search(date_text)
        
        if am_pm_match:
            start_ampm = am_pm_match.group(1)
            start_hour = int(am_pm_match.group(2))
            if start_ampm == "午後" and start_hour < 12:
                start_hour += 12
            
            start_minute = int(am_pm_match.group(3)) if am_pm_match.group(3) else 0
            
            if am_pm_match.group(5):
                end_ampm = am_pm_match.group(4) if am_pm_match.group(4) else start_ampm
                end_hour = int(am_pm_match.group(5))
                if end_ampm == "午後" and end_hour < 12:
                    end_hour += 12
                
                end_minute = int(am_pm_match.group(6)) if am_pm_match.group(6) else 0
            else:
                end_hour = start_hour + duration_hours
                end_minute = start_minute
    
    elif "正午" in date_text:
        start_hour = 12
        start_minute = 0
        end_hour = 13
        end_minute = 0
    
    if start_hour < 24 and end_hour < 24:
        start_time = datetime.combine(
            target_date, 
            time(hour=start_hour, minute=start_minute),
            tzinfo=jst
        )
        
        end_time = datetime.combine(
            target_date, 
            time(hour=end_hour, minute=end_minute),
            tzinfo=jst
        )
        
        if end_time <= start_time:
            end_time = end_time + timedelta(days=1)
    else:
        start_time = datetime.combine(
            target_date, 
            time(hour=9, minute=0),
            tzinfo=jst
        )
        
        end_time = datetime.combine(
            target_date, 
            time(hour=10, minute=0),
            tzinfo=jst
        )
    
    return {
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat()
    }

SYSTEM_PROMPT = """
あなたはAI予定管理秘書です。ユーザーのLINEメッセージから予定に関する意図を理解し、Googleカレンダーを操作します。
以下の操作が可能です：

1. 予定の作成: 「明日の10時から12時まで会議」のような入力から新しい予定を作成
2. 予定の確認: 「今日の予定は？」「来週の水曜日の予定を教えて」などの質問に回答
3. 予定の変更: 「明日の会議を13時から15時に変更して」などの指示に対応
4. 予定の削除: 「明日の会議をキャンセル」などの指示に対応

ユーザーの入力を分析し、適切なツールを呼び出して対応してください。
会話の文脈を考慮し、自然な対話を心がけてください。
"""

INTENT_UNDERSTANDING_PROMPT = """
ユーザーの入力から、予定に関する意図を抽出してください。
以下の情報を含むJSONを出力してください：

1. intent: 予定の操作種別（"create", "read", "update", "delete"のいずれか）
2. datetime_info: 日時に関する情報（「明日の10時から12時」「来週の水曜日」など）
3. title: 予定のタイトル
4. location: 場所（あれば）
5. description: 詳細説明（あれば）
6. confidence: この解釈の確信度（0.0〜1.0）

JSONフォーマット:
```json
{
  "intent": "create/read/update/delete",
  "datetime_info": "明日の10時から12時まで",
  "title": "会議",
  "location": "会議室A",
  "description": "プロジェクトの進捗確認",
  "confidence": 0.9
}
```

会話の文脈も考慮してください。例えば、ユーザーが「それを30分遅らせて」と言った場合、
前の会話で言及された予定を30分遅らせる意図だと解釈します。
"""

TOOL_DECISION_PROMPT = """
ユーザーの意図に基づいて、呼び出すべきツールを決定してください。
以下のツールが利用可能です：

1. create_calendar_event: 新しい予定を作成
   - パラメータ: user_id, start_time, end_time, title, location, description

2. read_calendar_events: 指定期間の予定を取得
   - パラメータ: user_id, start_time, end_time

3. update_calendar_event_tool: 既存の予定を更新
   - パラメータ: user_id, title, start_time, end_time, location, description

4. delete_calendar_event_tool: 予定を削除
   - パラメータ: user_id, title, start_time

5. parse_datetime: 自然言語の日時表現をISO形式に変換
   - パラメータ: date_text

以下のJSONフォーマットで出力してください：
```json
{
  "tool_name": "ツール名",
  "parameters": {
    "パラメータ名1": "値1",
    "パラメータ名2": "値2",
    ...
  }
}
```

または、ツールを呼び出す必要がない場合：
```json
{
  "tool_name": null,
  "reason": "ツールを呼び出さない理由"
}
```

日時情報がある場合は、必ず最初にparse_datetimeツールを使用して日時をISO形式に変換してください。
"""

RESPONSE_GENERATION_PROMPT = """
ツールの実行結果に基づいて、ユーザーへの応答を生成してください。
応答は自然な日本語で、親しみやすく、かつ簡潔にしてください。

以下のポイントを考慮してください：
1. ツールの実行が成功した場合は、その結果を伝える
2. エラーが発生した場合は、ユーザーが理解しやすい形でエラー内容を説明する
3. 複数の候補がある場合は、選択肢を提示する
4. 必要に応じて、次のアクションを提案する

応答例：
- 予定作成成功: 「明日の10時から12時まで会議を登録しました。」
- 予定確認: 「明日の予定は以下の通りです：\n1. 会議 (10:00〜12:00)\n2. ランチ (12:30〜13:30)」
- 予定更新成功: 「会議の時間を13時から15時に変更しました。」
- 予定削除成功: 「明日の会議をキャンセルしました。」
- 複数候補: 「複数の会議が見つかりました。どの予定を変更しますか？\n1. プロジェクトA会議 (10:00〜11:00)\n2. チーム会議 (14:00〜15:00)」
- エラー: 「申し訳ありません。予定の登録に失敗しました。時間の指定を確認してもう一度お試しください。」

会話の文脈を維持し、自然な対話の流れを作ってください。
"""

def understand_intent(state: AgentState) -> AgentState:
    """ユーザーの意図を理解するノード"""
    user_id = state["user_id"]
    current_input = state["current_input"]
    messages = state["messages"]
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT + "\n\n" + INTENT_UNDERSTANDING_PROMPT),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{input}")
    ])
    
    chain = prompt | llm | StrOutputParser()
    
    history = messages if messages else []
    
    result = chain.invoke({
        "history": history,
        "input": current_input
    })
    
    try:
        import re
        json_match = re.search(r'```json\s*(.*?)\s*```', result, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
            intent_data = json.loads(json_str)
        else:
            intent_data = json.loads(result)
    except Exception as e:
        intent_data = {
            "intent": "unknown",
            "datetime_info": "",
            "title": "",
            "location": "",
            "description": "",
            "confidence": 0.0,
            "error": str(e)
        }
    
    return {
        **state,
        "intent_data": intent_data
    }

def decide_tool_calls(state: AgentState) -> AgentState:
    """ツール呼び出しを決定するノード"""
    intent_data = state.get("intent_data", {})
    user_id = state["user_id"]
    messages = state["messages"]
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT + "\n\n" + TOOL_DECISION_PROMPT),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{intent_json}")
    ])
    
    chain = prompt | llm | StrOutputParser()
    
    history = messages if messages else []
    
    result = chain.invoke({
        "history": history,
        "intent_json": json.dumps(intent_data, ensure_ascii=False)
    })
    
    try:
        import re
        json_match = re.search(r'```json\s*(.*?)\s*```', result, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
            tool_decision = json.loads(json_str)
        else:
            tool_decision = json.loads(result)
    except Exception as e:
        tool_decision = {
            "tool_name": None,
            "reason": f"ツール決定中にエラーが発生しました: {str(e)}"
        }
    
    return {
        **state,
        "tool_calls": [tool_decision] if tool_decision.get("tool_name") else []
    }

def execute_tools(state: AgentState) -> AgentState:
    """ツールを実行するノード"""
    tool_calls = state.get("tool_calls", [])
    user_id = state["user_id"]
    intent_data = state.get("intent_data", {})
    
    tool_results = []
    
    for tool_call in tool_calls:
        tool_name = tool_call.get("tool_name")
        parameters = tool_call.get("parameters", {})
        
        try:
            if tool_name == "parse_datetime":
                date_text = parameters.get("date_text", "")
                result = parse_datetime(date_text)
                tool_results.append({
                    "tool_name": tool_name,
                    "result": result
                })
            
            elif tool_name == "create_calendar_event":
                start_time = parameters.get("start_time", "")
                end_time = parameters.get("end_time", "")
                title = parameters.get("title", "")
                location = parameters.get("location", "")
                description = parameters.get("description", "")
                
                result = create_calendar_event(
                    user_id=user_id,
                    start_time=start_time,
                    end_time=end_time,
                    title=title,
                    location=location,
                    description=description
                )
                
                tool_results.append({
                    "tool_name": tool_name,
                    "result": result
                })
            
            elif tool_name == "read_calendar_events":
                start_time = parameters.get("start_time", "")
                end_time = parameters.get("end_time", "")
                
                result = read_calendar_events(
                    user_id=user_id,
                    start_time=start_time,
                    end_time=end_time
                )
                
                tool_results.append({
                    "tool_name": tool_name,
                    "result": result
                })
            
            elif tool_name == "update_calendar_event_tool":
                title = parameters.get("title", "")
                start_time = parameters.get("start_time", "")
                end_time = parameters.get("end_time", "")
                location = parameters.get("location", "")
                description = parameters.get("description", "")
                
                result = update_calendar_event_tool(
                    user_id=user_id,
                    title=title,
                    start_time=start_time,
                    end_time=end_time,
                    location=location,
                    description=description
                )
                
                tool_results.append({
                    "tool_name": tool_name,
                    "result": result
                })
            
            elif tool_name == "delete_calendar_event_tool":
                title = parameters.get("title", "")
                start_time = parameters.get("start_time", "")
                
                result = delete_calendar_event_tool(
                    user_id=user_id,
                    title=title,
                    start_time=start_time
                )
                
                tool_results.append({
                    "tool_name": tool_name,
                    "result": result
                })
            
            else:
                tool_results.append({
                    "tool_name": tool_name,
                    "error": f"未知のツール: {tool_name}"
                })
        
        except Exception as e:
            tool_results.append({
                "tool_name": tool_name,
                "error": str(e)
            })
    
    return {
        **state,
        "tool_results": tool_results
    }

def generate_response(state: AgentState) -> AgentState:
    """応答を生成するノード"""
    tool_results = state.get("tool_results", [])
    intent_data = state.get("intent_data", {})
    messages = state["messages"]
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT + "\n\n" + RESPONSE_GENERATION_PROMPT),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{tool_results_json}\n\n{intent_json}")
    ])
    
    chain = prompt | llm | StrOutputParser()
    
    history = messages if messages else []
    
    result = chain.invoke({
        "history": history,
        "tool_results_json": json.dumps(tool_results, ensure_ascii=False),
        "intent_json": json.dumps(intent_data, ensure_ascii=False)
    })
    
    return {
        **state,
        "current_output": result
    }

def build_agent_graph() -> GraphRunner:
    """エージェントグラフを構築する"""
    workflow = StateGraph(AgentState)
    
    workflow.add_node("understand_intent", understand_intent)
    workflow.add_node("decide_tool_calls", decide_tool_calls)
    workflow.add_node("execute_tools", execute_tools)
    workflow.add_node("generate_response", generate_response)
    
    workflow.set_entry_point("understand_intent")
    workflow.add_edge("understand_intent", "decide_tool_calls")
    workflow.add_edge("decide_tool_calls", "execute_tools")
    workflow.add_edge("execute_tools", "generate_response")
    workflow.add_edge("generate_response", END)
    
    compiled_graph = workflow.compile()
    return GraphRunner(compiled_graph)

graph_runner = build_agent_graph()

def process_user_message(user_id: str, user_message: str) -> str:
    """
    ユーザーのメッセージを処理し、適切な応答を返す
    
    Args:
        user_id: ユーザーID
        user_message: ユーザーからのメッセージ
    
    Returns:
        応答メッセージ
    """
    try:
        messages = get_conversation_memory(user_id) or []
        
        messages.append(HumanMessage(content=user_message))
        
        initial_state = {
            "user_id": user_id,
            "messages": messages,
            "current_input": user_message,
            "current_output": None,
            "tool_calls": [],
            "tool_results": [],
            "error": None
        }
        
        result = graph_runner.invoke(initial_state)
        
        response = result.get("current_output", "申し訳ありません。処理中にエラーが発生しました。")
        
        messages.append(AIMessage(content=response))
        
        save_conversation_memory(user_id, messages)
        
        return response
    
    except Exception as e:
        print(f"Error processing message: {e}")
        return "申し訳ありません。メッセージ処理中にエラーが発生しました。後でもう一度お試しください。"
