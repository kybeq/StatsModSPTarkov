# ... (początek pliku bez zmian - importy, konfiguracja, funkcje pomocnicze do format_time, format_distance, get_item_name, process_item_list) ...
import os
import json
import math
import glob # Do wyszukiwania plików
import datetime # Do pracy z timestampami
from flask import Flask, render_template, abort, url_for
from collections import defaultdict

# Flask domyślnie używa folderu 'static'
app = Flask(__name__, static_folder='static')

# --- Konfiguracja Ścieżek ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEBUG_LOGS_FOLDER = os.path.join(BASE_DIR, 'debug_logs')
TRANSLATE_FOLDER = os.path.join(BASE_DIR, 'translate')
TRANSLATION_FILENAME = 'pl.json'
RAID_FILE_PATTERN = 'onEndLocalRaidRequest_request_*.json'
TRANSLATION_FILE_PATH = os.path.join(TRANSLATE_FOLDER, TRANSLATION_FILENAME)

MAP_IMAGES = {
    "Fabryce": "factory.avif",
    "Customs": "customs.avif", # Przykład, dodaj resztę map
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
    # Spróbuj znaleźć tłumaczenie dla kluczy ShortName, Name lub bezpośrednio ID
    short_name_key = f"{item_id} ShortName"; name_key = f"{item_id} Name"; plain_id_key = str(item_id)
    # Dodajmy też obsługę typowych ról i typów obrażeń jako fallback
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
        "usec": "USEC", "bear": "BEAR", "savage": "Scav",
        "Bullet": "Pocisk", "Explosion": "Eksplozja", "Melee": "Broń biała", "Fall": "Upadek",
        "Structural": "Strukturalne", "HeavyBleeding": "Mocne krwawienie", "LightBleeding": "Lekkie krwawienie",
        "Poison": "Trucizna", "Stimulator": "Stymulator", "Unknown": "Nieznany", "Undefined": "Niezdefiniowany",
        "Head": "Głowa", "Chest": "Klatka piersiowa", "Stomach": "Brzuch",
        "LeftArm": "Lewa ręka", "RightArm": "Prawa ręka",
        "LeftLeg": "Lewa noga", "RightLeg": "Prawa noga"
    }
    return translations.get(short_name_key, translations.get(name_key, translations.get(plain_id_key, fallback_keys.get(str(item_id), str(item_id)))))


def format_time(seconds):
    if seconds is None: return "N/A"
    try:
        seconds = int(seconds)
        if seconds < 0: seconds = 0
        hours = seconds // 3600; minutes = (seconds % 3600) // 60; remaining_seconds = seconds % 60
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
    """Konwertuje timestamp na czytelny string lub zwraca 'N/A'."""
    if ts is None: return "N/A"
    try:
        # Sprawdź, czy to timestamp sekundowy czy milisekundowy (heurystyka)
        if ts > 3000000000: # Prawdopodobnie milisekundy (po ~2065 roku w sekundach)
            dt = datetime.datetime.fromtimestamp(ts / 1000)
        else:
             dt = datetime.datetime.fromtimestamp(ts)
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError, OSError):
         return "N/A"

def process_item_list(items_dict_or_list, count_key='count', id_key='_tpl'):
    processed_items = []; item_counts = defaultdict(int)
    items_to_process = []
    if isinstance(items_dict_or_list, dict): items_to_process = items_dict_or_list.values()
    elif isinstance(items_dict_or_list, list): items_to_process = items_dict_or_list
    if not items_to_process: return [] # Zwróć pustą listę, jeśli nie ma nic do przetworzenia
    for item in items_to_process:
        if not isinstance(item, dict): continue # Ignoruj elementy, które nie są słownikami
        tpl_id = item.get(id_key) or item.get('ItemId')
        if tpl_id:
            count = item.get('upd', {}).get('StackObjectsCount', 1) if 'upd' in item else item.get(count_key, 1)
            # Upewnij się, że count jest liczbą
            try:
                item_counts[tpl_id] += int(count)
            except (ValueError, TypeError):
                item_counts[tpl_id] += 1 # Domyślnie 1, jeśli konwersja zawiedzie
    for tpl_id, count in item_counts.items():
        processed_items.append({'id': tpl_id, 'name': get_item_name(tpl_id), 'count': count})
    processed_items.sort(key=lambda x: x['name'])
    return processed_items


def extract_session_stats(session_counters):
    stats = {'damage_dealt': 0, 'body_parts_destroyed': 0, 'pedometer': 0, 'exp_kill': 0, 'exp_looting': 0, 'exp_exit_status': 0, 'deaths': 0, 'blood_loss': 0, 'damage_received_total': 0, 'damage_received_details': {}}
    if session_counters and 'Items' in session_counters:
        for item in session_counters.get('Items', []): # Użyj .get z domyślną pustą listą
            key = item.get('Key'); value = item.get('Value', 0)
            if key and isinstance(key, list): # Upewnij się, że klucz jest listą
                try:
                    key_str = "_".join(map(str, key))
                    if "CombatDamage" in key_str: stats['damage_dealt'] += value
                    elif key[0] == "BodyPartDamage" and len(key) > 1:
                        part_name = get_item_name(key[1]) # Tłumaczenie nazwy części ciała
                        stats['damage_received_total'] += value
                        stats['damage_received_details'][part_name] = stats['damage_received_details'].get(part_name, 0) + value
                    elif "BodyPartsDestroyed" in key_str: stats['body_parts_destroyed'] = value
                    elif "Pedometer" in key_str: stats['pedometer'] = value
                    elif key == ["Exp", "ExpKill"] or key_str == "ExpKill": stats['exp_kill'] = value # Dodatkowe sprawdzenie dla różnych formatów klucza
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
        for item in overall_counters.get('Items', []): # Użyj .get
            key = item.get('Key'); value = item.get('Value', 0)
            if key and isinstance(key, list): # Upewnij się, że klucz jest listą
                try:
                    key_str = "_".join(map(str, key)) # Pomocniczy string dla łatwiejszego sprawdzania
                    if key == ['Kills']: stats['kills'] = value
                    elif key == ['Deaths']: stats['deaths'] = value
                    elif key_str == "Sessions_Pmc": stats['sessions'] = value
                    elif key_str == "ExitStatus_Survived_Pmc": stats['survived_sessions'] = value
                    elif key == ['HeadShots']: stats['headshots'] = value
                    elif key_str == "LongestShot": stats['longest_shot'] = value # Może być 'LongestShot' lub ['LongShots']
                    elif key == ['LongShots']: stats['longest_shot'] = value
                except TypeError: pass
    stats['kd_ratio'] = f"{stats['kills'] / stats['deaths']:.2f}" if stats['deaths'] > 0 else 'N/A'
    stats['survival_rate'] = f"{(stats['survived_sessions'] / stats['sessions'] * 100):.1f}%" if stats['sessions'] > 0 else 'N/A'
    stats['longest_shot_formatted'] = format_distance(stats.get('longest_shot'))
    return stats


def extract_changed_skills(skills_data):
    """Przetwarza zarówno Common jak i Mastering skills."""
    changed = []
    if not skills_data: return changed

    # Przetwórz Common skills
    if 'Common' in skills_data and skills_data['Common']:
        for skill in skills_data['Common']:
            if not isinstance(skill, dict): continue # Pomiń, jeśli element nie jest słownikiem
            points_earned = skill.get('PointsEarnedDuringSession', 0)
            if points_earned > 0:
                skill_copy = skill.copy()
                try:
                    skill_copy['PointsEarnedFormatted'] = f"{points_earned:.2f}"
                    skill_copy['ProgressFormatted'] = f"{skill_copy.get('Progress', 0):.2f}"
                    skill_copy['SkillName'] = get_item_name(skill_copy.get('Id'))
                    skill_copy['SkillType'] = 'Common' # Dodaj typ dla rozróżnienia
                    changed.append(skill_copy)
                except (ValueError, TypeError): print(f"OSTRZEŻENIE: Problem z formatowaniem danych umiejętności Common: {skill}")

    # Przetwórz Mastering skills (jeśli istnieją)
    if 'Mastering' in skills_data and skills_data['Mastering']:
         for skill in skills_data['Mastering']:
            if not isinstance(skill, dict): continue
            points_earned = skill.get('PointsEarnedDuringSession', 0)
            # W Mastering często nie ma PointsEarnedDuringSession, sprawdzamy Progress
            progress = skill.get('Progress', 0)
            # Załóżmy, że jeśli progress > 0, to jest to istotne (można dostosować logikę)
            if progress > 0 or points_earned > 0: # Zmieniono warunek
                skill_copy = skill.copy()
                try:
                    # Mastering może nie mieć PointsEarnedDuringSession, dodajmy placeholder
                    skill_copy['PointsEarnedFormatted'] = f"{points_earned:.2f}" if points_earned else "N/A"
                    skill_copy['ProgressFormatted'] = f"{progress:.2f}"
                    skill_copy['SkillName'] = get_item_name(skill_copy.get('Id')) # Zakłada, że Mastering ID są w tłumaczeniach
                    skill_copy['SkillType'] = 'Mastering' # Dodaj typ
                    changed.append(skill_copy)
                except (ValueError, TypeError): print(f"OSTRZEŻENIE: Problem z formatowaniem danych umiejętności Mastering: {skill}")

    # Sortuj wszystkie zmienione umiejętności razem
    # Można sortować np. po typie, a potem po punktach/progressie
    changed.sort(key=lambda x: (x.get('SkillType', ''), -x.get('PointsEarnedDuringSession', 0), -x.get('Progress', 0)))
    return changed


def get_timestamp_from_filename(filename):
    """Próbuje wyciągnąć timestamp (w milisekundach) z końca nazwy pliku."""
    try:
        base_name = os.path.splitext(filename)[0]
        timestamp_ms_str = base_name.split('_')[-1]
        # Dodatkowe sprawdzenie, czy to na pewno liczba
        if not timestamp_ms_str.isdigit():
             raise ValueError("Ostatni segment nazwy pliku nie jest liczbą.")
        timestamp_ms = int(timestamp_ms_str)
        return datetime.datetime.fromtimestamp(timestamp_ms / 1000)
    except (IndexError, ValueError, TypeError):
        print(f"OSTRZEŻENIE: Nie można wyekstrahować timestampu z nazwy pliku: {filename}. Używam czasu modyfikacji pliku.")
        # Fallback na czas modyfikacji pliku, jeśli ekstrakcja zawiedzie
        try:
            # Potrzebujemy pełnej ścieżki do pliku dla os.path.getmtime
            full_path = os.path.join(DEBUG_LOGS_FOLDER, filename) # Zakładamy, że DEBUG_LOGS_FOLDER jest zdefiniowany globalnie
            if os.path.exists(full_path):
                 return datetime.datetime.fromtimestamp(os.path.getmtime(full_path))
            else:
                 return datetime.datetime.min # Jeśli plik nie istnieje
        except Exception:
            return datetime.datetime.min # Ostateczny fallback


# --- Funkcja przetwarzająca JEDEN plik raportu (ZMODYFIKOWANA) ---
def process_single_raid_file(filepath):
    """Wczytuje i przetwarza dane z jednego pliku JSON raportu rajdu."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        return None, f"Plik nie znaleziony: {os.path.basename(filepath)}"
    except json.JSONDecodeError as e:
        return None, f"Błąd parsowania JSON w pliku {os.path.basename(filepath)}: {e}"
    except Exception as e:
        return None, f"Nieoczekiwany błąd wczytywania pliku {os.path.basename(filepath)}: {e}"

    processed_data = {}
    error_message = None

    try:
        if not data or 'results' not in data:
            raise ValueError("Brak klucza 'results' w danych JSON.")

        results = data.get('results', {})
        profile = results.get('profile', {})
        if not profile: raise ValueError("Brak klucza 'profile' w 'results'.")

        info = profile.get('Info', {})
        stats_eft = profile.get('Stats', {}).get('Eft', {}) # stats_eft może być pusty
        health_info = profile.get('Health', {})

        # --- Podstawowe dane rajdu i gracza ---
        processed_data['filename'] = os.path.basename(filepath)
        processed_data['timestamp'] = get_timestamp_from_filename(processed_data['filename'])
        processed_data['timestamp_formatted'] = processed_data['timestamp'].strftime('%Y-%m-%d %H:%M:%S') if processed_data['timestamp'] != datetime.datetime.min else "N/A"

        processed_data['server_id'] = data.get('serverId')
        processed_data['raid_result'] = results.get('result')
        processed_data['exit_name'] = results.get('exitName') if processed_data['raid_result'] != 'Killed' else None
        processed_data['location_id'] = info.get('EntryPoint')
        processed_data['location'] = get_item_name(processed_data['location_id'])
        processed_data['nickname'] = info.get('Nickname')
        processed_data['level'] = info.get('Level')
        processed_data['side'] = info.get('Side')
        processed_data['total_experience'] = info.get('Experience') # Całkowite EXP profilu
        processed_data['karma_value'] = profile.get('karmaValue')   # Karma
        processed_data['registration_date_ts'] = info.get('RegistrationDate')
        processed_data['registration_date_formatted'] = format_timestamp(processed_data['registration_date_ts'])
        processed_data['game_version'] = info.get('GameVersion')
        processed_data['voice'] = info.get('Voice')
        processed_data['group_id'] = info.get('GroupId')
        processed_data['team_id'] = info.get('TeamId')
        processed_data['profile_id'] = profile.get('_id')
        processed_data['account_id'] = profile.get('aid')
        processed_data['killer_profile_id'] = results.get('killerId') # ID profilu zabójcy z 'results'
        processed_data['killer_account_id'] = results.get('killerAid') # ID konta zabójcy z 'results'


        # --- Czas, EXP i inne statystyki sesji ---
        # TotalInGameTime jest bardziej wiarygodne jeśli istnieje
        total_in_game_time = stats_eft.get('TotalInGameTime') if stats_eft else None
        # playTime z results jako fallback
        play_time_fallback = results.get('playTime')
        raid_duration_seconds = total_in_game_time if total_in_game_time is not None else play_time_fallback

        processed_data['play_time_seconds'] = raid_duration_seconds
        processed_data['play_time_formatted'] = format_time(raid_duration_seconds)

        processed_data['total_session_exp_from_json'] = stats_eft.get('TotalSessionExperience', 0) if stats_eft else 0
        session_counters = stats_eft.get('SessionCounters') if stats_eft else None
        processed_data['session_stats'] = extract_session_stats(session_counters)
        exp_sum_from_counters = sum(v for k, v in processed_data['session_stats'].items() if k.startswith('exp_'))
        processed_data['total_session_exp_calculated'] = round(exp_sum_from_counters)

        processed_data['session_exp_mult'] = stats_eft.get('SessionExperienceMult', 1) if stats_eft else 1 # Mnożnik EXP sesji
        processed_data['experience_bonus_mult'] = stats_eft.get('ExperienceBonusMult', 1) if stats_eft else 1 # Mnożnik bonusu EXP
        processed_data['survivor_class'] = stats_eft.get('SurvivorClass') if stats_eft else None # Klasa przetrwania

        processed_data['last_session_date_ts'] = stats_eft.get('LastSessionDate') if stats_eft else None
        processed_data['last_session_date_formatted'] = format_timestamp(processed_data['last_session_date_ts'])

        # --- Informacje o zabójcy (jeśli dotyczy) ---
        processed_data['killer_info'] = None
        if processed_data['raid_result'] == 'Killed' and stats_eft:
            aggressor = stats_eft.get('Aggressor')
            death_cause = stats_eft.get('DeathCause')
            damage_history = stats_eft.get('DamageHistory', {})
            killer_data = {}

            if aggressor:
                killer_data['name'] = aggressor.get('Name')
                killer_data['side'] = aggressor.get('Side')
                killer_data['role_raw'] = aggressor.get('Role') # Dodajemy surową rolę
                killer_data['role_translated'] = get_item_name(killer_data['role_raw']) # Tłumaczenie roli
                killer_data['aggressor_profile_id'] = aggressor.get('ProfileId') or aggressor.get('GInterface187.ProfileId') # ID profilu z aggressor
                killer_data['aggressor_account_id'] = aggressor.get('AccountId') # ID konta z aggressor

            if death_cause:
                 # Używamy WeaponId do tłumaczenia, bo WeaponName w Aggressor może być ID
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
                # Dodatkowe szczegóły obrażeń śmiertelnych
                killer_data['lethal_damage_source_id'] = lethal_damage_info.get('SourceId') # Np. ID pocisku
                killer_data['lethal_damage_source_name'] = get_item_name(killer_data['lethal_damage_source_id'])
                killer_data['lethal_damage_blunt'] = lethal_damage_info.get('Blunt', False)
                killer_data['lethal_damage_impacts'] = lethal_damage_info.get('ImpactsCount')

            processed_data['killer_info'] = killer_data

        # --- Końcowe zdrowie i witalność (z efektami) ---
        body_parts = health_info.get('BodyParts')
        processed_data['final_health'] = {}
        if body_parts:
            for part_id, details in body_parts.items():
                 health_details = details.get('Health', {})
                 effects = details.get('Effects', {})
                 active_effects = []
                 # Sprawdzamy czy efekty istnieją i czy czas jest > -1 (co oznacza aktywny)
                 for effect_id, effect_details in effects.items():
                      if isinstance(effect_details, dict) and effect_details.get('Time', -1) > -1:
                           active_effects.append(get_item_name(effect_id)) # Tłumaczymy nazwę efektu

                 processed_data['final_health'][get_item_name(part_id)] = {
                     'current': round(health_details.get('Current', 0), 1),
                     'maximum': health_details.get('Maximum', 1),
                     'effects': active_effects # Lista aktywnych efektów
                 }
        processed_data['final_vitals'] = {
            'Energy': round(health_info.get('Energy', {}).get('Current', 0)),
            'Hydration': round(health_info.get('Hydration', {}).get('Current', 0)),
            'Temperature': round(health_info.get('Temperature', {}).get('Current', 0)),
            'Poison': round(health_info.get('Poison', {}).get('Current', 0)), # Dodano truciznę
            'MaxEnergy': health_info.get('Energy', {}).get('Maximum', 110),
            'MaxHydration': health_info.get('Hydration', {}).get('Maximum', 100)
        }

        # --- Zmienione umiejętności (Common + Mastering) ---
        skills_data = profile.get('Skills', {}) # Pobierz cały obiekt Skills
        processed_data['skills_changed'] = extract_changed_skills(skills_data) # Przekaż cały obiekt

        # --- Ofiary gracza (bez zmian w logice, tylko upewnienie się, że działa z get) ---
        victims_list = stats_eft.get('Victims', []) if stats_eft else []
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

        # --- Przedmioty ---
        processed_data['transfer_items'] = process_item_list(data.get('transferItems', {}), id_key='_tpl')
        processed_data['found_in_raid_items'] = process_item_list(stats_eft.get('FoundInRaidItems', []), id_key='ItemId') if stats_eft else []
        processed_data['lost_insured_items'] = process_item_list(data.get('lostInsuredItems', []), id_key='ItemId')
        processed_data['carried_quest_items'] = process_item_list(stats_eft.get('CarriedQuestItems', []), id_key='ItemId') if stats_eft else [] # Zmieniono klucz na ItemId wg przykładu, ale może być _tpl? Sprawdź
        processed_data['dropped_items'] = process_item_list(stats_eft.get('DroppedItems', []), id_key='ItemId') if stats_eft else [] # Dodano upuszczone przedmioty


        # --- Statystyki Ogólne (z profilu po rajdzie) ---
        overall_counters = stats_eft.get('OverallCounters') if stats_eft else None
        processed_data['overall_stats'] = extract_overall_stats(overall_counters)

        # --- Liczba graczy w rajdzie (nadal placeholder) ---
        processed_data['player_count_in_raid'] = 1

    except ValueError as e:
        error_message = f"Błąd przetwarzania danych w pliku {os.path.basename(filepath)}: {e}"
        print(f"BŁĄD: {error_message}")
    except Exception as e:
        error_message = f"Nieoczekiwany błąd przetwarzania danych raportu {os.path.basename(filepath)}: {e}"
        print(f"BŁĄD: {error_message}")
        import traceback; traceback.print_exc() # Drukuj pełny traceback dla nieoczekiwanych błędów

    return processed_data if not error_message else None, error_message

# --- Funkcja do ładowania i agregowania danych ze WSZYSTKICH plików (BEZ ZMIAN) ---
def load_all_raid_data():
    """Skanuje folder logów, przetwarza wszystkie pliki rajdów i agreguje dane."""
    all_processed_raids = []
    # Zmieniamy players_summary na defaultdict dla łatwiejszego dodawania statystyk
    players_summary = defaultdict(lambda: {
        'raid_ids': [],
        'latest_timestamp': datetime.datetime.min,
        'latest_level': None,
        'latest_side': None,
        'latest_total_experience': 0,
        'raid_count': 0,
        'total_kills': 0,
        'total_deaths': 0, # Liczba rajdów nieprzetrwanych
        'total_survived': 0, # Liczba rajdów przetrwanych
        'total_headshots': 0,
        'calculated_kd': 'N/A', # Domyślnie N/A
        'overall_stats_latest': {} # Przechowamy ostatnie znane overall_stats
    })
    errors = []

    raid_files = glob.glob(os.path.join(DEBUG_LOGS_FOLDER, RAID_FILE_PATTERN))

    # Sortuj pliki po timestampie (najnowsze na końcu)
    raid_files.sort(key=lambda f: get_timestamp_from_filename(os.path.basename(f)))

    # Najpierw przetwórzmy wszystkie rajdy i zapiszmy je
    for filepath in raid_files:
        if not os.path.exists(filepath):
            print(f"OSTRZEŻENIE: Pomijanie nieistniejącego pliku znalezionego przez glob: {filepath}")
            continue

        processed_data, error = process_single_raid_file(filepath)
        if error:
            errors.append(f"{os.path.basename(filepath)}: {error}")
        if processed_data:
            all_processed_raids.append(processed_data)

    # Teraz agregujmy dane w players_summary, iterując po przetworzonych rajdach
    # Sortujemy rajdy rosnąco po dacie, aby 'latest' było faktycznie ostatnie
    all_processed_raids.sort(key=lambda r: r.get('timestamp', datetime.datetime.min))

    for raid_data in all_processed_raids:
        nickname = raid_data.get('nickname')
        if nickname:
            player = players_summary[nickname] # Dostęp do słownika gracza

            player['raid_ids'].append(raid_data['filename'])
            player['raid_count'] += 1

            # Aktualizuj 'latest' dane
            current_timestamp = raid_data.get('timestamp', datetime.datetime.min)
            # Zawsze aktualizujemy, bo iterujemy w kolejności chronologicznej
            player['latest_level'] = raid_data.get('level')
            player['latest_side'] = raid_data.get('side')
            player['latest_total_experience'] = raid_data.get('total_experience') # Zapiszmy ostatnie znane całkowite EXP
            player['latest_timestamp'] = current_timestamp # Zapiszmy timestamp ostatniego rajdu
            player['overall_stats_latest'] = raid_data.get('overall_stats', {}) # Zapiszmy ostatnie overall_stats

            # Agregacja statystyk
            player['total_kills'] += raid_data.get('kills_count', 0)

            # Liczenie headshotów z listy ofiar
            victims = raid_data.get('victims', [])
            for victim in victims:
                # Zakładamy, że 'BodyPart' zawiera informację o headshocie
                # Może być konieczne dostosowanie klucza lub wartości ('Head'?)
                # Sprawdzamy, czy 'BodyPart' to 'Head' (lub odpowiednik z tłumaczeń)
                # Użyjemy surowej wartości 'Head' dla pewności
                if victim.get('BodyPart') == 'Head':
                     player['total_headshots'] += 1

            # Sprawdzanie wyniku rajdu
            raid_result = raid_data.get('raid_result')
            if raid_result == 'Survived':
                player['total_survived'] += 1
            else:
                # Zakładamy, że każdy inny wynik to 'śmierć' w kontekście K/D i statystyk graczy
                # Można to doprecyzować, jeśli np. MIA ma być inaczej liczone
                player['total_deaths'] += 1


    # Po przetworzeniu wszystkich rajdów, oblicz K/D dla każdego gracza
    for nick, data in players_summary.items():
        if data['total_deaths'] > 0:
            data['calculated_kd'] = f"{data['total_kills'] / data['total_deaths']:.2f}"
        else:
            # Jeśli 0 śmierci, K/D jest równe liczbie killi lub N/A/'∞'
            data['calculated_kd'] = f"{data['total_kills']}" # Lub '∞' lub 'N/A'

        # Usuń pomocniczy timestamp z finalnego słownika, jeśli go nie potrzebujemy na zewnątrz
        # data.pop('latest_timestamp', None) # Zostawmy na razie, może się przydać

    # Zwracamy posortowane rajdy (od najnowszych) i podsumowanie graczy
    all_processed_raids.sort(key=lambda r: r.get('timestamp', datetime.datetime.min), reverse=True)

    return all_processed_raids, players_summary, errors

def get_map_image_url(location_name):
    """Zwraca URL do obrazka mapy na podstawie przetłumaczonej nazwy."""
    filename = MAP_IMAGES.get(location_name, MAP_IMAGES["unknown"])
    # Zwracaj pełną ścieżkę, którą obsłuży url_for w szablonie
    # Np. 'maps/factory.avif'
    return f"images/maps/{filename}"


# --- Kontekst procesora (Dodajemy map_images do kontekstu) ---
@app.context_processor
def inject_utilities():
    # Dajemy dostęp do funkcji get_map_image_url, get_item_name i aktualnej daty w każdym szablonie
    return {
        'now': datetime.datetime.utcnow,
        'get_map_image_url': get_map_image_url,
        'get_item_name': get_item_name # Dodajemy funkcję tłumaczącą
        }

# --- Trasy Aplikacji (BEZ ZMIAN W LOGICE, tylko w renderowaniu szablonów, które zostaną zaktualizowane) ---

@app.route('/')
def index():
    all_raids, players_summary, errors = load_all_raid_data()

    # Dane dla karty ostatniego rajdu (globalnie)
    latest_raid = all_raids[0] if all_raids else None

    # Dane dla tabeli ostatnich rajdów (np. 10 ostatnich)
    recent_raids_data = []
    limit = 10 # Ile ostatnich rajdów pokazać w tabeli
    for raid in all_raids[:limit]:
        nickname = raid.get('nickname')
        player_info = players_summary.get(nickname, {}) # Pobierz info gracza
        raid_summary = {
            'filename': raid['filename'],
            'timestamp_formatted': raid.get('timestamp_formatted', 'N/A'),
            'location': raid['location'],
            'nickname': nickname,
            'level': player_info.get('latest_level', 'N/A'), # Weź poziom z podsumowania
            'side': player_info.get('latest_side', 'N/A'),  # Weź frakcję z podsumowania
            'raid_count': player_info.get('raid_count', 0), # Liczba rajdów gracza
            'exp': raid.get('total_session_exp_calculated', 0),
            'map_image_filename': get_map_image_url(raid['location']) # Dodajemy nazwę pliku obrazka mapy
        }
        recent_raids_data.append(raid_summary)

    return render_template('index.html', # Używamy nowego szablonu
                           latest_raid=latest_raid,
                           recent_raids=recent_raids_data, # Przekazujemy przygotowane dane
                           errors=errors)

@app.route('/players')
def players_list():
    _, players_summary, errors = load_all_raid_data() # Potrzebujemy tylko summary

    # Konwertuj słownik summary na listę, dodając nick do każdego elementu
    players_list_data = []
    for nickname, data in players_summary.items():
        player_data = data.copy() # Skopiuj dane
        player_data['nickname'] = nickname # Dodaj nick bezpośrednio do słownika
        # Dodajemy też przetłumaczoną nazwę frakcji dla szablonu
        player_data['side_translated'] = get_item_name(player_data.get('latest_side', 'Unknown'))
        players_list_data.append(player_data)

    # Sortuj graczy alfabetycznie po nicku (ignorując wielkość liter)
    players_list_data.sort(key=lambda p: p['nickname'].lower())

    return render_template('gracze.html',
                           players_list=players_list_data,
                           errors=errors)

@app.route('/player/<nickname>')
def player_details(nickname):
    all_raids, players_summary, errors = load_all_raid_data()
    player_info = players_summary.get(nickname)

    if not player_info:
        abort(404, description="Gracz nie znaleziony")

    # Filtruj rajdy tylko dla tego gracza (najnowsze pierwsze, bo all_raids jest już posortowane)
    player_raids = [raid for raid in all_raids if raid.get('nickname') == nickname]

    # Wybierz szablon na podstawie ostatniej znanej frakcji gracza
    player_side = player_info.get('latest_side', 'Unknown').lower() # Pobierz frakcję i zmień na małe litery
    if player_side == 'usec':
        template_name = 'profil-usec.html'
    elif player_side == 'bear':
        template_name = 'profil-bear.html'
    else:
        # Domyślny szablon lub obsługa błędu, jeśli frakcja jest inna/nieznana
        # Na razie użyjemy usec jako fallback, można dodać dedykowany szablon ogólny
        template_name = 'profil-usec.html' # Można zmienić na np. 'profil-generic.html'

    latest_raid = player_raids[0] if player_raids else None

    # Przygotowanie danych dla sekcji statystyk ogólnych (używamy danych z player_info)
    # Te dane pochodzą z ostatniego rajdu (overall_stats_latest) lub są obliczone (calculated_kd, totals)
    player_stats = {
        'sessions': player_info.get('raid_count', 0),
        'survived_sessions': player_info.get('total_survived', 0),
        'deaths': player_info.get('total_deaths', 0), # Używamy obliczonej sumy śmierci
        'kills': player_info.get('total_kills', 0), # Używamy obliczonej sumy killi
        'survival_rate': player_info.get('overall_stats_latest', {}).get('survival_rate', 'N/A'), # SR z ostatniego overall
        'kd_ratio': player_info.get('calculated_kd', 'N/A'), # Obliczone KD
        'headshots': player_info.get('total_headshots', 0), # Obliczone headshoty
        'longest_shot': player_info.get('overall_stats_latest', {}).get('longest_shot_formatted', 'N/A'), # Longest shot z ostatniego overall
    }


    # Pobieramy umiejętności TYLKO jeśli to szablon BEAR i istnieje ostatni rajd
    skills_changed = []
    if template_name == 'profil-bear.html' and latest_raid:
        skills_changed = latest_raid.get('skills_changed', [])

    # TODO: Dodaj logikę dla Achievements, jeśli będziesz miał dane
    achievements = []

    return render_template(template_name,
                           nickname=nickname,
                           player_info=player_info, # Przekazujemy całe podsumowanie gracza
                           player_stats=player_stats, # Przekazujemy przygotowane statystyki
                           latest_raid=latest_raid, # Ostatni rajd tego gracza
                           player_raids=player_raids, # Pełna lista rajdów tego gracza (dla tabeli i modala)
                           skills=skills_changed, # Lista zmienionych umiejętności (tylko dla BEAR)
                           achievements=achievements, # Pusta lista achievements
                           errors=errors) # Globalne błędy


# Uruchomienie aplikacji
if __name__ == '__main__':
    load_translations()
    # Możesz ustawić host='0.0.0.0', aby serwer był dostępny w sieci lokalnej
    app.run(debug=True, host='127.0.0.1', port=5000)