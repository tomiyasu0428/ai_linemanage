import os
import datetime
from typing import Dict, List, Any, Optional, Union
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request as GoogleRequest

from app.services.database import get_user_tokens, save_user_tokens

def check_user_auth_status(user_id: str) -> bool:
    """ユーザーのGoogle認証状態を確認する"""
    try:
        tokens = get_user_tokens(user_id)
        return bool(tokens)
    except Exception:
        return False

def get_google_calendar_service(user_id: str):
    """Google Calendar APIのサービスオブジェクトを取得する"""
    try:
        token_info = get_user_tokens(user_id)
        if not token_info:
            raise ValueError("ユーザーの認証情報が見つかりません")
        
        credentials = Credentials(
            token=token_info.get("token"),
            refresh_token=token_info.get("refresh_token"),
            token_uri=token_info.get("token_uri"),
            client_id=token_info.get("client_id"),
            client_secret=token_info.get("client_secret"),
            scopes=token_info.get("scopes")
        )
        
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(GoogleRequest())
            
            token_info.update({
                "token": credentials.token,
                "refresh_token": credentials.refresh_token
            })
            save_user_tokens(user_id, token_info)
        
        service = build('calendar', 'v3', credentials=credentials)
        return service
    
    except Exception as e:
        print(f"Error getting calendar service: {e}")
        return None

def register_calendar_event(
    user_id: str,
    start_time: str,
    end_time: str,
    title: str,
    location: str = "",
    description: str = ""
) -> Optional[str]:
    """Googleカレンダーに予定を登録する"""
    try:
        service = get_google_calendar_service(user_id)
        if not service:
            return None
        
        event = {
            'summary': title,
            'location': location,
            'description': description,
            'start': {
                'dateTime': start_time,
                'timeZone': 'Asia/Tokyo',
            },
            'end': {
                'dateTime': end_time,
                'timeZone': 'Asia/Tokyo',
            },
        }
        
        event = service.events().insert(calendarId='primary', body=event).execute()
        return event.get('id')
    
    except Exception as e:
        print(f"Error registering calendar event: {e}")
        return None

def get_calendar_events(
    user_id: str,
    start_time: str,
    end_time: str
) -> List[Dict[str, Any]]:
    """指定期間のカレンダー予定を取得する"""
    try:
        service = get_google_calendar_service(user_id)
        if not service:
            return []
        
        events_result = service.events().list(
            calendarId='primary',
            timeMin=start_time,
            timeMax=end_time,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        return events_result.get('items', [])
    
    except Exception as e:
        print(f"Error getting calendar events: {e}")
        return []

def find_event_by_query(
    service, 
    event_query: Dict[str, Any]
) -> Optional[str]:
    """クエリ条件に一致する予定を検索する"""
    try:
        title = event_query.get('title', '')
        start_time = event_query.get('start_time')
        
        if start_time:
            date_part = start_time.split('T')[0]
            time_min = f"{date_part}T00:00:00+09:00"
            time_max = f"{date_part}T23:59:59+09:00"
        else:
            now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
            time_min = now.strftime("%Y-%m-%dT00:00:00+09:00")
            time_max = now.strftime("%Y-%m-%dT23:59:59+09:00")
        
        events_result = service.events().list(
            calendarId='primary',
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        matching_events = []
        for event in events:
            if title.lower() in event.get('summary', '').lower():
                matching_events.append(event)
        
        if len(matching_events) == 1:
            return matching_events[0].get('id')
        
        return None
    
    except Exception as e:
        print(f"Error finding event: {e}")
        return None

def update_calendar_event(
    user_id: str,
    event_query: Dict[str, Any],
    updated_data: Dict[str, Any]
) -> bool:
    """カレンダー予定を更新する"""
    try:
        service = get_google_calendar_service(user_id)
        if not service:
            return False
        
        event_id = find_event_by_query(service, event_query)
        if not event_id:
            return False
        
        event = service.events().get(calendarId='primary', eventId=event_id).execute()
        
        if 'title' in updated_data:
            event['summary'] = updated_data['title']
        if 'location' in updated_data:
            event['location'] = updated_data['location']
        if 'description' in updated_data:
            event['description'] = updated_data['description']
        if 'start_time' in updated_data:
            event['start'] = {
                'dateTime': updated_data['start_time'],
                'timeZone': 'Asia/Tokyo'
            }
        if 'end_time' in updated_data:
            event['end'] = {
                'dateTime': updated_data['end_time'],
                'timeZone': 'Asia/Tokyo'
            }
        
        service.events().update(calendarId='primary', eventId=event_id, body=event).execute()
        return True
    
    except Exception as e:
        print(f"Error updating calendar event: {e}")
        return False

def delete_calendar_event(
    user_id: str,
    event_query: Dict[str, Any]
) -> bool:
    """カレンダー予定を削除する"""
    try:
        service = get_google_calendar_service(user_id)
        if not service:
            return False
        
        event_id = find_event_by_query(service, event_query)
        if not event_id:
            return False
        
        service.events().delete(calendarId='primary', eventId=event_id).execute()
        return True
    
    except Exception as e:
        print(f"Error deleting calendar event: {e}")
        return False
