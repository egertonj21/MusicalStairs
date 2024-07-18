import pygame
import logging
import websocket
import json
import time
from config import WS_SERVER_URL

# Initialize pygame mixer for playing sound
pygame.mixer.init()

# Global dictionaries
sounds = {}
ranges = []
last_played = {}  # Dictionary to track last played note and timestamp for each sensor

# Cooldown period in seconds
COOLDOWN_PERIOD = 5
is_muted = False  # Mute state

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def load_sounds(retries=5, delay=2):
    for attempt in range(retries):
        try:
            ws = websocket.WebSocket()
            ws.connect(WS_SERVER_URL)
            payload = {"action": "getNotes"}
            ws.send(json.dumps(payload))
            response = ws.recv()
            logger.debug(f"Received raw response for getNotes: {response}")
            response_data = json.loads(response)
            logger.debug(f"Parsed response for getNotes: {response_data}")
            if response_data and response_data.get("action") == "getNotes":
                notes = response_data.get("data", [])
                for note in notes:
                    if isinstance(note, dict):
                        sounds[note["note_ID"]] = pygame.mixer.Sound(note["note_location"])
                    else:
                        logger.error(f"Unexpected note format: {note}")
                logger.info("Sounds loaded successfully")
                logger.debug(f"Loaded sounds: {sounds}")
                ws.close()
                return
            else:
                logger.critical(f"Failed to load sounds: Invalid response format: {response_data.get('message', '')}")
        except Exception as e:
            logger.error(f"Error loading sounds, attempt {attempt + 1} of {retries}: {e}")
            time.sleep(delay)
    logger.critical("Failed to load sounds after retries.")

def load_ranges(retries=5, delay=2):
    global ranges
    for attempt in range(retries):
        try:
            ws = websocket.WebSocket()
            ws.connect(WS_SERVER_URL)
            payload = {"action": "getRanges"}
            ws.send(json.dumps(payload))
            response = ws.recv()
            logger.debug(f"Received raw response for getRanges: {response}")
            response_data = json.loads(response)
            logger.debug(f"Parsed response for getRanges: {response_data}")
            if response_data and response_data.get("action") == "getRanges":
                ranges = response_data.get("data", [])
                logger.info("Ranges loaded successfully")
                logger.debug(f"Loaded ranges: {ranges}")
                ws.close()
                return
            else:
                logger.critical(f"Failed to load ranges: Invalid response format: {response_data.get('message', '')}")
        except Exception as e:
            logger.error(f"Error loading ranges, attempt {attempt + 1} of {retries}: {e}")
            time.sleep(delay)
    logger.critical("Failed to load ranges after retries.")

def play_sound(note_ID):
    if is_muted:
        logger.info("Audio is muted, not playing sound.")
        return
    
    current_time = time.time()
    last_played_time = last_played.get(note_ID, 0)
    
    if current_time - last_played_time < COOLDOWN_PERIOD:
        logger.info(f"Cooldown period active for note ID {note_ID}. Not playing sound.")
        return
    
    try:
        sound = sounds.get(note_ID)
        if sound:
            sound.play()
            last_played[note_ID] = current_time
            logger.info(f"Played sound for note ID {note_ID}")
        else:
            logger.warning(f"Sound for note ID {note_ID} not found.")
    except Exception as e:
        logger.error(f"Failed to play sound: {e}")

def main():
    load_sounds()
    load_ranges()

    # Example of playing a sound with a specific note ID
    play_sound(1)

if __name__ == "__main__":
    main()
