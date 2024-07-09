import paho.mqtt.client as mqtt
import logging
import threading
from sound import play_sound, is_muted
from config import MQTT_BROKER, MQTT_PORT, MQTT_TOPICS, MQTT_MUTE_TOPIC
from sensor_data import log_sensor_data, fetch_and_play_note_details

# Configure logging
logger = logging.getLogger(__name__)

def on_message(client, userdata, message):
    global is_muted
    topic = message.topic
    if topic == MQTT_MUTE_TOPIC:
        is_muted = message.payload.decode().lower() == 'mute'
        print(f"Mute state changed: {'Muted' if is_muted else 'Unmuted'}")
        logger.info(f"Mute state changed: {'Muted' if is_muted else 'Unmuted'}")
        return

    distance = float(message.payload.decode())

    # Extract sensor ID from topic
    sensor_id = int(topic.split("_")[-1][-1])

    log_sensor_data(sensor_id, distance)
    fetch_and_play_note_details(sensor_id, distance)

def setup_mqtt_client():
    client = mqtt.Client(client_id="", clean_session=True, userdata=None, protocol=mqtt.MQTTv311)
    client.on_message = on_message
    client.connect(MQTT_BROKER, MQTT_PORT)
    for topic in MQTT_TOPICS:
        client.subscribe(topic)
    client.subscribe(MQTT_MUTE_TOPIC)  # Subscribe to the mute topic
    return client
