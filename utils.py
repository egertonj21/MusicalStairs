import time
import logging
import json
import websocket
from config import WS_SERVER_URL

# Configure logging
logger = logging.getLogger(__name__)

def fetch_all_positions():
    try:
        ws = websocket.WebSocket()
        ws.connect(WS_SERVER_URL)
        payload = {"action": "fetchAllPositions"}
        ws.send(json.dumps(payload))
        response = ws.recv()
        response_data = json.loads(response)
        ws.close()

        if response_data.get("action") == "fetchAllPositions" and "data" in response_data:
            return response_data["data"]
        else:
            logger.error("Failed to fetch positions")
            return []
    except Exception as e:
        logger.error(f"Failed to fetch positions: {e}")
        return []

def retry_request(ws, payload, retries=5, delay=2):
    for attempt in range(retries):
        try:
            ws.send(json.dumps(payload))
            response = ws.recv()
            return json.loads(response)
        except Exception as e:
            logger.error(f"Request failed (attempt {attempt + 1}/{retries}): {e}")
            time.sleep(delay)
    logger.critical(f"All retries failed for payload: {payload}")
    return None

def log_response(response):
    if response:
        logger.info(f"Response status: {response.status_code}")
        logger.debug(f"Response headers: {response.headers}")
        logger.debug(f"Response text: {response.text}")
    else:
        logger.error("No response to log.")

def get_current_mode():
    try:
        ws = websocket.WebSocket()
        ws.connect(WS_SERVER_URL)
        payload = {"action": "fetchActiveMode"}
        ws.send(json.dumps(payload))
        response = ws.recv()
        response_data = json.loads(response)
        ws.close()
        if response_data.get("action") == "fetchActiveMode" and "data" in response_data:
            return response_data["data"].get("mode_ID")
        else:
            logger.error(f"Failed to fetch current mode: {response_data.get('error')}")
            return None
    except Exception as e:
        logger.error(f"Failed to fetch current mode: {e}")
        return None

def fetch_security_sequences():
    try:
        ws = websocket.WebSocket()
        ws.connect(WS_SERVER_URL)
        payload = {"action": "fetchAllSecuritySequences"}
        ws.send(json.dumps(payload))
        response = ws.recv()
        response_data = json.loads(response)
        ws.close()
        
        if response_data.get("action") == "fetchAllSecuritySequences" and "data" in response_data:
            return response_data["data"]
        else:
            logger.error("Failed to fetch security sequences")
            return []
    except Exception as e:
        logger.error(f"Failed to fetch security sequences: {e}")
        return []
