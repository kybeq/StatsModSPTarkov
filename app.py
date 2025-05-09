import os
import json
import datetime
from datetime import timezone
from flask import Flask, jsonify, request, render_template, url_for, abort
from collections import defaultdict
import locale
import shutil 

app = Flask(__name__)
app.json.ensure_ascii = False

try:
    locale.setlocale(locale.LC_ALL, 'pl_PL.UTF-8')
except locale.Error:
    try: locale.setlocale(locale.LC_ALL, 'Polish_Poland.1250')
    except locale.Error: print("OSTRZEŻENIE: Nie można ustawić polskiego locale.")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_RAID_DATA_ROOT_DIR = os.path.join(BASE_DIR, 'json_raid_data')
TRANSLATIONS_DIR = os.path.join(BASE_DIR, 'translate')
STATIC_FOLDER = os.path.join(BASE_DIR, 'static')
app.static_folder = STATIC_FOLDER

TRANSLATIONS_DICT = {}
MAP_IMAGES = {
    "Fabryka": "factory.avif", "Fabryce": "factory.avif", "Customs": "customs.avif",
    "Lasy": "woods.avif", "Linia Brzegowa": "shoreline.avif", "Węzeł": "interchange.avif",
    "Rezerwa": "reserve.avif", "Laboratorium": "labs.avif", "Ulice Tarkowa": "streets.avif",
    "Latarnia": "lighthouse.avif", "Ground Zero": "ground_zero.avif", "Miasto": "town.avif",
    "unknown": "unknown_map.avif", "Nieznana Mapa": "unknown_map.avif", "N/A": "unknown_map.avif"
}

IGNORED_PLAYER_NICKNAMES = ["handles", "another_ignored_nick"] 

RAID_DATA_CACHE = {'all_raids_summary': [], 'players_summary': {}, 'last_updated': datetime.datetime.min, 'errors': []}
CACHE_TTL_SECONDS = 60 
ACTIVE_RAIDS_INFO = {} 

def ensure_dir_exists(dir_path):
    if not os.path.exists(dir_path):
        try: os.makedirs(dir_path); print(f"Utworzono katalog: {dir_path}")
        except Exception as e: print(f"BŁĄD: Nie można utworzyć katalogu {dir_path}: {e}")

def load_translations(lang_code='pl'):
    global TRANSLATIONS_DICT
    try:
        translations_file = os.path.join(TRANSLATIONS_DIR, f'{lang_code}.json')
        if not os.path.exists(translations_file): TRANSLATIONS_DICT = {}; return
        with open(translations_file, 'r', encoding='utf-8') as f: TRANSLATIONS_DICT = json.load(f)
    except Exception as e: print(f"BŁĄD ładowania tłumaczeń {translations_file}: {e}"); TRANSLATIONS_DICT = {}

def get_item_name(item_id_or_key_list, default_if_not_found=True):
    original_value = str(item_id_or_key_list) if item_id_or_key_list is not None else ""
    if item_id_or_key_list is None or item_id_or_key_list == "": 
        return "N/A" if default_if_not_found and isinstance(item_id_or_key_list, str) and item_id_or_key_list == "" else ""
    if isinstance(item_id_or_key_list, list):
        key_str = "_".join(map(str, item_id_or_key_list)).lower()
        if key_str in TRANSLATIONS_DICT: return TRANSLATIONS_DICT[key_str]
        item_id_or_key_list = item_id_or_key_list[-1] if item_id_or_key_list else ""
    translation = TRANSLATIONS_DICT.get(str(item_id_or_key_list))
    return translation if translation is not None else (original_value if default_if_not_found else "")

def get_weapon_id_from_string(weapon_string):
    if weapon_string is None: return None
    return weapon_string.split(" ")[0]

def format_time_seconds(seconds_val):
    if seconds_val is None or str(seconds_val).strip() == "": return "N/A"
    try:
        seconds = int(float(seconds_val))
        if seconds < 0: seconds = 0
    except: return "N/A"
    minutes, remaining_seconds = divmod(seconds, 60)
    return f"{minutes:02d}:{remaining_seconds:02d}"

def format_distance_meters(meters_val, include_unit=False, is_longest_kill_shot=False):
    if meters_val is None or str(meters_val).strip() == "": return "N/A" if include_unit else ""
    try: 
        meters = float(meters_val)
        if is_longest_kill_shot: 
            meters /= 10.0
    except: return "N/A" if include_unit else ""
    unit = " m" if include_unit else ""
    return f"{meters:.1f}{unit}"

def format_exp(exp_val):
    if exp_val is None or str(exp_val).strip() == "": return "0"
    try:
        exp = int(float(exp_val))
        return locale.format_string("%d", exp, grouping=True).replace(",", " ")
    except: return str(exp_val)
    
def get_counter_value_from_json_list(items_list, target_key_as_list, default_value=0):
    if not isinstance(items_list, list): return default_value
    for item in reversed(items_list): 
        if isinstance(item, dict) and item.get("Key") == target_key_as_list:
            val = item.get("Value", default_value)
            try: return int(float(val))
            except: return val 
    return default_value

def save_raid_json_data(data, player_nickname_raw, session_id_raw, event_type):
    player_nickname = str(player_nickname_raw if player_nickname_raw else "UnknownPlayer")
    session_id = str(session_id_raw if session_id_raw else "unknown_session")
    if player_nickname.lower() in [nick.lower() for nick in IGNORED_PLAYER_NICKNAMES]:
        print(f"Pominięto zapis JSON dla gracza '{player_nickname}'.")
        return None
    player_dir_name = "".join(c if c.isalnum() else '_' for c in player_nickname)
    player_dir = os.path.join(JSON_RAID_DATA_ROOT_DIR, player_dir_name)
    ensure_dir_exists(player_dir)
    timestamp_file_str = datetime.datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
    safe_session_id = "".join(c if c.isalnum() or c in ['-', '_'] else '_' for c in session_id)
    filename = f"{safe_session_id}_{timestamp_file_str}_{event_type}.json"
    filepath_full = os.path.join(player_dir, filename)
    filepath_relative = os.path.join(player_dir_name, filename) 
    try:
        with open(filepath_full, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Zapisano JSON: {filepath_relative}")
        return filepath_relative 
    except Exception as e:
        print(f"BŁĄD zapisu JSON {filepath_full}: {e}")
        return None

def parse_raid_end_json_for_summary(filepath_full, filepath_relative_to_root):
    try:
        with open(filepath_full, 'r', encoding='utf-8') as f: data = json.load(f)
    except Exception as e: print(f"Błąd odczytu JSON {filepath_full}: {e}"); return None
    summary = {}
    try:
        request_data = data.get('request', {}); results = request_data.get('results', {})
        profile_node = results.get('profile', {}); profile_info = profile_node.get('Info', {}) # Użyj profile_node
        stats_eft = profile_node.get('Stats', {}).get('Eft', {})
        session_counters = stats_eft.get('SessionCounters', {}).get('Items', [])
        victims = stats_eft.get('Victims', [])

        summary['session_id'] = data.get('sessionId', profile_node.get('_id', 'N/A'))
        try:
            filename_parts = os.path.basename(filepath_full).split('_')
            if len(filename_parts) >= 4:
                dt_str_date = filename_parts[1]; dt_str_time = filename_parts[2]
                summary['timestamp_utc'] = datetime.datetime.strptime(f"{dt_str_date}{dt_str_time}", '%Y%m%d%H%M%S').strftime('%Y-%m-%d %H:%M:%S')
            else: summary['timestamp_utc'] = datetime.datetime.fromtimestamp(os.path.getmtime(filepath_full), tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        except: summary['timestamp_utc'] = datetime.datetime.fromtimestamp(os.path.getmtime(filepath_full), tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        
        summary['player_nickname'] = profile_info.get('Nickname', 'N/A')
        summary['player_level'] = profile_info.get('Level', '0')
        summary['player_side'] = get_item_name(profile_info.get('Side', ''))
        summary['map_name'] = get_item_name(profile_info.get('EntryPoint', ''))
        raw_raid_result = results.get('result', 'Unknown')
        summary['raid_result'] = get_item_name(raw_raid_result)
        summary['raid_duration_formatted'] = format_time_seconds(results.get('playTime', stats_eft.get('TotalInGameTime')))
        raid_res_lower = raw_raid_result.lower()
        survived_key = get_item_name('Survived', False).lower()
        if raid_res_lower == survived_key or (survived_key == "" and raid_res_lower == 'survived'):
            summary['exit_name'] = get_item_name(results.get('exitName', ''))
        else: summary['exit_name'] = ''
        summary['kills_total_session'] = len(victims) if isinstance(victims, list) else 0
        summary['kills_headshots_session'] = sum(1 for v in victims if isinstance(v,dict) and v.get('BodyPart','').lower() == 'head') if isinstance(victims, list) else 0
        exp_kill = get_counter_value_from_json_list(session_counters, ["ExpKill"], 0)
        exp_loot = get_counter_value_from_json_list(session_counters, ["ExpLooting"], 0)
        exp_exit = get_counter_value_from_json_list(session_counters, ["Exp", "ExpExitStatus"], 0)
        summary['experience_gained_session'] = exp_kill + exp_loot + exp_exit
        lks_val = get_counter_value_from_json_list(session_counters, ["LongestKillShot"], None)
        summary['longest_shot_session_val'] = (float(lks_val) / 10.0) if lks_val is not None else 0.0
        summary['json_file_path_relative'] = filepath_relative_to_root 
        return summary
    except Exception as e:
        print(f"Błąd parsowania podsumowania z {filepath_full}: {e}"); import traceback; traceback.print_exc()
        return None

def get_or_refresh_data_cache():
    global RAID_DATA_CACHE
    now = datetime.datetime.now()
    if RAID_DATA_CACHE.get('all_raids_summary') and \
       (now - RAID_DATA_CACHE.get('last_updated', datetime.datetime.min)).total_seconds() < CACHE_TTL_SECONDS:
        return RAID_DATA_CACHE 
    print("Odświeżanie cache (z plików JSON)...")
    all_raids_summary_list = [] 
    players_summary_intermediate = defaultdict(lambda: {
        'nickname': '', 'latest_level': '0', 'latest_side': '', 'latest_game_edition': '',
        'raid_count': 0, 'total_kills': 0, 'total_deaths': 0, 'total_survived': 0,
        'total_headshots': 0, 'total_gained_exp_from_raids': 0, 'longest_shot_ever': 0.0 
    })
    current_errors = []
    ensure_dir_exists(JSON_RAID_DATA_ROOT_DIR)
    for player_nick_dir_name in os.listdir(JSON_RAID_DATA_ROOT_DIR):
        player_dir_path = os.path.join(JSON_RAID_DATA_ROOT_DIR, player_nick_dir_name)
        if os.path.isdir(player_dir_path) and player_nick_dir_name.lower() not in [n.lower() for n in IGNORED_PLAYER_NICKNAMES]:
            for filename in os.listdir(player_dir_path):
                if filename.endswith("_end.json"):
                    filepath_full = os.path.join(player_dir_path, filename)
                    filepath_relative = os.path.join(player_nick_dir_name, filename)
                    raid_summary = parse_raid_end_json_for_summary(filepath_full, filepath_relative)
                    if raid_summary:
                        all_raids_summary_list.append(raid_summary)
                        nickname = raid_summary.get('player_nickname')
                        if nickname:
                            player = players_summary_intermediate[nickname]
                            if not player['nickname']: player['nickname'] = nickname
                            player['latest_level'] = raid_summary.get('player_level', player['latest_level'])
                            player['latest_side'] = raid_summary.get('player_side', player['latest_side'])
                            try:
                                if not player.get('latest_game_edition') and os.path.exists(filepath_full):
                                    with open(filepath_full, 'r', encoding='utf-8') as f_temp: data_temp = json.load(f_temp)
                                    player['latest_game_edition'] = data_temp.get('request',{}).get('results',{}).get('profile',{}).get('Info',{}).get('GameVersion','')
                            except Exception as e_ge: print(f"Błąd odczytu game_edition z {filepath_full}: {e_ge}")
                            player['raid_count'] += 1
                            player['total_kills'] += int(raid_summary.get('kills_total_session', 0) or 0)
                            player['total_headshots'] += int(raid_summary.get('kills_headshots_session', 0) or 0)
                            player['total_gained_exp_from_raids'] += int(raid_summary.get('experience_gained_session', 0) or 0)
                            current_raid_lks = raid_summary.get('longest_shot_session_val', 0.0)
                            if current_raid_lks > player['longest_shot_ever']:
                                player['longest_shot_ever'] = current_raid_lks
                            raid_res_lower = raid_summary.get('raid_result', '').lower()
                            survived_key = get_item_name('Survived').lower() 
                            killed_key = get_item_name('Killed').lower()
                            mia_key = get_item_name('MissingInAction').lower()
                            runner_key = get_item_name('Runner').lower()
                            if raid_res_lower == survived_key: player['total_survived'] += 1
                            elif raid_res_lower in [killed_key, mia_key, runner_key]: player['total_deaths'] += 1
    final_players_summary = {}
    for nickname, data in players_summary_intermediate.items():
        data_copy = dict(data) 
        data_copy['calculated_kd'] = f"{data_copy['total_kills'] / data_copy['total_deaths']:.2f}" if data_copy['total_deaths'] > 0 else str(data_copy['total_kills'])
        data_copy['survival_rate'] = f"{(data_copy['total_survived'] / data_copy['raid_count'] * 100):.1f}%" if data_copy['raid_count'] > 0 else "0.0%"
        data_copy['latest_total_experience_formatted'] = format_exp(data_copy['total_gained_exp_from_raids'])
        data_copy['side_translated'] = get_item_name(data_copy['latest_side'])
        data_copy['longest_shot_ever_formatted'] = format_distance_meters(data_copy['longest_shot_ever'], include_unit=True, is_longest_kill_shot=False) if data_copy['longest_shot_ever'] > 0 else "N/A" # is_longest_kill_shot=False bo to już metry
        final_players_summary[nickname] = data_copy

    all_raids_summary_list.sort(key=lambda r: r.get('timestamp_utc', '0'), reverse=True) 
    RAID_DATA_CACHE['all_raids_summary'] = all_raids_summary_list
    RAID_DATA_CACHE['players_summary'] = final_players_summary
    RAID_DATA_CACHE['last_updated'] = now
    RAID_DATA_CACHE['errors'] = current_errors
    if not current_errors: print("Cache (z JSON) został odświeżony.")
    else: print(f"Cache (z JSON) odświeżony z błędami: {current_errors}")
    return RAID_DATA_CACHE

@app.context_processor
def inject_utilities():
    def get_map_image_url_for_template(location_name_from_data):
        map_key = location_name_from_data 
        if map_key not in MAP_IMAGES: map_key = get_item_name(location_name_from_data)
        filename = MAP_IMAGES.get(map_key, MAP_IMAGES["unknown"])
        try: return url_for('static', filename=f"images/maps/{filename}")
        except RuntimeError: return f"/static/images/maps/{filename}" 
    return dict(get_item_name=get_item_name, format_exp=format_exp, get_map_image_url=get_map_image_url_for_template, now=datetime.datetime.now(timezone.utc))

@app.route('/')
def index():
    cache = get_or_refresh_data_cache()
    recent_raids_display = []
    for summary_row in cache['all_raids_summary'][:20]: 
        player_s = cache['players_summary'].get(summary_row.get('player_nickname'), {})
        display_raid = dict(summary_row) 
        display_raid['exp'] = summary_row.get('experience_gained_session') 
        display_raid['raid_count'] = player_s.get('raid_count', 'N/A')
        ts_utc_str = summary_row.get('timestamp_utc')
        try: display_raid['timestamp_formatted'] = datetime.datetime.strptime(ts_utc_str, '%Y-%m-%d %H:%M:%S').strftime('%d.%m.%Y %H:%M') if ts_utc_str else 'N/A'
        except ValueError: display_raid['timestamp_formatted'] = ts_utc_str 
        display_raid['location'] = summary_row.get('map_name')
        display_raid['kills_count'] = summary_row.get('kills_total_session')
        display_raid['play_time_formatted'] = summary_row.get('raid_duration_formatted')
        display_raid['nickname'] = summary_row.get('player_nickname')
        display_raid['level'] = player_s.get('latest_level', summary_row.get('player_level'))
        display_raid['side'] = player_s.get('latest_side', summary_row.get('player_side'))
        recent_raids_display.append(display_raid)
    latest_raid_display = recent_raids_display[0] if recent_raids_display else None
    return render_template('index.html', latest_raid=latest_raid_display, recent_raids=recent_raids_display, errors=cache.get('errors', []))

@app.route('/players')
def players_list():
    cache = get_or_refresh_data_cache()
    sorted_players = sorted(cache['players_summary'].values(), key=lambda p: p.get('nickname','').lower())
    return render_template('gracze.html', players_list=sorted_players, errors=cache.get('errors', []))

@app.route('/player/<nickname>')
def player_details(nickname):
    cache = get_or_refresh_data_cache()
    player_info_summary = cache['players_summary'].get(nickname)
    if not player_info_summary: abort(404)
    player_raids_summary_list = [rs for rs in cache['all_raids_summary'] if rs.get('player_nickname') == nickname]
    player_raids_for_template = []
    for summary in player_raids_summary_list:
        raid_display_data = dict(summary)
        ts_utc_str = summary.get('timestamp_utc')
        try: raid_display_data['timestamp_formatted'] = datetime.datetime.strptime(ts_utc_str, '%Y-%m-%d %H:%M:%S').strftime('%d.%m.%Y %H:%M') if ts_utc_str else 'N/A'
        except ValueError: raid_display_data['timestamp_formatted'] = ts_utc_str
        raid_display_data['location'] = summary.get('map_name')
        raid_display_data['play_time_formatted'] = summary.get('raid_duration_formatted')
        raid_display_data['kills_count'] = summary.get('kills_total_session')
        raid_display_data['total_session_exp_calculated'] = summary.get('experience_gained_session')
        raid_display_data['data_json_path_relative'] = summary.get('json_file_path_relative')
        player_raids_for_template.append(raid_display_data)
    latest_raid_for_player_template = player_raids_for_template[0] if player_raids_for_template else None
    player_stats_display = {
        'sessions': player_info_summary.get('raid_count', 0), 'survived_sessions': player_info_summary.get('total_survived', 0),
        'deaths': player_info_summary.get('total_deaths', 0), 'kills': player_info_summary.get('total_kills', 0),
        'survival_rate': player_info_summary.get('survival_rate', 'N/A'), 'kd_ratio': player_info_summary.get('calculated_kd', 'N/A'),
        'headshots': player_info_summary.get('total_headshots',0), 'longest_shot_formatted': player_info_summary.get('longest_shot_ever_formatted', 'N/A')
    }
    skills_for_template = [] 
    achievements_for_template = []
    if latest_raid_for_player_template and latest_raid_for_player_template.get('json_file_path_relative'):
        try:
            full_path = os.path.join(JSON_RAID_DATA_ROOT_DIR, latest_raid_for_player_template['json_file_path_relative'])
            if os.path.exists(full_path):
                with open(full_path, 'r', encoding='utf-8') as f_raid:
                    raid_detail_data_payload = json.load(f_raid)
                    raid_detail_request = raid_detail_data_payload.get('request', {})
                    profile_data = raid_detail_request.get('results',{}).get('profile',{}) # Zmieniono na profile_data
                    
                    profile_skills = profile_data.get('Skills',{}) # Użyj profile_data
                    if isinstance(profile_skills.get('Common'), list):
                        for skill in profile_skills['Common']:
                            if isinstance(skill, dict) and float(skill.get('PointsEarnedDuringSession', 0) or 0) > 0:
                                skills_for_template.append({'SkillName': get_item_name(skill.get('Id')), 'Progress': f"{float(skill.get('Progress',0) or 0):.2f}", 
                                                            'PointsEarnedFormatted': f"{float(skill.get('PointsEarnedDuringSession',0) or 0):.2f}", 'SkillType': 'Common'})
                    if isinstance(profile_skills.get('Mastering'), list):
                        for skill in profile_skills['Mastering']:
                            if isinstance(skill, dict) and float(skill.get('Progress', 0) or 0) > 0 :
                                skills_for_template.append({'SkillName': get_item_name(skill.get('Id')), 'Progress': f"{float(skill.get('Progress',0) or 0):.2f}", 
                                                            'PointsEarnedFormatted': 'N/A', 'SkillType': 'Mastering'})

                    profile_achievements = profile_data.get('Achievements',{}) # Użyj profile_data
                    if isinstance(profile_achievements, dict):
                        for ach_id, timestamp in profile_achievements.items():
                            ach_ts_str = 'N/A'
                            if isinstance(timestamp, (int, float)) and timestamp > 0:
                                try: ach_ts_str = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M')
                                except: pass
                            achievements_for_template.append({'id': get_item_name(ach_id).lower().replace(" ","_").replace("(","").replace(")","").replace(":",""), 
                                                              'name': get_item_name(ach_id), 'timestamp': ach_ts_str})
            else: print(f"Plik JSON dla umiejętności/osiągnięć nie znaleziony: {full_path}")
        except Exception as e: print(f"Błąd wczytywania szczegółów JSON dla profilu: {e}")

    return render_template('profil.html', 
                           nickname=nickname, player_info=player_info_summary, 
                           player_stats=player_stats_display,
                           latest_raid=latest_raid_for_player_template, 
                           player_raids=player_raids_for_template,
                           skills=skills_for_template, achievements=achievements_for_template, 
                           errors=cache.get('errors', []))

@app.route('/api/raid_json_details') 
def api_raid_json_details():
    filepath_relative = request.args.get('path') 
    if not filepath_relative: return jsonify(error="Brak parametru 'path'", data=None), 400
    safe_base = os.path.abspath(JSON_RAID_DATA_ROOT_DIR)
    filepath_relative_cleaned = filepath_relative.lstrip('/\\')
    full_filepath = os.path.abspath(os.path.join(JSON_RAID_DATA_ROOT_DIR, filepath_relative_cleaned))
    if not full_filepath.startswith(safe_base) or ".." in filepath_relative_cleaned :
        return jsonify(error="Nieprawidłowa ścieżka pliku.", data=None), 400
    if not os.path.exists(full_filepath) or not os.path.isfile(full_filepath):
        return jsonify(error=f"Plik JSON nie znaleziony: {filepath_relative_cleaned}", data=None), 404
    try:
        with open(full_filepath, 'r', encoding='utf-8') as f: raid_full_data_payload = json.load(f)
        
        modal_response_data = {}
        request_node = raid_full_data_payload.get('request', {})
        results_node = request_node.get('results', {})
        # POPRAWKA: profile_node zamiast profile
        profile_node = results_node.get('profile', {}) 
        
        if not profile_node: # Sprawdzenie czy profile_node istnieje
             print(f"BŁĄD API: Brak 'profile' w {filepath_relative_cleaned}")
             return jsonify(error="Brak kluczowych danych 'profile' w pliku JSON rajdu.", data=None), 500

        profile_info_node = profile_node.get('Info', {})
        stats_eft_node = profile_node.get('Stats', {}).get('Eft', {})
        health_data_raw = profile_node.get('Health', {})
        skills_data_raw = profile_node.get('Skills', {})
        inventory_items_raw = profile_node.get('Inventory',{}).get('items',[])

        modal_response_data['location'] = get_item_name(profile_info_node.get('EntryPoint'))
        try:
            fn_parts = os.path.basename(full_filepath).split('_')
            if len(fn_parts) >= 4: dt_str = f"{fn_parts[1]}{fn_parts[2]}"; modal_response_data['timestamp_formatted'] = datetime.datetime.strptime(dt_str, '%Y%m%d%H%M%S').strftime('%d.%m.%Y %H:%M')
            else: modal_response_data['timestamp_formatted'] = 'N/A'
        except: modal_response_data['timestamp_formatted'] = 'N/A'
        raw_raid_result_modal = results_node.get('result')
        modal_response_data['raid_result'] = get_item_name(raw_raid_result_modal)
        if (raw_raid_result_modal or "").lower() in ['survived', get_item_name('Survived',False).lower(), 'przetrwano']:
            modal_response_data['exit_name'] = get_item_name(results_node.get('exitName'))
        else: modal_response_data['exit_name'] = "---"
        modal_response_data['survivor_class'] = get_item_name(stats_eft_node.get('SurvivorClass'))
        modal_response_data['play_time_formatted'] = format_time_seconds(results_node.get('playTime', stats_eft_node.get('TotalInGameTime')))
        modal_response_data['player_count_in_raid'] = "N/A"
        
        victims_list_raw = stats_eft_node.get('Victims', [])
        parsed_victims = []
        if isinstance(victims_list_raw, list):
            for v_dict in victims_list_raw:
                if not isinstance(v_dict, dict): continue
                weapon_id_raw = v_dict.get('Weapon'); weapon_id_clean = get_weapon_id_from_string(weapon_id_raw)
                dist_val = v_dict.get('Distance')
                parsed_victims.append({'Name':v_dict.get('Name','N/A'),'RoleTranslated':get_item_name(v_dict.get('Role','')),
                                       'Level':v_dict.get('Level',0),'BodyPartTranslated':get_item_name(v_dict.get('BodyPart','')),
                                       'WeaponName':get_item_name(weapon_id_clean),'DistanceFormatted':format_distance_meters(dist_val, include_unit=True)})
        modal_response_data['victims'] = parsed_victims 
        modal_response_data['kills_count'] = len(parsed_victims)

        killer_info_data = {}
        if (raw_raid_result_modal or "").lower() in ['killed', get_item_name('Killed',False).lower(), 'zabity']:
            aggressor = stats_eft_node.get('Aggressor', {}); death_cause = stats_eft_node.get('DeathCause', {}); 
            dmg_hist = stats_eft_node.get('DamageHistory', {})
            lethal_dmg_info = dmg_hist.get('LethalDamage',{})
            killer_info_data = {
                'name': aggressor.get('Name', 'N/A'), 'role_translated': get_item_name(aggressor.get('Role', '')),
                'side': get_item_name(aggressor.get('Side', '')), 
                'weapon_name': get_item_name(death_cause.get('WeaponId') or get_weapon_id_from_string(aggressor.get('WeaponName'))),
                'killed_by_part_translated': get_item_name(dmg_hist.get('LethalDamagePart', '')),
                'lethal_damage_amount': "{:.1f}".format(lethal_dmg_info.get('Amount', 0.0)) if lethal_dmg_info.get('Amount') is not None else 'N/A',
                'lethal_damage_type_translated': get_item_name(lethal_dmg_info.get('Type'))
            }
        modal_response_data['killer_info'] = killer_info_data if killer_info_data else None
        
        session_counters_modal = stats_eft_node.get('SessionCounters', {}).get('Items', [])
        modal_response_data['session_stats'] = {
            'exp_kill': get_counter_value_from_json_list(session_counters_modal, ["ExpKill"], 0),
            'exp_looting': get_counter_value_from_json_list(session_counters_modal, ["ExpLooting"], 0),
            'exp_exit_status': get_counter_value_from_json_list(session_counters_modal, ["Exp", "ExpExitStatus"], 0),
            'damage_dealt': get_counter_value_from_json_list(session_counters_modal, ["CombatDamage"], 0),
            'distance_formatted': format_distance_meters(get_counter_value_from_json_list(session_counters_modal, ["Pedometer"], 0), include_unit=True, is_longest_kill_shot=False),
            'deaths': get_counter_value_from_json_list(session_counters_modal, ["Deaths"], 0),
            'blood_loss': get_counter_value_from_json_list(session_counters_modal, ["BloodLoss"], 0),
            'damage_received_total': 'N/A' 
        }
        modal_response_data['total_session_exp_calculated'] = modal_response_data['session_stats']['exp_kill'] + modal_response_data['session_stats']['exp_looting'] + modal_response_data['session_stats']['exp_exit_status']
        modal_response_data['total_session_exp_from_json'] = stats_eft_node.get('TotalSessionExperience', 0)
        modal_response_data['session_exp_mult'] = stats_eft_node.get('SessionExperienceMult', 1.0)
        modal_response_data['experience_bonus_mult'] = stats_eft_node.get('ExperienceBonusMult', 1.0)

        final_health_modal = {}; health_vitals_modal = {}
        body_parts_health_data_raw_modal = health_data_raw.get('BodyParts', {})
        for part_name_eng, display_name_key in {"Head": "Głowa", "Chest": "Klatka piersiowa", "Stomach": "Brzuch", "LeftArm": "Lewa ręka", "RightArm": "Prawa ręka", "LeftLeg": "Lewa noga", "RightLeg": "Prawa noga"}.items():
            part_info_modal = body_parts_health_data_raw_modal.get(part_name_eng, {}); health_values_modal = part_info_modal.get('Health', {})
            current_hp_modal = health_values_modal.get('Current', 0); max_hp_modal = health_values_modal.get('Maximum', 0)
            effects_dict_modal = part_info_modal.get('Effects', {}); active_effects_modal = [get_item_name(eff_id) for eff_id, eff_details in effects_dict_modal.items() if isinstance(eff_details, dict) and eff_details.get('Time', -2) != -2]
            final_health_modal[display_name_key] = {'current': float(current_hp_modal), 'maximum': float(max_hp_modal), 'effects': active_effects_modal}
        health_vitals_modal['Energy'] = float(health_data_raw.get('Energy',{}).get('Current',0)); health_vitals_modal['MaxEnergy'] = float(health_data_raw.get('Energy',{}).get('Maximum',110))
        health_vitals_modal['Hydration'] = float(health_data_raw.get('Hydration',{}).get('Current',0)); health_vitals_modal['MaxHydration'] = float(health_data_raw.get('Hydration',{}).get('Maximum',100))
        health_vitals_modal['Temperature'] = float(health_data_raw.get('Temperature',{}).get('Current',37)); health_vitals_modal['Poison'] = float(health_data_raw.get('Poison',{}).get('Current',0))
        modal_response_data['final_health'] = final_health_modal
        modal_response_data['final_vitals'] = health_vitals_modal
        
        skills_for_modal = []
        if isinstance(skills_data_raw.get('Common'), list):
            for skill in skills_data_raw['Common']:
                if isinstance(skill, dict): 
                    skills_for_modal.append({'SkillName': get_item_name(skill.get('Id')), 'Progress': f"{float(skill.get('Progress',0) or 0):.2f}", 
                                             'PointsEarnedFormatted': f"{float(skill.get('PointsEarnedDuringSession',0) or 0):.2f}", 'SkillType': 'Common'})
        if isinstance(skills_data_raw.get('Mastering'), list):
            for skill in skills_data_raw['Mastering']:
                if isinstance(skill, dict):
                     skills_for_modal.append({'SkillName': get_item_name(skill.get('Id')), 'Progress': f"{float(skill.get('Progress',0) or 0):.2f}", 
                                              'PointsEarnedFormatted': 'N/A', 'SkillType': 'Mastering'})
        modal_response_data['skills_changed'] = skills_for_modal

        found_in_raid_items_modal = []
        # Poprawka dla FoundInRaidItems - iterujemy po Stats.Eft.FoundInRaidItems (lista obiektów {ItemId, count})
        # a nazwy bierzemy z Inventory na podstawie _tpl (ItemId)
        # To jest złożone, uproszczona wersja poniżej:
        if isinstance(stats_eft_node.get('FoundInRaidItems'), list):
            for fir_item_stat in stats_eft_node.get('FoundInRaidItems'):
                if isinstance(fir_item_stat, dict):
                    found_in_raid_items_modal.append({'name':get_item_name(fir_item_stat.get('ItemId')), 'count':fir_item_stat.get('count',1)})
        modal_response_data['found_in_raid_items'] = found_in_raid_items_modal
        
        modal_response_data['transfer_items'] = [] 
        if isinstance(results_node.get('transferItems'), list): # Z results_node
            for item in results_node.get('transferItems'):
                if isinstance(item,dict): modal_response_data['transfer_items'].append({'name':get_item_name(item.get('_tpl')), 'count':item.get('upd',{}).get('StackObjectsCount',1)})

        modal_response_data['dropped_items'] = [{'name':get_item_name(item.get('ItemId')), 'count':item.get('count',1)} for item in stats_eft_node.get('DroppedItems',[]) if isinstance(item,dict)]
        modal_response_data['lost_insured_items'] = [{'name':get_item_name(item.get('itemId')), 'count':1} for item in results_node.get('lostInsuredItems',[]) if isinstance(item,dict)]
        
        damage_received_details_modal = {}
        damage_history_body_parts = stats_eft_node.get('DamageHistory', {}).get('BodyParts', {})
        if isinstance(damage_history_body_parts, dict):
            for part_name_eng, damages_list in damage_history_body_parts.items():
                if isinstance(damages_list, list) and damages_list:
                    total_dmg_on_part = sum(float(d.get('Amount',0) or 0) for d in damages_list if isinstance(d,dict))
                    if total_dmg_on_part > 0: 
                        damage_received_details_modal[get_item_name(part_name_eng)] = round(total_dmg_on_part,1)
        modal_response_data['session_stats']['damage_received_details'] = damage_received_details_modal

        return jsonify(error=None, data=modal_response_data)
    except Exception as e:
        print(f"Błąd API /api/raid_json_details dla {filepath_relative}: {e}"); import traceback; traceback.print_exc()
        return jsonify(error=f"Błąd serwera API przy przetwarzaniu JSON: {e}", data=None), 500

@app.route('/api/mod/connect', methods=['POST'])
def mod_connect(): 
    data = request.get_json(); 
    save_raid_json_data(data, "SYSTEM", data.get("mod","mod_unknown"), "connect_event")
    return jsonify({"status": "success"})

@app.route('/api/raid/start', methods=['POST'])
def raid_start():
    data = request.get_json();
    if not data: return jsonify({"error": "Brak danych JSON"}), 400
    session_id = data.get('sessionId', 'unknownS')
    player_nickname = data.get('request',{}).get('playerProfile',{}).get('Info',{}).get('Nickname', session_id)
    
    json_path_relative = save_raid_json_data(data, player_nickname, session_id, "start")
    
    if session_id != 'unknownS' and json_path_relative:
        start_info = {"timestamp_utc_start": datetime.datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'), 
                      "json_file_start_path_relative": json_path_relative, 
                      "player_level_start": data.get('request',{}).get('playerProfile',{}).get('Info',{}).get('Level')}
        ACTIVE_RAIDS_INFO[session_id] = start_info
    return jsonify({"status": "success"})

@app.route('/api/raid/end', methods=['POST'])
def raid_end():
    data = request.get_json();
    if not data: return jsonify({"error": "Brak danych JSON"}), 400
    session_id = data.get('sessionId'); player_nickname = "UnknownPlayer" 
    try: 
        profile_info_temp = data['request']['results']['profile']['Info']
        session_id = session_id or profile_info_temp.get('_id')
        player_nickname = profile_info_temp.get('Nickname', session_id)
    except (AttributeError, KeyError, TypeError): 
        session_id = session_id or f"no_sid_end_{datetime.datetime.now().strftime('%f')}"
        player_nickname = session_id if player_nickname == "UnknownPlayer" else player_nickname

    save_raid_json_data(data, player_nickname, session_id, "end")
    
    global RAID_DATA_CACHE
    RAID_DATA_CACHE['last_updated'] = datetime.datetime.min

    return jsonify({"status": "success"})

if __name__ == '__main__':
    print("Uruchamianie aplikacji Flask (tryb: tylko JSON)...")
    load_translations()
    ensure_dir_exists(JSON_RAID_DATA_ROOT_DIR)
    print(f"Nasłuchiwanie na http://0.0.0.0:5000"); 
    print(f"Zrzuty JSON będą w: {JSON_RAID_DATA_ROOT_DIR}")
    if not TRANSLATIONS_DICT: print("OSTRZEŻENIE: Słownik tłumaczeń pusty.")
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)