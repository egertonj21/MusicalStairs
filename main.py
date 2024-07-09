import logging
import os
from mqtt_handler import setup_mqtt_client
from sound import load_sounds, load_ranges

# Set the logging level based on an environment variable
log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
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
    
    # Start the MQTT loop to handle incoming messages
    try:
        logger.debug("Starting MQTT client loop")
        client.loop_forever()
    except KeyboardInterrupt:
        logger.info("MQTT client loop stopped by user.")
    finally:
        client.disconnect()
        logger.info("MQTT client disconnected.")

if __name__ == "__main__":
    main()
