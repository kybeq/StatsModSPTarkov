# config.py
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Ścieżki
JSON_RAID_DATA_ROOT_DIR = os.path.join(BASE_DIR, 'json_raid_data')
TRANSLATIONS_DIR = os.path.join(BASE_DIR, 'translate')
STATIC_FOLDER_NAME = 'static'
TEMPLATES_FOLDER_NAME = 'templates' 

# Ustawienia aplikacji
DEBUG_MODE = True
HOST = '0.0.0.0'
PORT = 5000
USE_RELOADER = True

# Ustawienia tłumaczeń
DEFAULT_LANGUAGE = 'pl'

# Ustawienia cache
CACHE_TTL_SECONDS = 60

# Inne stałe
IGNORED_PLAYER_NICKNAMES = ["handles", "another_ignored_nick"]

MAP_IMAGES = {
    "Fabryka": "factory.avif",
    "Customs": "customs.avif",
    "Woods": "woods.avif",
    "Shoreline": "shoreline.avif",
    "Interchange": "interchange.avif",
    "Reserve": "reserve.avif",
    "Labs": "labs.avif",
    "Streets of Tarkov": "streets.avif",
    "Lighthouse": "lighthouse.avif",
    "Ground Zero": "ground_zero.avif",
    "unknown": "unknown_map.avif"
}