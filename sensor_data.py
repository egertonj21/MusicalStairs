import requests
import json
import logging
import time
from sound import play_sound, last_played, COOLDOWN_PERIOD
from config import JS_SERVER_URL, NOTE_DETAILS_URL

# Configure logging
logger = logging.getLogger(__name__)

def log_sensor_data(sensor_id, distance):
    # Log sensor data to the JavaScript server
    try:
        payload = {
            "sensor_ID": sensor_id,
            "distance": distance
        }
        headers = {'Content-Type': 'application/json'}
        response = requests.post(JS_SERVER_URL, data=json.dumps(payload), headers=headers)
        if response.status_code == 200:
            print(f"Sensor data logged successfully for sensor {sensor_id}: {distance}")
            logger.info(f"Sensor data logged successfully for sensor {sensor_id}: {distance}")
        else:
            print(f"Failed to log sensor data for sensor {sensor_id}: {response.text}")
            logger.error(f"Failed to log sensor data for sensor {sensor_id}: {response.text}")
    except requests.ConnectionError as ce:
        print(f"Connection error: {ce}")
        logger.error(f"Connection error: {ce}")
    except Exception as e:
        print(f"Failed to send data to server: {e}")
        logger.error(f"Failed to send data to server: {e}")

def fetch_and_play_note_details(sensor_id, distance):
    # Fetch note details from the server based on sensor ID and range ID
    try:
        range_id = determine_range_id(distance)
        logger.debug(f"Fetching note details for sensor_id: {sensor_id}, range_id: {range_id}")
        response = requests.get(f"{NOTE_DETAILS_URL}/{sensor_id}/{range_id}")
        response.raise_for_status()
        logger.debug(f"Server response: {response.text}")
        if response.text.strip():
            note_details = response.json()
            if note_details:
                note_id = note_details.get("note_ID")
                print(f"Fetched note ID: {note_id}")
                logger.debug(f"Fetched note ID: {note_id}")

                # Check cooldown period for the note
                current_time = time.time()
                last_note, last_time = last_played.get(sensor_id, (None, 0))

                if note_id != last_note or (current_time - last_time) > COOLDOWN_PERIOD:
                    last_played[sensor_id] = (note_id, current_time)
                    threading.Thread(target=play_sound, args=(note_id,)).start()
                else:
                    print(f"Skipping note {note_id} for sensor {sensor_id} due to cooldown.")
                    logger.info(f"Skipping note {note_id} for sensor {sensor_id} due to cooldown.")
            else:
                print(f"No note details found for sensor {sensor_id} at range {range_id}.")
                logger.warning(f"No note details found for sensor {sensor_id} at range {range_id}.")
        else:
            print(f"Empty response from server for sensor_id: {sensor_id}, range_id: {range_id}")
            logger.warning(f"Empty response from server for sensor_id: {sensor_id}, range_id: {range_id}")
    except requests.RequestException as e:
        print(f"Failed to fetch note details: {e}")
        logger.error(f"Failed to fetch note details: {e}")
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e} - Response content: {response.content}")
        logger.error(f"JSON decode error: {e} - Response content: {response.content}")

def determine_range_id(distance):
    from sound import ranges
    for range_data in ranges:
        if range_data['lower_limit'] <= distance < range_data['upper_limit']:
            return range_data['range_ID']
    return None
