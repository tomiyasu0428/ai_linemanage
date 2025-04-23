import os
import json
import time
from typing import Dict, Any, Optional, List
import firebase_admin
from firebase_admin import credentials, firestore
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

_in_memory_db = {
    'tokens': {},
    'memories': {}
}

def initialize_firebase():
    """Firebase初期化（実際の実装では使用）"""
    pass

def save_user_tokens(user_id: str, token_info: Dict[str, Any]) -> bool:
    """ユーザーのトークン情報を保存する"""
    try:
        _in_memory_db['tokens'][user_id] = token_info
        return True
        
    except Exception as e:
        print(f"Error saving user tokens: {e}")
        return False

def get_user_tokens(user_id: str) -> Optional[Dict[str, Any]]:
    """ユーザーのトークン情報を取得する"""
    try:
        return _in_memory_db['tokens'].get(user_id)
        
    except Exception as e:
        print(f"Error getting user tokens: {e}")
        return None

def save_conversation_memory(user_id: str, messages: List[BaseMessage]) -> bool:
    """
    ユーザーの会話メモリをデータベースに保存する
    
    Args:
        user_id: ユーザーID
        messages: 会話メッセージのリスト
    
    Returns:
        保存が成功したかどうか
    """
    try:
        serialized_messages = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                serialized_messages.append({
                    'type': 'human',
                    'content': msg.content,
                    'timestamp': time.time()
                })
            elif isinstance(msg, AIMessage):
                serialized_messages.append({
                    'type': 'ai',
                    'content': msg.content,
                    'timestamp': time.time()
                })
        
        _in_memory_db['memories'][user_id] = {
            'messages': serialized_messages,
            'last_updated': time.time()
        }
        
        return True
        
    except Exception as e:
        print(f"Error saving conversation memory: {e}")
        return False

def get_conversation_memory(user_id: str) -> Optional[List[BaseMessage]]:
    """
    ユーザーの会話メモリをデータベースから取得する
    
    Args:
        user_id: ユーザーID
    
    Returns:
        会話メッセージのリスト、存在しない場合はNone
    """
    try:
        memory_data = _in_memory_db['memories'].get(user_id)
        
        if not memory_data:
            return None
        
        messages = []
        for msg_data in memory_data.get('messages', []):
            if msg_data['type'] == 'human':
                messages.append(HumanMessage(content=msg_data['content']))
            elif msg_data['type'] == 'ai':
                messages.append(AIMessage(content=msg_data['content']))
        
        return messages
        
    except Exception as e:
        print(f"Error getting conversation memory: {e}")
        return None

def clear_expired_memories(expiry_hours: int = 24) -> int:
    """
    有効期限が切れた会話メモリを削除する
    
    Args:
        expiry_hours: 有効期限（時間）
    
    Returns:
        削除されたメモリの数
    """
    try:
        current_time = time.time()
        expiry_seconds = expiry_hours * 3600
        expired_users = []
        
        for user_id, memory_data in _in_memory_db['memories'].items():
            last_updated = memory_data.get('last_updated', 0)
            if current_time - last_updated > expiry_seconds:
                expired_users.append(user_id)
        
        for user_id in expired_users:
            del _in_memory_db['memories'][user_id]
        
        return len(expired_users)
        
    except Exception as e:
        print(f"Error clearing expired memories: {e}")
        return 0
