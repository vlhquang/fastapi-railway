import json
from fastapi import FastAPI
from pydantic import BaseModel
from Core.analysis_engine_api import AnalysisEngineAPI
from Core.database_manager import DatabaseManager
from fastapi.middleware.cors import CORSMiddleware
from Core.gemini_manager import GeminiManager

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

@app.get("/")
def healthcheck():
    return {"status": "ok"}

@app.post("/discoverKeywords")
def discoverKeywords(request: DiscoverKeywords):
    
    # 1
    result = engine.discover_keywords(request.keyword, request.regionCode, request.radar)
    # 2
    # result = engine.full_analysis_for_keyword(request.keyword, request.region_code)
    return {"result": result}

@app.post("/fullAnalysisForKeyword")
def fullAnalysisForKeyword(request: FullAnalysisForKeyword):
    
    # 1
    # result = engine.discover_keywords(request.keyword, request.region_code, request.radar)
    # 2
    result = engine.full_analysis_for_keyword(request.keyword, request.regionCode)
    return {"result": result}

@app.post("/fullAnalysisByChannelId")
def fullAnalysisByChannelId(request: FullAnalysisByChannelId):
    
    # 1
    # result = engine.discover_keywords(request.keyword, request.region_code, request.radar)
    # 2
    result = engine.analyze_competitor_for_m4(request.channelId, request.marketKeywords)
    return {"result": result}

@app.post("/aiSuggestion")
def aiSuggestion(request: AiSuggestion):
    GeminiManager = some_class.GeminiManager
 
    result = GeminiManager.get_overtake_plan(request.analysisData.get('result'), request.marketKeywords)
    return {"result": result}
