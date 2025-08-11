import json
import logging
from fastapi import FastAPI, Request, HTTPException, Depends
from pydantic import BaseModel
from Core.analysis_engine_api import AnalysisEngineAPI
from Core.database_manager import DatabaseManager
from main_window import ApiManager  # Import ApiManager from main_window.py
from fastapi.middleware.cors import CORSMiddleware
from Core.gemini_manager import GeminiManager
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from fastapi_cache.decorator import cache
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import hashlib
import os
from dotenv import load_dotenv

import time
import uuid

from db import connect_db, close_db, fetch_now, fetch_now_timezone, data_analytics_by_module_insert, getDataAnalyticsByModule
from manage_cache import ManageCache

load_dotenv()

VALID_TOKEN = os.getenv("AUTHOR_BEARER_TOKEN")

class TokenAuth(HTTPBearer):
    async def __call__(self, request: Request) -> HTTPAuthorizationCredentials:
        credentials = await super().__call__(request)
        logging.debug(f"Received credentials: {credentials}")
        if credentials.scheme.lower() != "bearer" or credentials.credentials != VALID_TOKEN:
            raise HTTPException(status_code=401, detail="Invalid or missing token")
        return credentials

# Tạo instance để dùng trong Depends()
token_auth_scheme = TokenAuth()


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Hoặc ['http://localhost:3000'] nếu dùng React
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SomeClass:
    def __init__(self):
        self.api_keys = self._load_api_keys()
        self.GeminiManager = self.get_gemini_manager()
        self.ManageCache = ManageCache()

    def _load_api_keys(self, account_dir="Account"):
        import glob, os, logging
        key_files = glob.glob(os.path.join(account_dir, '**', '*.key'), recursive=True)
        keys = []

        for file_path in key_files:
            try:
                with open(file_path, 'r') as f:
                    key = f.read().strip()
                    if key:
                        keys.append(key)
                        logging.debug(f"✅ Nạp API key từ: {file_path}")
                    else:
                        logging.warning(f"⚠️ File key rỗng: {file_path}")
            except Exception as e:
                logging.warning(f"❌ Không đọc được file {file_path}: {e}")

        if not keys:
            raise RuntimeError("Không tìm thấy API key hợp lệ trong thư mục /Account.")

        logging.info(f"Đã tải {len(keys)} API key(s) hợp lệ.")
        return keys

    def get_gemini_manager(self):
        import glob, os, logging
        key_path = os.path.join("Account", "studio_gemini.key")
        gemini_api_key = open(key_path, 'r').read().strip()
        return GeminiManager(api_key=gemini_api_key)

# Load API keys (use a placeholder or load from file as in main_window.py)
# api_key_path = "Account/studio_gemini.key"  # Or another .key file in Account/
# with open(api_key_path, 'r') as f:
#     api_keys = [f.read().strip()]
some_class = SomeClass()

api_manager = ApiManager(api_keys=some_class.api_keys)
db_manager = DatabaseManager()
engine = AnalysisEngineAPI(api_manager, db_manager)

TIME_CACHE = 5 * 60  # 5 minutes

class Login(BaseModel):
    email: str
    token: str

class Logout(BaseModel):
    userId: str

class DiscoverKeywords(BaseModel):
    userId: str
    keyword: str
    regionCode: str
    radar: str

class FullAnalysisForKeyword(BaseModel):
    keyword: str
    regionCode: str

class FullAnalysisByChannelId(BaseModel):
    channelId: str
    marketKeywords: list[str]

class AiSuggestion(BaseModel):
    analysisData: dict  # Accept as JSON string
    marketKeywords: list[str]

@app.on_event("startup")
async def startup():
    logging.basicConfig(level=logging.INFO)
    logging.info("Starting FastAPI server...")

    await connect_db()

@app.on_event("shutdown")
async def shutdown():
    await close_db()

@app.get("/")
def healthcheck():
    return {"status": "ok"}

@app.post("/discoverKeywords", dependencies=[Depends(token_auth_scheme)])
async def discoverKeywords(request: DiscoverKeywords):
    logging.info(f"Received request to discover keywords: {request.keyword}, Region: {request.regionCode}, Radar: {request.radar}")
    userId = request.userId or "default_user"
    if (userId == "default_user"):
        logging.warning("No userId provided, using default 'default_user'.")

    key = hashlib.md5(json.dumps("discoverKeywords".join(request.keyword).join(request.regionCode).join(request.radar), sort_keys=True).encode()).hexdigest()
    # backend = FastAPICache.get_backend()

    cached = await some_class.ManageCache.get(key)
    # logging.info(f"Cache key: {key}, Cached value: {cached}")
    if cached:
        logging.info(f"Cache in memory hit for key: {key}")
        return {"result": json.loads(cached)}
    
    cacheDB = await getDataAnalyticsByModule('module1', json.dumps({
        "keyword": request.keyword,
        "regionCode": request.regionCode,
        "radar": request.radar
    }))
    if cacheDB:
        logging.info(f"Cache hit in database for key: {key}")
        await some_class.ManageCache.set(key, cacheDB['response_data'], TIME_CACHE)
        return {"result": json.loads(cacheDB['response_data'])}
    # Nếu chưa có cache, xử lý bình thường
    logging.info(f"Cache miss for key: {key}, processing request...")
    result = engine.discover_keywords(request.keyword, request.regionCode, request.radar)
    await data_analytics_by_module_insert(
        'module1',
        'test_user',
        {
            "keyword": request.keyword,
            "regionCode": request.regionCode,
            "radar": request.radar
        },
        result
    )
    await some_class.ManageCache.set(key, json.dumps(result), TIME_CACHE)
    return {"result": result}

@app.post("/fullAnalysisForKeyword", dependencies=[Depends(token_auth_scheme)])
async def fullAnalysisForKeyword(request: FullAnalysisForKeyword):
    key = hashlib.md5(json.dumps('fullAnalysisForKeyword'.join(request.keyword).join(request.regionCode), sort_keys=True).encode()).hexdigest()

    cached = await some_class.ManageCache.get(key)
    if cached:
        print("✅ From cache")
        return {"result": json.loads(cached)}

    cacheDB = await getDataAnalyticsByModule('module2.1', json.dumps({
        "keyword": request.keyword,
        "regionCode": request.regionCode
    }))

    if cacheDB:
        logging.info(f"Cache hit in database for key: {key}")
        await some_class.ManageCache.set(key, cacheDB['response_data'], TIME_CACHE)
        return {"result": json.loads(cacheDB['response_data'])}
    
    result = engine.full_analysis_for_keyword(request.keyword, request.regionCode)
    await data_analytics_by_module_insert(
        'module2.1',
        'test_user',
        {
            "keyword": request.keyword,
            "regionCode": request.regionCode
        },
        result
    )
    await some_class.ManageCache.set(key, json.dumps(result), TIME_CACHE)
    return {"result": result}

@app.post("/fullAnalysisByChannelId", dependencies=[Depends(token_auth_scheme)])
async def fullAnalysisByChannelId(request: FullAnalysisByChannelId):
    key = hashlib.md5(json.dumps("fullAnalysisByChannelId".join(request.channelId).join(request.marketKeywords), sort_keys=True).encode()).hexdigest()

    cached = await some_class.ManageCache.get(key)
    if cached:
        print("✅ From cache")
        return {"result": json.loads(cached)}

    # Nếu chưa có cache, xử lý bình thường
    cacheDB = await getDataAnalyticsByModule('module2.2', json.dumps({
        "channelId": request.channelId,
        "marketKeywords": request.marketKeywords
    }))

    if cacheDB:
        logging.info(f"Cache hit in database for key: {key}")
        await some_class.ManageCache.set(key, cacheDB['response_data'], TIME_CACHE)
        return {"result": json.loads(cacheDB['response_data'])}
    
    result = engine.analyze_competitor_for_m4(request.channelId, request.marketKeywords)
    await data_analytics_by_module_insert(
        'module2.2',
        'test_user',
        {
            "channelId": request.channelId,
            "marketKeywords": request.marketKeywords
        },
        result
    )
    await some_class.ManageCache.set(key, json.dumps(result), TIME_CACHE)
    return {"result": result}

@app.post("/aiSuggestion", dependencies=[Depends(token_auth_scheme)])
def aiSuggestion(request: AiSuggestion):
    GeminiManager = some_class.GeminiManager
 
    result = GeminiManager.get_overtake_plan(request.analysisData.get('result'), request.marketKeywords)
    return {"result": result}

@app.post("/login", dependencies=[Depends(token_auth_scheme)])
def login(request: Login):
    logging.info(f"User {request.email} logged in with JWT: {request.jwt}")
    return {"result": uuid.uuid4().hex}  # Return a random userId for simplicity