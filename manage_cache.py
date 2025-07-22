from fastapi import FastAPI
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from fastapi_cache.decorator import cache
import logging

class ManageCache:
    def __init__(self):
        logging.basicConfig(level=logging.INFO)
        logging.info("Initializing FastAPI Cache...")
        # Initialize FastAPI Cache with InMemoryBackend
        FastAPICache.init(InMemoryBackend(), prefix="fastapi-cache")
        # Set the cache backend to be used
        logging.info("FastAPI Cache initialized with InMemoryBackend.")
        # Store the cache instance for later use
        self.cache = FastAPICache.get_backend()
    
    async def get(self, key):
        logging.info(f"Fetching from cache with key: {key}")
        return await self.cache.get(key)
    
    async def set(self, key, value, expireVal=60):
        logging.info(f"Setting cache with key: {key}, expire: {expireVal} seconds")
        await self.cache.set(key, value, expire=expireVal)
    
    def clear(self):
        self.cache.clear()