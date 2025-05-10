# data_handler.py
import os
import json
import datetime
from datetime import timezone
from collections import defaultdict
import locale
import config

TRANSLATIONS_DH_DICT = {} 
ACHIEVEMENTS_DATA_DICT = {}

def load_dh_translations(lang_code=config.DEFAULT_LANGUAGE):
    global TRANSLATIONS_DH_DICT, ACHIEVEMENTS_DATA_DICT
    try:
        translations_file = os.path.join(config.TRANSLATIONS_DIR, f'{lang_code}.json')
        if not os.path.exists(translations_file): TRANSLATIONS_DH_DICT = {}
        else:
            with open(translations_file, 'r', encoding='utf-8') as f: TRANSLATIONS_DH_DICT = json.load(f)
    except Exception as e:
        print(f"BŁĄD (data_handler): ładowania głównych tłumaczeń z {translations_file}: {e}"); TRANSLATIONS_DH_DICT = {}
    try:
        achievements_data_file = os.path.join(config.TRANSLATIONS_DIR, 'achievements.json')
        if not os.path.exists(achievements_data_file): ACHIEVEMENTS_DATA_DICT = {}
        else:
            with open(achievements_data_file, 'r', encoding='utf-8') as f:
                ach_list = json.load(f)
                temp_ach_dict = {}
                if isinstance(ach_list, list):
                    for ach_data in ach_list:
                        if isinstance(ach_data, dict) and 'id' in ach_data: temp_ach_dict[ach_data['id']] = ach_data
                ACHIEVEMENTS_DATA_DICT = temp_ach_dict
    except Exception as e:
        print(f"BŁĄD (data_handler): ładowania achievements.json z {achievements_data_file}: {e}"); ACHIEVEMENTS_DATA_DICT = {}

load_dh_translations()

try:
    locale.setlocale(locale.LC_ALL, 'pl_PL.UTF-8')
except locale.Error:
    try: locale.setlocale(locale.LC_ALL, 'Polish_Poland.1250')
    except locale.Error: print("OSTRZEŻENIE (data_handler): Nie można ustawić polskiego locale.")

def get_dh_item_name(item_id_or_key, default_if_not_found=True):
    if item_id_or_key is None: return "N/A" if default_if_not_found else ""
    key_to_check_str = str(item_id_or_key)
    original_value = key_to_check_str
    if key_to_check_str == "": return "N/A" if default_if_not_found else ""

    if isinstance(item_id_or_key, str): # Dla ID osiągnięć i broni
        # 1. Spróbuj "{ID} ShortName" (dla broni)
        short_name_key = f"{key_to_check_str} ShortName"
        if short_name_key in TRANSLATIONS_DH_DICT:
            return TRANSLATIONS_DH_DICT[short_name_key]
        
        # 2. Spróbuj "{ID} name" (dla osiągnięć, zgodnie z Twoim pl.json)
        specific_ach_name_key = f"{key_to_check_str} name"
        if specific_ach_name_key in TRANSLATIONS_DH_DICT:
            return TRANSLATIONS_DH_DICT[specific_ach_name_key]

        # 3. Spróbuj "{ID} Name" (dla pełnej nazwy broni)
        full_name_key = f"{key_to_check_str} Name"
        if full_name_key in TRANSLATIONS_DH_DICT:
            return TRANSLATIONS_DH_DICT[full_name_key]

    # 4. Spróbuj bezpośredniego tłumaczenia klucza (dla ogólnych kluczy lub samego ID)
    if key_to_check_str in TRANSLATIONS_DH_DICT:
        return TRANSLATIONS_DH_DICT[key_to_check_str]
        
    # 5. Jeśli to lista (np. dla liczników ["Exp", "ExpKill"]), spróbuj połączonego klucza
    if isinstance(item_id_or_key, list):
        list_key_joined = "_".join(map(str, item_id_or_key)).lower() # np. exp_expkill
        if list_key_joined in TRANSLATIONS_DH_DICT:
            return TRANSLATIONS_DH_DICT[list_key_joined]
        
        # Spróbuj przetłumaczyć każdy element listy i połączyć
        translated_parts = [get_dh_item_name(part, default_if_not_found=True) for part in item_id_or_key]
        # Jeśli wszystkie części to N/A, zwróć oryginalny klucz listy jako string
        if all(part == "N/A" for part in translated_parts) and default_if_not_found:
             return original_value # Zwróć oryginalną listę jako string np. "['Exp', 'ExpKill']"
        # Zwróć połączone przetłumaczone części, jeśli przynajmniej jedna została przetłumaczona
        # lub jeśli default_if_not_found jest False i chcemy oryginalne części
        filtered_parts = [p for p in translated_parts if p != "N/A" or not default_if_not_found]
        if filtered_parts:
            return " - ".join(filtered_parts) if any(p != "N/A" for p in translated_parts) else original_value

        # Fallback dla listy: ostatni element
        if item_id_or_key: 
            last_element_key_str = str(item_id_or_key[-1])
            if last_element_key_str in TRANSLATIONS_DH_DICT:
                return TRANSLATIONS_DH_DICT[last_element_key_str]
            original_value = last_element_key_str
            
    return original_value if default_if_not_found else ""


def get_dh_weapon_id_from_string(weapon_string):
    if weapon_string is None: return None
    return weapon_string.split(" ")[0]

def format_dh_time_seconds(seconds_val):
    if seconds_val is None or str(seconds_val).strip() == "": return "N/A"
    try: seconds = int(float(seconds_val)); seconds = max(0, seconds)
    except: return "N/A"
    minutes, rs = divmod(seconds, 60); return f"{minutes:02d}:{rs:02d}"

def format_dh_distance_meters(meters_val, include_unit=False, is_lks_from_json=False):
    if meters_val is None or str(meters_val).strip() == "": return "N/A" if include_unit else ""
    try: meters = float(meters_val)
    except: return "N/A" if include_unit else ""
    if is_lks_from_json: meters /= 10.0 
    unit = " m" if include_unit else ""
    try: return locale.format_string("%.1f", meters, grouping=False) + unit
    except: return f"{meters:.1f}{unit}"

def format_dh_exp(exp_val):
    if exp_val is None or str(exp_val).strip() == "": return "0"
    try: return locale.format_string("%d", int(float(exp_val)), grouping=True).replace(",", " ")
    except: return str(int(float(exp_val))) if str(exp_val).replace('.','',1).isdigit() else "0"

def format_dh_decimal_one(value):
    if value is None or str(value).strip() == "": return "N/A"
    try: return locale.format_string("%.1f", float(value), grouping=False)
    except: return str(float(value)) if str(value).replace('.','',1).replace('-','',1).isdigit() else "N/A"

def get_dh_counter_value(items_list, target_key_as_list, default_value=0):
    if not isinstance(items_list, list): return default_value
    for item in reversed(items_list): 
        if isinstance(item, dict) and item.get("Key") == target_key_as_list:
            val = item.get("Value", default_value);
            try: return int(float(val))
            except: return val 
    return default_value

def ensure_dh_dir_exists(dir_path):
    if not os.path.exists(dir_path):
        try: os.makedirs(dir_path)
        except Exception as e: print(f"BŁĄD (data_handler): Tworzenie katalogu {dir_path}: {e}")

def save_dh_raid_json_data(data_payload, player_nickname_raw, session_id_raw, event_type):
    player_nickname = str(player_nickname_raw if player_nickname_raw else "UnknownPlayer"); session_id = str(session_id_raw if session_id_raw else "unknown_session")
    if player_nickname.lower() in [nick.lower() for nick in config.IGNORED_PLAYER_NICKNAMES]: return None
    player_dir_name = "".join(c if c.isalnum() else '_' for c in player_nickname); player_dir_path = os.path.join(config.JSON_RAID_DATA_ROOT_DIR, player_dir_name)
    ensure_dh_dir_exists(player_dir_path)
    timestamp_file_str = datetime.datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f'); safe_session_id = "".join(c if c.isalnum() or c in ['-', '_'] else '_' for c in session_id)
    filename = f"{safe_session_id}_{timestamp_file_str}_{event_type}.json"; filepath_full = os.path.join(player_dir_path, filename)
    try:
        with open(filepath_full, 'w', encoding='utf-8') as f: json.dump(data_payload, f, ensure_ascii=False, indent=2)
        relative_path = os.path.join(player_dir_name, filename); print(f"INFO (data_handler): Zapisano: {relative_path}"); return relative_path
    except Exception as e: print(f"BŁĄD (data_handler): Zapis JSON {filepath_full}: {e}"); return None

def load_dh_json_file(filepath_full):
    if not os.path.exists(filepath_full): return None
    try:
        with open(filepath_full, 'r', encoding='utf-8') as f: return json.load(f)
    except Exception as e: print(f"BŁĄD (data_handler): Wczytywania {filepath_full}: {e}"); return None

RAID_DATA_CACHE_DH = {'all_raids_summary': [], 'players_summary': {}, 'last_updated': datetime.datetime.min, 'errors': []}

def parse_dh_raid_end_summary(filepath_full, filepath_relative_to_root):
    raid_data = load_dh_json_file(filepath_full)
    if not raid_data: return None
    summary = {}
    try:
        results_node = raid_data.get('request', {}).get('results', {})
        profile_node = results_node.get('profile', {})
        profile_info_node = profile_node.get('Info', {})
        stats_eft_node = profile_node.get('Stats', {}).get('Eft', {})
        
        summary['session_id'] = raid_data.get('sessionId', profile_node.get('_id', 'N/A'))
        ts_utc_from_filename_obj = None
        try:
            fn_parts = os.path.basename(filepath_full).split('_')
            if len(fn_parts) >= 4: ts_utc_from_filename_obj = datetime.datetime.strptime(f"{fn_parts[1]}{fn_parts[2]}", '%Y%m%d%H%M%S')
        except: pass
        if ts_utc_from_filename_obj:
            summary['timestamp_utc'] = ts_utc_from_filename_obj.strftime('%Y-%m-%d %H:%M:%S')
            summary['timestamp_formatted'] = ts_utc_from_filename_obj.replace(tzinfo=timezone.utc).astimezone().strftime('%d.%m.%Y %H:%M')
        else:
            file_mtime = datetime.datetime.fromtimestamp(os.path.getmtime(filepath_full), tz=timezone.utc)
            summary['timestamp_utc'] = file_mtime.strftime('%Y-%m-%d %H:%M:%S')
            summary['timestamp_formatted'] = file_mtime.astimezone().strftime('%d.%m.%Y %H:%M')
        summary['player_nickname'] = profile_info_node.get('Nickname', 'N/A')
        summary['player_level'] = profile_info_node.get('Level', '0')
        summary['player_side'] = get_dh_item_name(profile_info_node.get('Side', ''), default_if_not_found=True)
        summary['map_name'] = get_dh_item_name(profile_info_node.get('EntryPoint', ''), default_if_not_found=True)
        raw_result = results_node.get('result', 'Unknown')
        summary['raid_result'] = get_dh_item_name(raw_result, default_if_not_found=True)
        summary['raw_raid_result'] = raw_result
        summary['duration_formatted'] = format_dh_time_seconds(results_node.get('playTime', stats_eft_node.get('TotalInGameTime')))
        summary['exit_name'] = '---'
        if str(raw_result).lower() in ["survived", "runner"]:
            summary['exit_name'] = get_dh_item_name(results_node.get('exitName', ''), default_if_not_found=True) or '---'
        victims_list = stats_eft_node.get('Victims', []) or []
        summary['kills'] = len(victims_list)
        summary['headshots'] = sum(1 for v in victims_list if isinstance(v,dict) and v.get('BodyPart','').lower() == 'head')
        session_counters = stats_eft_node.get('SessionCounters', {}).get('Items', [])
        if isinstance(session_counters, list) and any(isinstance(sc, dict) and "ExpKill" in sc.get("Key",[]) for sc in session_counters):
            exp_k = get_dh_counter_value(session_counters, ["ExpKill"],0); exp_l = get_dh_counter_value(session_counters, ["ExpLooting"],0); exp_e = get_dh_counter_value(session_counters, ["Exp", "ExpExitStatus"],0)
            summary['exp_gained'] = exp_k + exp_l + exp_e
        else:
            summary['exp_gained'] = stats_eft_node.get('TotalSessionExperience', 0)
            if summary['exp_gained'] == 0 and (not isinstance(session_counters, list) or not session_counters) : # Dodatkowe sprawdzenie
                overall_counters = stats_eft_node.get('OverallCounters', {}).get('Items', [])
                exp_k_ov = get_dh_counter_value(overall_counters, ["ExpKill"],0); exp_l_ov = get_dh_counter_value(overall_counters, ["ExpLooting"],0); exp_e_ov = get_dh_counter_value(overall_counters, ["Exp", "ExpExitStatus"],0)
                summary['exp_gained'] = exp_k_ov + exp_l_ov + exp_e_ov
        lks_val_session = get_dh_counter_value(session_counters, ["LongestKillShot"], None)
        lks_val_overall = get_dh_counter_value(stats_eft_node.get('OverallCounters',{}).get('Items',[]), ["LongestKillShot"], None)
        lks_to_use = lks_val_session if lks_val_session is not None else lks_val_overall
        summary['longest_shot_meters'] = float(lks_to_use) / 10.0 if lks_to_use is not None else 0.0
        summary['json_file_path_relative'] = filepath_relative_to_root
        return summary
    except Exception as e: print(f"BŁĄD (data_handler - parse_dh_raid_end_summary): Błąd parsowania {filepath_full}: {e}"); import traceback; traceback.print_exc(); return None

def get_dh_cached_data():
    global RAID_DATA_CACHE_DH
    now = datetime.datetime.now()
    if RAID_DATA_CACHE_DH.get('all_raids_summary') and (now - RAID_DATA_CACHE_DH.get('last_updated', datetime.datetime.min)).total_seconds() < config.CACHE_TTL_SECONDS:
        return RAID_DATA_CACHE_DH
    print("INFO (data_handler): Odświeżanie cache danych rajdów...")
    all_raids_summaries = []; player_aggregated_stats = defaultdict(lambda: {'nickname': '', 'latest_level': '0', 'latest_side': '', 'latest_game_edition': '', 'raid_count': 0, 'total_kills': 0, 'total_deaths': 0, 'total_survived': 0, 'total_headshots': 0, 'total_gained_exp_from_raids': 0, 'longest_shot_ever_meters': 0.0}); parsing_errors = []
    ensure_dh_dir_exists(config.JSON_RAID_DATA_ROOT_DIR)
    for player_folder_name in os.listdir(config.JSON_RAID_DATA_ROOT_DIR):
        player_dir_path = os.path.join(config.JSON_RAID_DATA_ROOT_DIR, player_folder_name)
        if os.path.isdir(player_dir_path) and player_folder_name.lower() not in [n.lower() for n in config.IGNORED_PLAYER_NICKNAMES]:
            raid_files = sorted([f for f in os.listdir(player_dir_path) if f.endswith("_end.json")])
            for filename in raid_files:
                full_path = os.path.join(player_dir_path, filename); relative_path = os.path.join(player_folder_name, filename)
                summary = parse_dh_raid_end_summary(full_path, relative_path)
                if summary:
                    all_raids_summaries.append(summary)
                    nick = summary.get('player_nickname')
                    if nick and nick != 'N/A':
                        p_agg_stats = player_aggregated_stats[nick]
                        if not p_agg_stats['nickname']: p_agg_stats['nickname'] = nick
                        p_agg_stats['latest_level'] = summary.get('player_level', p_agg_stats['latest_level'])
                        p_agg_stats['latest_side'] = summary.get('player_side', p_agg_stats['latest_side'])
                        p_agg_stats['raid_count'] += 1; p_agg_stats['total_kills'] += summary.get('kills', 0); p_agg_stats['total_headshots'] += summary.get('headshots', 0); p_agg_stats['total_gained_exp_from_raids'] += summary.get('exp_gained', 0)
                        current_lks_meters = summary.get('longest_shot_meters', 0.0)
                        if current_lks_meters > p_agg_stats['longest_shot_ever_meters']: p_agg_stats['longest_shot_ever_meters'] = current_lks_meters
                        raw_res_lower = str(summary.get('raw_raid_result', '')).lower()
                        if raw_res_lower == "survived" or raw_res_lower == "runner": p_agg_stats['total_survived'] += 1
                        elif raw_res_lower == "killed" or raw_res_lower == "missinginaction": p_agg_stats['total_deaths'] += 1
                        if not p_agg_stats['latest_game_edition']:
                            full_raid_data = load_dh_json_file(full_path)
                            if full_raid_data: p_agg_stats['latest_game_edition'] = full_raid_data.get('request',{}).get('results',{}).get('profile',{}).get('Info',{}).get('GameVersion','')
                else: parsing_errors.append(f"Błąd parsowania podsumowania dla pliku: {relative_path}")
    final_players_summary_dict = {}
    for nick, aggregated_data in player_aggregated_stats.items():
        aggregated_data['calculated_kd'] = f"{aggregated_data['total_kills'] / aggregated_data['total_deaths']:.2f}" if aggregated_data['total_deaths'] > 0 else str(aggregated_data['total_kills'])
        aggregated_data['survival_rate'] = f"{(aggregated_data['total_survived'] / aggregated_data['raid_count'] * 100):.1f}%" if aggregated_data['raid_count'] > 0 else "0.0%"
        aggregated_data['latest_total_experience_formatted'] = format_dh_exp(aggregated_data['total_gained_exp_from_raids'])
        aggregated_data['longest_shot_ever_formatted'] = format_dh_distance_meters(aggregated_data['longest_shot_ever_meters'], include_unit=True, is_lks_from_json=False) if aggregated_data['longest_shot_ever_meters'] > 0 else "N/A"
        final_players_summary_dict[nick] = aggregated_data
    all_raids_summaries.sort(key=lambda r: r.get('timestamp_utc', '0'), reverse=True)
    RAID_DATA_CACHE_DH = {'all_raids_summary': all_raids_summaries, 'players_summary': final_players_summary_dict, 'last_updated': now, 'errors': parsing_errors}
    if parsing_errors: print(f"OSTRZEŻENIE (data_handler): Wystąpiły błędy cache: {len(parsing_errors)} plików.")
    return RAID_DATA_CACHE_DH

def invalidate_dh_cache():
    global RAID_DATA_CACHE_DH
    RAID_DATA_CACHE_DH['last_updated'] = datetime.datetime.min
    print("INFO (data_handler): Cache danych rajdów został unieważniony.")

def prepare_modal_data(raid_json_path_relative):
    full_path = os.path.join(config.JSON_RAID_DATA_ROOT_DIR, raid_json_path_relative)
    raid_full_data_payload = load_dh_json_file(full_path)
    if not raid_full_data_payload: return None, f"Nie znaleziono lub nie udało się wczytać pliku JSON: {raid_json_path_relative}"
    processed_data = extract_data_for_modal(raid_full_data_payload, full_path)
    if not processed_data or "error" in processed_data:
        error_message = processed_data.get("error") if isinstance(processed_data, dict) else "Nieznany błąd przetwarzania"
        return None, f"Błąd przetwarzania danych dla {raid_json_path_relative}: {error_message}"
    return processed_data, None

def extract_data_for_modal(raid_full_data_payload, full_filepath_for_timestamp=""):
    if not raid_full_data_payload: return {"error": "Brak danych wejściowych."}
    details = {}
    try:
        results_node = raid_full_data_payload.get('request', {}).get('results', {})
        profile_node = results_node.get('profile', {})
        if not profile_node: return {"error": "Brak węzła 'profile' w danych."}
        profile_info_node = profile_node.get('Info', {})
        stats_eft_node = profile_node.get('Stats', {}).get('Eft', {})
        health_data_raw = profile_node.get('Health', {}) 
        skills_data_raw = profile_node.get('Skills', {})
        
        base_summary = parse_dh_raid_end_summary(full_filepath_for_timestamp, "")
        if not base_summary:
            base_summary = {'map_name': get_dh_item_name(profile_info_node.get('EntryPoint')),'timestamp_formatted': 'N/A','raid_result': get_dh_item_name(results_node.get('result')), 'raw_raid_result': results_node.get('result', 'Unknown'), 'exit_name': '---','duration_formatted': format_dh_time_seconds(results_node.get('playTime')),'kills': 0,'exp_gained': 0}
            try:
                fn_parts = os.path.basename(full_filepath_for_timestamp).split('_')
                if len(fn_parts) >= 4: ts_utc_from_filename_obj = datetime.datetime.strptime(f"{fn_parts[1]}{fn_parts[2]}", '%Y%m%d%H%M%S'); base_summary['timestamp_formatted'] = ts_utc_from_filename_obj.replace(tzinfo=timezone.utc).astimezone().strftime('%d.%m.%Y %H:%M')
            except: base_summary['timestamp_formatted'] = datetime.datetime.fromtimestamp(os.path.getmtime(full_filepath_for_timestamp), tz=timezone.utc).astimezone().strftime('%d.%m.%Y %H:%M') if full_filepath_for_timestamp and os.path.exists(full_filepath_for_timestamp) else 'N/A'
            raw_res_fb = results_node.get('result')
            if str(raw_res_fb).lower() in ["survived", "runner"]: base_summary['exit_name'] = get_dh_item_name(results_node.get('exitName')) or "---"

        details['location'] = base_summary.get('map_name', 'N/A')
        details['timestamp_formatted'] = base_summary.get('timestamp_formatted', 'N/A')
        details['raid_result'] = base_summary.get('raid_result', 'N/A')
        details['raw_raid_result'] = base_summary.get('raw_raid_result', 'Unknown') # Dodajemy raw_raid_result
        details['exit_name'] = base_summary.get('exit_name', '---')
        details['play_time_formatted'] = base_summary.get('duration_formatted', 'N/A')
        details['survivor_class'] = get_dh_item_name(stats_eft_node.get('SurvivorClass'))
        details['player_count_in_raid'] = "N/A" 
        victims_list_raw = stats_eft_node.get('Victims', []) or []; parsed_victims = []
        for v_dict in victims_list_raw:
            if not isinstance(v_dict, dict): continue
            weapon_id_raw = v_dict.get('Weapon'); weapon_id_clean = get_dh_weapon_id_from_string(weapon_id_raw)
            victim_weapon_display_name = "N/A"
            if weapon_id_clean:
                short_name_key = f"{weapon_id_clean} ShortName"; victim_weapon_display_name = get_dh_item_name(short_name_key, default_if_not_found=False)
                if not victim_weapon_display_name: name_key = f"{weapon_id_clean} Name"; victim_weapon_display_name = get_dh_item_name(name_key, default_if_not_found=True)
            parsed_victims.append({'Name':v_dict.get('Name','N/A'), 'RoleTranslated':get_dh_item_name(v_dict.get('Role','SCAV')),'Level':v_dict.get('Level',1), 'BodyPartTranslated':get_dh_item_name(v_dict.get('BodyPart','Unknown')), 'WeaponName':victim_weapon_display_name, 'DistanceFormatted':format_dh_distance_meters(v_dict.get('Distance'), include_unit=True)})
        details['victims'] = parsed_victims; details['kills_count'] = len(parsed_victims)
        killer_info_data = None
        raw_raid_result_from_results = results_node.get('result')
        if str(raw_raid_result_from_results).lower() == "killed":
            aggressor = stats_eft_node.get('Aggressor', {}); death_cause = stats_eft_node.get('DeathCause', {}); dmg_hist = stats_eft_node.get('DamageHistory', {}); lethal_dmg_info = dmg_hist.get('LethalDamage',{})
            if aggressor or death_cause or dmg_hist:
                killer_weapon_id_raw = death_cause.get('WeaponId') or aggressor.get('WeaponName'); killer_weapon_id_clean = get_dh_weapon_id_from_string(killer_weapon_id_raw)
                killer_weapon_display_name = "N/A"
                if killer_weapon_id_clean:
                    short_name_key_killer = f"{killer_weapon_id_clean} ShortName"; killer_weapon_display_name = get_dh_item_name(short_name_key_killer, default_if_not_found=False)
                    if not killer_weapon_display_name: name_key_killer = f"{killer_weapon_id_clean} Name"; killer_weapon_display_name = get_dh_item_name(name_key_killer, default_if_not_found=True)
                killer_info_data = {'name': aggressor.get('Name', 'N/A'), 'role_translated': get_dh_item_name(aggressor.get('Role', '')), 'side': get_dh_item_name(aggressor.get('Side', '')), 'weapon_name': killer_weapon_display_name, 'killed_by_part_translated': get_dh_item_name(dmg_hist.get('LethalDamagePart', '')), 'lethal_damage_amount': lethal_dmg_info.get('Amount', 0.0), 'lethal_damage_type_translated': get_dh_item_name(lethal_dmg_info.get('Type'))}
        details['killer_info'] = killer_info_data
        details['total_session_exp_from_json'] = stats_eft_node.get('TotalSessionExperience', 0)
        details['total_session_exp_calculated'] = base_summary.get('exp_gained', details['total_session_exp_from_json'])
        details['session_exp_mult'] = stats_eft_node.get('SessionExperienceMult', 1.0); details['experience_bonus_mult'] = stats_eft_node.get('ExperienceBonusMult', 1.0)
        session_counters_items = stats_eft_node.get('SessionCounters', {}).get('Items', [])
        overall_counters_items = stats_eft_node.get('OverallCounters', {}).get('Items', [])
        exp_kill_s = get_dh_counter_value(session_counters_items, ["ExpKill"], None); exp_looting_s = get_dh_counter_value(session_counters_items, ["ExpLooting"], None); exp_exit_s = get_dh_counter_value(session_counters_items, ["Exp", "ExpExitStatus"], None)
        details['session_stats_source_note'] = None
        if exp_kill_s is None and exp_looting_s is None and exp_exit_s is None and isinstance(session_counters_items, list) and not session_counters_items: 
            details['session_stats_source_note'] = "(globalne)"
            exp_kill_s = get_dh_counter_value(overall_counters_items, ["ExpKill"], 0); exp_looting_s = get_dh_counter_value(overall_counters_items, ["ExpLooting"], 0); exp_exit_s = get_dh_counter_value(overall_counters_items, ["Exp", "ExpExitStatus"], 0)
        details['session_stats'] = {'exp_kill': exp_kill_s or 0, 'exp_looting': exp_looting_s or 0, 'exp_exit_status': exp_exit_s or 0, 'damage_dealt': get_dh_counter_value(session_counters_items, ["CauseBodyDamage"], get_dh_counter_value(overall_counters_items, ["CauseBodyDamage"],0)), 'distance_formatted': format_dh_distance_meters(get_dh_counter_value(session_counters_items, ["Pedometer"], get_dh_counter_value(overall_counters_items,["Pedometer"],0)), include_unit=True), 'blood_loss': get_dh_counter_value(session_counters_items, ["BloodLoss"], get_dh_counter_value(overall_counters_items,["BloodLoss"],0))}
        damage_received_details = {}
        damage_history_body_parts = stats_eft_node.get('DamageHistory', {}).get('BodyParts', {})
        if isinstance(damage_history_body_parts, dict):
            for part_name_eng, damages_list in damage_history_body_parts.items():
                total_dmg_on_part = sum(float(d.get('Amount',0) or 0) for d in (damages_list or []) if isinstance(d,dict))
                if total_dmg_on_part > 0: damage_received_details[get_dh_item_name(part_name_eng)] = round(total_dmg_on_part,1) 
        details['session_stats']['damage_received_details'] = damage_received_details
        
        # Parsowanie SessionCounters.Items na listę dla modala
        parsed_session_counters = []
        if isinstance(session_counters_items, list):
            for item in session_counters_items:
                if isinstance(item, dict) and "Key" in item and "Value" in item:
                    key_list = item.get("Key", [])
                    display_key = ""
                    if isinstance(key_list, list):
                        translated_parts = [get_dh_item_name(part) for part in key_list]
                        display_key = " - ".join(p for p in translated_parts if p != "N/A") # Łącz tylko przetłumaczone
                        if not display_key: display_key = " ".join(map(str,key_list)) # Fallback na oryginalne klucze
                    elif isinstance(key_list, str): 
                        display_key = get_dh_item_name(key_list)
                    
                    value = item.get("Value")
                    formatted_value = str(value)
                    if isinstance(value, (int, float)):
                        # Specjalne formatowanie dla niektórych kluczy
                        raw_key_str_for_check = "_".join(map(str,key_list)).lower() if isinstance(key_list, list) else str(key_list).lower()
                        if "damage" in raw_key_str_for_check:
                            formatted_value = format_dh_exp(value) 
                        elif "longestkillshot" in raw_key_str_for_check:
                            formatted_value = format_dh_distance_meters(value, include_unit=True, is_lks_from_json=True)
                        elif "exp" in raw_key_str_for_check and "multiplier" not in raw_key_str_for_check and "bonus" not in raw_key_str_for_check:
                            formatted_value = format_dh_exp(value)
                        # Możesz dodać więcej warunków formatowania tutaj
                        else:
                             formatted_value = format_dh_exp(value) if value >= 1000 else str(value) # Domyślnie dla innych liczb

                    if display_key and formatted_value : # Dodaj tylko jeśli mamy klucz i wartość
                        parsed_session_counters.append({'key': display_key, 'value': formatted_value})
        details['parsed_session_counters'] = parsed_session_counters


        final_health = {}; final_vitals = {}
        body_parts_raw = health_data_raw.get('BodyParts', {})
        default_body_parts_map = {"Head": "Głowa", "Chest": "Klatka piersiowa", "Stomach": "Brzuch", "LeftArm": "Lewa ręka", "RightArm": "Prawa ręka", "LeftLeg": "Lewa noga", "RightLeg": "Prawa noga"}
        for part_key, default_translation in default_body_parts_map.items():
            part_info = body_parts_raw.get(part_key, {}); health_values = part_info.get('Health', {}); current_hp = float(health_values.get('Current', 0)); max_hp = float(health_values.get('Maximum', 0))
            if max_hp == 0:
                if part_key == "Head": max_hp = 35.0
                elif part_key == "Chest": max_hp = 85.0
                elif part_key == "Stomach": max_hp = 70.0
                elif part_key in ["LeftArm", "RightArm"]: max_hp = 60.0
                elif part_key in ["LeftLeg", "RightLeg"]: max_hp = 65.0
            current_hp = min(current_hp, max_hp) if max_hp > 0 else current_hp
            effects_dict = part_info.get('Effects', {}); active_effects = [get_dh_item_name(eff_id) for eff_id, eff_details in (effects_dict or {}).items() if isinstance(eff_details, dict) and eff_details.get('Time', -2) != -2]
            final_health[get_dh_item_name(part_key) or default_translation] = {'current': current_hp, 'maximum': max_hp, 'effects': active_effects}
        final_vitals['Energy'] = float(health_data_raw.get('Energy',{}).get('Current',0)); final_vitals['MaxEnergy'] = float(health_data_raw.get('Energy',{}).get('Maximum',100))
        final_vitals['Hydration'] = float(health_data_raw.get('Hydration',{}).get('Current',0)); final_vitals['MaxHydration'] = float(health_data_raw.get('Hydration',{}).get('Maximum',100))
        final_vitals['Temperature'] = float(health_data_raw.get('Temperature',{}).get('Current',37)); final_vitals['Poison'] = float(health_data_raw.get('Poison',{}).get('Current',0));
        details['final_health'] = final_health; details['final_vitals'] = final_vitals
        skills_changed = []
        if isinstance(skills_data_raw.get('Common'), list):
            for skill in skills_data_raw['Common']:
                if isinstance(skill, dict): skills_changed.append({'SkillName': get_dh_item_name(skill.get('Id')), 'Progress': f"{float(skill.get('Progress',0) or 0):.2f}", 'PointsEarnedFormatted': f"{float(skill.get('PointsEarnedDuringSession',0) or 0):.2f}", 'SkillType': 'Common'})
        if isinstance(skills_data_raw.get('Mastering'), list):
            for skill in skills_data_raw['Mastering']:
                if isinstance(skill, dict): skills_changed.append({'SkillName': get_dh_item_name(skill.get('Id')), 'Progress': f"{float(skill.get('Progress',0) or 0):.2f}", 'PointsEarnedFormatted': 'N/A', 'SkillType': 'Mastering'})
        details['skills_changed'] = skills_changed
        details['found_in_raid_items'] = [{'name':get_dh_item_name(item.get('ItemId')), 'count':item.get('count',1)} for item in (stats_eft_node.get('FoundInRaidItems') or []) if isinstance(item,dict)]
        transfer_items_raw = results_node.get('transferItems', [])
        details['transfer_items'] = [{'name':get_dh_item_name(item.get('_tpl')), 'count':item.get('upd',{}).get('StackObjectsCount',1)} for item in (transfer_items_raw if isinstance(transfer_items_raw, list) else [])]
        details['dropped_items'] = [{'name':get_dh_item_name(item.get('ItemId')), 'count':item.get('count',1)} for item in (stats_eft_node.get('DroppedItems') or []) if isinstance(item,dict)]
        details['lost_insured_items'] = [{'name':get_dh_item_name(item.get('itemId')), 'count':1} for item in (results_node.get('lostInsuredItems') or []) if isinstance(item,dict)]
        return details
    except Exception as e:
        print(f"KRYTYCZNY BŁĄD (extract_data_for_modal): {e}"); import traceback; traceback.print_exc(); return {"error": f"Wew. błąd serwera (modal): {str(e)}"}