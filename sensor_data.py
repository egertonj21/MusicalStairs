import requests
import json
import logging
import time
import threading
from config import JS_SERVER_URL, NOTE_DETAILS_URL
from sound import last_played, COOLDOWN_PERIOD, play_sound

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
            logger.info(f"Sensor data logged successfully for sensor {sensor_id}: {distance}")
        else:
            logger.error(f"Failed to log sensor data for sensor {sensor_id}: {response.text}")
    except requests.ConnectionError as ce:
        logger.error(f"Connection error: {ce}")
    except Exception as e:
        logger.error(f"Failed to send data to server: {e}")

def fetch_and_play_note_details(sensor_id, distance, is_muted):
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
                logger.debug(f"Fetched note ID: {note_id}")

                # Log sensor data irrespective of mute state
                log_sensor_data(sensor_id, distance)

                # Check cooldown period for the note
                current_time = time.time()
                last_note, last_time = last_played.get(sensor_id, (None, 0))

                if (note_id != last_note or (current_time - last_time) > COOLDOWN_PERIOD) and not is_muted:
                    last_played[sensor_id] = (note_id, current_time)
                    threading.Thread(target=play_sound, args=(note_id,)).start()
                else:
                    logger.info(f"Skipping note {note_id} for sensor {sensor_id} due to cooldown or mute.")
            else:
                logger.warning(f"No note details found for sensor {sensor_id} at range {range_id}.")
        else:
            logger.warning(f"Empty response from server for sensor_id: {sensor_id}, range_id: {range_id}")
    except requests.RequestException as e:
        logger.error(f"Failed to fetch note details: {e}")
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e} - Response content: {response.content}")

def determine_range_id(distance):
    from sound import ranges
    for range_data in ranges:
        if range_data['lower_limit'] <= distance < range_data['upper_limit']:
            return range_data['range_ID']
    return None
