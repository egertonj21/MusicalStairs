import paho.mqtt.client as mqtt
import logging
import time
import threading
import websocket
import json
from sensor_data import fetch_and_play_note_details
from config import (MQTT_BROKER, MQTT_PORT, MQTT_TOPICS, MQTT_MUTE_TOPIC, CONTROL_TOPIC, 
                    MOTION_CONTROL_TOPIC, WS_SERVER_URL)
from utils import retry_request

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Mute state
is_muted = False
NUM_LEDS = 31

# Timeout period for ultrasonic sensors to sleep (in seconds)
TIMEOUT_PERIOD = 300  # 5 minutes
ALIVE_CHECK_PERIOD = 5  # Period to check for alive messages (in seconds)

# Dictionary to track the last activity time for each ultrasonic sensor
last_activity = {sensor_id: time.time() for sensor_id in range(1, 5)}

# Dictionary to track the last activity time for each LED strip
led_strip_last_activity = {f"ledstrip{i}": time.time() for i in range(1, 3)}  # Update based on actual LED strips

def update_sensor_alive(sensors_on):
    payload = {
        "sensors_on": sensors_on
    }
    logger.debug(f"Updating sensor alive status with payload: {payload}")
    try:
        ws = websocket.WebSocket()
        ws.connect(WS_SERVER_URL)
        ws_payload = {
            "action": "updateSensorAlive",
            "payload": payload
        }
        ws.send(json.dumps(ws_payload))
        response = ws.recv()
        response_data = json.loads(response)
        logger.debug(f"Received response for updateSensorAlive: {response_data}")
        if response_data.get("action") == "update_sensor_status" and "error" not in response_data:
            logger.info(f"Sensor alive status updated successfully: {payload}")
        else:
            logger.error(f"Failed to update sensor alive status: {response_data.get('error')}")
        ws.close()
    except websocket.WebSocketException as e:
        logger.error(f"WebSocket error: {e}")
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e} - Response content: {response}")
    except Exception as e:
        logger.error(f"Failed to send data to server: {e}")

def update_sensor_status(sensors_on):
    payload = {
        "sensors_on": sensors_on
    }
    try:
        ws = websocket.WebSocket()
        ws.connect(WS_SERVER_URL)
        ws_payload = {
            "action": "updateSensorStatus",
            "payload": payload
        }
        ws.send(json.dumps(ws_payload))
        response = ws.recv()
        response_data = json.loads(response)
        logger.debug(f"Received response for updateSensorAlive: {response_data}")
        if response_data.get("action") == "update_sensor_status" and "error" not in response_data:
            logger.info(f"Sensor status updated successfully: {payload}")
        else:
            logger.error(f"Failed to update sensor status: {response_data.get('error')}")
        ws.close()
    except websocket.WebSocketException as e:
        logger.error(f"WebSocket error: {e}")
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e} - Response content: {response}")
    except Exception as e:
        logger.error(f"Failed to send data to server: {e}")

def update_led_strip_status(led_strip_name, alive=None):
    payload = {
        "led_strip_name": led_strip_name,
        "alive": alive
    }
    try:
        ws = websocket.WebSocket()
        ws.connect(WS_SERVER_URL)
        ws_payload = {
            "action": "updateLedStripAlive",
            "payload": payload
        }
        ws.send(json.dumps(ws_payload))
        response = ws.recv()
        response_data = json.loads(response)
        logger.debug(f"Received response for updateLedStripAlive: {response_data}")
        if response_data.get("action") == "updateLedStripAlive" and "error" not in response_data:
            logger.info(f"LED strip status updated successfully for {led_strip_name}: {payload}")
        else:
            logger.error(f"Failed to update LED strip status for {led_strip_name}: {response_data.get('error')}")
        ws.close()
    except websocket.WebSocketException as e:
        logger.error(f"WebSocket error: {e}")
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e} - Response content: {response}")
    except Exception as e:
        logger.error(f"Failed to send data to server: {e}")

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
            last_activity[sensor_id] = time.time()  # Update the last alive time
            update_sensor_status(active)
            
        elif topic.startswith("alive/ledstrip"):
            led_strip_name = topic.split("/")[-1]
            alive = payload.lower() == "alive"
            logger.debug(f"Alive message for LED strip: led_strip_name={led_strip_name}, alive={alive}")
            led_strip_last_activity[led_strip_name] = time.time()  # Update the last alive time
            update_led_strip_status(led_strip_name, alive=alive)
            
        elif topic == CONTROL_TOPIC:
            sensors_on = payload.lower() == "wake"
            logger.info(f"Setting all sensors to {'awake' if sensors_on else 'sleep'}")
            update_sensor_status(sensors_on)
            client.publish(MOTION_CONTROL_TOPIC, "wake" if sensors_on else "sleep")
                    
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

def check_for_alive_messages():
    while True:
        current_time = time.time()
        for sensor_id, last_time in last_activity.items():
            if current_time - last_time >= ALIVE_CHECK_PERIOD:
                logger.info(f"Sensor {sensor_id} has not sent an alive message for {ALIVE_CHECK_PERIOD} seconds. Marking as inactive.")
                update_sensor_alive(False)
        for led_strip_name, last_time in led_strip_last_activity.items():
            if current_time - last_time >= ALIVE_CHECK_PERIOD:
                logger.info(f"LED strip {led_strip_name} has not sent an alive message for {ALIVE_CHECK_PERIOD} seconds. Marking as inactive.")
                update_led_strip_status(led_strip_name, alive=False)
        time.sleep(ALIVE_CHECK_PERIOD)

def setup_mqtt_client():
    client = mqtt.Client(client_id="", clean_session=True, userdata=None, protocol=mqtt.MQTTv311)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_BROKER, MQTT_PORT)
    return client


