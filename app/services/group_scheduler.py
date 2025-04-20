import os
import datetime
from typing import Dict, List, Any, Optional
from linebot.v3.messaging import FlexMessage, FlexContainer, FlexBubble, FlexBox, FlexButton, FlexText
from linebot.v3.messaging import MessagingApi, ApiClient, Configuration, PushMessageRequest

from app.services.google_calendar import get_google_calendar_service, get_calendar_events, register_calendar_event

def find_available_times(
    organizer_id: str,
    participant_ids: List[str],
    start_date: str,
    end_date: str,
    duration_minutes: int = 60
) -> List[Dict[str, Any]]:
    """グループメンバーの空き時間を検索する"""
    try:
        all_events = []
        for user_id in [organizer_id] + participant_ids:
            events = get_calendar_events(user_id, start_date, end_date)
            all_events.extend([(event, user_id) for event in events])
        
        slots = []
        start_dt = datetime.datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        end_dt = datetime.datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        
        current_dt = start_dt
        while current_dt < end_dt:
            if current_dt.weekday() < 5:  
                day_start = current_dt.replace(hour=9, minute=0, second=0, microsecond=0)
                day_end = current_dt.replace(hour=18, minute=0, second=0, microsecond=0)
                
                slot_start = day_start
                while slot_start < day_end:
                    slot_end = slot_start + datetime.timedelta(minutes=30)
                    slots.append({
                        'start': slot_start.isoformat(),
                        'end': slot_end.isoformat(),
                        'available': True
                    })
                    slot_start = slot_end
            
            current_dt = current_dt + datetime.timedelta(days=1)
        
        for event, user_id in all_events:
            event_start = datetime.datetime.fromisoformat(
                event['start']['dateTime'].replace('Z', '+00:00')
            )
            event_end = datetime.datetime.fromisoformat(
                event['end']['dateTime'].replace('Z', '+00:00')
            )
            
            for slot in slots:
                slot_start = datetime.datetime.fromisoformat(slot['start'])
                slot_end = datetime.datetime.fromisoformat(slot['end'])
                
                if (slot_start < event_end and slot_end > event_start):
                    slot['available'] = False
        
        required_consecutive_slots = duration_minutes // 30
        available_times = []
        
        i = 0
        while i <= len(slots) - required_consecutive_slots:
            consecutive_available = True
            for j in range(required_consecutive_slots):
                if i + j >= len(slots) or not slots[i + j]['available']:
                    consecutive_available = False
                    break
            
            if consecutive_available:
                start_time = datetime.datetime.fromisoformat(slots[i]['start'])
                end_time = start_time + datetime.timedelta(minutes=duration_minutes)
                
                available_times.append({
                    'start': start_time.isoformat(),
                    'end': end_time.isoformat()
                })
            
            i += 1
        
        return available_times
        
    except Exception as e:
        print(f"Error finding available times: {e}")
        return []

def create_voting_message(
    group_id: str,
    event_title: str,
    available_times: List[Dict[str, Any]],
    max_options: int = 5
) -> FlexMessage:
    """投票用のFlexメッセージを作成する"""
    try:
        options = available_times[:max_options]
        
        bubble = {
            "type": "bubble",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": f"{event_title} - 日程投票",
                        "weight": "bold",
                        "size": "lg"
                    }
                ]
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": []
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "button",
                        "action": {
                            "type": "postback",
                            "label": "投票を締め切る",
                            "data": f"close_vote_{group_id}_{event_title}"
                        },
                        "style": "primary"
                    }
                ]
            }
        }
        
        for i, option in enumerate(options):
            start_dt = datetime.datetime.fromisoformat(option['start'])
            formatted_date = start_dt.strftime("%m/%d(%a) %H:%M")
            
            bubble["body"]["contents"].append({
                "type": "button",
                "action": {
                    "type": "postback",
                    "label": formatted_date,
                    "data": f"vote_{group_id}_{event_title}_{i}_{option['start']}_{option['end']}"
                },
                "style": "secondary",
                "margin": "sm"
            })
        
        flex_message = FlexMessage(
            alt_text=f"{event_title}の日程投票",
            contents=FlexContainer.from_dict(bubble)
        )
        
        return flex_message
        
    except Exception as e:
        print(f"Error creating voting message: {e}")
        return None

def process_vote(
    user_id: str,
    group_id: str,
    event_title: str,
    option_index: int,
    start_time: str,
    end_time: str
) -> bool:
    """投票を処理する"""
    try:
        global _votes
        if '_votes' not in globals():
            _votes = {}
        
        vote_key = f"{group_id}_{event_title}"
        if vote_key not in _votes:
            _votes[vote_key] = {
                'title': event_title,
                'options': [],
                'votes': {}
            }
        
        if len(_votes[vote_key]['options']) <= option_index:
            _votes[vote_key]['options'].append({
                'start': start_time,
                'end': end_time
            })
        
        _votes[vote_key]['votes'][user_id] = option_index
        
        return True
        
    except Exception as e:
        print(f"Error processing vote: {e}")
        return False

def close_voting(
    group_id: str,
    event_title: str,
    line_bot_api: MessagingApi
) -> bool:
    """投票を締め切り、最も多く投票された日時を選択する"""
    try:
        global _votes
        if '_votes' not in globals():
            return False
        
        vote_key = f"{group_id}_{event_title}"
        if vote_key not in _votes:
            return False
        
        vote_data = _votes[vote_key]
        
        option_counts = [0] * len(vote_data['options'])
        for user_id, option_index in vote_data['votes'].items():
            option_counts[option_index] += 1
        
        max_votes = max(option_counts)
        winning_indices = [i for i, count in enumerate(option_counts) if count == max_votes]
        
        winning_index = winning_indices[0]
        winning_option = vote_data['options'][winning_index]
        
        for user_id in vote_data['votes'].keys():
            register_calendar_event(
                user_id=user_id,
                start_time=winning_option['start'],
                end_time=winning_option['end'],
                title=event_title
            )
        
        start_dt = datetime.datetime.fromisoformat(winning_option['start'])
        formatted_date = start_dt.strftime("%Y年%m月%d日(%a) %H:%M")
        
        message = f"{event_title}の日程が決定しました：{formatted_date}\n参加者全員のGoogleカレンダーに登録しました。"
        
        line_bot_api.push_message(
            PushMessageRequest(
                to=group_id,
                messages=[{
                    "type": "text",
                    "text": message
                }]
            )
        )
        
        del _votes[vote_key]
        
        return True
        
    except Exception as e:
        print(f"Error closing voting: {e}")
        return False
