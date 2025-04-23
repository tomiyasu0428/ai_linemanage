import os
import json
import datetime
from typing import Dict, Any, List, Optional

from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.tools import Tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.output_parsers import JsonOutputParser
from langchain.memory import ConversationBufferMemory
from langchain.tools import StructuredTool

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
    success = update_calendar_event(
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
    
    if success:
        return f"予定「{title}」を更新しました。"
    else:
        return "予定の更新に失敗しました。該当する予定が見つからないか、複数の候補があります。"

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
    success = delete_calendar_event(
        user_id=user_id,
        event_query={
            "title": title,
            "start_time": start_time
        }
    )
    
    if success:
        return f"予定「{title}」を削除しました。"
    else:
        return "予定の削除に失敗しました。該当する予定が見つからないか、複数の候補があります。"

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

tools = [
    StructuredTool.from_function(
        func=create_calendar_event,
        name="create_calendar_event",
        description="Googleカレンダーに新しい予定を登録する"
    ),
    StructuredTool.from_function(
        func=read_calendar_events,
        name="read_calendar_events",
        description="指定期間のGoogleカレンダー予定を取得する"
    ),
    StructuredTool.from_function(
        func=update_calendar_event_tool,
        name="update_calendar_event",
        description="Googleカレンダーの予定を更新する"
    ),
    StructuredTool.from_function(
        func=delete_calendar_event_tool,
        name="delete_calendar_event",
        description="Googleカレンダーの予定を削除する"
    ),
    StructuredTool.from_function(
        func=parse_datetime,
        name="parse_datetime",
        description="自然言語の日時表現をISO形式に変換する"
    )
]

prompt = ChatPromptTemplate.from_messages([
    ("system", """
    あなたは日本語で会話するAI予定管理秘書です。ユーザーの自然言語入力から予定に関する意図を理解し、
    適切なツールを使用してGoogleカレンダーの予定を管理します。
    
    以下のツールが利用可能です：
    - create_calendar_event: 新しい予定を登録
    - read_calendar_events: 予定を確認
    - update_calendar_event: 予定を更新
    - delete_calendar_event: 予定を削除
    - parse_datetime: 自然言語の日時表現をISO形式に変換
    
    ユーザーの入力から、予定の作成/確認/更新/削除のどの操作が必要かを判断し、
    適切なツールを使用してください。日時情報は必ずparse_datetimeツールで解析してください。
    
    前回の会話内容を覚えておき、文脈を理解して応答してください。例えば、ユーザーが「それを30分遅らせて」と言った場合、
    前回の会話で話題になった予定を30分遅らせるという意味だと理解してください。
    
    応答は常に日本語で、丁寧かつ簡潔に行ってください。
    """),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

def get_user_memory(user_id: str) -> ConversationBufferMemory:
    """ユーザーごとの会話メモリを取得する（存在しない場合は新規作成）"""
    if user_id in user_memories:
        return user_memories[user_id]
    
    db_messages = get_conversation_memory(user_id)
    
    memory = ConversationBufferMemory(
        memory_key="chat_history",
        return_messages=True
    )
    
    if db_messages:
        for message in db_messages:
            memory.chat_memory.add_message(message)
    
    user_memories[user_id] = memory
    return memory

def create_agent_executor(memory: ConversationBufferMemory) -> AgentExecutor:
    """エージェント実行環境を作成する"""
    agent = create_openai_tools_agent(llm, tools, prompt)
    return AgentExecutor(
        agent=agent,
        tools=tools,
        memory=memory,
        verbose=True
    )

def process_user_message(user_id: str, user_message: str) -> str:
    """ユーザーのメッセージを処理し、適切な応答を返す"""
    try:
        memory = get_user_memory(user_id)
        
        agent_executor = create_agent_executor(memory)
        
        context = {"user_id": user_id}
        
        response = agent_executor.invoke({
            "input": user_message,
            **context
        })
        
        messages = memory.chat_memory.messages
        save_conversation_memory(user_id, messages)
        
        return response["output"]
            
    except Exception as e:
        print(f"Error processing message: {e}")
        return "申し訳ありません。メッセージ処理中にエラーが発生しました。後でもう一度お試しください。"
