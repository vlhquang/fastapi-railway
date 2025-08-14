import time
import json
import logging
from datetime import date

def write_log(method: str, actionType: str, message: str):
    log_message = f"[{method}][{actionType}] ==> {
        json.dumps({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "result": message
        })}"
    with open("api_server.log", "a") as log_file:
        log_file.write(log_message + "\n") 
    logging.info(log_message)