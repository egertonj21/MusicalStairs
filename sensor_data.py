import logging
import json
import time
import threading
import websocket
from config import WS_SERVER_URL
from sound import last_played, COOLDOWN_PERIOD, play_sound

# Configure logging
logger = logging.getLogger(__name__)

def log_sensor_data(sensor_id, distance):
    try:
        ws = websocket.WebSocket()
        ws.connect(WS_SERVER_URL)
        payload = {
            "action": "logSensorData",
            "payload": {
                "sensor_ID": sensor_id,
                "distance": distance
            }
        }
        ws.send(json.dumps(payload))
        response = ws.recv()
        response_data = json.loads(response)
        logger.debug(f"Received response for logSensorData: {response_data}")
        if response_data.get("action") == "logSensorData" and "error" not in response_data:
            logger.info(f"Sensor data logged successfully for sensor {sensor_id}: {distance}")
        else:
            logger.error(f"Failed to log sensor data for sensor {sensor_id}: {response_data.get('error')}")
        ws.close()
    except websocket.WebSocketException as e:
        logger.error(f"WebSocket error: {e}")
    except Exception as e:
        logger.error(f"Failed to send data to server: {e}")

def determine_range_id(distance):
    from sound import ranges
    logger.debug(f"Determining range_id for distance: {distance}")
    for range_data in ranges:
        logger.debug(f"Checking range: {range_data}")
        if range_data['lower_limit'] <= distance < range_data['upper_limit']:
            logger.debug(f"Distance {distance} falls within range: {range_data}")
            return range_data['range_ID']
    logger.warning(f"No matching range found for distance: {distance}")
    return None

def fetch_and_play_note_details(sensor_id, distance, is_muted):
    try:
        range_id = determine_range_id(distance)
        if range_id is None:
            logger.warning(f"No matching range found for distance: {distance}")
            return

        logger.debug(f"Fetching note details for sensor_id: {sensor_id}, range_id: {range_id}")
        ws = websocket.WebSocket()
        ws.connect(WS_SERVER_URL)
        payload = {
            "action": "getNoteDetails",
            "payload": {
                "sensor_ID": sensor_id,
                "range_ID": range_id
            }
        }
        ws.send(json.dumps(payload))
        response = ws.recv()
        response_data = json.loads(response)
        logger.debug(f"Received response for getNoteDetails: {response_data}")
        if response_data.get("action") == "getNoteDetails" and "data" in response_data:
            note_details = response_data["data"]
            logger.debug(f"Note details received: {note_details}")
            note_id = note_details.get("note_ID")

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
        ws.close()
    except websocket.WebSocketException as e:
        logger.error(f"WebSocket error: {e}")
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e} - Response content: {response}")
    except Exception as e:
        logger.error(f"Unexpected error in fetch_and_play_note_details: {e}")

