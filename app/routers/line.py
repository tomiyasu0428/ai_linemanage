import os
import re
import datetime
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from linebot.v3 import WebhookHandler
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage
from linebot.v3.webhooks import MessageEvent, TextMessageContent, PostbackEvent
from linebot.v3.exceptions import InvalidSignatureError

from app.services.ai_processor_langgraph import process_user_message
from app.services.google_calendar import check_user_auth_status
from app.services.group_scheduler import (
    find_available_times, 
    create_voting_message, 
    process_vote, 
    close_voting
)

router = APIRouter(prefix="/line", tags=["line"])

line_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "dummy_token")
line_secret = os.getenv("LINE_CHANNEL_SECRET", "dummy_secret")

configuration = Configuration(access_token=line_token)
handler = WebhookHandler(line_secret)

@router.post("/callback")
async def callback(request: Request, background_tasks: BackgroundTasks):
    signature = request.headers.get('X-Line-Signature', '')
    body = await request.body()
    body_text = body.decode('utf-8')
    
    try:
        handler.handle(body_text, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    return "OK"

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    user_message = event.message.text
    
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        
        if hasattr(event.source, 'group_id'):
            group_id = event.source.group_id
            
            schedule_match = re.match(r'日程調整\s+(.+)', user_message)
            if schedule_match:
                event_title = schedule_match.group(1)
                
                is_authenticated = check_user_auth_status(user_id)
                if not is_authenticated:
                    auth_url = f"{os.getenv('APP_BASE_URL')}/google/authorize?user_id={user_id}"
                    reply_text = f"Googleカレンダーへのアクセス許可が必要です。以下のリンクから認証を行ってください。\n{auth_url}"
                    line_bot_api.reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text=reply_text)]
                        )
                    )
                    return
                
                participant_ids = []
                
                start_date = datetime.datetime.now().isoformat()
                end_date = (datetime.datetime.now() + datetime.timedelta(days=7)).isoformat()
                
                available_times = find_available_times(
                    organizer_id=user_id,
                    participant_ids=participant_ids,
                    start_date=start_date,
                    end_date=end_date,
                    duration_minutes=60
                )
                
                if not available_times:
                    reply_text = "指定された期間内に全員が参加可能な時間が見つかりませんでした。"
                    line_bot_api.reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text=reply_text)]
                        )
                    )
                    return
                
                voting_message = create_voting_message(
                    group_id=group_id,
                    event_title=event_title,
                    available_times=available_times
                )
                
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[voting_message]
                    )
                )
                return
        
        is_authenticated = check_user_auth_status(user_id)
        
        if not is_authenticated and "カレンダー" in user_message:
            auth_url = f"{os.getenv('APP_BASE_URL')}/google/authorize?user_id={user_id}"
            reply_text = f"Googleカレンダーへのアクセス許可が必要です。以下のリンクから認証を行ってください。\n{auth_url}"
        else:
            reply_text = process_user_message(user_id, user_message)
        
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)]
            )
        )

@handler.add(PostbackEvent)
def handle_postback(event):
    user_id = event.source.user_id
    postback_data = event.postback.data
    
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        
        if postback_data.startswith('vote_'):
            parts = postback_data.split('_', 5)
            if len(parts) >= 6:
                _, group_id, event_title, option_index, start_time, end_time = parts
                
                success = process_vote(
                    user_id=user_id,
                    group_id=group_id,
                    event_title=event_title,
                    option_index=int(option_index),
                    start_time=start_time,
                    end_time=end_time
                )
                
                if success:
                    line_bot_api.reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text=f"{event_title}の日程に投票しました。")]
                        )
                    )
                else:
                    line_bot_api.reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text="投票処理中にエラーが発生しました。")]
                        )
                    )
        
        elif postback_data.startswith('close_vote_'):
            parts = postback_data.split('_', 3)
            if len(parts) >= 4:
                _, _, group_id, event_title = parts
                
                success = close_voting(
                    group_id=group_id,
                    event_title=event_title,
                    line_bot_api=line_bot_api
                )
                
                if success:
                    line_bot_api.reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text=f"{event_title}の投票を締め切りました。最も多く投票された日時が選択されました。")]
                        )
                    )
                else:
                    line_bot_api.reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text="投票締め切り処理中にエラーが発生しました。")]
                        )
                    )
