import threading
import logging
from mqtt_handler import setup_mqtt_client
from sound import load_sounds, load_ranges

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    # Load sounds and ranges from the server with retries
    load_sounds()
    load_ranges()
    
    # Create and set up MQTT client
    client = setup_mqtt_client()
    
    # Start the MQTT loop to handle incoming messages
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("MQTT client loop stopped by user.")
        logger.info("MQTT client loop stopped by user.")
    finally:
        client.disconnect()
        print("MQTT client disconnected.")
        logger.info("MQTT client disconnected.")

if __name__ == "__main__":
    main()
