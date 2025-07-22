import asyncpg
import os
from dotenv import load_dotenv
import json
import json as pyjson

from fastapi import HTTPException
import logging

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
db_pool = None  # Global pool

async def connect_db():
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL,
    init=init_connection)

async def init_connection(conn):
    print(">>> Đang set TIME ZONE cho kết nối PostgreSQL...")
    await conn.execute("SET TIME ZONE 'Asia/Ho_Chi_Minh'")

async def close_db():
    await db_pool.close()

async def fetch_now():
    async with db_pool.acquire() as conn:
        result = await conn.fetchval("SELECT LOCALTIMESTAMP")
        return result
    
async def fetch_now_timezone():
    async with db_pool.acquire() as conn:
        result = await conn.fetchval("SHOW TIME ZONE")
        return result
    
async def getDataAnalyticsByModule(module: str, request_data: str):
    query = """
        SELECT * FROM youtrader.data_analytics_by_module
         WHERE module=$1 AND request_data=$2
    """
    async with db_pool.acquire() as conn:
        logging.info(f"Fetching data analytics for module: {module}, request_data: {request_data}")
        result = await conn.fetchrow(query, module, request_data)
        return result
    
async def data_analytics_by_module_insert(module: str, userid_scan: str, request_data: json, response_data: json):
    query = """
        INSERT INTO youtrader.data_analytics_by_module (
            module, lasted_scan_date, userid_scan, request_data, response_data
        ) VALUES ($1, LOCALTIMESTAMP, $2, $3, $4)
        RETURNING id, create_date
    """
    async with db_pool.acquire() as conn:
        try:
            row = await conn.fetchrow(
                query,
                module,
                userid_scan,
                pyjson.dumps(request_data),
                pyjson.dumps(response_data),
            )
            return {
                "id": str(row["id"]),
                "create_date": row["create_date"].isoformat(),
                "message": "Insert successful"
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

