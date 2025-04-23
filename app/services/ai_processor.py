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

gemini_api_key = os.getenv("GEMINI_API_KEY")
llm = ChatGoogleGenerativeAI(model="gemini-pro", google_api_key=gemini_api_key)

user_memories = {}

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
        date_text: 日時を表す自然言語テキスト（例：「明日の10時から12時まで」）
    
    Returns:
        開始時間と終了時間のISO形式文字列を含む辞書
    """
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
    
    if "今日" in date_text:
        target_date = now.date()
    elif "明日" in date_text:
        target_date = (now + datetime.timedelta(days=1)).date()
    elif "明後日" in date_text:
        target_date = (now + datetime.timedelta(days=2)).date()
    elif "昨日" in date_text:
        target_date = (now - datetime.timedelta(days=1)).date()
    else:
        target_date = now.date()
    
    start_hour, end_hour = 9, 10  # デフォルト値
    
    import re
    time_pattern = re.compile(r'(\d{1,2})時から(\d{1,2})時まで')
    match = time_pattern.search(date_text)
    if match:
        start_hour = int(match.group(1))
        end_hour = int(match.group(2))
    
    start_time = datetime.datetime.combine(
        target_date, 
        datetime.time(hour=start_hour, minute=0),
        tzinfo=datetime.timezone(datetime.timedelta(hours=9))
    )
    
    end_time = datetime.datetime.combine(
        target_date, 
        datetime.time(hour=end_hour, minute=0),
        tzinfo=datetime.timezone(datetime.timedelta(hours=9))
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
    if user_id not in user_memories:
        user_memories[user_id] = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )
    return user_memories[user_id]

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
        
        return response["output"]
            
    except Exception as e:
        print(f"Error processing message: {e}")
        return "申し訳ありません。メッセージ処理中にエラーが発生しました。後でもう一度お試しください。"
