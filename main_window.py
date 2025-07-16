import tkinter as tk
from tkinter import ttk, messagebox
import threading, queue, sys, os, glob, webbrowser, logging, base64
from PIL import Image, ImageTk
from io import BytesIO
import urllib.request
from Core.gemini_manager import GeminiManager
import textwrap
import os
import pandas as pd
import json

# --- Cấu hình logging và import các module Core ---
log_file = 'app_activity.log'
if os.path.exists(log_file): os.remove(log_file)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[logging.FileHandler(log_file, mode='w', encoding='utf-8'), logging.StreamHandler(sys.stdout)])
try:
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from Core.database_manager import DatabaseManager
    from Core.analysis_engine import AnalysisEngine
except ImportError as e:
    logging.critical(f"LỖI IMPORT: {e}", exc_info=True)
    messagebox.showerror("Lỗi nghiêm trọng", f"Lỗi Import. Vui lòng kiểm tra log."); sys.exit(1)

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

# Dữ liệu icon cành cây (Base64)
ICON_DATA = b'iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABHNCSVQICAgIfAhkiAAAAAlwSFlzAAALEwAACxMBAJqcGAAAAdpJREFUOI2N0z9oFEEcx/HPSxGxEBvFQkHFRhQLK7EyKASBUYRYWFjY2Nha2AUEi9hYCYqFklYQBVFEEIsYpUTiZVgYCxuxsFCASEIuEhc/H3b32Hsz724e3L3z+H7/393/u7ujUql8r4lY5kKsg41M4jFE8S0OUbWBDXQhD/2k49ve4g1aEZnwDDbRt3BUp9sEF9GUcAs20Z5wAx4i+hmd8AkmkYt87gWZzOMZPASTiB/wA57C12iOt/EGWpCLuAyLqIj+oTUeoA/oQz/q41k8iv3EaWiGBtAHehGYGIZdaMMWmqENnBDI8DNeYAs1KIZG+I/o+A4/YBNdiM6YgUnEc4zBHhoxFXsQyDiMeYgj+mJLYhvO4V0sQT/q4318ivU4ikG4iuHpBC7gVczFTEyjj+MFPAwMvIWlqEXfNvw3eCgD0hGvYAe+x2c4jSGYjZ2YgVmIY3qEIXqC0/gd36E5NmAe7uNfPA1n0YQ/sAlGkY84DpuIFfEPltCLlBAZ8AxW0ZvQhT7kY+9sA73IzvgEvcgjFssQzDiA36A/nEf/uI1W1KJbWFbjGZwQyEAN2kEf2kEftqEV1qEPHqHPNKAC3egeTmA2/gfZ6ELfNZw+4r+PPsA/6F9gC/r3wQ8A/k24z/wH3jC7wWf83gAAAABJRU5ErkJggg=='

class SEOApp(tk.Tk):
    def __init__(self):
        super().__init__()
        # --- CẤU HÌNH FONT CHỮ TRUNG TÂM ---
        self.FONT_NORMAL = ('Arial', 9)
        self.FONT_BOLD = ('Arial', 9, 'bold')
        self.FONT_HEADING = ('Arial', 10, 'bold')
        
        logging.info("Bắt đầu khởi tạo SEOApp...")
        self.title("SEO Analysis Tool v3.0 - Final")
        self.geometry("1800x700")

        # === TRUNG TÂM DỮ LIỆU QUỐC GIA ===
        # Key: Tên hiển thị trên giao diện
        # Value: Mã quốc gia 2 ký tự (ISO 3166-1 alpha-2)
        self.COUNTRY_DATA = {
            "Việt Nam": "VN",
            "United States": "US",
            "Nhật Bản": "JP",
            "Hàn Quốc": "KR",
            "Tây Ban Nha": "ES",
            "Bồ Đào Nha": "PT",
            "Đức": "DE",
            "Indonesia": "ID",
            # --- BẠN CÓ THỂ THÊM CÁC QUỐC GIA MỚI Ở ĐÂY ---
            # Ví dụ:
            "Pháp": "FR",
            "Anh": "GB",
            "Canada": "CA",
            "Úc": "AU",
            "Thái Lan": "TH"
        }

        # === START: THÊM BIẾN QUẢN LÝ CHO MODULE 1 ===
        self.m1_stop_event = threading.Event()
        # === END: THÊM BIẾN QUẢN LÝ CHO MODULE 1 ===

        self.ui_queue = queue.Queue()
        try:
            api_keys = self._load_api_keys()
            logging.info(f'api_keys: {api_keys}')
            self.api_manager = ApiManager(api_keys=api_keys)
            self.db_manager = DatabaseManager()
            self.db_manager.setup_tables()
            self.analysis_engine = AnalysisEngine(self.api_manager, self.db_manager)
            self.current_selected_keyword_for_analysis = ""
            self.last_m4_analysis_data = {}

            # === KHỞI TẠO GEMINI MANAGER ===
            # !! QUAN TRỌNG: Thay "YOUR_GEMINI_API_KEY" bằng key của bạn
            # Bạn có thể lấy key tại: https://aistudio.google.com/app/apikey
            try:
                # Đường dẫn tới file key trong thư mục Account
                key_path = os.path.join("Account", "studio_gemini.key")
                gemini_api_key = open(key_path, 'r').read().strip()
                self.gemini_manager = GeminiManager(api_key=gemini_api_key)
            except (FileNotFoundError, ValueError) as e:
                logging.warning(f"Không thể khởi tạo Gemini Manager: {e}. Vui lòng tạo file 'studio_gemini.key' trong thư mục 'Account'. Chức năng Module 4 sẽ bị hạn chế.")
                self.gemini_manager = None

            self.session_cache = {}
        except Exception as e:
            logging.critical(f"Lỗi khởi tạo Engine: {e}", exc_info=True); messagebox.showerror("Lỗi Khởi tạo", f"Lỗi: {e}\nKiểm tra log."); self.destroy(); return

        self.style = ttk.Style(self); self.style.theme_use('clam')
        self.style.configure("TNotebook.Tab", font=self.FONT_BOLD, padding=[10, 5])
        self.style.configure("TButton", font=self.FONT_BOLD, padding=10)
        self.style.configure("Treeview.Heading", font=self.FONT_HEADING)
        self.style.configure("Treeview", rowheight=25, font=self.FONT_NORMAL)
        self.style.configure("TLabel", font=self.FONT_NORMAL); self.style.configure("TEntry", font=self.FONT_NORMAL)
        self.style.configure("TLabelframe.Label", font=self.FONT_BOLD)
        logging.info("DEBUG: BƯỚC 1 - Sắp định nghĩa độ rộng cột...")

        # === TRUNG TÂM ĐIỀU CHỈNH ĐỘ RỘNG CỘT ===
        self.M1_COL_WIDTHS = {'Rank': 40, 'Keyword': 800, 'Word count': 100, 'Character count': 100}
        self.M2_COL_WIDTHS = {'Keyword': 200, 'Cầu (30d)': 120, 'Cung (30d)': 100, 'Lượt xem TB': 120, 'Tỷ lệ Tương tác TB': 120, 'Competition': 100, 'Cơ hội SEO': 100, 'Đánh giá': 120}
        self.M3_COL_WIDTHS = {'Channel Link': 120, 'Tên kênh': 250, 'Tổng Sub': 100, 'Tổng Video': 100, 'Tổng View': 120, 'Ngày tạo': 100, 'Phân tích': 100}
        self.M4_COL_WIDTHS = {'Tần suất': 100, 'View TB': 100, 'Chiến lược': 150, 'Định dạng': 80, 'Gắn kết': 120, 'Lỗ hổng N.Dung': 250, 'Kế hoạch (Rule)': 300, 'Kế hoạch (Gemini)': 450}
        logging.info("DEBUG: BƯỚC 2 - ĐÃ định nghĩa xong độ rộng cột.")
        logging.info("DEBUG: BƯỚC 3 - Sắp gọi self.create_widgets()...")
        self.create_widgets()
        self.process_queue()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.load_initial_data()
        logging.info("Giao diện đã khởi tạo thành công.")

    def _load_api_keys(self, account_dir="Account"):
        key_files = glob.glob(os.path.join(account_dir, '**', '*.key'), recursive=True)
        keys = [open(file_path, 'r').read().strip() for file_path in key_files]
        if not keys: raise RuntimeError("Không tìm thấy API key trong thư mục /Account.")
        logging.info(f"Đã tải {len(keys)} API keys."); return keys
    
    # === START: CÁC HÀM CHỨC NĂNG CHO MODULE 1 ===

    def start_keyword_discovery_thread(self):
        """Bắt đầu luồng tìm kiếm từ khóa cho Module 1."""
        seed_keyword = self.m1_seed_keyword_entry.get().strip()
        if not seed_keyword:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập chủ đề cần tìm kiếm.")
            return

        # Vô hiệu hóa nút và xóa kết quả cũ
        self.m1_search_button['state'] = 'disabled'
        self.m1_stop_button['state'] = 'normal'
        self.status_var.set(f"Bắt đầu tìm kiếm từ khóa cho chủ đề: '{seed_keyword}'...")
        self.m1_stop_event.clear() # Đảm bảo cờ stop được reset
        for i in self.treeview_m1.get_children():
            self.treeview_m1.delete(i)

        # Lấy thông tin từ combobox
        radar_mode_map = {
            "Từ khóa Vua (Liên quan)": "relevance",
            "Từ khóa Mới nổi (Xu hướng)": "date",
            "Từ khóa Ngách (Chuyên sâu)": "niche"
        }
        country_name = self.m1_country_combo.get()
        region_code = self.COUNTRY_DATA.get(country_name) # Lấy mã từ dictionary

        radar_mode = radar_mode_map.get(self.m1_radar_combo.get())
        region_code = self.COUNTRY_DATA.get(self.m1_country_combo.get())

        # Khởi chạy luồng nền
        thread = threading.Thread(
            target=self.run_discovery_in_background,
            args=(seed_keyword, region_code, radar_mode),
            daemon=True
        )
        thread.start()

    def run_discovery_in_background(self, seed_keyword, region_code, radar_mode):
        """Hàm chạy trong luồng nền để gọi engine và lấy kết quả."""
        try:
            results = self.analysis_engine.discover_keywords(seed_keyword, region_code, radar_mode, self.m1_stop_event)
            # Đưa kết quả vào queue để UI cập nhật
            self.ui_queue.put({'module': 1, 'data': results})
        except Exception as e:
            logging.error(f"LỖI TRONG LUỒNG TÌM KIẾM TỪ KHÓA: {e}", exc_info=True)
            self.ui_queue.put({'module': 1, 'error': f"Lỗi nghiêm trọng: {e}"})

    def stop_keyword_discovery(self):
        """Gửi tín hiệu dừng cho luồng tìm kiếm từ khóa."""
        self.status_var.set("Đang yêu cầu dừng tác vụ...")
        self.m1_stop_event.set()
        self.m1_stop_button['state'] = 'disabled'

    def show_m1_context_menu(self, event):
        """Hiển thị menu chuột phải trên bảng kết quả Module 1."""
        # Chỉ hiển thị menu nếu có ít nhất một dòng được chọn
        if self.treeview_m1.selection():
            self.m1_context_menu.post(event.x_root, event.y_root)

    def copy_m1_keywords_to_m2(self):
        """Lấy các từ khóa đã chọn ở Module 1 và dán vào Module 2."""
        selected_items = self.treeview_m1.selection()
        if not selected_items:
            return

        keywords_to_copy = []
        for item_id in selected_items:
            # Lấy dữ liệu của dòng, từ khóa nằm ở cột thứ 2 (index 1)
            keyword = self.treeview_m1.item(item_id)['values'][1]
            keywords_to_copy.append(str(keyword))

        if not keywords_to_copy:
            return

        # Lấy nội dung hiện có và thêm từ khóa mới vào
        current_text = self.text_keywords.get("1.0", tk.END).strip()
        new_text = "\n".join(keywords_to_copy)

        # Xóa nội dung cũ và chèn lại để tránh dòng trắng thừa
        final_text = ""
        if current_text:
            final_text = current_text + "\n" + new_text
        else:
            final_text = new_text
        
        self.text_keywords.delete("1.0", tk.END)
        self.text_keywords.insert("1.0", final_text)
        
        # Tự động chuyển sang tab Module 2 để người dùng thấy kết quả
        # Tìm widget notebook để có thể điều khiển
        notebook = self.treeview_m1.winfo_toplevel().nametowidget('.!frame.!notebook')
        notebook.select(1) # Tab 1 là Module 2 (vì index bắt đầu từ 0)
        
        self.status_var.set(f"Đã sao chép {len(keywords_to_copy)} từ khóa sang Module 2.")

    def update_module1_grid(self, results):
        """Cập nhật bảng kết quả của Module 1."""
        # Xóa kết quả cũ
        for i in self.treeview_m1.get_children():
            self.treeview_m1.delete(i)

        if not results:
             self.status_var.set("Hoàn tất. Không tìm thấy từ khóa nào phù hợp.")
        else:
            for i, item in enumerate(results, 1):
                self.treeview_m1.insert('', 'end', values=(
                    i,
                    item['keyword'],
                    item['word_count'],
                    item['char_count']
                ))
            self.status_var.set(f"Hoàn tất! Tìm thấy và gợi ý {len(results)} từ khóa.")
        
        # Reset trạng thái các nút
        self.m1_search_button['state'] = 'normal'
        self.m1_stop_button['state'] = 'disabled'

    def on_m1_double_click(self, event):
        """
        Xử lý sự kiện double-click ở Module 1: Chuyển từ khóa sang Module 2 và tự động phân tích.
        """
        selected_item = self.treeview_m1.focus()
        if not selected_item: return

        # Lấy từ khóa từ dòng được chọn
        keyword = self.treeview_m1.item(selected_item)['values'][1]

        # Chuyển sang tab Module 2
        notebook = self.treeview_m1.winfo_toplevel().nametowidget('.!frame.!notebook')
        notebook.select(1)

        # Điền từ khóa vào ô phân tích và bắt đầu chạy
        self.keyword_entry.delete(0, tk.END)
        self.keyword_entry.insert(0, keyword)
        self.start_analysis_thread()

    # === END: CÁC HÀM CHỨC NĂNG CHO MODULE 1 ===

    def start_analysis_thread(self):
        """
        Hàm mới: Chỉ phân tích 1 từ khóa từ ô Entry.
        """
        keyword = self.keyword_entry.get().strip()
        if not keyword:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập từ khóa cần phân tích.")
            return
            
        self.go_button['state'] = 'disabled'
        self.status_var.set(f"Bắt đầu phân tích từ khóa: '{keyword}'...")
        self.clear_all_results() 
        
        country_name = self.country_combo.get()
        region_code = self.COUNTRY_DATA.get(country_name)

        thread = threading.Thread(target=self.run_analysis_in_background, args=(keyword, region_code), daemon=True)
        thread.start()

    def run_analysis_in_background(self, keyword, region_code):
        """
        Hàm mới: Bỏ vòng lặp, chỉ gọi engine một lần.
        """
        logging.info(f'run_analysis_in_background keyword: {keyword}, region_code: {region_code}')
        try:
            self.session_cache.clear() # Xóa cache session cũ
            result = self.analysis_engine.full_analysis_for_keyword(keyword, region_code)
            self.session_cache[keyword] = result
            self.ui_queue.put({'module': 2, 'data': result}) # Gửi 1 result duy nhất
        except Exception as e:
            logging.error(f"LỖI KHÔNG XÁC ĐỊNH TRONG LUỒNG NỀN: {e}", exc_info=True)
            self.ui_queue.put({'module': 2, 'error': f"Lỗi nghiêm trọng: {e}"})

    def process_queue(self):
        try:
            message = self.ui_queue.get_nowait()
            module = message.get('module')

            if module == 1:
                if 'error' in message:
                    self.status_var.set(f"Lỗi Module 1: {message['error']}")
                    self.m1_search_button['state'] = 'normal'
                    self.m1_stop_button['state'] = 'disabled'
                else:
                    self.update_module1_grid(message.get('data', []))
            
            elif module == 2:
                self.clear_all_results()
                result_data = message.get('data')
                
                if 'error' in message:
                    self.status_var.set(f"Lỗi: {message['error']}")
                elif result_data:
                    # Cập nhật cả 2 bảng
                    self.update_module2_grid(result_data)
                    self.update_module3_grid(result_data.get('competitors', []))
                    self.status_var.set(f"Hoàn tất phân tích từ khóa: '{result_data.get('keyword')}'.")
                
                self.go_button['state'] = 'normal'
            elif module == 4:
                self.update_module4_grid(message.get('data', {}))

        except queue.Empty: 
            pass
        finally: 
            self.after(100, self.process_queue)
            
    def get_rating_icon(self, opportunity_score):
        if opportunity_score > 5.0: return "A+ (Mỏ Vàng)"
        if opportunity_score > 3.5: return "A (Tốt)"
        if opportunity_score > 2.0: return "B (Trung bình)"
        return "C (Thấp)"

    def update_module2_grid(self, result):
        """
        Hàm mới: Chỉ hiển thị 1 dòng kết quả duy nhất.
        """
        opportunity_score = result.get('opportunity_score', 0)
        self.treeview_m2.insert('', 'end', values=(
            result.get('keyword', 'N/A'), 
            f"{int(result.get('demand_score', 0)):,}", 
            result.get('supply_score', 0),
            f"{result.get('avg_views', 0):,.0f}", 
            f"{result.get('avg_engagement_rate', 0):.2%}",
            f"{result.get('competition_score', 0):.2f}", 
            f"{opportunity_score:.2f}", 
            self.get_rating_icon(opportunity_score)
        ))

    def update_module3_grid(self, competitors):
        """
        Sửa đổi: Thêm avatar url của kênh vào tags để sử dụng sau.
        """
        for i in self.treeview_m3.get_children(): self.treeview_m3.delete(i)
        for channel in competitors:
            stats = channel.get('statistics', {}); snippet = channel.get('snippet', {})
            channel_id = channel.get('id')
            # Lấy URL ảnh đại diện của kênh
            channel_thumbnail_url = snippet.get('thumbnails', {}).get('high', {}).get('url')
            
            # Lưu cả channel_id và channel_thumbnail_url vào tags
            self.treeview_m3.insert('', 'end', tags=(channel_id, channel_thumbnail_url), values=(
                f"https://www.youtube.com/channel/{channel_id}",
                snippet.get('title'),
                f"{int(stats.get('subscriberCount', 0)):,}", 
                f"{int(stats.get('videoCount', 0)):,}", 
                f"{int(stats.get('viewCount', 0)):,}",
                snippet.get('publishedAt', 'N/A')[:10],
                "Phân tích 🔬"
            ))

    # Hàm mới để tạo giao diện Module 4
    def create_module4_gui(self, parent, col_widths):
        self.style.configure("Module4.Treeview", rowheight=300) 
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        # Khung thông tin
        info_frame = ttk.Frame(parent, padding=10)
        info_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        self.m4_channel_name_var = tk.StringVar(value="Kênh đang phân tích: (chưa chọn)")
        self.m4_competitor_type_var = tk.StringVar(value="Phân loại: (chưa chọn)")
        ttk.Label(info_frame, textvariable=self.m4_channel_name_var, font=self.FONT_HEADING).pack(side="left")
        ttk.Label(info_frame, textvariable=self.m4_competitor_type_var, font=self.FONT_BOLD).pack(side="left", padx=20)

        # === THÊM CÁC NÚT EXPORT VÀO ĐÂY ===
        export_button_frame = ttk.Frame(info_frame)
        export_button_frame.pack(side="right", padx=10)
        ttk.Button(export_button_frame, text="Export Excel", command=lambda: self.export_m4_result('excel')).pack(side="left", padx=5)
        ttk.Button(export_button_frame, text="Export JSON", command=lambda: self.export_m4_result('json')).pack(side="left")
        # === KẾT THÚC PHẦN THÊM VÀO ===

        # Khung kết quả chính
        results_frame = ttk.Frame(parent, padding=10)
        results_frame.grid(row=1, column=0, sticky="nsew", padx=10)
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)

        cols_m4 = list(col_widths.keys())
        self.treeview_m4 = ttk.Treeview(results_frame, columns=cols_m4, show='headings', style="Module4.Treeview")
        for col, width in col_widths.items():
            self.treeview_m4.heading(col, text=col)
            self.treeview_m4.column(col, width=width, anchor='w' if col in ['Lỗ hổng N.Dung', 'Kế hoạch (Rule)', 'Kế hoạch (Gemini)'] else 'center')

        # Cấu hình cột
        cols_m4 = list(self.M4_COL_WIDTHS.keys())
        self.treeview_m4 = ttk.Treeview(results_frame, columns=cols_m4, show='headings', style="Module4.Treeview")
        for col, width in self.M4_COL_WIDTHS.items():
            self.treeview_m4.heading(col, text=col)
            self.treeview_m4.column(col, width=width, anchor='w' if col in ['Lỗ hổng N.Dung', 'Kế hoạch (Rule)', 'Kế hoạch (Gemini)'] else 'center')

        self.treeview_m4.column('Tần suất', width=100, anchor='center')
        self.treeview_m4.column('View TB', width=100, anchor='center')
        self.treeview_m4.column('Chiến lược', width=150, anchor='w')
        self.treeview_m4.column('Định dạng', width=80, anchor='center')
        self.treeview_m4.column('Gắn kết', width=120, anchor='center')
        self.treeview_m4.column('Lỗ hổng N.Dung', width=250, anchor='w')
        self.treeview_m4.column('Kế hoạch (Rule)', width=300, anchor='w')
        self.treeview_m4.column('Kế hoạch (Gemini)', width=450, anchor='w')

        vsb = ttk.Scrollbar(results_frame, orient="vertical", command=self.treeview_m4.yview)
        hsb = ttk.Scrollbar(results_frame, orient="horizontal", command=self.treeview_m4.xview)
        self.treeview_m4.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.treeview_m4.grid(row=0, column=0, sticky="nsew"); vsb.grid(row=0, column=1, sticky="ns"); hsb.grid(row=1, column=0, sticky="ew")

        # === THÊM KHỐI MÃ NÀY VÀO CUỐI HÀM ===
        # Tạo và gán menu chuột phải
        self.m4_context_menu = tk.Menu(parent, tearoff=0)
        self.m4_context_menu.add_command(label="Copy nội dung cột", state="disabled")
        self.m4_context_menu.add_separator()
        self.m4_context_menu.add_command(label="Export to Excel (.xlsx)", command=lambda: self.export_m4_result('excel'))
        self.m4_context_menu.add_command(label="Export to JSON (.json)", command=lambda: self.export_m4_result('json'))
        self.treeview_m4.bind("<Button-3>", self.show_m4_context_menu)

        # Khung ghi chú
        legend_frame = ttk.LabelFrame(parent, text="Chú giải tiêu chí", padding=10)
        legend_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=10)
        legend1 = "Tần suất: Rất cao (≥5 video/tuần) | Bình thường (2-4 video/tuần) | Thấp (<2 video/tuần)"
        legend2 = "Gắn kết: Rất cao (>5%) | Tốt (2-5%) | Ít tương tác (1-2%) | Chí mạng (<1%)"
        ttk.Label(legend_frame, text=legend1, font=self.FONT_NORMAL).pack(anchor='w')
        ttk.Label(legend_frame, text=legend2, font=self.FONT_NORMAL).pack(anchor='w')

    def on_competitor_right_click(self, event):
        """
        Sửa đổi: Mở link kênh và hiển thị ảnh đại diện của kênh (miễn phí quota).
        """
        item_id = self.treeview_m3.identify_row(event.y)
        if not item_id: return
        
        self.treeview_m3.selection_set(item_id)
        self.treeview_m3.focus(item_id)

        item_tags = self.treeview_m3.item(item_id)['tags']
        item_values = self.treeview_m3.item(item_id)['values']
        
        channel_url = item_values[0]
        # URL ảnh đại diện của kênh được lưu ở tag thứ hai
        channel_thumbnail_url = item_tags[1] if len(item_tags) > 1 else None
    
        if channel_url and 'http' in channel_url:
            webbrowser.open_new_tab(channel_url)
        if channel_thumbnail_url:
            self.show_thumbnail_window(channel_thumbnail_url)

    def show_thumbnail_window(self, url):
        top = tk.Toplevel(self); top.title("Xem Thumbnail"); top.geometry("480x360")
        try:
            with urllib.request.urlopen(url) as u: raw_data = u.read()
            image = Image.open(BytesIO(raw_data)); photo = ImageTk.PhotoImage(image)
            label = tk.Label(top, image=photo); label.image = photo; label.pack()
        except Exception as e:
            logging.error(f"Lỗi tải ảnh thumbnail: {e}"); label = tk.Label(top, text="Không thể tải ảnh."); label.pack()

    def sort_treeview(self, treeview, col, reverse):
        def convert(value):
            try: return int(str(value).replace(',', ''))
            except (ValueError, AttributeError):
                try: 
                    return datetime.strptime(str(value), '%Y-%m-%d')
                except ValueError:
                    return str(value).lower()
        
        data = [(convert(treeview.set(item, col)), item) for item in treeview.get_children('')]
        data.sort(key=lambda t: t[0], reverse=reverse)
        for index, (val, item) in enumerate(data): treeview.move(item, '', index)
        treeview.heading(col, command=lambda: self.sort_treeview(treeview, col, not reverse))

        # === START: MODULE 4 FUNCTIONS ===
    def on_competitor_select(self, event):
        """
        Khi người dùng chọn một đối thủ ở Module 3, kích hoạt phân tích cho Module 4.
        """
        selected_item = self.treeview_m3.focus()
        if not selected_item: return

        channel_id = self.treeview_m3.item(selected_item, 'tags')[0]

        self.status_var.set(f"Bắt đầu phân tích chuyên sâu đối thủ (ID: {channel_id})...")
        
        # === XÓA DÒNG LỆNH NÀY ĐI ===
        # self.clear_module4_results() 
        # ============================
        
        notebook = self.treeview_m3.winfo_toplevel().nametowidget('.!frame.!notebook')
        notebook.select(2) # Module 4 giờ ở index 2

        market_keywords = list(self.session_cache.keys())
        if not market_keywords:
            messagebox.showwarning("Thiếu dữ liệu", "Vui lòng phân tích ít nhất một từ khóa ở Module 2 để có dữ liệu thị trường cho việc phân tích Content Gap.")
            self.status_var.set("Sẵn sàng.")
            return

        thread = threading.Thread(
            target=self.run_m4_analysis_in_background,
            args=(channel_id, market_keywords),
            daemon=True
        )
        thread.start()

    def run_m4_analysis_in_background(self, channel_id, market_keywords):
        """
        Luồng nền để chạy phân tích M4 và gọi Gemini AI.
        """
        try:
            # Lấy dữ liệu phân tích từ engine
            analysis_data = self.analysis_engine.analyze_competitor_for_m4(channel_id, market_keywords)
            
            # Nếu có lỗi từ engine, hiển thị và dừng lại
            if 'error' in analysis_data:
                self.ui_queue.put({'module': 4, 'data': analysis_data})
                return

            # Gọi Gemini AI để lấy kế hoạch
            if self.gemini_manager:
                gemini_plan = self.gemini_manager.get_overtake_plan(analysis_data, market_keywords)
                analysis_data['gemini_plan'] = gemini_plan
            else:
                analysis_data['gemini_plan'] = "Gemini Manager chưa được cấu hình. Vui lòng kiểm tra file gemini.key."

            # Đưa kết quả cuối cùng vào queue
            self.ui_queue.put({'module': 4, 'data': analysis_data})

        except Exception as e:
            logging.error(f"LỖI TRONG LUỒNG M4: {e}", exc_info=True)
            self.ui_queue.put({'module': 4, 'data': {'error': f"Lỗi nghiêm trọng: {e}"}})

    def update_module4_grid(self, data):
        """
        Cập nhật giao diện Module 4 với dữ liệu phân tích.
        """
        self.last_m4_analysis_data = data
        self.clear_module4_results()
        if 'error' in data:
            self.m4_channel_name_var.set(f"Lỗi: {data['error']}")
            self.status_var.set("Phân tích chuyên sâu thất bại.")
            return
            
        # Cập nhật các label
        self.m4_channel_name_var.set(f"Kênh đang phân tích: {data.get('channel_title', 'N/A')}")
        self.m4_competitor_type_var.set(f"Phân loại: {data.get('competitor_type_text', 'N/A')}")
        
        # Wrap text cho các cột dài
        wrapped_gaps = textwrap.fill(", ".join(data.get('content_gaps', [])), width=40)
        wrapped_plan = textwrap.fill(data.get('action_plan_text', ''), width=50)
        gemini_raw_text = data.get('gemini_plan', '')
        ui_gemini_text = gemini_raw_text.replace('**', '').replace('*', '•').replace('#', '')
        wrapped_gemini = textwrap.fill(ui_gemini_text, width=70)

        # Chèn dữ liệu vào Treeview
        self.treeview_m4.insert('', 'end', values=(
            data.get('upload_frequency_text', 'N/A'),
            data.get('avg_view_rate_text', 'N/A'),
            data.get('strategy_text', 'N/A'),
            data.get('avg_duration_text', 'N/A'),
            data.get('engagement_text', 'N/A'),
            wrapped_gaps,
            wrapped_plan,
            wrapped_gemini
        ))
        self.status_var.set(f"Hoàn tất phân tích chuyên sâu kênh '{data.get('channel_title', 'N/A')}'.")

    def clear_module4_results(self):
        self.m4_channel_name_var.set("Kênh đang phân tích: (chưa chọn)")
        self.m4_competitor_type_var.set("Phân loại: (chưa chọn)")
        for i in self.treeview_m4.get_children():
            self.treeview_m4.delete(i)

    def create_widgets(self):
        """
        Hàm mới: Chỉ tạo 3 tab, gộp M2 và M3.
        Sửa đổi: Truyền trực tiếp các dictionary độ rộng cột.
        """
        main_frame = ttk.Frame(self); main_frame.pack(expand=True, fill='both')
        main_frame.rowconfigure(0, weight=1); main_frame.columnconfigure(0, weight=1)
        
        notebook = ttk.Notebook(main_frame, name="!notebook")
        notebook.grid(row=0, column=0, sticky="nsew", padx=10, pady=5)
        
        self.status_var = tk.StringVar(value="Sẵn sàng")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor='w', padding=5, font=self.FONT_NORMAL)
        status_bar.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 5))
        
        tab1 = ttk.Frame(notebook)
        tab2 = ttk.Frame(notebook)
        tab4 = ttk.Frame(notebook)
        
        notebook.add(tab1, text='Module 1 - Gợi ý Từ khóa')
        notebook.add(tab2, text='Module 2 - Phân tích & Đối thủ')
        notebook.add(tab4, text='Module 4 - Kế hoạch Vượt mặt')
        
        # === SỬA ĐỔI TẠI ĐÂY ===
        self.create_module1_gui(tab1, self.M1_COL_WIDTHS)
        self.create_module2_gui(tab2, self.M2_COL_WIDTHS, self.M3_COL_WIDTHS)
        self.create_module4_gui(tab4, self.M4_COL_WIDTHS)

    # === START: TRIỂN KHAI GIAO DIỆN MODULE 1 ===
    def create_module1_gui(self, parent, col_widths):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        # --- Khung điều khiển ---
        controls_frame = ttk.LabelFrame(parent, text="Bảng điều khiển", padding=10)
        controls_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)

        # Radar
        ttk.Label(controls_frame, text="Radar:", font=self.FONT_BOLD).pack(side="left", padx=(0, 5))
        radar_options = ["Từ khóa Vua (Liên quan)", "Từ khóa Mới nổi (Xu hướng)", "Từ khóa Ngách (Chuyên sâu)"]
        self.m1_radar_combo = ttk.Combobox(controls_frame, values=radar_options, state="readonly", font=self.FONT_NORMAL, width=25)
        self.m1_radar_combo.pack(side="left", padx=5)
        self.m1_radar_combo.current(0)
        
        # Seed Keyword
        ttk.Label(controls_frame, text="Chủ đề:", font=self.FONT_BOLD).pack(side="left", padx=(10, 5))
        self.m1_seed_keyword_entry = ttk.Entry(controls_frame, font=self.FONT_NORMAL, width=40)
        self.m1_seed_keyword_entry.pack(side="left", padx=5, fill="x", expand=True)

        # Country
        ttk.Label(controls_frame, text="Quốc gia:", font=self.FONT_BOLD).pack(side="left", padx=(10, 5))
        country_options = list(self.COUNTRY_DATA.keys())
        self.m1_country_combo = ttk.Combobox(controls_frame, values=country_options, state="readonly", font=self.FONT_NORMAL, width=15)
        self.m1_country_combo.pack(side="left", padx=5)
        self.m1_country_combo.current(0)

        # Nút Search và Stop
        self.m1_search_button = ttk.Button(controls_frame, text="Search-Module1", style="TButton", command=self.start_keyword_discovery_thread)
        self.m1_search_button.pack(side="left", padx=(10, 5))
        
        self.m1_stop_button = ttk.Button(controls_frame, text="Stop", style="TButton", command=self.stop_keyword_discovery, state="disabled")
        self.m1_stop_button.pack(side="left", padx=5)

        # --- Khung kết quả ---
        results_frame = ttk.Frame(parent)
        results_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=(0, 5))
        results_frame.rowconfigure(0, weight=1)
        results_frame.columnconfigure(0, weight=1)

        cols_m1 = list(col_widths.keys())
        self.treeview_m1 = ttk.Treeview(results_frame, columns=cols_m1, show='headings')
        for col, width in col_widths.items():
            self.treeview_m1.heading(col, text=col, command=lambda c=col: self.sort_treeview(self.treeview_m1, c, False))
            self.treeview_m1.column(col, width=width, anchor='center' if col != 'Keyword' else 'w')

        # Định nghĩa các cột
        self.treeview_m1.heading('Rank', text='STT', command=lambda: self.sort_treeview(self.treeview_m1, 'Rank', False))
        self.treeview_m1.heading('Keyword', text='Từ khóa gợi ý', command=lambda: self.sort_treeview(self.treeview_m1, 'Keyword', False))
        self.treeview_m1.heading('Word count', text='Số từ', command=lambda: self.sort_treeview(self.treeview_m1, 'Word count', False))
        self.treeview_m1.heading('Character count', text='Số ký tự', command=lambda: self.sort_treeview(self.treeview_m1, 'Character count', False))

        # Căn chỉnh và độ rộng cột
        self.treeview_m1.column('Rank', width=30, anchor='center')
        self.treeview_m1.column('Keyword', width=900, anchor='w')
        self.treeview_m1.column('Word count', width=100, anchor='center')
        self.treeview_m1.column('Character count', width=100, anchor='center')

        # Scrollbar
        scrollbar_m1 = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.treeview_m1.yview)
        self.treeview_m1.configure(yscrollcommand=scrollbar_m1.set)

        self.treeview_m1.grid(row=0, column=0, sticky="nsew")
        scrollbar_m1.grid(row=0, column=1, sticky="ns")

        # === START: ĐOẠN MÃ THÊM VÀO ===
        # Tạo menu chuột phải
        self.m1_context_menu = tk.Menu(parent, tearoff=0)
        self.m1_context_menu.add_command(
            label="Copy từ khóa đã chọn sang Module 2",
            command=self.copy_m1_keywords_to_m2
        )

        # Gán sự kiện chuột phải cho Treeview
        self.treeview_m1.bind("<Double-1>", self.on_m1_double_click)

    def create_module2_gui(self, parent, m2_col_widths, m3_col_widths):
        """
        HÀM VIẾT LẠI HOÀN TOÀN: Giao diện gộp M2 và M3.
        Sửa lỗi: Tất cả widget con phải có `parent` là widget cha, không phải `self`.
        """
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(2, weight=1)

        controls_frame = ttk.Frame(parent, padding=20)
        controls_frame.grid(row=0, column=0, sticky="ew", padx=10)

        ttk.Label(controls_frame, text="Nhập từ khóa:", font=self.FONT_BOLD).pack(side="left", padx=(0, 5))
        self.keyword_entry = ttk.Entry(controls_frame, font=self.FONT_NORMAL, width=50)
        self.keyword_entry.pack(side="left", padx=5)

        ttk.Label(controls_frame, text="Quốc gia:", font=self.FONT_NORMAL).pack(side="left", padx=(10, 5))
        country_options = list(self.COUNTRY_DATA.keys())
        self.country_combo = ttk.Combobox(controls_frame, values=country_options, state="readonly", font=self.FONT_NORMAL, width=15)
        self.country_combo.pack(side="left", padx=5)
        self.country_combo.current(0)

        self.go_button = ttk.Button(controls_frame, text="Phân tích", style="TButton", command=self.start_analysis_thread)
        self.go_button.pack(side="left", padx=10)

        # --- Bảng 1: Kết quả phân tích từ khóa ---
        kw_frame = ttk.LabelFrame(parent, text="Kết quả Phân tích Từ khóa", padding=5) # SỬA LỖI Ở ĐÂY
        kw_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=10)
        kw_frame.columnconfigure(0, weight=1)

        cols_m2 = list(m2_col_widths.keys())
        self.treeview_m2 = ttk.Treeview(kw_frame, columns=cols_m2, show='headings', height=1)
        for col, width in m2_col_widths.items():
            self.treeview_m2.heading(col, text=col)
            self.treeview_m2.column(col, width=width, anchor='w' if col == 'Keyword' else 'center')
        self.treeview_m2.pack(expand=True, fill="x")

        # --- Bảng 2: Kết quả phân tích đối thủ ---
        competitor_frame = ttk.LabelFrame(parent, text="Top 5 Đối thủ Liên quan", padding=10)
        competitor_frame.grid(row=2, column=0, sticky="nsew", padx=10)
        competitor_frame.columnconfigure(0, weight=1)
        competitor_frame.rowconfigure(0, weight=1)

        cols_m3 = list(m3_col_widths.keys())
        self.treeview_m3 = ttk.Treeview(competitor_frame, columns=cols_m3, show='headings')
        for col, width in m3_col_widths.items():
            self.treeview_m3.heading(col, text=col)
            self.treeview_m3.column(col, width=width, anchor='w' if col == 'Tên kênh' else 'center')

        
        scrollbar_m3 = ttk.Scrollbar(competitor_frame, orient=tk.VERTICAL, command=self.treeview_m3.yview)
        self.treeview_m3.configure(yscrollcommand=scrollbar_m3.set)
        self.treeview_m3.grid(row=0, column=0, sticky="nsew")
        scrollbar_m3.grid(row=0, column=1, sticky="ns")

        self.treeview_m3.bind("<Button-1>", self.on_m3_click)
        self.treeview_m3.bind("<Button-3>", self.on_competitor_right_click)

    def on_m3_click(self, event):
        """
        Hàm mới: Xử lý click vào "button" Phân tích giả trong Module 3.
        """
        region = self.treeview_m3.identify_region(event.x, event.y)
        if region != "cell":
            return
            
        column_id = self.treeview_m3.identify_column(event.x)
        # Cột cuối cùng là cột 'Phân tích'
        if column_id == f"#{len(self.treeview_m3['columns'])}":
            selected_item = self.treeview_m3.focus()
            if selected_item:
                self.on_competitor_select(event)

    def on_closing(self):
        # Thêm sự kiện dừng trước khi đóng để tránh luồng zombie
        self.m1_stop_event.set()
        if messagebox.askokcancel("Thoát", "Bạn có muốn thoát chương trình?"): 
            self.db_manager.close(); self.destroy()

    def show_m4_context_menu(self, event):
        """Hiển thị menu chuột phải cho Module 4"""
        if self.treeview_m4.selection():
            # Kích hoạt các menu dựa trên cột được click
            col_id = self.treeview_m4.identify_column(event.x)
            col_index = int(col_id.replace('#', '')) - 1
            
            # Chỉ cho phép copy các cột 6, 7, 8 (index 5, 6, 7)
            if col_index in [5, 6, 7]:
                self.m4_context_menu.entryconfigure("Copy nội dung cột", state="normal", command=lambda: self.copy_m4_column(col_index))
            else:
                self.m4_context_menu.entryconfigure("Copy nội dung cột", state="disabled")

            self.m4_context_menu.post(event.x_root, event.y_root)

    def copy_m4_column(self, col_index):
        """Copy nội dung của một cột cụ thể trong Module 4."""
        item = self.treeview_m4.focus()
        if not item: return
        
        content = self.treeview_m4.item(item, 'values')[col_index]
        self.clipboard_clear()
        self.clipboard_append(content)
        self.status_var.set(f"Đã copy nội dung cột #{col_index + 1} vào clipboard.")

    def export_m4_result(self, export_format):
        """Xuất kết quả của Module 4 ra file Excel hoặc JSON."""
        if not self.treeview_m4.get_children():
            messagebox.showwarning("Không có dữ liệu", "Không có dữ liệu để xuất.")
            return

        os.makedirs("Action", exist_ok=True)
        channel_name = self.m4_channel_name_var.get().replace("Kênh đang phân tích: ", "").strip()
        
        # Lấy dữ liệu thô đã lưu từ lần phân tích gần nhất
        full_data = self.last_m4_analysis_data 
        if not full_data:
            messagebox.showerror("Lỗi", "Không tìm thấy dữ liệu phân tích để xuất.")
            return

        # Dữ liệu sạch để export
        export_data = {
            'Tần suất': full_data.get('upload_frequency_text', 'N/A'),
            'View TB': full_data.get('avg_view_rate_text', 'N/A'),
            'Chiến lược': full_data.get('strategy_text', 'N/A'),
            'Định dạng': full_data.get('avg_duration_text', 'N/A'),
            'Gắn kết': full_data.get('engagement_text', 'N/A'),
            'Lỗ hổng N.Dung': ", ".join(full_data.get('content_gaps', [])),
            'Kế hoạch (Rule)': full_data.get('action_plan_text', ''),
            'Kế hoạch (Gemini)': full_data.get('gemini_plan', '') 
        }

        base_filename = f"{self.current_selected_keyword_for_analysis}_{channel_name}".replace(" ", "_").replace('"', '')
        
        try:
            if export_format == 'excel':
                filepath = os.path.join("Action", f"{base_filename}.xlsx")
                df = pd.DataFrame([export_data])
                df.to_excel(filepath, index=False)
            
            elif export_format == 'json':
                filepath = os.path.join("Action", f"{base_filename}.json")
                with open(filepath, 'w', encoding='utf-8') as f:
                    # SỬA LỖI: dùng đúng biến 'export_data'
                    json.dump(export_data, f, ensure_ascii=False, indent=4)
            
            messagebox.showinfo("Thành công", f"Đã xuất thành công kết quả ra file:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể xuất file: {e}")

    def clear_all_results(self): self.clear_results()
    def clear_keywords_text(self): self.text_keywords.delete("1.0", tk.END); self.clear_results(); self.status_var.set("Sẵn sàng")
    def clear_results(self):
        for i in self.treeview_m2.get_children(): self.treeview_m2.delete(i)
        for i in self.treeview_m3.get_children(): self.treeview_m3.delete(i)

    def load_initial_data(self):
        logging.info("Tải dữ liệu khởi tạo..."); 
        self.status_var.set("Đang tải dữ liệu gần đây...")
        
        # Chỉ lấy 1 từ khóa gần nhất
        recent_keywords = self.db_manager.get_recent_keywords(limit=1)
        
        if recent_keywords:
            keyword_to_load = recent_keywords[0]
            # Cập nhật vào ô Entry mới
            self.keyword_entry.delete(0, tk.END)
            self.keyword_entry.insert(0, keyword_to_load)
            # Tự động chạy phân tích cho từ khóa đó
            self.start_analysis_thread()
        else:
            self.status_var.set("Sẵn sàng. Không có dữ liệu cũ.")
            logging.info("Không tìm thấy dữ liệu cũ.")
            
if __name__ == "__main__":
    # Cấu hình logging cơ bản để bắt lỗi ngay cả khi app chưa khởi tạo
    log_file = 'app_activity.log'
    logging.basicConfig(level=logging.INFO, 
                        format='%(asctime)s - %(levelname)s - %(message)s', 
                        handlers=[logging.FileHandler(log_file, mode='w', encoding='utf-8'), 
                                  logging.StreamHandler(sys.stdout)])

    try:
        # Khởi chạy ứng dụng chính
        app = SEOApp()
        app.mainloop()

    except Exception as e:
        # Nếu có bất kỳ lỗi nào trong quá trình khởi tạo SEOApp, nó sẽ bị bắt ở đây
        logging.critical(f"LỖI KHỞI ĐỘNG NGHIÊM TRỌNG: {e}", exc_info=True)
        
        # Hiển thị hộp thoại báo lỗi cho người dùng
        import tkinter as tk
        from tkinter import messagebox
        
        root = tk.Tk()
        root.withdraw() # Ẩn cửa sổ gốc không cần thiết
        messagebox.showerror(
            "Lỗi Khởi Động Nghiêm Trọng",
            f"Không thể khởi chạy ứng dụng.\n\nLỗi: {e}\n\nVui lòng kiểm tra file 'app_activity.log' để biết chi tiết."
        )