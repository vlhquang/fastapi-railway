import uuid
import asyncpg
import os
from dotenv import load_dotenv
import json
import json as pyjson

from fastapi import HTTPException
import logging
from datetime import date

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

async def check_account_login_by_email(email: str):
    today = date.today()
    logging.info(f"Checking account login for email: {email} on date: {today}")
    query = """
        SELECT * FROM youtrader.account_ WHERE email = $1 AND login_date = $2
    """
    async with db_pool.acquire() as conn:
        try:
            row = await conn.fetchrow(
                query,
                email,
                today
            )
            return row
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        
async def check_account_login_by_user_id(userId: str):
    logging.info(f"Checking account login for userId: {userId}")
    query = """
        SELECT * FROM youtrader.account_ WHERE user_id = $1
    """
    async with db_pool.acquire() as conn:
        try:
            row = await conn.fetchrow(
                query,
                userId
            )
            return row
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        
async def update_account_login(user_id: str, email: str, token: str):
    query = """
        UPDATE youtrader.account_ SET user_id = $1, token = $2 WHERE email = $3 AND login_date = $4
        RETURNING user_id
    """
    async with db_pool.acquire() as conn:
        try:
            row = await conn.fetchrow(
                query,
                user_id,
                token,
                email,
                date.today()
            )
            return {
                "id": str(row["user_id"]),
                "message": "Login record updated successfully"
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        
async def update_action_log_account(user_id: str, action_log: str):
    query = """
        UPDATE youtrader.account_ SET action_log = $1 WHERE user_id = $2
    """
    async with db_pool.acquire() as conn:
        try:
            row = await conn.fetchrow(
                query,
                action_log,
                user_id
            )
            return {
                "id": str(user_id),
                "message": "Login record updated successfully"
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

async def handle_login_db(email: str, token: str):
    check_account_login_result = await check_account_login_by_email(email)
    isExistAccount = bool(check_account_login_result is not None)
    logging.info(f"Update account login for email: {email}, already logged in: {check_account_login_result}")
    if isExistAccount:
        logging.info(f"Account already logged in for email: {email}")
        userId = uuid.uuid4().hex
        update_account_login_result = await update_account_login(
            userId,
            email,
            token
        )
        return {
            "id": str(update_account_login_result["id"]),
            "message": "Login record updated successfully"
        }
    else:
        userId = uuid.uuid4().hex
        query = """
            INSERT INTO youtrader.account_ (email, token, login_date, user_id)
            VALUES ($1, $2, $3, $4)
            RETURNING user_id
        """
        async with db_pool.acquire() as conn:
            try:
                row = await conn.fetchrow(
                    query,
                    email,
                    token,
                    date.today(),
                    userId
                )
                return {
                    "id": str(row["user_id"]),
                    "message": "Login record created successfully"
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

async def handle_update_action_log_account_db(userId: str, actionLog: str):
    check_account_login_result = await check_account_login_by_user_id(userId)
    isExistAccount = bool(check_account_login_result is not None)
    if not isExistAccount:
        logging.info(f"###handle_update_action_log_account_db### UserId {userId} not found in account login records")
        return {
            "id": str(check_account_login_result["user_id"]),
            "message": "userId not found in account login records"
        }
    else:
        logging.info(f"###handle_update_action_log_account_db### UserId {userId} found in account login records")
        update_action_log_account_result = await update_action_log_account(
            userId,
            actionLog
        )
        logging.info(f"Action log updated for userId {userId}: {update_action_log_account_result}")
        return update_action_log_account_result