import logging
import json
import time
import threading
import websocket
from config import WS_SERVER_URL
from sound import last_played, COOLDOWN_PERIOD, play_sound
from utils import get_current_mode, fetch_security_sequences, fetch_all_positions

# Configure logging
logger = logging.getLogger(__name__)

last_step = None
current_step_index = 0
security_sequences = fetch_security_sequences()
positions = fetch_all_positions()

def reset_user_steps():
    global current_step_index
    current_step_index = 0

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
        logger.debug(f"Sending payload for logSensorData: {payload}")
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
    
def send_led_trigger(sensor_id, range_id):
    try:
        ws = websocket.WebSocket()
        ws.connect(WS_SERVER_URL)
        payload = {
            "action": "getLEDTriggerPayload",
            "payload": {
                "sensor_id": sensor_id,
                "distance": range_id  # Correcting the payload to send distance
            }
        }
        ws.send(json.dumps(payload))
        response = ws.recv()
        response_data = json.loads(response)
        logger.debug(f"Received response for getLEDTriggerPayload: {response_data}")
        if response_data.get("action") == "LEDTrigger" and "payload" in response_data:
            led_payload = response_data["payload"]
            logger.debug(f"LED Trigger Payload: {led_payload}")

            # Now send the LED trigger payload
            payload = {
                "action": "sendLEDTrigger",
                "payload": led_payload
            }
            ws.send(json.dumps(payload))
            response = ws.recv()
            response_data = json.loads(response)
            logger.debug(f"Received response for sendLEDTrigger: {response_data}")
        else:
            logger.warning(f"Failed to get LED trigger payload for sensor {sensor_id} at range {range_id}.")
        ws.close()
    except websocket.WebSocketException as e:
        logger.error(f"WebSocket error: {e}")
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e} - Response content: {response}")
    except Exception as e:
        logger.error(f"Unexpected error in send_led_trigger: {e}")

def send_security_led_trigger(sensor_id, color):
    try:
        ws = websocket.WebSocket()
        ws.connect(WS_SERVER_URL)
        range_str = '0-30'
        duration = '3000'  # 3 seconds in milliseconds
        color_code = '0,0,0'

        if color == 'green':
            color_code = '0,255,0'  # RGB for green
        elif color == 'red':
            color_code = '255,0,0'  # RGB for red

        message = f"{range_str}&{color_code}&{duration}"
        payload = {
            "action": "sendLEDTrigger",
            "payload": {
                "sensor_id": sensor_id,
                "message": message
            }
        }
        ws.send(json.dumps(payload))
        response = ws.recv()
        response_data = json.loads(response)
        logger.debug(f"Received response for sendLEDTrigger: {response_data}")
        if response_data.get("action") == "LEDTrigger" and "message" in response_data:
            logger.debug(f"LED Trigger message sent: {response_data['message']}")
        else:
            logger.warning(f"Failed to send LED trigger for sensor {sensor_id} with color {color}.")
        ws.close()
    except websocket.WebSocketException as e:
        logger.error(f"WebSocket error: {e}")
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e} - Response content: {response}")
    except Exception as e:
        logger.error(f"Unexpected error in send_security_led_trigger: {e}")

def map_position_id_to_sensor_range(position_id):
    for position in positions:
        if position["position_ID"] == position_id:
            return position["sensor_ID"], position["range_ID"]
    return None, None

def check_security_sequence(sensor_id, range_id):
    global last_step, current_step_index, security_sequences

    current_step = (sensor_id, range_id)
    logger.debug(f"Current step: {current_step}")

    # Ignore repeated steps
    if current_step == last_step:
        return

    last_step = current_step

    for sequence in security_sequences:
        position_id = sequence[f"step{current_step_index + 1}_position_ID"]
        expected_sensor_id, expected_range_id = map_position_id_to_sensor_range(position_id)
        expected_step = (expected_sensor_id, expected_range_id)
        logger.debug(f"Expected step: {expected_step}")

        if current_step == expected_step:
            send_security_led_trigger(sensor_id, 'green')
            time.sleep(2)
            send_security_led_trigger(sensor_id, 'off')
            logger.info(f"Step {current_step_index + 1} matched, sent green light.")
            current_step_index += 1

            if current_step_index == 3:
                logger.info("Security sequence matched successfully.")
                reset_user_steps()
            return
        else:
            send_security_led_trigger(sensor_id, 'red')
            logger.info(f"Step {current_step_index + 1} did not match, sent red light.")
            time.sleep(2)
            send_security_led_trigger(sensor_id, 'off')
            reset_user_steps()
            return

def fetch_and_play_note_details(sensor_id, distance, is_muted):
    try:
        current_mode = get_current_mode()
        if current_mode is None:
            logger.error("Could not determine current mode, skipping processing.")
            return

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

            log_sensor_data(sensor_id, distance)

            if current_mode == 1:  # Musical Stairs mode
                send_led_trigger(sensor_id, distance)
                current_time = time.time()
                last_note, last_time = last_played.get(sensor_id, (None, 0))

                if (note_id != last_note or (current_time - last_time) > COOLDOWN_PERIOD) and not is_muted:
                    last_played[sensor_id] = (note_id, current_time)
                    threading.Thread(target=play_sound, args=(note_id,)).start()
                else:
                    logger.info(f"Skipping note {note_id} for sensor {sensor_id} due to cooldown or mute.")

            elif current_mode == 2:  # Security mode
                check_security_sequence(sensor_id, range_id)

            # Add more modes as needed

        else:
            logger.warning(f"No note details found for sensor {sensor_id} at range {range_id}.")
        ws.close()
    except websocket.WebSocketException as e:
        logger.error(f"WebSocket error: {e}")
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e} - Response content: {response}")
    except Exception as e:
        logger.error(f"Unexpected error in fetch_and_play_note_details: {e}")

