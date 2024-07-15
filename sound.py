import pygame
import logging
import websocket
import json
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
logger = logging.getLogger(__name__)

def load_sounds(retries=5, delay=2):
    ws = websocket.WebSocket()
    ws.connect(WS_SERVER_URL)
    payload = {
        "action": "getNotes"
    }
    ws.send(json.dumps(payload))
    response = ws.recv()
    response_data = json.loads(response)
    logger.debug(f"Received response for getNotes: {response_data}")
    if response_data and response_data.get("action") == "getNotes":
        notes = response_data.get("data", [])
        for note in notes:
            if isinstance(note, dict):
                sounds[note["note_ID"]] = pygame.mixer.Sound(note["note_location"])
            else:
                logger.error(f"Unexpected note format: {note}")
        logger.info("Sounds loaded successfully")
        logger.debug(f"Loaded sounds: {sounds}")
    else:
        logger.critical("Failed to load sounds.")
    ws.close()

def load_ranges(retries=5, delay=2):
    global ranges
    ws = websocket.WebSocket()
    ws.connect(WS_SERVER_URL)
    payload = {
        "action": "getRanges"
    }
    ws.send(json.dumps(payload))
    response = ws.recv()
    response_data = json.loads(response)
    logger.debug(f"Received response for getRanges: {response_data}")
    if response_data and response_data.get("action") == "getRanges":
        ranges = response_data.get("data", [])
        logging.info("Ranges loaded successfully")
        logging.debug(f"Loaded ranges: {ranges}")
    else:
        logging.critical("Failed to load ranges.")
    ws.close()

def play_sound(note_ID):
    if is_muted:
        logger.info("Audio is muted, not playing sound.")
        return
    
    try:
        sound = sounds.get(note_ID)
        if sound:
            sound.play()
        else:
            logger.warning(f"Sound for note ID {note_ID} not found.")
    except Exception as e:
        logger.error(f"Failed to play sound: {e}")
