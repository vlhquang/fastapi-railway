# Core/analysis_engine.py
import logging
import math
import re
from datetime import datetime, timedelta
from collections import Counter
from isodate import parse_duration

class AnalysisEngineAPI:
    def __init__(self, api_manager, db_manager):
        self.api = api_manager
        self.db = db_manager
        self.channel_cache = {}
        self.VIETNAMESE_STOP_WORDS = set(['và', 'của', 'là', 'cho', 'có', 'không', 'được', 'để', 'một', 'trong', 'với', 'khi', 'thì', 'từ', 'đã', 'sẽ', 'cũng', 'như', 'tại', 'ra', 'vào', 'đến', 'làm', 'cách', 'video', 'hướng', 'dẫn', 'review', 'top', 'mới', 'nhất'])

    # Sửa đổi để xử lý regionCode rỗng
    def discover_keywords(self, seed_keyword, region_code, mode):
        params = {
            'part': "id,snippet", 'q': seed_keyword, 'type': "video", 'maxResults': 50
        }
        if region_code: # CHỈ THÊM NẾU CÓ GIÁ TRỊ
            params['regionCode'] = region_code
            
        if mode == 'relevance':
            params['order'] = 'relevance'
        elif mode == 'date':
            params['order'] = 'date'
        elif mode == 'niche':
            params['order'] = 'relevance'
            params['videoDuration'] = 'long'
            params['videoDefinition'] = 'high'
        
        # if stop_event.is_set(): return []
        search_results = self.api.search(**params)
        if not search_results: return []

        video_ids = [item['id']['videoId'] for item in search_results if item['id'].get('kind') == 'youtube#video']
        video_details = self.api.get_video_details(video_ids)
        all_tags, all_titles_phrases = [], []

        for video in video_details:
            # if stop_event.is_set(): return []
            snippet = video.get('snippet', {}); tags = snippet.get('tags', []); title = video.get('title', '').lower()
            if tags: all_tags.extend([tag.lower() for tag in tags])
            clean_title = re.sub(r'[^\w\s]', '', title)
            title_words = [word for word in clean_title.split() if word not in self.VIETNAMESE_STOP_WORDS]
            all_titles_phrases.extend([' '.join(title_words[i:i+n]) for n in [2, 3, 4] for i in range(len(title_words)-n+1)])

        tag_counts, phrase_counts = Counter(all_tags), Counter(all_titles_phrases)
        combined_scores = Counter()
        for keyword, count in tag_counts.items(): combined_scores[keyword] += count * 1.5 
        for keyword, count in phrase_counts.items(): combined_scores[keyword] += count

        final_keywords = []
        for keyword, score in combined_scores.most_common(300): 
            word_count = len(keyword.split())
            if 1 < word_count < 7 and len(keyword) > 5 and not any(char in keyword for char in '|\\/#*[]"'):
                final_keywords.append({"keyword": keyword, "word_count": word_count, "char_count": len(keyword), "score": score})
                if len(final_keywords) >= 150: break
        return sorted(final_keywords, key=lambda k: k['score'], reverse=True)

    def full_analysis_for_keyword(self, keyword, region_code):
        logging.info(f'full_analysis_for_keyword keyword: {keyword}, region_code: {region_code}')
        """
        Thực hiện phân tích đầy đủ cho 1 TỪ KHÓA DUY NHẤT.
        Đã loại bỏ các chỉ số 7 ngày.
        """
        # 1. Kiểm tra cache trước
        cached_result = self.db.get_analysis_result(keyword)
        if cached_result:
            # Lấy danh sách đối thủ từ cache
            cached_result['competitors'] = self.db.get_competitors(keyword)
            return cached_result

        # 2. Phân tích nếu không có cache

        logging.info(f"No valid cache for '{keyword}', performing full analysis.")
        demand_30d = self._calculate_demand(keyword, region_code, 30)
        supply_30d = self._calculate_supply(keyword, region_code, 30)
        competition_metrics = self._calculate_advanced_competition(demand_30d['video_details'])
        
        word_count = len(keyword.split())
        niche_factor = 1 + max(0, word_count - 2) * 0.1
        opportunity_score = (math.log10(demand_30d['score'] + 1) / competition_metrics['score']) * niche_factor if competition_metrics['score'] > 0 else 0
        
        # === THAY ĐỔI: Chỉ tìm 5 đối thủ ===
        competitors = self.find_competitors(keyword, region_code, limit=5)
        
        result = {
            "keyword": keyword, 
            "demand_score": demand_30d['score'], 
            "total_views": demand_30d['total_views'], 
            "supply_score": supply_30d['score'],
            "avg_views": competition_metrics['avg_views'], 
            "avg_engagement_rate": competition_metrics['avg_engagement_rate'], 
            "competition_score": competition_metrics['score'], 
            "opportunity_score": opportunity_score, 
            "competitors": competitors
        }
        
        # Lưu kết quả mới vào DB
        self.db.save_analysis_result(result)
        self.db.save_competitors(keyword, competitors)
        return result

    def find_competitors(self, keyword, region_code, limit=5):
        """
        Tối ưu triệt để: Bỏ hoàn toàn chức năng tìm video nổi bật.
        """
        logging.info(f'find_competitors keyword: {keyword}, region_code: {region_code}')
        params = {'part': "snippet", 'q': keyword, 'type': "video", 'maxResults': 50, 'order': 'relevance'}
        if region_code: params['regionCode'] = region_code
            
        videos = self.api.search(**params)
        if not videos: return []
        
        channel_ids = [v['snippet']['channelId'] for v in videos]
        channel_counts = Counter(channel_ids)
        top_channel_ids = [cid for cid, count in channel_counts.most_common(limit)]
        
        if not top_channel_ids: return []
        
        # Sử dụng cache để tránh gọi API thừa
        channels_to_fetch = [cid for cid in top_channel_ids if cid not in self.channel_cache]
        if channels_to_fetch:
            logging.info(f"Fetching details for {len(channels_to_fetch)} new channels.")
            new_channel_details = self.api.get_channel_details(channels_to_fetch)
            for channel in new_channel_details:
                self.channel_cache[channel['id']] = channel
        
        channel_details = [self.channel_cache[cid] for cid in top_channel_ids if cid in self.channel_cache]
        return sorted(channel_details, key=lambda x: int(x.get('statistics', {}).get('subscriberCount', 0)), reverse=True)

    # Sửa đổi để xử lý regionCode rỗng
    def _calculate_demand(self, keyword, region_code, timeframe_days, limit=50):
        params = {
            'part': "id,snippet", 'q': keyword, 'type': "video", 
            'maxResults': limit, 'order': 'viewCount', 
            'publishedAfter': (datetime.utcnow() - timedelta(days=timeframe_days)).isoformat("T") + "Z"
        }
        if region_code: # CHỈ THÊM NẾU CÓ GIÁ TRỊ
            params['regionCode'] = region_code
            
        videos = self.api.search(**params)
        if not videos: return {'score': 0, 'total_views': 0, 'video_details': []}
        video_ids = [item['id']['videoId'] for item in videos if item['id'].get('kind') == 'youtube#video']
        video_details = self.api.get_video_details(video_ids)
        total_views, total_likes, total_comments = 0, 0, 0
        for video in video_details:
            stats = video.get('statistics', {})
            total_views += int(stats.get('viewCount', 0))
            total_likes += int(stats.get('likeCount', 0))
            total_comments += int(stats.get('commentCount', 0))
        return {'score': (total_views * 1) + (total_likes * 2) + (total_comments * 3), 'total_views': total_views, 'video_details': video_details}

    # Sửa đổi để xử lý regionCode rỗng
    def _calculate_supply(self, keyword, region_code, timeframe_days, limit=50):
        params = {
            'part': "id", 'q': keyword, 'type': "video", 'maxResults': limit, 'order': 'date',
            'publishedAfter': (datetime.utcnow() - timedelta(days=timeframe_days)).isoformat("T") + "Z"
        }
        if region_code: # CHỈ THÊM NẾU CÓ GIÁ TRỊ
            params['regionCode'] = region_code
        
        videos = self.api.search(**params)
        return {'score': len(videos)}
        
    def _calculate_advanced_competition(self, video_details_list):
        if not video_details_list:
            return {'score': 1, 'avg_views': 0, 'avg_engagement_rate': 0}

        total_views, total_engagement_rate, engaged_videos_count = 0, 0, 0
        channel_ids = [v['snippet']['channelId'] for v in video_details_list]
        for v in video_details_list:
            stats = v.get('statistics', {}); views = int(stats.get('viewCount', 0)); likes = int(stats.get('likeCount', 0)); comments = int(stats.get('commentCount', 0))
            total_views += views
            if views > 0:
                total_engagement_rate += (likes + comments) / views; engaged_videos_count += 1
        
        num_videos = len(video_details_list)
        avg_views = total_views / num_videos if num_videos > 0 else 0
        avg_engagement_rate = total_engagement_rate / engaged_videos_count if engaged_videos_count > 0 else 0
        content_competition_score = math.log10(avg_views + 1) * (1 + avg_engagement_rate) + 1

        unique_channel_ids = list(set(channel_ids))
        channel_details = self.api.get_channel_details(unique_channel_ids)
        
        total_subs, valid_sub_channels = 0, 0
        for ch in channel_details:
            subs = int(ch.get('statistics', {}).get('subscriberCount', 0))
            if subs > 0: total_subs += subs; valid_sub_channels += 1
        avg_subs = total_subs / valid_sub_channels if valid_sub_channels > 0 else 0
        authority_score = math.log10(avg_subs + 1)
        saturation_score = len(video_details_list) / len(unique_channel_ids) if unique_channel_ids else 1

        w1, w2, w3 = 0.4, 0.3, 0.3
        final_competition_score = (w1 * content_competition_score) + (w2 * authority_score) + (w3 * saturation_score)
        
        return {'score': final_competition_score, 'avg_views': avg_views, 'avg_engagement_rate': avg_engagement_rate}

    # Sửa đổi để xử lý regionCode rỗng
    def find_competitors(self, keyword, region_code, limit=20):
        params = {
            'part': "snippet", 'q': keyword, 'type': "video", 'maxResults': 50, 'order': 'relevance'
        }
        if region_code:
            params['regionCode'] = region_code
            
        videos = self.api.search(**params)
        if not videos: return []
        
        channel_ids = [v['snippet']['channelId'] for v in videos]
        channel_counts = Counter(channel_ids)
        top_channel_ids = [cid for cid, count in channel_counts.most_common(limit)]
        
        if not top_channel_ids: return []
        
        # Chỉ lấy thông tin của các kênh chưa có trong cache
        channels_to_fetch = [cid for cid in top_channel_ids if cid not in self.channel_cache]
        if channels_to_fetch:
            logging.info(f"Fetching details for {len(channels_to_fetch)} new channels.")
            new_channel_details = self.api.get_channel_details(channels_to_fetch)
            for channel in new_channel_details:
                self.channel_cache[channel['id']] = channel # Lưu vào cache
        
        # Lấy thông tin chi tiết từ cache
        channel_details = [self.channel_cache[cid] for cid in top_channel_ids if cid in self.channel_cache]

        for channel in channel_details:
            # Chỉ tìm video nổi bật nếu kênh chưa có thông tin này trong cache
            if 'top_video' not in channel:
                logging.info(f"Finding top video for new channel: {channel['snippet']['title']}")
                top_video_search = self.api.search(part="snippet", q="", channelId=channel['id'], order='viewCount', type='video', maxResults=1)
                if top_video_search:
                    top_video_details = self.api.get_video_details([top_video_search[0]['id']['videoId']])
                    if top_video_details:
                        channel['top_video'] = top_video_details[0]
                else:
                    channel['top_video'] = {} # Đánh dấu đã tìm để không tìm lại
        
        return sorted(channel_details, key=lambda x: int(x.get('statistics', {}).get('subscriberCount', 0)), reverse=True)

    def analyze_competitor_for_m4(self, channel_id, market_keywords):
        """
        Phiên bản tối ưu quota: Content Gap được ƯỚC TÍNH, không dùng API.
        """
        logging.info(f'analyze_competitor_for_m4 channel_id: {channel_id}, market_keywords: {market_keywords}')
        analysis_result = {}

        # 1. Lấy thông tin cơ bản của kênh
        channel_details_list = self.api.get_channel_details([channel_id])
        if not channel_details_list:
            return {"error": "Không thể lấy thông tin kênh."}
        
        channel_info = channel_details_list[0]
        stats = channel_info.get('statistics', {})
        snippet = channel_info.get('snippet', {})
        analysis_result.update({
            'channel_title': snippet.get('title'),
            'subs_count': int(stats.get('subscriberCount', 0)),
            'video_count': int(stats.get('videoCount', 0)),
            'total_views': int(stats.get('viewCount', 0)),
            'published_at': snippet.get('publishedAt', 'N/A')[:10],
        })

        # 2. Lấy 50 video gần nhất để phân tích
        search_params = {'part': 'snippet', 'channelId': channel_id, 'order': 'date', 'maxResults': 50, 'type': 'video'}
        recent_videos_search = self.api.search(**search_params)
        if not recent_videos_search:
            return {"error": "Kênh không có video nào gần đây để phân tích."}
        
        video_ids = [v['id']['videoId'] for v in recent_videos_search if v['id'].get('kind') == 'youtube#video']
        video_details_list = self.api.get_video_details(video_ids)
        if not video_details_list:
            return {"error": "Không thể lấy chi tiết các video của kênh."}

        # 3. Tính toán các chỉ số
        # Tần suất đăng bài
        publish_dates = sorted([datetime.fromisoformat(v['snippet']['publishedAt'].replace('Z', '+00:00')) for v in video_details_list], reverse=True)
        if len(publish_dates) > 1:
            days_span = (publish_dates[0] - publish_dates[-1]).days
            videos_per_week = len(publish_dates) / (days_span / 7) if days_span > 0 else len(publish_dates)
        else:
            videos_per_week = 0
        analysis_result['videos_per_week'] = videos_per_week

        # View, Engagement, Duration
        total_views, total_likes, total_comments, total_duration_seconds = 0, 0, 0, 0
        video_titles = []
        for v in video_details_list:
            v_stats = v.get('statistics', {})
            total_views += int(v_stats.get('viewCount', 0))
            total_likes += int(v_stats.get('likeCount', 0))
            total_comments += int(v_stats.get('commentCount', 0))
            duration_iso = v.get('contentDetails', {}).get('duration', 'PT0S')
            total_duration_seconds += parse_duration(duration_iso).total_seconds()
            video_titles.append(v['snippet']['title'].lower())
        
        avg_views = total_views / len(video_details_list) if video_details_list else 0
        engagement_rate = (total_likes + total_comments) / total_views if total_views > 0 else 0
        avg_duration_seconds = total_duration_seconds / len(video_details_list) if video_details_list else 0
        
        analysis_result.update({
            'avg_views': avg_views,
            'engagement_rate': engagement_rate,
            'avg_duration_seconds': avg_duration_seconds
        })

        # 4. Content Gap Analysis (ƯỚC TÍNH - KHÔNG TỐN THÊM QUOTA)
        logging.info(f"Starting Estimated Content Gap analysis...")
        video_titles = [v['snippet']['title'].lower() for v in video_details_list]
        content_gaps = []
        for market_kw in market_keywords:
            is_covered = any(market_kw.lower() in title for title in video_titles)
            if not is_covered:
                content_gaps.append(market_kw)
        analysis_result['content_gaps'] = content_gaps
        logging.info(f"Found {len(content_gaps)} potential content gaps.")

        # 5. Tạo các chuỗi đánh giá định tính (Rule-based)
        # Competitor Type
        if analysis_result['subs_count'] > 50000 and analysis_result['video_count'] > 200:
            analysis_result['competitor_type_text'] = "Đối thủ mạnh"
        elif datetime.fromisoformat(analysis_result['published_at']).year >= datetime.utcnow().year - 1:
             analysis_result['competitor_type_text'] = "Đối thủ mới"
        else:
             analysis_result['competitor_type_text'] = "Đối thủ chính"

        # Upload Frequency
        if videos_per_week >= 5: analysis_result['upload_frequency_text'] = "Rất cao"
        elif videos_per_week >= 2: analysis_result['upload_frequency_text'] = "Bình thường"
        else: analysis_result['upload_frequency_text'] = "Thấp"

        # Avg View Rate
        if avg_views > 50000: analysis_result['avg_view_rate_text'] = "Viral"
        elif avg_views > 15000: analysis_result['avg_view_rate_text'] = "Tốt"
        else: analysis_result['avg_view_rate_text'] = "Không đột phá"

        # Strategy
        if videos_per_week >= 3 and avg_views < 20000: analysis_result['strategy_text'] = "Phủ rộng về Số lượng"
        elif videos_per_week < 3 and avg_views >= 20000: analysis_result['strategy_text'] = "Chất lượng, Viral"
        elif avg_duration_seconds > 1200: analysis_result['strategy_text'] = "Nội dung sâu, Video dài"
        else: analysis_result['strategy_text'] = "Cân bằng Chất Lượng và Số lượng"
        
        # Core Content Format
        mins, secs = divmod(avg_duration_seconds, 60)
        analysis_result['avg_duration_text'] = f"{int(mins)}m {int(secs)}s"

        # Community Engagement
        if engagement_rate > 0.05: analysis_result['engagement_text'] = "Rất cao (Fan cứng)"
        elif engagement_rate > 0.02: analysis_result['engagement_text'] = "Tốt"
        elif engagement_rate > 0.01: analysis_result['engagement_text'] = "Ít tương tác"
        else: analysis_result['engagement_text'] = "Chí mạng (Yếu)"
        
        # Rule-based Action Plan (LOGIC MỚI, SÂU SẮC HƠN)
        plan = []
        if analysis_result['engagement_text'] in ["Ít tương tác", "Chí mạng (Yếu)"]:
            plan.append("Điểm yếu Gắn kết: Tập trung vào các video tương tác cao (Q&A, livestream), đặt câu hỏi mở và xây dựng cộng đồng mà họ đang thiếu.")
        if analysis_result['upload_frequency_text'] == "Thấp":
            plan.append("Điểm yếu Tần suất: Duy trì lịch đăng bài ổn định hơn họ (2-3 video/tuần) để chiếm lấy thói quen chờ đợi của khán giả.")
        
        if content_gaps:
            plan.append(f"Điểm yếu Nội dung (LỚN NHẤT): Hãy sản xuất ngay video chất lượng cao về các chủ đề bị bỏ lỡ như '{', '.join(content_gaps[:2])}...'.")
        else:
            plan.append("Đối thủ đã phủ sóng nội dung rất tốt. Cần tạo sự khác biệt bằng cách làm sâu hơn, chất lượng hơn hoặc tìm một góc nhìn độc đáo cho các chủ đề hiện có.")

        if analysis_result['strategy_text'] == "Phủ rộng về Số lượng":
             plan.append("Chiến lược đối thủ là 'lấy thịt đè người'. Hãy đánh bại họ bằng chất lượng video vượt trội thay vì chạy đua số lượng.")

        analysis_result['action_plan_text'] = "\n".join(f"-> {p}" for p in plan)

        return analysis_result
    # === END: MODULE 4 ANALYSIS FUNCTION ===