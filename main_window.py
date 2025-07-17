import sys, logging, os
from Core.gemini_manager import GeminiManager
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from Core.database_manager import DatabaseManager
from Core.analysis_engine import AnalysisEngine

# --- Cấu hình logging và import các module Core ---
log_file = 'app_activity.log'
if os.path.exists(log_file): os.remove(log_file)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[logging.FileHandler(log_file, mode='w', encoding='utf-8'), logging.StreamHandler(sys.stdout)])

# Lớp ApiManager tích hợp
class ApiManager:
    YOUTUBE_API_SERVICE_NAME = "youtube"; YOUTUBE_API_VERSION = "v3"
    def __init__(self, api_keys: list):
        if not api_keys: raise ValueError("Danh sách API keys không được để trống.")
        self.api_keys, self.current_key_index = api_keys, 0; self.Youtube = self._build_service()
    def _build_service(self):
        api_key = self.api_keys[self.current_key_index]; logging.info(f"Sử dụng API Key index: {self.current_key_index}"); return build(self.YOUTUBE_API_SERVICE_NAME, self.YOUTUBE_API_VERSION, developerKey=api_key, cache_discovery=False)
    def _rotate_key_and_retry(self):
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys); logging.warning(f"Quota có thể đã hết. Xoay vòng sang API Key index: {self.current_key_index}"); self.Youtube = self._build_service()
        if self.current_key_index == 0: logging.error("Tất cả API keys có thể đã hết quota."); return False
        return True
    def search(self, **kwargs):
        try:
            request = self.Youtube.search().list(**kwargs); response = request.execute(); return response.get("items", [])
        except HttpError as e:
            if e.resp.status == 403:
                if self._rotate_key_and_retry(): return self.search(**kwargs)
            logging.error(f"Lỗi API khi tìm kiếm: {e}", exc_info=True); return []
    def get_video_details(self, video_ids: list):
        if not video_ids: return []
        try:
            request = self.Youtube.videos().list(part="snippet,statistics,contentDetails", id=",".join(video_ids)); response = request.execute(); return response.get("items", [])
        except HttpError as e:
            if e.resp.status == 403:
                if self._rotate_key_and_retry(): return self.get_video_details(video_ids)
            logging.error(f"Lỗi API khi lấy chi tiết video: {e}", exc_info=True); return []
    def get_channel_details(self, channel_ids: list):
        if not channel_ids: return []
        try:
            request = self.Youtube.channels().list(part="snippet,statistics", id=",".join(channel_ids)); response = request.execute(); return response.get("items", [])
        except HttpError as e:
            if e.resp.status == 403:
                if self._rotate_key_and_retry(): return self.get_channel_details(channel_ids)
            logging.error(f"Lỗi API khi lấy chi tiết kênh: {e}", exc_info=True); return []