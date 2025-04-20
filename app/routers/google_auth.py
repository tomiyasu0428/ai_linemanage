import os
from fastapi import APIRouter, Request, HTTPException, Depends, Response
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest

from app.services.database import save_user_tokens, get_user_tokens

router = APIRouter(prefix="/google", tags=["google"])

CLIENT_CONFIG = {
    "web": {
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": [f"{os.getenv('APP_BASE_URL')}/google/oauth2callback"]
    }
}

SCOPES = ["https://www.googleapis.com/auth/calendar"]

@router.get("/authorize")
async def authorize(user_id: str):
    flow = Flow.from_client_config(
        client_config=CLIENT_CONFIG,
        scopes=SCOPES
    )
    flow.redirect_uri = f"{os.getenv('APP_BASE_URL')}/google/oauth2callback"
    
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        state=user_id
    )
    
    return RedirectResponse(authorization_url)

@router.get("/oauth2callback")
async def oauth2callback(request: Request):
    query_params = dict(request.query_params)
    code = query_params.get("code")
    state = query_params.get("state")  # stateにはuser_idが含まれている
    
    if not code or not state:
        raise HTTPException(status_code=400, detail="Invalid request")
    
    flow = Flow.from_client_config(
        client_config=CLIENT_CONFIG,
        scopes=SCOPES
    )
    flow.redirect_uri = f"{os.getenv('APP_BASE_URL')}/google/oauth2callback"
    
    flow.fetch_token(code=code)
    credentials = flow.credentials
    
    user_id = state
    token_info = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes
    }
    save_user_tokens(user_id, token_info)
    
    return {"message": "認証が完了しました。LINEに戻って操作を続けてください。"}
