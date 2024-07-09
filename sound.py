import requests
import pygame
import time
import logging

from config import NOTES_URL, RANGES_URL

# Initialize pygame mixer for playing sound
pygame.mixer.init()

# Global dictionaries
sounds = {}
ranges = []
last_played = {}  # Dictionary to track last played note and timestamp for each sensor

# Cooldown period in seconds
COOLDOWN_PERIOD = 5
is_muted = False

# Configure logging
logger = logging.getLogger(__name__)

def load_sounds(retries=5, delay=2):
    for attempt in range(retries):
        try:
            response = requests.get(NOTES_URL)
            response.raise_for_status()
            notes = response.json()
            for note in notes:
                sounds[note["note_ID"]] = pygame.mixer.Sound(note["note_location"])
            print("Sounds loaded successfully")
            logger.info("Sounds loaded successfully")
            logger.debug(f"Loaded sounds: {sounds}")
            return
        except requests.RequestException as e:
            print(f"Failed to load sounds (attempt {attempt + 1}/{retries}): {e}")
            logger.error(f"Failed to load sounds (attempt {attempt + 1}/{retries}): {e}")
            time.sleep(delay)
    print("All retries to load sounds have failed.")
    logger.critical("All retries to load sounds have failed.")

def load_ranges(retries=5, delay=2):
    global ranges
    for attempt in range(retries):
        try:
            response = requests.get(RANGES_URL)
            response.raise_for_status()
            ranges = response.json()
            print("Ranges loaded successfully")
            logger.info("Ranges loaded successfully")
            logger.debug(f"Loaded ranges: {ranges}")
            return
        except requests.RequestException as e:
            print(f"Failed to load ranges (attempt {attempt + 1}/{retries}): {e}")
            logger.error(f"Failed to load ranges (attempt {attempt + 1}/{retries}): {e}")
            time.sleep(delay)
    print("All retries to load ranges have failed.")
    logger.critical("All retries to load ranges have failed.")

def play_sound(note_ID):
    if is_muted:
        print("Audio is muted, not playing sound.")
        logger.info("Audio is muted, not playing sound.")
        return
    
    try:
        sound = sounds.get(note_ID)
        if sound:
            sound.play()
        else:
            print(f"Sound for note ID {note_ID} not found.")
            logger.warning(f"Sound for note ID {note_ID} not found.")
    except Exception as e:
        print(f"Failed to play sound: {e}")
        logger.error(f"Failed to play sound: {e}")
