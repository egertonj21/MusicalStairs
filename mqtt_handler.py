import paho.mqtt.client as mqtt
import logging
import mysql.connector
from mysql.connector import Error
from sensor_data import fetch_and_play_note_details
from config import MQTT_BROKER, MQTT_PORT, MQTT_TOPICS, MQTT_MUTE_TOPIC, CONTROL_TOPIC, DB_HOST, DB_USER, DB_PASSWORD, DB_NAME

# Configure logging
logger = logging.getLogger(__name__)

# Mute state
is_muted = False

def connect_db():
    try:
        connection = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        if connection.is_connected():
            logger.info("Connected to the database")
        return connection
    except Error as e:
        logger.error(f"Error connecting to the database: {e}")
        return None

def sensor_exists(connection, sensor_id):
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT 1 FROM alive WHERE sensor_ID = %s", (sensor_id,))
        result = cursor.fetchone()
        return result is not None
    except Error as e:
        logger.error(f"Error checking if sensor exists: {e}")
        return False

def update_sensor_status(sensor_id, active=None, awake=None):
    connection = connect_db()
    if connection is None:
        return

    try:
        cursor = connection.cursor()
        if not sensor_exists(connection, sensor_id):
            cursor.execute("INSERT INTO alive (sensor_ID, active, awake) VALUES (%s, %s, %s)",
                           (sensor_id, active if active is not None else 0, awake if awake is not None else 0))
            logger.info(f"Inserted new sensor: sensor_ID={sensor_id}, active={active}, awake={awake}")
        else:
            if active is not None:
                cursor.execute("UPDATE alive SET active = %s WHERE sensor_ID = %s", (active, sensor_id))
            if awake is not None:
                cursor.execute("UPDATE alive SET awake = %s WHERE sensor_ID = %s", (awake, sensor_id))
            logger.info(f"Updated sensor status: sensor_ID={sensor_id}, active={active}, awake={awake}")
        connection.commit()
    except Error as e:
        logger.error(f"Error updating sensor status: {e}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

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
            sensor_id = int(topic.split("_")[-1][-1])
            fetch_and_play_note_details(sensor_id, distance, is_muted)
        elif topic.startswith("alive/distance_sensor"):
            sensor_id = int(topic.split("_")[-1][-1])
            active = payload.lower() == "alive"
            logger.debug(f"Alive message for sensor_id={sensor_id}, active={active}")
            update_sensor_status(sensor_id, active=active)
        elif topic == CONTROL_TOPIC:
            for sensor_id in range(1, 5):  # Assuming 4 sensors
                if payload == "sleep":
                    update_sensor_status(sensor_id, awake=False)
                    logger.info(f"Set sensor_id={sensor_id} to sleep")
                elif payload == "wake":
                    update_sensor_status(sensor_id, awake=True)
                    logger.info(f"Set sensor_id={sensor_id} to wake")
    except ValueError as e:
        logger.error(f"Failed to decode message payload: {e}")

def setup_mqtt_client():
    client = mqtt.Client(client_id="", clean_session=True, userdata=None, protocol=mqtt.MQTTv311)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_BROKER, MQTT_PORT)
    return client
