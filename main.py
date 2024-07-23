import logging
import os
import time
import threading
from mqtt_handler import setup_mqtt_client, check_for_inactivity, check_for_alive_messages
from sound import load_sounds, load_ranges

# Set the logging level based on an environment variable
log_level = os.getenv('LOG_LEVEL', 'DEBUG').upper()
logging.basicConfig(level=getattr(logging, log_level))
logger = logging.getLogger(__name__)

def main():
    logger.debug("Starting main function")

    # Load sounds and ranges from the server with retries
    logger.debug("Loading sounds")
    load_sounds()
    logger.debug("Loading ranges")
    load_ranges()

    # Create and set up MQTT client
    logger.debug("Setting up MQTT client")
    client = setup_mqtt_client()
    
    # Start the thread to check for alive messages
    logger.debug("Starting thread to check for alive messages")
    threading.Thread(target=check_for_alive_messages, daemon=True).start()

    # Start the MQTT loop to handle incoming messages
    try:
        logger.debug("Starting MQTT client loop")
        while True:
            client.loop()
            check_for_inactivity(client)
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("MQTT client loop stopped by user.")
    finally:
        client.disconnect()
        logger.info("MQTT client disconnected.")

if __name__ == "__main__":
    main()
