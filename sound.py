import pygame
import logging
from config import NOTES_URL, RANGES_URL
from utils import retry_request

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
    response = retry_request(NOTES_URL, retries=retries, delay=delay)
    if response:
        notes = response.json()
        for note in notes:
            sounds[note["note_ID"]] = pygame.mixer.Sound(note["note_location"])
        logger.info("Sounds loaded successfully")
        logger.debug(f"Loaded sounds: {sounds}")
    else:
        logger.critical("All retries to load sounds have failed.")

def load_ranges(retries=5, delay=2):
    global ranges
    response = retry_request(RANGES_URL, retries=retries, delay=delay)
    if response:
        ranges = response.json()
        logging.info("Ranges loaded successfully")
        logging.debug(f"Loaded ranges: {ranges}")
    else:
        logging.critical("All retries to load ranges have failed.")

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
