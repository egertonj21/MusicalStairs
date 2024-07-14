import paho.mqtt.client as mqtt
import logging
import mysql.connector
from mysql.connector import Error
from sensor_data import fetch_and_play_note_details
from config import (MQTT_BROKER, MQTT_PORT, MQTT_TOPICS, MQTT_MUTE_TOPIC, CONTROL_TOPIC, 
                    MOTION_CONTROL_TOPIC, DB_HOST, DB_USER, DB_PASSWORD, DB_NAME)
import time

# Configure logging
logger = logging.getLogger(__name__)

# Mute state
is_muted = False
NUM_LEDS = 31

# Timeout period for ultrasonic sensors to sleep (in seconds)
TIMEOUT_PERIOD = 300  # 5 minutes

# Dictionary to track the last activity time for each ultrasonic sensor
last_activity = {sensor_id: time.time() for sensor_id in range(1, 5)}

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

def led_strip_exists(connection, led_strip_name):
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT 1 FROM LED_strip WHERE LED_strip_name = %s", (led_strip_name,))
        result = cursor.fetchone()
        return result is not None
    except Error as e:
        logger.error(f"Error checking if LED strip exists: {e}")
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

def get_default_colour_id():
    connection = connect_db()
    if connection is None:
        return None

    try:
        cursor = connection.cursor()
        cursor.execute("SELECT colour_ID FROM colour LIMIT 1")
        result = cursor.fetchone()
        if result:
            return result[0]
        else:
            logger.error("No default colour_ID found")
            return None
    except Error as e:
        logger.error(f"Error fetching default colour_ID: {e}")
        return None
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def update_led_strip_status(led_strip_name, active=None, alive=None, colour_id=None):
    connection = connect_db()
    if connection is None:
        return

    try:
        cursor = connection.cursor()
        if not led_strip_exists(connection, led_strip_name):
            if colour_id is None:
                colour_id = get_default_colour_id()
                if colour_id is None:
                    logger.error("Cannot insert LED strip without a valid colour_ID")
                    return
            cursor.execute("INSERT INTO LED_strip (LED_strip_name, LED_alive, LED_active, colour_ID) VALUES (%s, %s, %s, %s)",
                           (led_strip_name, alive if alive is not None else 0, active if active is not None else 0, colour_id))
            logger.info(f"Inserted new LED strip: LED_strip_name={led_strip_name}, active={active}, alive={alive}, colour_id={colour_id}")
        else:
            if colour_id is None:
                cursor.execute("SELECT colour_ID FROM LED_strip WHERE LED_strip_name = %s", (led_strip_name,))
                colour_id = cursor.fetchone()[0]
            if active is not None:
                cursor.execute("UPDATE LED_strip SET LED_active = %s WHERE LED_strip_name = %s", (active, led_strip_name))
            if alive is not None:
                cursor.execute("UPDATE LED_strip SET LED_alive = %s WHERE LED_strip_name = %s", (alive, led_strip_name))
            cursor.execute("UPDATE LED_strip SET colour_ID = %s WHERE LED_strip_name = %s", (colour_id, led_strip_name))
            logger.info(f"Updated LED strip status: LED_strip_name={led_strip_name}, active={active}, alive={alive}, colour_id={colour_id}")
        connection.commit()
    except Error as e:
        logger.error(f"Error updating LED strip status: {e}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def fetch_led_strip_id(led_strip_name):
    connection = connect_db()
    if connection is None:
        return None

    try:
        cursor = connection.cursor()
        cursor.execute("SELECT LED_strip_ID FROM LED_strip WHERE LED_strip_name = %s", (led_strip_name,))
        result = cursor.fetchone()
        if result:
            return result[0]
        else:
            logger.error(f"No LED_strip_ID found for LED_strip_name={led_strip_name}")
            return None
    except Error as e:
        logger.error(f"Error fetching LED_strip_ID: {e}")
        return None
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def fetch_colour_id(LED_strip_id, range_id):
    connection = connect_db()
    if connection is None:
        return None

    try:
        cursor = connection.cursor()
        query = """
            SELECT sl.colour_ID
            FROM sensor_light sl
            INNER JOIN LED_strip ls ON sl.LED_strip_ID = ls.LED_strip_ID
            WHERE sl.LED_strip_ID = %s AND sl.range_ID = %s
        """
        cursor.execute(query, (LED_strip_id, range_id))
        result = cursor.fetchone()
        if result:
            return result[0]
        else:
            logger.error(f"No colour_ID found for LED_strip_ID={LED_strip_id}, range_ID={range_id}")
            return None
    except Error as e:
        logger.error(f"Error fetching colour_ID: {e}")
        return None
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
            
def fetch_colour_rgb(LED_strip_id, range_id):
    connection = connect_db()
    if connection is None:
        return None

    try:
        cursor = connection.cursor()
        query = """
            SELECT c.red, c.green, c.blue
            FROM sensor_light sl
            INNER JOIN LED_strip ls ON sl.LED_strip_ID = ls.LED_strip_ID
            INNER JOIN colour c ON sl.colour_ID = c.colour_ID
            WHERE sl.LED_strip_ID = %s AND sl.range_ID = %s
        """
        cursor.execute(query, (LED_strip_id, range_id))
        result = cursor.fetchone()
        if result:
            return result  # returns (red, green, blue)
        else:
            logger.error(f"No colour found for LED_strip_ID={LED_strip_id}, range_ID={range_id}")
            return None
    except Error as e:
        logger.error(f"Error fetching colour: {e}")
        return None
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
def fetch_sensor_ranges():
    connection = connect_db()
    if connection is None:
        return None

    try:
        cursor = connection.cursor()
        query = "SELECT range_ID, lower_limit, upper_limit FROM sensor_range"
        cursor.execute(query)
        results = cursor.fetchall()
        sensor_ranges = {row[0]: (row[1], row[2]) for row in results}
        return sensor_ranges
    except Error as e:
        logger.error(f"Error fetching sensor ranges: {e}")
        return None
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
def fetch_light_duration():
    connection = connect_db()
    if connection is None:
        return None

    try:
        cursor = connection.cursor()
        query = "SELECT duration FROM light_duration WHERE light_duration_ID = 1"
        cursor.execute(query)
        result = cursor.fetchone()
        if result:
            return result[0]
        else:
            logger.error("No duration found in light_duration table")
            return None
    except Error as e:
        logger.error(f"Error fetching light duration: {e}")
        return None
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
    
def main():
    client = setup_mqtt_client()
    while True:
        client.loop()
        check_for_inactivity(client)
        time.sleep(1)
        
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()
