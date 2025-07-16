# Core/gemini_manager.py
import google.generativeai as genai
import logging

class GeminiManager:
    def __init__(self, api_key):
        if not api_key:
            raise ValueError("Gemini API key is required.")
        self.api_key = api_key
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash') # Sử dụng model Flash cho tốc độ và hiệu quả
        logging.info("Gemini Manager initialized.")

    def get_overtake_plan(self, competitor_data, market_keywords):
        """
        Gửi prompt đến Gemini AI để lấy về kế hoạch vượt mặt đối thủ.
        """
        try:
            logging.info(f"Generating Gemini overtake plan for channel: {competitor_data.get('channel_title')}")
            
            # Xây dựng một prompt chi tiết và rõ ràng
            prompt = f"""
            Bạn là một chuyên gia chiến lược YouTube hàng đầu với 10 năm kinh nghiệm.
            Dựa trên các dữ liệu phân tích chi tiết về đối thủ cạnh tranh và thị trường dưới đây, hãy đưa ra một kế hoạch hành động TOÀN DIỆN và CỤ THỂ để một kênh YouTube mới có thể vượt mặt họ.

            **DỮ LIỆU PHÂN TÍCH:**

            **1. Đối thủ cạnh tranh cần phân tích:**
            - Tên kênh: {competitor_data.get('channel_title')}
            - Lượng Subscribers: {competitor_data.get('subs_count'):,}
            - Tổng số video: {competitor_data.get('video_count')}
            - Tuổi kênh (ngày tạo): {competitor_data.get('published_at')}
            - Tần suất đăng bài: {competitor_data.get('upload_frequency_text')} ({competitor_data.get('videos_per_week'):.1f} video/tuần)
            - Tỉ lệ view trung bình: {competitor_data.get('avg_views'):,}/video
            - Mức độ gắn kết cộng đồng: {competitor_data.get('engagement_text')} ({competitor_data.get('engagement_rate'):.2%})
            - Định dạng video chủ đạo: Video dài khoảng {competitor_data.get('avg_duration_text')}

            **2. Phân tích thị trường:**
            - Các từ khóa mục tiêu của tôi (thị trường đang có nhu cầu): {', '.join(market_keywords)}
            - Các chủ đề vàng mà đối thủ đã BỎ LỠ (Content Gaps): {', '.join(competitor_data.get('content_gaps', ['Không có']))}

            **YÊU CẦU KẾ HOẠCH HÀNH ĐỘNG:**
            Hãy trả lời bằng tiếng Việt, chia các mục rõ ràng và đưa ra các đề xuất cụ thể, có thể hành động ngay.
            
            1.  **Định vị Kênh & Tên gọi:** Đề xuất một tên kênh mới hấp dẫn và một câu định vị (slogan) để tạo sự khác biệt.
            2.  **Chiến lược nội dung:** Dựa vào điểm yếu và "Content Gaps" của đối thủ, tôi nên tập trung vào loại nội dung gì?
            3.  **Tối ưu SEO (SEO Blueprint):**
                - Đề xuất 3-5 từ khóa SEO chính.
                - Đề xuất 5-7 từ khóa phụ (long-tail keywords).
                - Đề xuất một bộ tags mặc định cho kênh.
            4.  **Định dạng và Lịch trình:**
                - Độ dài video lý tưởng nên là bao nhiêu phút?
                - Lịch đăng bài tối ưu (mỗi tuần mấy video, vào những ngày nào)?
            5.  **Lời khuyên đặc biệt:** Một lời khuyên "đắt giá" để tạo ra sự đột phá so với đối thủ này.
            """

            response = self.model.generate_content(prompt)
            logging.info("Successfully received response from Gemini.")
            return response.text

        except Exception as e:
            logging.error(f"Error calling Gemini API: {e}", exc_info=True)
            return f"LỖI: Không thể kết nối hoặc xử lý yêu cầu từ Gemini AI. Chi tiết: {e}"