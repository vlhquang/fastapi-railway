import sqlite3
import logging
from datetime import datetime
import json

class DatabaseManager:
    def __init__(self, db_name="youtube_data.db"):
        self.db_name = db_name
        self.conn = sqlite3.connect(db_name, check_same_thread=False)

    def setup_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS analysis_results (
                keyword TEXT PRIMARY KEY,
                demand_score REAL, total_views INTEGER, supply_score INTEGER,
                demand_7d REAL, supply_7d INTEGER,
                avg_views REAL, avg_engagement_rate REAL,
                competition_score REAL, opportunity_score REAL,
                last_updated TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS competitors (
                keyword TEXT, channel_id TEXT, name TEXT, subs_count INTEGER,
                total_videos INTEGER, view_count INTEGER, create_date TEXT,
                top_video_title TEXT, top_video_duration TEXT, top_video_publish_date TEXT,
                top_video_thumbnail TEXT,
                PRIMARY KEY (keyword, channel_id)
            )
        ''')
        self.conn.commit()

    def save_analysis_result(self, result: dict):
        cursor = self.conn.cursor()
        query = '''
            INSERT OR REPLACE INTO analysis_results VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        cursor.execute(query, (
            result.get('keyword'), result.get('demand_score'), result.get('total_views'),
            result.get('supply_score'), result.get('demand_7d'), result.get('supply_7d'),
            result.get('avg_views'), result.get('avg_engagement_rate'),
            result.get('competition_score'), result.get('opportunity_score'),
            datetime.utcnow().isoformat()
        ))
        self.conn.commit()

    def get_analysis_result(self, keyword: str):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM analysis_results WHERE keyword = ?", (keyword,))
        row = cursor.fetchone()
        if not row: return None
        return {
            "keyword": row[0], "demand_score": row[1], "total_views": row[2],
            "supply_score": row[3], "demand_7d": row[4], "supply_7d": row[5],
            "avg_views": row[6], "avg_engagement_rate": row[7], "competition_score": row[8],
            "opportunity_score": row[9], "last_updated": datetime.fromisoformat(row[10])
        }
        
    def save_competitors(self, keyword, competitors_list):
        if not competitors_list: return
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM competitors WHERE keyword = ?", (keyword,))
        query = '''
            INSERT OR REPLACE INTO competitors VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        rows = []
        for channel in competitors_list:
            stats = channel.get('statistics', {}); snippet = channel.get('snippet', {}); top_video = channel.get('top_video', {})
            top_video_snippet = top_video.get('snippet', {}); top_video_details = top_video.get('contentDetails', {})
            rows.append((
                keyword, channel.get('id'), snippet.get('title'),
                int(stats.get('subscriberCount', 0)), int(stats.get('videoCount', 0)),
                int(stats.get('viewCount', 0)), snippet.get('publishedAt', 'N/A')[:10],
                top_video_snippet.get('title', 'N/A'),
                top_video_details.get('duration', 'N/A'),
                top_video_snippet['publishedAt'][:10] if top_video_snippet and 'publishedAt' in top_video_snippet else 'N/A',
                top_video_snippet.get('thumbnails', {}).get('high', {}).get('url')
            ))
        cursor.executemany(query, rows)
        self.conn.commit()

    def get_competitors(self, keyword: str):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM competitors WHERE keyword = ?", (keyword,))
        rows = cursor.fetchall()
        competitors = []
        for row in rows:
            competitors.append({
                'id': row[1], 'snippet': {'title': row[2], 'publishedAt': row[6]},
                'statistics': {'subscriberCount': row[3], 'videoCount': row[4], 'viewCount': row[5]},
                'top_video': {
                    'snippet': {'title': row[7], 'publishedAt': row[9], 'thumbnails': {'high': {'url': row[10]}}},
                    'contentDetails': {'duration': row[8]}
                }
            })
        return competitors

    def get_recent_keywords(self, limit=10):
        cursor = self.conn.cursor()
        cursor.execute("SELECT keyword FROM analysis_results ORDER BY last_updated DESC LIMIT ?", (limit,))
        return [row[0] for row in cursor.fetchall()]

    def close(self):
        if self.conn:
            self.conn.close()