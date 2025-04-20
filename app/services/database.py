import os
import json
from typing import Dict, Any, Optional
import firebase_admin
from firebase_admin import credentials, firestore

_in_memory_db = {}

def initialize_firebase():
    """Firebase初期化（実際の実装では使用）"""
    pass

def save_user_tokens(user_id: str, token_info: Dict[str, Any]) -> bool:
    """ユーザーのトークン情報を保存する"""
    try:
        _in_memory_db[user_id] = token_info
        return True
        
    except Exception as e:
        print(f"Error saving user tokens: {e}")
        return False

def get_user_tokens(user_id: str) -> Optional[Dict[str, Any]]:
    """ユーザーのトークン情報を取得する"""
    try:
        return _in_memory_db.get(user_id)
        
    except Exception as e:
        print(f"Error getting user tokens: {e}")
        return None
