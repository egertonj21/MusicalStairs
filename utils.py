import time
import logging

# Configure logging
logger = logging.getLogger(__name__)

def retry_request(ws, payload, retries=5, delay=2):
    """
    A utility function to perform WebSocket requests with retries.

    Args:
        ws (WebSocket): The WebSocket instance.
        payload (dict): The payload to send.
        retries (int): The number of retry attempts.
        delay (int): Delay between retries in seconds.

    Returns:
        Response: The response object if the request is successful.
        None: If all retries fail.
    """
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
    """
    Logs the details of an HTTP response.

    Args:
        response (requests.Response): The HTTP response to log.
    """
    if response:
        logger.info(f"Response status: {response.status_code}")
        logger.debug(f"Response headers: {response.headers}")
        logger.debug(f"Response text: {response.text}")
    else:
        logger.error("No response to log.")
