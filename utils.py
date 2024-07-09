import requests
import time
import logging

# Configure logging
logger = logging.getLogger(__name__)

def retry_request(url, retries=5, delay=2, method='GET', **kwargs):
    """
    A utility function to perform HTTP requests with retries.

    Args:
        url (str): The URL to request.
        retries (int): The number of retry attempts.
        delay (int): Delay between retries in seconds.
        method (str): HTTP method ('GET', 'POST', etc.).
        **kwargs: Additional arguments to pass to the request method.

    Returns:
        Response: The response object if the request is successful.
        None: If all retries fail.
    """
    for attempt in range(retries):
        try:
            response = requests.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            logger.error(f"Request failed (attempt {attempt + 1}/{retries}): {e}")
            time.sleep(delay)
    logger.critical(f"All retries failed for URL: {url}")
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
