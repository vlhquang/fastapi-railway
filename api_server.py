import json
import logging
from fastapi import FastAPI
from pydantic import BaseModel
from Core.analysis_engine_api import AnalysisEngineAPI
from Core.database_manager import DatabaseManager
from main_window import ApiManager  # Import ApiManager from main_window.py
from fastapi.middleware.cors import CORSMiddleware
from Core.gemini_manager import GeminiManager
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from fastapi_cache.decorator import cache
import hashlib
import json

import time

from db import connect_db, close_db, fetch_now, fetch_now_timezone, data_analytics_by_module_insert, getDataAnalyticsByModule
from manage_cache import ManageCache

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

class DiscoverKeywords(BaseModel):
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

# @app.get("/db-time")
# async def get_db_time():
#     now = await fetch_now()
#     return {"db_time": str(now)}

# @app.get("/timezone")
# async def get_timezone():
#     timezone = await fetch_now_timezone()
#     return {"timezone": timezone}

@app.post("/time")
@cache(expire=10)  # TTL 10 giây
async def get_time(request: DiscoverKeywords):
    key = hashlib.md5(json.dumps(request.keyword, sort_keys=True).encode()).hexdigest()

    cached = await some_class.ManageCache.get(key)
    logging.info(f"Cache key: {key}, Cached value: {cached}")
    if cached:
        print("✅ From cache")
        return {"time cache": json.loads(cached)}
    print("💡 Cache miss")
    # Giả lập thời gian xử lý
    timeNow = time.time()
    logging.info(f"Current time for {request.keyword}: {timeNow}")
    await some_class.ManageCache.set(key, json.dumps(timeNow), 15*60)
    # Trả về thời gian hiện tại
    # return {"time": time.time()}
    return {"time": timeNow}

@app.get("/")
def healthcheck():
    return {"status": "ok"}

@app.post("/discoverKeywords")
@cache(expire=15*60)  # TTL 15 phút
# @cache(namespace="discover_keywords")  # Sử dụng namespace để phân tách cache
async def discoverKeywords(request: DiscoverKeywords):
    logging.info(f"Received request to discover keywords: {request.keyword}, Region: {request.regionCode}, Radar: {request.radar}")

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
        await some_class.ManageCache.set(key, cacheDB['response_data'], 5 * 60)
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
    await some_class.ManageCache.set(key, json.dumps(result), 5 * 60)
    return {"result": result}

@app.post("/fullAnalysisForKeyword")
async def fullAnalysisForKeyword(request: FullAnalysisForKeyword):
    
    # 1
    # result = engine.discover_keywords(request.keyword, request.region_code, request.radar)
    # 2
    # result = engine.full_analysis_for_keyword(request.keyword, request.regionCode)
    # return {"result": result}

    key = hashlib.md5(json.dumps('fullAnalysisForKeyword'.join(request.keyword).join(request.regionCode), sort_keys=True).encode()).hexdigest()
    backend = FastAPICache.get_backend()

    cached = await backend.get(key)
    if cached:
        print("✅ From cache")
        return {"result": json.loads(cached)}

    # Nếu chưa có cache, xử lý bình thường
    print("💡 Cache miss")
    result = engine.full_analysis_for_keyword(request.keyword, request.regionCode)
    await backend.set(key, json.dumps(result), expire=15 * 60)
    return {"result": result}

@app.post("/fullAnalysisByChannelId")
async def fullAnalysisByChannelId(request: FullAnalysisByChannelId):
    
    # 1
    # result = engine.discover_keywords(request.keyword, request.region_code, request.radar)
    # 2
    # result = engine.analyze_competitor_for_m4(request.channelId, request.marketKeywords)
    # return {"result": result}

    key = hashlib.md5(json.dumps("fullAnalysisByChannelId".join(request.channelId).join(request.marketKeywords), sort_keys=True).encode()).hexdigest()
    backend = FastAPICache.get_backend()

    cached = await backend.get(key)
    if cached:
        print("✅ From cache")
        return {"result": json.loads(cached)}

    # Nếu chưa có cache, xử lý bình thường
    print("💡 Cache miss")
    result = engine.analyze_competitor_for_m4(request.channelId, request.marketKeywords)
    await backend.set(key, json.dumps(result), expire=15 * 60)
    return {"result": result}

@app.post("/aiSuggestion")
def aiSuggestion(request: AiSuggestion):
    GeminiManager = some_class.GeminiManager
 
    result = GeminiManager.get_overtake_plan(request.analysisData.get('result'), request.marketKeywords)
    return {"result": result}

@app.post("/dataAnalyticsByModuleInsert")
async def dataAnalyticsByModuleInsert():
    result = await data_analytics_by_module_insert('test_module', 'test_user', {'key': 'value'}, {'response': 'data'})
    return {"result": result}