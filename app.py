import os
import csv
import json
import datetime
from datetime import timezone
from flask import Flask, jsonify, request, render_template
from collections import defaultdict

app = Flask(__name__)
app.json.ensure_ascii = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE = os.path.join(BASE_DIR, 'raid_data_full.csv')
TRANSLATIONS_DIR = os.path.join(BASE_DIR, 'translate')
TRANSLATIONS_DICT = {}

CSV_HEADERS = [
    "session_id", "timestamp_utc", "event_type",
    "player_nickname", "player_level", "player_side", "player_game_edition", "player_account_type",
    "map_name", "map_time_of_day", "map_ingame_time_variant",
    "raid_result", "raid_duration_seconds", "raid_duration_formatted",
    "exit_name", "exit_status",
    "experience_total_session", "experience_kill_session", "experience_loot_session", "experience_exit_status_session",
    "kills_total_session", "kills_headshots_session", "damage_inflicted_session",
    "longest_shot_session", 
    "currency_loot_value_roubles_session",
    "victims_details",
    "killed_by_name", "killed_by_role", "killed_by_weapon_name", "killed_on_body_part",
    "body_parts_destroyed_session", "distance_pedometer_session"
]

def load_translations(lang_code='pl'):
    global TRANSLATIONS_DICT
    try:
        translations_file = os.path.join(TRANSLATIONS_DIR, f'{lang_code}.json')
        if not os.path.exists(translations_file):
            TRANSLATIONS_DICT = {}
            return
        with open(translations_file, 'r', encoding='utf-8') as f:
            TRANSLATIONS_DICT = json.load(f)
    except Exception as e:
        print(f"BŁĄD ładowania tłumaczeń {translations_file}: {e}")
        TRANSLATIONS_DICT = {}

def get_item_name(item_id_or_key_list):
    if item_id_or_key_list is None: return ""
    if isinstance(item_id_or_key_list, list):
        key_str = "_".join(map(str, item_id_or_key_list)).lower()
        if key_str in TRANSLATIONS_DICT: return TRANSLATIONS_DICT[key_str]
        item_id_or_key_list = item_id_or_key_list[-1] if item_id_or_key_list else ""
    return TRANSLATIONS_DICT.get(str(item_id_or_key_list), str(item_id_or_key_list))

def get_weapon_id_from_string(weapon_string):
    if weapon_string is None: return None
    return weapon_string.split(" ")[0]

def format_time_seconds(seconds_val):
    if seconds_val is None: return "N/A"
    try:
        seconds = int(float(seconds_val))
        if seconds < 0: seconds = 0
    except: return "N/A"
    minutes, remaining_seconds = divmod(seconds, 60)
    return f"{minutes:02d}:{remaining_seconds:02d}"

def format_distance_meters(meters_val):
    if meters_val is None: return "N/A"
    try: meters = float(meters_val)
    except: return "N/A"
    return f"{meters:.1f} m" # Zwraca z " m"

def get_counter_value(items_list, target_key_as_list, default_value=0):
    if not isinstance(items_list, list): return default_value
    for item in items_list: # Bierze PIERWSZY napotkany pasujący klucz
        if isinstance(item, dict) and item.get("Key") == target_key_as_list:
            return item.get("Value", default_value)
    return default_value

def initialize_csv_file():
    if not os.path.exists(CSV_FILE):
        try:
            with open(CSV_FILE, 'w', encoding='utf-8', newline='') as f:
                csv.writer(f).writerow(CSV_HEADERS)
            print(f"Utworzono plik CSV z nagłówkami: {CSV_FILE}")
        except Exception as e:
            print(f"BŁĄD krytyczny tworzenia CSV: {e}")
    else: 
        try:
            with open(CSV_FILE, 'r', encoding='utf-8', newline='') as f:
                reader = csv.reader(f)
                existing_headers = next(reader, None)
                if existing_headers != CSV_HEADERS:
                    print(f"OSTRZEŻENIE: Nagłówki w CSV ({CSV_FILE}) różnią się. Rozważ usunięcie pliku.")
        except Exception: 
            try: 
                with open(CSV_FILE, 'w', encoding='utf-8', newline='') as f_write:
                    csv.writer(f_write).writerow(CSV_HEADERS)
                print(f"Nadpisano/utworzono plik CSV ({CSV_FILE}) z poprawnymi nagłówkami (poprzedni był pusty/uszkodzony).")
            except Exception as e_write:
                 print(f"BŁĄD krytyczny nadpisywania/tworzenia CSV: {e_write}")

def append_to_csv_file(raid_data_dict):
    if not os.path.exists(CSV_FILE):
        initialize_csv_file()
        if not os.path.exists(CSV_FILE):
             print(f"KRYTYCZNY BŁĄD: CSV nie istnieje. Dane nie zostaną zapisane.")
             return
    try:
        row_values = [str(raid_data_dict.get(h, "")).replace('\r\n',' ').replace('\n',' ').replace('\r',' ') for h in CSV_HEADERS]
        with open(CSV_FILE, 'a', encoding='utf-8', newline='') as f:
            csv.writer(f).writerow(row_values)
    except Exception as e:
        print(f"BŁĄD zapisu do CSV: {e}. Dane: {raid_data_dict}")

def process_raid_data(data_from_mod, is_start_event=False):
    try:
        session_id = data_from_mod.get('sessionId', 'unknown_session')
        timestamp_utc = datetime.datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        processed = defaultdict(str)
        processed['session_id'] = session_id
        processed['timestamp_utc'] = timestamp_utc
        processed['event_type'] = 'start' if is_start_event else 'end'
        request_payload = data_from_mod.get('request', {})

        if is_start_event:
            player_profile = request_payload.get('playerProfile', {}).get('Info', {})
            processed['player_nickname'] = player_profile.get('Nickname', '')
            processed['player_level'] = player_profile.get('Level', '')
            processed['player_side'] = get_item_name(player_profile.get('Side', ''))
            processed['player_game_edition'] = player_profile.get('GameVersion', '')
            time_weather = request_payload.get('timeAndWeatherSettings', {})
            processed['map_name'] = get_item_name(request_payload.get('location', ''))
            processed['map_ingame_time_variant'] = get_item_name(time_weather.get('timeVariant', 'DAY'))
        else: # is_end_event
            results = request_payload.get('results', {})
            profile = results.get('profile', {})
            profile_info = profile.get('Info', {})
            stats_eft = profile.get('Stats', {}).get('Eft', {})
            
            sc_items_debug = stats_eft.get('SessionCounters', {}).get('Items', "BRAK SC.Items")
            print(f"DEBUG SessionCounters.Items (sesja {session_id}): {json.dumps(sc_items_debug, ensure_ascii=False)}")
            
            session_counters = stats_eft.get('SessionCounters', {}).get('Items', [])

            processed['player_nickname'] = profile_info.get('Nickname', '')
            processed['player_level'] = profile_info.get('Level', '')
            processed['player_side'] = get_item_name(profile_info.get('Side', ''))
            processed['player_game_edition'] = profile_info.get('GameVersion', '')
            processed['map_name'] = get_item_name(profile_info.get('EntryPoint', ''))
            
            raw_result = results.get('result', 'Unknown')
            processed['raid_result'] = get_item_name(raw_result)
            duration_s = results.get('playTime', stats_eft.get('TotalInGameTime'))
            processed['raid_duration_seconds'] = str(int(float(duration_s))) if duration_s is not None else ''
            processed['raid_duration_formatted'] = format_time_seconds(duration_s)

            if raw_result.lower() == 'survived':
                processed['exit_name'] = get_item_name(results.get('exitName', ''))
                processed['exit_status'] = get_item_name(results.get('exitStatus', raw_result))

            processed['experience_total_session'] = str(profile_info.get('Experience', 0))
            processed['experience_kill_session'] = str(get_counter_value(session_counters, ["ExpKill"], 0))
            processed['experience_loot_session'] = str(get_counter_value(session_counters, ["ExpLooting"], 0))
            processed['experience_exit_status_session'] = str(get_counter_value(session_counters, ["Exp", "ExpExitStatus"], 0))

            victims = stats_eft.get('Victims', [])
            processed['kills_total_session'] = str(len(victims))
            headshots = sum(1 for v in victims if v.get('BodyPart','').lower() == 'head')
            processed['kills_headshots_session'] = str(headshots)
            
            processed['damage_inflicted_session'] = str(get_counter_value(session_counters, ["CombatDamage"], 0))
            processed['body_parts_destroyed_session'] = str(get_counter_value(session_counters, ["BodyPartsDestroyed"], 0)) # Bierze pierwszy napotkany
            
            longest_kill_shot_val = get_counter_value(session_counters, ["LongestKillShot"], None)
            # Usuwamy " m" z format_distance_meters, bo chcemy tylko liczbę
            processed['longest_shot_session'] = format_distance_meters(longest_kill_shot_val).replace(' m', '') if longest_kill_shot_val is not None else ''
            
            pedometer_val = get_counter_value(session_counters, ["Pedometer"], 0)
            processed['distance_pedometer_session'] = str(int(float(pedometer_val))) if pedometer_val is not None else ''

            victim_details = [f"{v.get('Name','N/A')}|{get_item_name(v.get('Role',''))}|{v.get('Level',0)}|{get_item_name(v.get('BodyPart',''))}|{get_item_name(get_weapon_id_from_string(v.get('Weapon')))}|{format_distance_meters(v.get('Distance'))}" for v in victims]
            processed['victims_details'] = "; ".join(victim_details)

            if raw_result.lower() == 'killed':
                aggressor = stats_eft.get('Aggressor', {})
                death_cause = stats_eft.get('DeathCause', {})
                dmg_hist = stats_eft.get('DamageHistory', {})
                processed['killed_by_name'] = aggressor.get('Name', 'N/A')
                processed['killed_by_role'] = get_item_name(aggressor.get('Role', ''))
                weapon_id_aggr = get_weapon_id_from_string(aggressor.get('WeaponName'))
                weapon_id_dc = death_cause.get('WeaponId')
                processed['killed_by_weapon_name'] = get_item_name(weapon_id_dc or weapon_id_aggr)
                processed['killed_on_body_part'] = get_item_name(dmg_hist.get('LethalDamagePart', ''))
        return processed, None
    except Exception as e:
        print(f"KRYTYCZNY BŁĄD przetwarzania: {e}")
        import traceback
        traceback.print_exc()
        return None, f"Błąd przetwarzania: {e}"

@app.route('/')
def route_index():
    entries = []
    if os.path.exists(CSV_FILE):
        try:
            with open(CSV_FILE, 'r', encoding='utf-8') as f:
                if not f.read(1): return render_template('index.html', raids=[], csv_headers=CSV_HEADERS)
                f.seek(0)
                reader = csv.DictReader(f)
                try:
                    all_entries = list(reader)
                    entries = all_entries[-20:]
                    entries.reverse()
                except csv.Error as csv_e: entries = [{"error": f"Błąd struktury CSV: {csv_e}"}]
        except Exception as e: entries = [{"error": str(e)}]
    else:
        print(f"Plik CSV ({CSV_FILE}) nie istnieje. index.html otrzyma puste dane.")
    return render_template('index.html', raids=entries, csv_headers=CSV_HEADERS)

@app.route('/api/mod/connect', methods=['POST'])
def mod_connect():
    request.get_json() 
    return jsonify({"status": "success"})

@app.route('/api/raid/start', methods=['POST'])
def raid_start():
    data = request.get_json()
    if not data: return jsonify({"error": "Brak danych JSON"}), 400
    processed, error = process_raid_data(data, is_start_event=True)
    if error: return jsonify({"error": error}), 400
    append_to_csv_file(processed)
    return jsonify({"status": "success"})

@app.route('/api/raid/end', methods=['POST'])
def raid_end():
    data = request.get_json()
    if not data: return jsonify({"error": "Brak danych JSON"}), 400
    processed, error = process_raid_data(data, is_start_event=False)
    if error: return jsonify({"error": error}), 400
    append_to_csv_file(processed)
    return jsonify({"status": "success"})

if __name__ == '__main__':
    print("Uruchamianie aplikacji Flask...")
    load_translations()
    initialize_csv_file() 
    print(f"Nasłuchiwanie na http://0.0.0.0:5000")
    print(f"Dane CSV: {CSV_FILE}")
    if not TRANSLATIONS_DICT: print("OSTRZEŻENIE: Słownik tłumaczeń pusty.")
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)