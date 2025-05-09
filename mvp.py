import os
import csv
import json
import datetime
from flask import Flask, jsonify, request
from collections import defaultdict

app = Flask(__name__)
app.json.ensure_ascii = False  # Obsługa polskich znaków

# Ścieżka do pliku CSV
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE = os.path.join(BASE_DIR, 'raid_data.csv')

# Słownik tłumaczeń
TRANSLATIONS = {
    "factory4_day": "Fabryka",
    "Factory": "Fabryka",
    "assault": "Szturmowiec (Scav)",
    "Head": "Głowa",
    "Chest": "Klatka piersiowa",
    "pmcBEAR": "PMC BEAR",
    "pmcUSEC": "PMC USEC",
    "Bear": "BEAR",
    "Usec": "USEC",
    "Bullet": "Pocisk",
    "Melee": "Broń biała",
    # Dodaj inne, jeśli potrzebne
}

def get_item_name(item_id):
    return TRANSLATIONS.get(item_id, str(item_id))

def format_time(seconds):
    if seconds is None:
        return "N/A"
    seconds = int(seconds)
    minutes = seconds // 60
    remaining_seconds = seconds % 60
    return f"{minutes:02d}:{remaining_seconds:02d}"

def format_distance(meters):
    if meters is None:
        return "N/A"
    meters = float(meters)
    return f"{meters:.1f} m"

def initialize_csv():
    """Tworzy pusty plik CSV z nagłówkami, jeśli nie istnieje."""
    if not os.path.exists(CSV_FILE):
        headers = [
            "session_id", "timestamp", "type", "location", "time_of_day", "nickname",
            "level", "side", "raid_result", "play_time", "kills_count", "victims",
            "total_experience", "killer_info"
        ]
        with open(CSV_FILE, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
        print(f"Utworzono plik CSV: {CSV_FILE}")

def append_to_csv(raid_data):
    """Dodaje dane rajdu do CSV."""
    try:
        with open(CSV_FILE, 'a', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            victims_str = ";".join([
                f"{v['Name']}|{v['RoleTranslated']}|{v['BodyPartTranslated']}|{v['DistanceFormatted']}"
                for v in raid_data.get('victims', [])
            ]) if raid_data.get('victims') else ""
            killer_info = raid_data.get('killer_info', '')
            if killer_info:
                killer_info = f"{killer_info['name']}|{killer_info['role_translated']}|{killer_info['weapon_name']}|{killer_info['killed_by_part_translated']}"
            row = [
                raid_data.get('session_id', ''),
                raid_data.get('timestamp', ''),
                raid_data.get('type', ''),
                raid_data.get('location', ''),
                raid_data.get('time_of_day', ''),
                raid_data.get('nickname', ''),
                raid_data.get('level', ''),
                raid_data.get('side', ''),
                raid_data.get('raid_result', ''),
                raid_data.get('play_time', ''),
                raid_data.get('kills_count', ''),
                victims_str,
                raid_data.get('total_experience', ''),
                killer_info
            ]
            writer.writerow(row)
        print(f"Zapisano dane do CSV: {raid_data.get('session_id')}")
    except Exception as e:
        print(f"BŁĄD: Nie można zapisać do CSV: {e}")

def process_raid_data(data, is_start=False):
    """Przetwarza dane rajdu na format do CSV."""
    try:
        session_id = data.get('sessionId', 'unknown')
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        processed = {
            'session_id': session_id,
            'timestamp': timestamp,
            'type': 'start' if is_start else 'end'
        }

        if is_start:
            request = data.get('request', {})
            processed['location'] = get_item_name(request.get('location', 'unknown'))
            processed['time_of_day'] = request.get('timeAndWeatherSettings', {}).get('timeVariant', 'day')  # Domyślnie 'day'
        else:
            results = data.get('request', {}).get('results', {})
            profile = results.get('profile', {})
            info = profile.get('Info', {})
            stats_eft = profile.get('Stats', {}).get('Eft', {})

            processed['location'] = get_item_name(info.get('EntryPoint', 'unknown'))
            processed['nickname'] = info.get('Nickname', '')
            processed['level'] = info.get('Level', '')
            processed['side'] = get_item_name(info.get('Side', ''))
            processed['raid_result'] = results.get('result', '').capitalize()  # Np. 'killed' → 'Killed'
            processed['total_experience'] = info.get('Experience', 0)
            play_time = stats_eft.get('TotalInGameTime', results.get('playTime', 0))
            processed['play_time'] = format_time(play_time)
            victims = stats_eft.get('Victims', [])
            processed['kills_count'] = len(victims)
            processed['victims'] = [
                {
                    'Name': v.get('Name', ''),
                    'RoleTranslated': get_item_name(v.get('Role', '')),
                    'BodyPartTranslated': get_item_name(v.get('BodyPart', '')),
                    'DistanceFormatted': format_distance(v.get('Distance'))
                }
                for v in victims
            ]

            # Informacje o zabójcy (jeśli raid_result == 'Killed')
            if processed['raid_result'] == 'Killed':
                aggressor = stats_eft.get('Aggressor', {})
                death_cause = stats_eft.get('DeathCause', {})
                damage_history = stats_eft.get('DamageHistory', {})
                killer_data = {
                    'name': aggressor.get('Name', 'Unknown'),
                    'role_translated': get_item_name(aggressor.get('Role', 'Unknown')),
                    'weapon_name': get_item_name(death_cause.get('WeaponId', 'Unknown')),
                    'killed_by_part_translated': get_item_name(damage_history.get('LethalDamagePart', 'Unknown'))
                }
                processed['killer_info'] = killer_data

        return processed, None
    except Exception as e:
        return None, f"Nie można przetworzyć danych: {e}"

@app.route('/api/mod/connect', methods=['POST'])
def mod_connect():
    data = request.get_json()
    if not data:
        print("BŁĄD: Brak danych JSON w /api/mod/connect")
        return jsonify({"error": "Brak danych JSON"}), 400
    mod_name = data.get("mod", "Unknown")
    status = data.get("status", "unknown")
    print(f"Mod connected: {mod_name} (Status: {status})")
    return jsonify({"status": "success"})

@app.route('/api/raid/start', methods=['POST'])
def raid_start():
    data = request.get_json()
    if not data:
        print("BŁĄD: Brak danych JSON w /api/raid/start")
        return jsonify({"error": "Brak danych JSON"}), 400
    processed_data, error = process_raid_data(data, is_start=True)
    if error:
        print(f"BŁĄD: {error}")
        return jsonify({"error": error}), 400
    append_to_csv(processed_data)
    return jsonify({"status": "success"})

@app.route('/api/raid/end', methods=['POST'])
def raid_end():
    data = request.get_json()
    if not data:
        print("BŁĄD: Brak danych JSON w /api/raid/end")
        return jsonify({"error": "Brak danych JSON"}), 400
    processed_data, error = process_raid_data(data, is_start=False)
    if error:
        print(f"BŁĄD: {error}")
        return jsonify({"error": error}), 400
    append_to_csv(processed_data)
    return jsonify({"status": "success"})

if __name__ == '__main__':
    initialize_csv()
    app.run(debug=True, host='0.0.0.0', port=5000)