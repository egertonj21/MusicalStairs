import paho.mqtt.client as mqtt
import logging
import time
import requests
from sensor_data import fetch_and_play_note_details
from config import (MQTT_BROKER, MQTT_PORT, MQTT_TOPICS, MQTT_MUTE_TOPIC, CONTROL_TOPIC, 
                    MOTION_CONTROL_TOPIC, JS_SERVER_URL)
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
    url = f"{JS_SERVER_URL}/others/sensor-status"
    response = retry_request(url, method='POST', json=payload)
    if response:
        logger.info(f"Updated sensor status: {response.json()}")

def update_led_strip_status(led_strip_name, active=None, alive=None, colour_id=None):
    payload = {
        "led_strip_name": led_strip_name,
        "active": active,
        "alive": alive,
        "colour_id": colour_id
    }
    url = f"{JS_SERVER_URL}/ledstrip/update_status"
    response = retry_request(url, method='PUT', json=payload)
    if response:
        logger.info(f"Updated LED strip status: {response.json()}")

def fetch_led_strip_id(led_strip_name):
    url = f"{JS_SERVER_URL}/ledstrip/id/{led_strip_name}"
    response = retry_request(url)
    if response:
        result = response.json()
        logger.debug(f"LED strip ID response: {result}")

        if isinstance(result, list) and len(result) > 0:
            return result[0].get('led_strip_id')
        elif isinstance(result, dict):
            return result.get('led_strip_id')
    return None

def fetch_colour_rgb(led_strip_id, range_id):
    url = f"{JS_SERVER_URL}/ledstrip/colour_rgb/{led_strip_id}/{range_id}"
    response = retry_request(url)
    if response:
        result = response.json()
        logger.debug(f"Colour RGB response: {result}")

        if isinstance(result, list) and len(result) > 0:
            return result[0]
        elif isinstance(result, dict):
            return result
    return None




def fetch_light_duration():
    url = f"{JS_SERVER_URL}/sensor/light_duration"
    response = retry_request(url)
    if response:
        return response.json().get('duration')
    return None

def fetch_sensor_ranges():
    url = f"{JS_SERVER_URL}/others/ranges"
    response = retry_request(url)
    if response:
        return response.json().get('sensor_ranges')
    return None

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
            
            # Fetch sensor ranges
            sensor_ranges = fetch_sensor_ranges()
            if not sensor_ranges:
                logger.error("Failed to fetch sensor ranges")
                return

            # Determine range_id based on distance
            range_id = None
            for rid, (lower, upper) in sensor_ranges.items():
                if lower <= distance <= upper:
                    range_id = rid
                    break

            if range_id is None:
                logger.error(f"No matching range found for distance {distance}")
                return

            # Determine LED range based on range_id
            if range_id == 1:  # close
                start_led = 0
                end_led = 9
            elif range_id == 2:  # mid
                start_led = 10
                end_led = 19
            elif range_id == 3:  # far
                start_led = 20
                end_led = NUM_LEDS - 1
            else:
                logger.error(f"Unknown range_id {range_id} for distance {distance}")
                return

            # Fetch the light duration
            light_duration = fetch_light_duration()
            if not light_duration:
                logger.error("Failed to fetch light duration")
                return

            # Construct LED strip name from sensor name
            sensor_name = topic.split("/")[-1]  # Extract the sensor name from the topic
            sensor_number = ''.join(filter(str.isdigit, sensor_name))  # Extract the number from the sensor name
            led_strip_name = f"ledstrip{sensor_number}"  # Construct the LED strip name
            
            # Fetch the LED strip ID using the constructed name
            led_strip_id = fetch_led_strip_id(led_strip_name)
            if led_strip_id:
                colour_rgb = fetch_colour_rgb(led_strip_id, range_id)
                if colour_rgb:
                    rgb_color = f"{colour_rgb[0]},{colour_rgb[1]},{colour_rgb[2]}"  # Format RGB string
                    message = f"{start_led}-{end_led}&{rgb_color}&{light_duration}"  # Example: "0-9&255,0,0&5" for 5 seconds
                    client.publish(f"trigger/{led_strip_name}", message)
                    logger.info(f"Published '{message}' to trigger/{led_strip_name}")
                else:
                    logger.error(f"No colour found for LED_strip_ID={led_strip_id} and range_ID={range_id}")
            else:
                logger.error(f"No LED_strip_ID found for LED_strip_name={led_strip_name}")

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
    for sensor_id, last_time in last_activity.items():
        if current_time - last_time >= TIMEOUT_PERIOD:
            logger.info(f"Sensor {sensor_id} has been inactive for {TIMEOUT_PERIOD} seconds. Sending sleep command.")
            client.publish(CONTROL_TOPIC, "sleep")
            client.publish(MOTION_CONTROL_TOPIC, "motion_wake")
            
def setup_mqtt_client():
    client = mqtt.Client(client_id="", clean_session=True, userdata=None, protocol=mqtt.MQTTv311)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_BROKER, MQTT_PORT)
    return client
