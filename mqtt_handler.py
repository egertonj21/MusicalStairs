import paho.mqtt.client as mqtt
import logging
import time
from sensor_data import fetch_and_play_note_details
from config import (MQTT_BROKER, MQTT_PORT, MQTT_TOPICS, MQTT_MUTE_TOPIC, CONTROL_TOPIC, 
                    MOTION_CONTROL_TOPIC)
from utils import retry_request

# Configure logging
logger = logging.getLogger(__name__)

# Mute state
is_muted = False
NUM_LEDS = 31

# Timeout period for ultrasonic sensors to sleep (in seconds)
TIMEOUT_PERIOD = 300  # 5 minutes

# Dictionary to track the last activity time for each ultrasonic sensor
last_activity = {sensor_id: time.time() for sensor_id in range(1, 5)}

def update_sensor_status(sensor_id, active=None, awake=None):
    payload = {
        "sensor_id": sensor_id,
        "active": active,
        "awake": awake
    }
    # Here we can send the payload to the WebSocket server if needed

def update_led_strip_status(led_strip_name, active=None, alive=None, colour_id=None):
    payload = {
        "led_strip_name": led_strip_name,
        "active": active,
        "alive": alive,
        "colour_id": colour_id
    }
    # Here we can send the payload to the WebSocket server if needed

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info("Connected to MQTT broker successfully")
        for topic in MQTT_TOPICS:
            client.subscribe(topic)
            logger.info(f"Subscribed to topic: {topic}")
        client.subscribe(MQTT_MUTE_TOPIC)
        client.subscribe(CONTROL_TOPIC)
        logger.info(f"Subscribed to mute topic: {MQTT_MUTE_TOPIC}")
        logger.info(f"Subscribed to control topic: {CONTROL_TOPIC}")
    else:
        logger.error(f"Failed to connect to MQTT broker, return code {rc}")

def on_message(client, userdata, message):
    global is_muted
    topic = message.topic
    logger.debug(f"Received message on topic: {topic} with payload: {message.payload}")

    if topic == MQTT_MUTE_TOPIC:
        is_muted = message.payload.decode().lower() == 'mute'
        logger.info(f"Mute state changed: {'Muted' if is_muted else 'Unmuted'}")
        return

    try:
        payload = message.payload.decode()
        logger.debug(f"Decoded payload: {payload}")
        
        if topic.startswith("ultrasonic/distance_sensor"):
            distance = float(payload)
            if distance == 0:
                return  # Ignore erroneous reading of 0
            sensor_id = int(topic.split("_")[-1][-1])  # Ensure the extraction is correct
            fetch_and_play_note_details(sensor_id, distance, is_muted)
            last_activity[sensor_id] = time.time()  # Update the last activity time
            
        elif topic.startswith("alive/distance_sensor"):
            sensor_id = int(topic.split("_")[-1][-1])
            active = payload.lower() == "alive"
            logger.debug(f"Alive message for sensor_id={sensor_id}, active={active}")
            update_sensor_status(sensor_id, active=active)
            
        elif topic.startswith("alive/ledstrip"):
            led_strip_name = topic.split("/")[-1]
            active = payload.lower() == "alive"
            logger.debug(f"Alive message for LED strip: led_strip_name={led_strip_name}, active={active}")
            update_led_strip_status(led_strip_name, active=active, alive=active)
            
        elif topic == CONTROL_TOPIC:
            for sensor_id in range(1, 5):  # Assuming 4 sensors
                if payload == "sleep":
                    update_sensor_status(sensor_id, awake=False)
                    logger.info(f"Set sensor_id={sensor_id} to sleep")
                    client.publish(MOTION_CONTROL_TOPIC, "wake")
                elif payload == "wake":
                    update_sensor_status(sensor_id, awake=True)
                    logger.info(f"Set sensor_id={sensor_id} to wake")
                    client.publish(MOTION_CONTROL_TOPIC, "sleep")
                    
    except ValueError as e:
        logger.error(f"Failed to decode message payload: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in on_message: {e}")

def check_for_inactivity(client):
    current_time = time.time()
    all_inactive = True  # Flag to check if all sensors are inactive

    for sensor_id, last_time in last_activity.items():
        if current_time - last_time < TIMEOUT_PERIOD:
            all_inactive = False  # If any sensor is active, set flag to False
            break  # No need to check further, as we found an active sensor

    if all_inactive:
        logger.info(f"All sensors have been inactive for {TIMEOUT_PERIOD} seconds. Sending sleep command.")
        client.publish(CONTROL_TOPIC, "sleep")
        client.publish(MOTION_CONTROL_TOPIC, "motion_wake")

            
def setup_mqtt_client():
    client = mqtt.Client(client_id="", clean_session=True, userdata=None, protocol=mqtt.MQTTv311)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_BROKER, MQTT_PORT)
    return client
