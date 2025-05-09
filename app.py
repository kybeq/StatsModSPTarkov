import os
import json
import math
import datetime
import locale
from flask import Flask, render_template, abort, jsonify, request
from collections import defaultdict

# Ustawienie polskiego locale dla formatowania liczb
try:
    locale.setlocale(locale.LC_ALL, 'pl_PL.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_ALL, 'Polish_Poland.1250')
    except locale.Error:
        print("OSTRZEŻENIE: Nie można ustawić polskiego locale. Formatowanie liczb może być domyślne.")

app = Flask(__name__, static_folder='static')
app.json.ensure_ascii = False  # Obsługa polskich znaków w JSON

# --- Konfiguracja Ścieżek ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TRANSLATE_FOLDER = os.path.join(BASE_DIR, 'translate')
TRANSLATION_FILENAME = 'pl.json'
TRANSLATION_FILE_PATH = os.path.join(TRANSLATE_FOLDER, TRANSLATION_FILENAME)
RAID_DATA_FILE = os.path.join(BASE_DIR, 'raid_data.json')

MAP_IMAGES = {
    "Fabryce": "factory.avif",
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

# --- Wczytywanie Tłumaczeń ---
translations = {}

def load_translations():
    global translations
    if not os.path.exists(TRANSLATION_FILE_PATH):
        print(f"OSTRZEŻENIE: Plik tłumaczeń nie został znaleziony: {TRANSLATION_FILE_PATH}")
        translations = {}
        return
    try:
        with open(TRANSLATION_FILE_PATH, 'r', encoding='utf-8') as f:
            translations = json.load(f)
        print(f"Pomyślnie wczytano tłumaczenia z: {TRANSLATION_FILENAME}")
    except json.JSONDecodeError as e:
        print(f"BŁĄD: Nie można sparsować pliku tłumaczeń {TRANSLATION_FILENAME}: {e}")
        translations = {}
    except Exception as e:
        print(f"BŁĄD: Nieoczekiwany problem podczas wczytywania tłumaczeń: {e}")
        translations = {}

load_translations()

# --- Funkcje Pomocnicze ---
def get_item_name(item_id):
    if not translations or not item_id: return str(item_id)
    short_name_key = f"{item_id} ShortName"
    name_key = f"{item_id} Name"
    plain_id_key = str(item_id)
    fallback_keys = {
        "pmcBEAR": "PMC BEAR", "pmcUSEC": "PMC USEC", "sptBear": "SPT BEAR", "sptUsec": "SPT USEC",
        "assault": "Szturmowiec (Scav)", "marksman": "Snajper (Scav)", "exUsec": "Renegat",
        "bossBully": "Reshala", "bossKilla": "Killa", "bossTagilla": "Tagilla", "bossSanitar": "Sanitar",
        "bossGluhar": "Glukhar", "bossKnight": "Knight", "bossBirdeye": "Birdeye", "bossBigPipe": "Big Pipe",
        "followerBully": "Strażnik Reshali", "followerKilla": "Strażnik Killi", "followerTagilla": "Strażnik Tagilli",
        "followerSanitar": "Strażnik Sanitara", "followerGluharAssault": "Strażnik Glukhara (Szturm)",
        "followerGluharScout": "Strażnik Glukhara (Zwiad)", "followerGluharSecurity": "Strażnik Glukhara (Ochrona)",
        "followerGluharSnipe": "Strażnik Glukhara (Snajper)", "followerKojaniy": "Shturman", "followerZryachiy": "Zryachiy",
        "sectantPriest": "Kultysta (Kapłan)", "sectantWarrior": "Kultysta (Wojownik)",
        "gifter": "Santa Claus",
        "usec": "USEC", "bear": "BEAR", "savage": "Scav", "Default": "Bot",
        "Bullet": "Pocisk", "Explosion": "Eksplozja", "Melee": "Broń biała", "Fall": "Upadek",
        "Structural": "Strukturalne", "HeavyBleeding": "Mocne krwawienie", "LightBleeding": "Lekkie krwawienie",
        "Poison": "Trucizna", "Stimulator": "Stymulator", "Unknown": "Nieznany", "Undefined": "Niezdefiniowany",
        "Head": "Głowa", "Chest": "Klatka piersiowa", "Stomach": "Brzuch",
        "LeftArm": "Lewa ręka", "RightArm": "Prawa ręka",
        "LeftLeg": "Lewa noga", "RightLeg": "Prawa noga",
        "Destroyed": "Zniszczona"
    }
    return translations.get(short_name_key, translations.get(name_key, translations.get(plain_id_key, fallback_keys.get(str(item_id), str(item_id)))))

def format_exp(exp):
    try:
        return locale.format_string("%d", int(exp), grouping=True)
    except (ValueError, TypeError):
        return str(exp)

def format_time(seconds):
    if seconds is None: return "N/A"
    try:
        seconds = int(seconds)
        if seconds < 0: seconds = 0
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        remaining_seconds = seconds % 60
        if hours > 0: return f"{hours:02d}:{minutes:02d}:{remaining_seconds:02d}"
        else: return f"{minutes:02d}:{remaining_seconds:02d}"
    except (ValueError, TypeError): return "N/A"

def format_distance(meters):
    if meters is None: return "N/A"
    try:
        meters = float(meters)
        if meters >= 1000: return f"{meters / 1000:.2f} km"
        else: return f"{meters:.1f} m"
    except (ValueError, TypeError): return "N/A"

def format_timestamp(ts):
    if ts is None: return "N/A"
    try:
        if ts > 3000000000: dt = datetime.datetime.fromtimestamp(ts / 1000)
        else: dt = datetime.datetime.fromtimestamp(ts)
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError, OSError): return "N/A"

def process_item_list(items_dict_or_list, count_key='count', id_key='_tpl'):
    processed_items = []
    item_counts = defaultdict(int)
    items_to_process = []
    if isinstance(items_dict_or_list, dict): items_to_process = items_dict_or_list.values()
    elif isinstance(items_dict_or_list, list): items_to_process = items_dict_or_list
    if not items_to_process: return []
    for item in items_to_process:
        if not isinstance(item, dict): continue
        tpl_id = item.get(id_key) or item.get('ItemId')
        if tpl_id:
            count = item.get('upd', {}).get('StackObjectsCount', 1) if 'upd' in item else item.get(count_key, 1)
            try: item_counts[tpl_id] += int(count)
            except (ValueError, TypeError): item_counts[tpl_id] += 1
    for tpl_id, count in item_counts.items():
        processed_items.append({'id': tpl_id, 'name': get_item_name(tpl_id), 'count': count})
    processed_items.sort(key=lambda x: x['name'])
    return processed_items

def extract_session_stats(session_counters):
    stats = {'damage_dealt': 0, 'body_parts_destroyed': 0, 'pedometer': 0, 'exp_kill': 0, 'exp_looting': 0, 'exp_exit_status': 0, 'deaths': 0, 'blood_loss': 0, 'damage_received_total': 0, 'damage_received_details': {}}
    if session_counters and 'Items' in session_counters:
        for item in session_counters.get('Items', []):
            key = item.get('Key')
            value = item.get('Value', 0)
            if key and isinstance(key, list):
                try:
                    key_str = "_".join(map(str, key))
                    if "CombatDamage" in key_str: stats['damage_dealt'] += value
                    elif key[0] == "BodyPartDamage" and len(key) > 1:
                        part_name = get_item_name(key[1])
                        stats['damage_received_total'] += value
                        stats['damage_received_details'][part_name] = stats['damage_received_details'].get(part_name, 0) + value
                    elif "BodyPartsDestroyed" in key_str: stats['body_parts_destroyed'] = value
                    elif "Pedometer" in key_str: stats['pedometer'] = value
                    elif key == ["Exp", "ExpKill"] or key_str == "ExpKill": stats['exp_kill'] = value
                    elif key == ["Exp", "ExpLooting"] or key_str == "ExpLooting": stats['exp_looting'] = value
                    elif key == ["Exp", "ExpExitStatus"]: stats['exp_exit_status'] = value
                    elif "Deaths" in key_str: stats['deaths'] = value
                    elif "BloodLoss" in key_str: stats['blood_loss'] = value
                except (TypeError, IndexError): pass
    stats['damage_dealt'] = round(stats.get('damage_dealt', 0))
    stats['blood_loss'] = round(stats.get('blood_loss', 0))
    stats['damage_received_total'] = round(stats.get('damage_received_total', 0))
    for part, dmg in stats['damage_received_details'].items(): stats['damage_received_details'][part] = round(dmg, 1)
    stats['distance_formatted'] = format_distance(stats['pedometer'])
    return stats

def extract_overall_stats(overall_counters):
    stats = {'kills': 0, 'deaths': 0, 'sessions': 0, 'survived_sessions': 0, 'headshots': 0, 'longest_shot': 0}
    if overall_counters and 'Items' in overall_counters:
        for item in overall_counters.get('Items', []):
            key = item.get('Key')
            value = item.get('Value', 0)
            if key and isinstance(key, list):
                try:
                    key_str = "_".join(map(str, key))
                    if key == ['Kills']: stats['kills'] = value
                    elif key == ['Deaths']: stats['deaths'] = value
                    elif key_str == "Sessions_Pmc": stats['sessions'] = value
                    elif key_str == "ExitStatus_Survived_Pmc": stats['survived_sessions'] = value
                    elif key == ['HeadShots']: stats['headshots'] = value
                    elif key_str == "LongestShot": stats['longest_shot'] = value
                    elif key == ['LongShots']: stats['longest_shot'] = value
                except TypeError: pass
    stats['kd_ratio'] = f"{stats['kills'] / stats['deaths']:.2f}" if stats['deaths'] > 0 else 'N/A'
    stats['survival_rate'] = f"{(stats['survived_sessions'] / stats['sessions'] * 100):.1f}%" if stats['sessions'] > 0 else 'N/A'
    stats['longest_shot_formatted'] = format_distance(stats.get('longest_shot'))
    return stats

def extract_changed_skills(skills_data):
    changed = []
    if not skills_data: return changed
    if 'Common' in skills_data and skills_data['Common']:
        for skill in skills_data['Common']:
            if not isinstance(skill, dict): continue
            points_earned = skill.get('PointsEarnedDuringSession', 0)
            if points_earned > 0:
                skill_copy = skill.copy()
                try:
                    skill_copy['PointsEarnedFormatted'] = f"{points_earned:.2f}"
                    skill_copy['ProgressFormatted'] = f"{skill_copy.get('Progress', 0):.2f}"
                    skill_copy['SkillName'] = get_item_name(skill_copy.get('Id'))
                    skill_copy['SkillType'] = 'Common'
                    changed.append(skill_copy)
                except (ValueError, TypeError): print(f"OSTRZEŻENIE: Problem z formatowaniem danych umiejętności Common: {skill}")
    if 'Mastering' in skills_data and skills_data['Mastering']:
        for skill in skills_data['Mastering']:
            if not isinstance(skill, dict): continue
            points_earned = skill.get('PointsEarnedDuringSession', 0)
            progress = skill.get('Progress', 0)
            if progress > 0 or points_earned > 0:
                skill_copy = skill.copy()
                try:
                    skill_copy['PointsEarnedFormatted'] = f"{points_earned:.2f}" if points_earned else "N/A"
                    skill_copy['ProgressFormatted'] = f"{progress:.2f}"
                    skill_copy['SkillName'] = get_item_name(skill_copy.get('Id'))
                    skill_copy['SkillType'] = 'Mastering'
                    changed.append(skill_copy)
                except (ValueError, TypeError): print(f"OSTRZEŻENIE: Problem z formatowaniem danych umiejętności Mastering: {skill}")
    changed.sort(key=lambda x: (x.get('SkillType', ''), -x.get('PointsEarnedDuringSession', 0), -x.get('Progress', 0)))
    return changed

def process_single_raid_data(data, timestamp_ms, is_start=False):
    processed_data = {}
    try:
        session_id = data.get('sessionId')
        if is_start:
            request = data.get('request', {})
            result = data.get('result', {})
            processed_data['filename'] = f"startLocalRaid_request_{session_id}_{timestamp_ms}.json"
            processed_data['timestamp'] = datetime.datetime.fromtimestamp(timestamp_ms / 1000)
            processed_data['timestamp_formatted'] = processed_data['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
            processed_data['location_id'] = request.get('location', 'unknown')
            processed_data['location'] = get_item_name(processed_data['location_id'])
            processed_data['time_of_day'] = request.get('timeAndWeatherSettings', {}).get('timeVariant', 'unknown')
            processed_data['profile_id'] = session_id
        else:
            results = data.get('request', {}).get('results', {})
            profile = results.get('profile', {})
            info = profile.get('Info', {})
            stats_eft = profile.get('Stats', {}).get('Eft', {})
            health_info = profile.get('Health', {})

            processed_data['filename'] = f"onEndLocalRaidRequest_request_{session_id}_{timestamp_ms}.json"
            processed_data['timestamp'] = datetime.datetime.fromtimestamp(timestamp_ms / 1000)
            processed_data['timestamp_formatted'] = processed_data['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
            processed_data['server_id'] = data.get('request', {}).get('serverId')
            processed_data['raid_result'] = results.get('result')
            processed_data['exit_name'] = results.get('exitName') if processed_data['raid_result'] == 'Survived' else None
            processed_data['location_id'] = info.get('EntryPoint')
            processed_data['location'] = get_item_name(processed_data['location_id'])
            processed_data['nickname'] = info.get('Nickname')
            processed_data['level'] = info.get('Level')
            processed_data['side'] = info.get('Side')
            processed_data['total_experience'] = info.get('Experience')
            processed_data['karma_value'] = profile.get('karmaValue')
            processed_data['registration_date_ts'] = info.get('RegistrationDate')
            processed_data['registration_date_formatted'] = format_timestamp(processed_data['registration_date_ts'])
            processed_data['game_version'] = info.get('GameVersion')
            processed_data['voice'] = info.get('Voice')
            processed_data['group_id'] = info.get('GroupId')
            processed_data['team_id'] = info.get('TeamId')
            processed_data['profile_id'] = profile.get('_id')
            processed_data['account_id'] = profile.get('aid')
            processed_data['killer_profile_id'] = results.get('killerId')
            processed_data['killer_account_id'] = results.get('killerAid')

            total_in_game_time = stats_eft.get('TotalInGameTime')
            play_time_fallback = results.get('playTime')
            raid_duration_seconds = total_in_game_time if total_in_game_time is not None else play_time_fallback
            processed_data['play_time_seconds'] = raid_duration_seconds
            processed_data['play_time_formatted'] = format_time(raid_duration_seconds)
            processed_data['total_session_exp_from_json'] = stats_eft.get('TotalSessionExperience', 0)
            session_counters = stats_eft.get('SessionCounters')
            processed_data['session_stats'] = extract_session_stats(session_counters)
            exp_sum_from_counters = sum(v for k, v in processed_data['session_stats'].items() if k.startswith('exp_'))
            processed_data['total_session_exp_calculated'] = round(exp_sum_from_counters)
            processed_data['session_exp_mult'] = stats_eft.get('SessionExperienceMult', 1)
            processed_data['experience_bonus_mult'] = stats_eft.get('ExperienceBonusMult', 1)
            processed_data['survivor_class'] = stats_eft.get('SurvivorClass')
            processed_data['last_session_date_ts'] = stats_eft.get('LastSessionDate')
            processed_data['last_session_date_formatted'] = format_timestamp(processed_data['last_session_date_ts'])

            processed_data['killer_info'] = None
            if processed_data['raid_result'] == 'Killed':
                aggressor = stats_eft.get('Aggressor')
                death_cause = stats_eft.get('DeathCause')
                damage_history = stats_eft.get('DamageHistory', {})
                killer_data = {}
                if aggressor:
                    killer_data['name'] = aggressor.get('Name')
                    killer_data['side'] = aggressor.get('Side')
                    killer_data['role_raw'] = aggressor.get('Role')
                    killer_data['role_translated'] = get_item_name(killer_data['role_raw'])
                    killer_data['aggressor_profile_id'] = aggressor.get('ProfileId') or aggressor.get('GInterface187.ProfileId')
                    killer_data['aggressor_account_id'] = aggressor.get('AccountId')
                if death_cause:
                    killer_data['weapon_id'] = death_cause.get('WeaponId')
                    killer_data['weapon_name'] = get_item_name(killer_data['weapon_id'])
                    killer_data['death_cause_damage_type_raw'] = death_cause.get('DamageType')
                    killer_data['death_cause_damage_type_translated'] = get_item_name(killer_data['death_cause_damage_type_raw'])
                    killer_data['death_cause_side'] = death_cause.get('Side')
                    killer_data['death_cause_role_raw'] = death_cause.get('Role')
                    killer_data['death_cause_role_translated'] = get_item_name(killer_data['death_cause_role_raw'])
                killer_data['killed_by_part_raw'] = damage_history.get('LethalDamagePart')
                killer_data['killed_by_part_translated'] = get_item_name(killer_data['killed_by_part_raw'])
                lethal_damage_info = damage_history.get('LethalDamage', {})
                if lethal_damage_info:
                    killer_data['lethal_damage_amount'] = round(lethal_damage_info.get('Amount', 0), 1)
                    killer_data['lethal_damage_type_raw'] = lethal_damage_info.get('Type')
                    killer_data['lethal_damage_type_translated'] = get_item_name(killer_data['lethal_damage_type_raw'])
                    killer_data['lethal_damage_source_id'] = lethal_damage_info.get('SourceId')
                    killer_data['lethal_damage_source_name'] = get_item_name(killer_data['lethal_damage_source_id'])
                    killer_data['lethal_damage_blunt'] = lethal_damage_info.get('Blunt', False)
                    killer_data['lethal_damage_impacts'] = lethal_damage_info.get('ImpactsCount')
                processed_data['killer_info'] = killer_data

            body_parts = health_info.get('BodyParts')
            processed_data['final_health'] = {}
            if body_parts:
                for part_id, details in body_parts.items():
                    health_details = details.get('Health', {})
                    effects = details.get('Effects', {})
                    active_effects = []
                    for effect_id, effect_details in effects.items():
                        if isinstance(effect_details, dict) and effect_details.get('Time', -1) > -1:
                            active_effects.append(get_item_name(effect_id))
                    processed_data['final_health'][get_item_name(part_id)] = {
                        'current': round(health_details.get('Current', 0), 1),
                        'maximum': health_details.get('Maximum', 1),
                        'effects': active_effects
                    }
            processed_data['final_vitals'] = {
                'Energy': round(health_info.get('Energy', {}).get('Current', 0)),
                'Hydration': round(health_info.get('Hydration', {}).get('Current', 0)),
                'Temperature': round(health_info.get('Temperature', {}).get('Current', 0)),
                'Poison': round(health_info.get('Poison', {}).get('Current', 0)),
                'MaxEnergy': health_info.get('Energy', {}).get('Maximum', 110),
                'MaxHydration': health_info.get('Hydration', {}).get('Maximum', 100)
            }

            skills_data = profile.get('Skills', {})
            processed_data['skills_changed'] = extract_changed_skills(skills_data)

            victims_list = stats_eft.get('Victims', [])
            processed_victims = []
            for victim in victims_list:
                if not isinstance(victim, dict): continue
                victim_copy = victim.copy()
                victim_copy['WeaponName'] = get_item_name(victim_copy.get('Weapon'))
                victim_copy['DistanceFormatted'] = format_distance(victim_copy.get('Distance'))
                victim_copy['RoleTranslated'] = get_item_name(victim_copy.get('Role'))
                victim_copy['SideTranslated'] = get_item_name(victim_copy.get('Side'))
                victim_copy['BodyPartTranslated'] = get_item_name(victim_copy.get('BodyPart'))
                processed_victims.append(victim_copy)
            processed_data['victims'] = processed_victims
            processed_data['kills_count'] = len(processed_victims)

            processed_data['transfer_items'] = process_item_list(data.get('request', {}).get('transferItems', {}))
            processed_data['found_in_raid_items'] = process_item_list(stats_eft.get('FoundInRaidItems', []), id_key='ItemId')
            processed_data['lost_insured_items'] = process_item_list(data.get('request', {}).get('lostInsuredItems', []), id_key='ItemId')
            processed_data['carried_quest_items'] = process_item_list(stats_eft.get('CarriedQuestItems', []), id_key='ItemId')
            processed_data['dropped_items'] = process_item_list(stats_eft.get('DroppedItems', []), id_key='ItemId')

            overall_counters = stats_eft.get('OverallCounters')
            processed_data['overall_stats'] = extract_overall_stats(overall_counters)
            processed_data['player_count_in_raid'] = 1  # Placeholder

        return processed_data, None
    except Exception as e:
        error_message = f"Nieoczekiwany błąd przetwarzania danych: {e}"
        print(f"BŁĄD: {error_message}")
        import traceback
        traceback.print_exc()
        return None, error_message

def save_raid_data_to_file(all_raids):
    try:
        with open(RAID_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_raids, f, ensure_ascii=False, indent=2)
        print(f"Zapisano dane rajdów do: {RAID_DATA_FILE}")
    except Exception as e:
        print(f"BŁĄD: Nie można zapisać danych rajdów do pliku: {e}")

def load_raid_data_from_file():
    if not os.path.exists(RAID_DATA_FILE):
        print(f"OSTRZEŻENIE: Plik danych rajdów nie istnieje: {RAID_DATA_FILE}")
        return []
    try:
        with open(RAID_DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"BŁĄD: Nie można sparsować pliku danych rajdów: {e}")
        return []
    except Exception as e:
        print(f"BŁĄD: Nieoczekiwany problem podczas wczytywania danych rajdów: {e}")
        return []

def update_raid_data_cache():
    all_raids = load_raid_data_from_file()
    players_summary = defaultdict(lambda: {
        'raid_ids': [], 'latest_timestamp': datetime.datetime.min, 'latest_level': None, 'latest_side': None,
        'latest_total_experience': 0, 'raid_count': 0, 'total_kills': 0, 'total_deaths': 0,
        'total_survived': 0, 'total_headshots': 0, 'calculated_kd': 'N/A', 'overall_stats_latest': {},
        'latest_total_experience_formatted': '0'
    })
    errors = []
    file_cache = {}

    for raid in all_raids:
        filename = raid.get('filename')
        file_cache[filename] = raid
        nickname = raid.get('nickname')
        if nickname:
            player = players_summary[nickname]
            player['raid_ids'].append(filename)
            player['raid_count'] += 1
            player['latest_level'] = raid.get('level')
            player['latest_side'] = raid.get('side')
            player['latest_total_experience'] = raid.get('total_experience', 0)
            player['latest_total_experience_formatted'] = format_exp(player['latest_total_experience'])
            player['latest_timestamp'] = datetime.datetime.fromtimestamp(raid.get('timestamp', datetime.datetime.min).timestamp())
            player['overall_stats_latest'] = raid.get('overall_stats', {})
            player['total_kills'] += raid.get('kills_count', 0)
            victims = raid.get('victims', [])
            for victim in victims:
                if victim.get('BodyPart') == 'Head': player['total_headshots'] += 1
            raid_result = raid.get('raid_result')
            if raid_result == 'Survived': player['total_survived'] += 1
            else: player['total_deaths'] += 1

    for nick, data in players_summary.items():
        if data['total_deaths'] > 0: data['calculated_kd'] = f"{data['total_kills'] / data['total_deaths']:.2f}"
        else: data['calculated_kd'] = f"{data['total_kills']}"

    all_raids.sort(key=lambda r: r.get('timestamp', datetime.datetime.min), reverse=True)
    return {
        'all_raids': all_raids,
        'players_summary': players_summary,
        'errors': errors,
        'file_cache': file_cache
    }

# Globalny cache
RAID_DATA_CACHE = {}
LAST_CACHE_UPDATE = datetime.datetime.min
CACHE_TTL = datetime.timedelta(minutes=1)

def get_cached_raid_data():
    global RAID_DATA_CACHE, LAST_CACHE_UPDATE
    now = datetime.datetime.now()
    if not RAID_DATA_CACHE or now - LAST_CACHE_UPDATE > CACHE_TTL:
        print("Odświeżanie cache danych rajdów...")
        RAID_DATA_CACHE = update_raid_data_cache()
        LAST_CACHE_UPDATE = now
        print("Cache zaktualizowany.")
    return RAID_DATA_CACHE

def get_map_image_url(location_name):
    filename = MAP_IMAGES.get(location_name, MAP_IMAGES["unknown"])
    return f"images/maps/{filename}"

@app.context_processor
def inject_utilities():
    return {'now': datetime.datetime.utcnow, 'get_map_image_url': get_map_image_url, 'get_item_name': get_item_name, 'format_exp': format_exp}

# --- Endpointy API dla mod.js ---
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
        return jsonify({"error": "Brak danych JSON"}), 400
    timestamp_ms = int(datetime.datetime.now().timestamp() * 1000)
    processed_data, error = process_single_raid_data(data, timestamp_ms, is_start=True)
    if error:
        print(f"BŁĄD: {error}")
        return jsonify({"error": error}), 400
    cached_data = get_cached_raid_data()
    cached_data['all_raids'].append(processed_data)
    cached_data['file_cache'][processed_data['filename']] = processed_data
    save_raid_data_to_file(cached_data['all_raids'])
    return jsonify({"status": "success"})

@app.route('/api/raid/end', methods=['POST'])
def raid_end():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Brak danych JSON"}), 400
    timestamp_ms = int(datetime.datetime.now().timestamp() * 1000)
    processed_data, error = process_single_raid_data(data, timestamp_ms, is_start=False)
    if error:
        print(f"BŁĄD: {error}")
        return jsonify({"error": error}), 400
    cached_data = get_cached_raid_data()
    cached_data['all_raids'].append(processed_data)
    cached_data['file_cache'][processed_data['filename']] = processed_data
    cached_data['players_summary'] = defaultdict(lambda: {
        'raid_ids': [], 'latest_timestamp': datetime.datetime.min, 'latest_level': None, 'latest_side': None,
        'latest_total_experience': 0, 'raid_count': 0, 'total_kills': 0, 'total_deaths': 0,
        'total_survived': 0, 'total_headshots': 0, 'calculated_kd': 'N/A', 'overall_stats_latest': {},
        'latest_total_experience_formatted': '0'
    })
    nickname = processed_data.get('nickname')
    if nickname:
        player = cached_data['players_summary'][nickname]
        player['raid_ids'].append(processed_data['filename'])
        player['raid_count'] += 1
        player['latest_level'] = processed_data.get('level')
        player['latest_side'] = processed_data.get('side')
        player['latest_total_experience'] = processed_data.get('total_experience', 0)
        player['latest_total_experience_formatted'] = format_exp(player['latest_total_experience'])
        player['latest_timestamp'] = processed_data.get('timestamp', datetime.datetime.min)
        player['overall_stats_latest'] = processed_data.get('overall_stats', {})
        player['total_kills'] += processed_data.get('kills_count', 0)
        victims = processed_data.get('victims', [])
        for victim in victims:
            if victim.get('BodyPart') == 'Head': player['total_headshots'] += 1
        raid_result = processed_data.get('raid_result')
        if raid_result == 'Survived': player['total_survived'] += 1
        else: player['total_deaths'] += 1
        if player['total_deaths'] > 0: player['calculated_kd'] = f"{player['total_kills'] / player['total_deaths']:.2f}"
        else: player['calculated_kd'] = f"{player['total_kills']}"
    save_raid_data_to_file(cached_data['all_raids'])
    return jsonify({"status": "success"})

# --- Istniejące Trasy ---
@app.route('/')
def index():
    cached_data = get_cached_raid_data()
    all_raids = cached_data['all_raids']
    players_summary = cached_data['players_summary']
    errors = cached_data['errors']

    latest_raid = all_raids[0] if all_raids else None
    recent_raids_data = []
    limit = 10
    for raid in all_raids[:limit]:
        nickname = raid.get('nickname', 'Unknown')
        player_info = players_summary.get(nickname, {})
        raid_summary = {
            'filename': raid['filename'],
            'timestamp_formatted': raid.get('timestamp_formatted', 'N/A'),
            'location': raid.get('location', 'unknown'),
            'nickname': nickname,
            'level': player_info.get('latest_level', 'N/A'),
            'side': player_info.get('latest_side', 'N/A'),
            'raid_count': player_info.get('raid_count', 0),
            'exp': raid.get('total_session_exp_calculated', 0),
            'map_image_filename': get_map_image_url(raid.get('location', 'unknown'))
        }
        recent_raids_data.append(raid_summary)
    return render_template('index.html', latest_raid=latest_raid, recent_raids=recent_raids_data, errors=errors)

@app.route('/players')
def players_list():
    cached_data = get_cached_raid_data()
    players_summary = cached_data['players_summary']
    errors = cached_data['errors']

    players_list_data = []
    for nickname, data in players_summary.items():
        player_data = data.copy()
        player_data['nickname'] = nickname
        player_data['side_translated'] = get_item_name(player_data.get('latest_side', 'Unknown'))
        players_list_data.append(player_data)
    players_list_data.sort(key=lambda p: p['nickname'].lower())
    return render_template('gracze.html', players_list=players_list_data, errors=errors)

@app.route('/player/<nickname>')
def player_details(nickname):
    cached_data = get_cached_raid_data()
    all_raids = cached_data['all_raids']
    players_summary = cached_data['players_summary']
    errors = cached_data['errors']
    player_info = players_summary.get(nickname)

    if not player_info: abort(404, description="Gracz nie znaleziony")

    player_raids = [raid for raid in all_raids if raid.get('nickname') == nickname]
    latest_raid = player_raids[0] if player_raids else None

    player_stats = {
        'sessions': player_info.get('raid_count', 0),
        'survived_sessions': player_info.get('total_survived', 0),
        'deaths': player_info.get('total_deaths', 0),
        'kills': player_info.get('total_kills', 0),
        'survival_rate': player_info.get('overall_stats_latest', {}).get('survival_rate', 'N/A'),
        'kd_ratio': player_info.get('calculated_kd', 'N/A'),
        'headshots': player_info.get('total_headshots', 0),
        'longest_shot': player_info.get('overall_stats_latest', {}).get('longest_shot_formatted', 'N/A'),
    }

    skills_changed = latest_raid.get('skills_changed', []) if latest_raid else []
    achievements = []

    return render_template('profil.html',
                           nickname=nickname,
                           player_info=player_info,
                           player_stats=player_stats,
                           latest_raid=latest_raid,
                           player_raids=player_raids,
                           skills=skills_changed,
                           achievements=achievements,
                           errors=errors)

@app.route('/api/raid/<path:filename>')
def api_raid_details(filename):
    cached_data = get_cached_raid_data()
    processed_data = cached_data['file_cache'].get(filename)
    if processed_data:
        return jsonify(error=None, data=processed_data)
    return jsonify(error=f"Nie znaleziono danych dla pliku {filename}.", data=None), 404

# Uruchomienie aplikacji
if __name__ == '__main__':
    load_translations()
    get_cached_raid_data()
    app.run(debug=True, host='127.0.0.1', port=5000)