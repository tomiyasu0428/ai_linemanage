import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

def test_line_webhook():
    """LINE Webhookのテスト用スクリプト"""
    url = "http://localhost:8000/line/callback"
    
    test_personal_message()
    
    test_group_message()

def test_personal_message():
    """個人メッセージのテスト"""
    url = "http://localhost:8000/line/callback"
    
    payload = {
        "destination": "xxxxxxxxxx",
        "events": [
            {
                "type": "message",
                "message": {
                    "type": "text",
                    "id": "14353798921116",
                    "text": "明日の10時から12時まで会議"
                },
                "timestamp": 1625665242211,
                "source": {
                    "type": "user",
                    "userId": "U80xxxxxxxxxxxxxxx"
                },
                "replyToken": "5e46634d6xxxxxxxxxxxxxx",
                "mode": "active"
            }
        ]
    }
    
    headers = {
        "Content-Type": "application/json",
        "X-Line-Signature": "dummy_signature"
    }
    
    response = requests.post(url, data=json.dumps(payload), headers=headers)
    
    print(f"個人メッセージテスト - Status Code: {response.status_code}")
    print(f"個人メッセージテスト - Response: {response.text}")

def test_group_message():
    """グループメッセージのテスト"""
    url = "http://localhost:8000/line/callback"
    
    payload = {
        "destination": "xxxxxxxxxx",
        "events": [
            {
                "type": "message",
                "message": {
                    "type": "text",
                    "id": "14353798921117",
                    "text": "日程調整 プロジェクト会議"
                },
                "timestamp": 1625665242211,
                "source": {
                    "type": "group",
                    "groupId": "G80xxxxxxxxxxxxxxx",
                    "userId": "U80xxxxxxxxxxxxxxx"
                },
                "replyToken": "5e46634d6xxxxxxxxxxxxxx",
                "mode": "active"
            }
        ]
    }
    
    headers = {
        "Content-Type": "application/json",
        "X-Line-Signature": "dummy_signature"
    }
    
    response = requests.post(url, data=json.dumps(payload), headers=headers)
    
    print(f"グループメッセージテスト - Status Code: {response.status_code}")
    print(f"グループメッセージテスト - Response: {response.text}")

if __name__ == "__main__":
    test_line_webhook()
