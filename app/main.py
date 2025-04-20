import os
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.routers.line import router as line_router
from app.routers.google_auth import router as google_auth_router

app = FastAPI(title="AI予定管理秘書アプリ")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本番環境では適切に制限する
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "AI予定管理秘書アプリのバックエンドAPIへようこそ"}

app.include_router(line_router)
app.include_router(google_auth_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
