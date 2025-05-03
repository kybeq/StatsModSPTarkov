import os
import json
import math
from flask import Flask, render_template, abort
from collections import defaultdict # Do zliczania przedmiotów

app = Flask(__name__)

# --- Konfiguracja Ścieżek ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEBUG_LOGS_FOLDER = os.path.join(BASE_DIR, 'debug_logs')
TRANSLATE_FOLDER = os.path.join(BASE_DIR, 'translate')
RAID_JSON_FILENAME = 'onEndLocalRaidRequest_request_6815e32400054ef804243ea0_1746269594425.json'
TRANSLATION_FILENAME = 'pl.json'

RAID_JSON_FILE_PATH = os.path.join(DEBUG_LOGS_FOLDER, RAID_JSON_FILENAME)
TRANSLATION_FILE_PATH = os.path.join(TRANSLATE_FOLDER, TRANSLATION_FILENAME)

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
    """Pobiera nazwę przedmiotu (preferując ShortName) lub tłumaczenie ID."""
    if not translations or not item_id:
        return str(item_id) # Zwróć ID jako string, jeśli nie ma tłumaczeń lub ID
    short_name_key = f"{item_id} ShortName"
    name_key = f"{item_id} Name"
    plain_id_key = str(item_id) # Klucz dla prostych tłumaczeń ID (np. części ciała, role)
    # Kolejność: ShortName -> Name -> ID
    return translations.get(short_name_key, translations.get(name_key, translations.get(plain_id_key, str(item_id))))

def format_time(seconds):
    """Formatuje czas w sekundach na HH:MM:SS lub MM:SS."""
    if seconds is None: return "N/A"
    try:
        seconds = int(seconds)
        if seconds < 0: seconds = 0 # Obsługa potencjalnych ujemnych wartości
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        remaining_seconds = seconds % 60
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{remaining_seconds:02d}"
        else:
            return f"{minutes:02d}:{remaining_seconds:02d}"
    except (ValueError, TypeError): return "N/A"

def format_distance(meters):
     """Formatuje dystans."""
     if meters is None: return "N/A"
     try:
         meters = float(meters)
         if meters >= 1000:
             return f"{meters / 1000:.2f} km"
         else:
             return f"{meters:.1f} m"
     except (ValueError, TypeError): return "N/A"

def process_item_list(items_dict_or_list, count_key='count', id_key='_tpl'):
    """Przetwarza listę lub słownik przedmiotów, zlicza je i tłumaczy nazwy."""
    processed_items = []
    item_counts = defaultdict(int)

    items_to_process = []
    if isinstance(items_dict_or_list, dict):
         # Obsługa formatu, gdzie kluczem jest unikalny ID przedmiotu, a wartością obiekt
         # Przykład: transferItems
        items_to_process = items_dict_or_list.values()
    elif isinstance(items_dict_or_list, list):
        # Obsługa formatu, gdzie jest to lista obiektów
        # Przykład: FoundInRaidItems, lostInsuredItems
        items_to_process = items_dict_or_list

    for item in items_to_process:
        # Dostosuj klucze w zależności od struktury JSON
        # W transferItems często jest '_tpl', a w innych 'ItemId'
        tpl_id = item.get(id_key) or item.get('ItemId')
        if tpl_id:
            # Zliczaj stacki lub indywidualne przedmioty
            count = item.get('upd', {}).get('StackObjectsCount', 1) if 'upd' in item else item.get(count_key, 1)
            item_counts[tpl_id] += count

    # Stwórz listę przetworzonych przedmiotów
    for tpl_id, count in item_counts.items():
        processed_items.append({
            'id': tpl_id,
            'name': get_item_name(tpl_id),
            'count': count
        })

    # Sortuj po nazwie dla lepszej czytelności
    processed_items.sort(key=lambda x: x['name'])
    return processed_items

def extract_session_stats(session_counters):
    """Wyciąga i formatuje kluczowe statystyki sesji."""
    stats = {
        'damage_dealt': 0, 'body_parts_destroyed': 0, 'pedometer': 0,
        'exp_kill': 0, 'exp_looting': 0, 'exp_exit_status': 0, 'deaths': 0,
        'blood_loss': 0, 'damage_received_total': 0, 'damage_received_details': {}
    }
    if session_counters and 'Items' in session_counters:
        for item in session_counters['Items']:
            key = item.get('Key'); value = item.get('Value', 0)
            if key:
                try:
                    key_str = "_".join(map(str, key))
                    if "CombatDamage" in key_str: stats['damage_dealt'] += value
                    elif key[0] == "BodyPartDamage" and len(key) > 1:
                        part_name = get_item_name(key[1]) # Przetłumacz nazwę części ciała
                        stats['damage_received_total'] += value
                        stats['damage_received_details'][part_name] = stats['damage_received_details'].get(part_name, 0) + value
                    elif "BodyPartsDestroyed" in key_str: stats['body_parts_destroyed'] = value
                    elif "Pedometer" in key_str: stats['pedometer'] = value
                    elif key == ["Exp", "ExpKill"]: stats['exp_kill'] = value
                    elif key == ["Exp", "ExpLooting"]: stats['exp_looting'] = value
                    elif key == ["Exp", "ExpExitStatus"]: stats['exp_exit_status'] = value
                    elif "Deaths" in key_str: stats['deaths'] = value
                    elif "BloodLoss" in key_str: stats['blood_loss'] = value
                except (TypeError, IndexError): pass

    stats['damage_dealt'] = round(stats.get('damage_dealt', 0))
    stats['blood_loss'] = round(stats.get('blood_loss', 0))
    stats['damage_received_total'] = round(stats.get('damage_received_total', 0))
    for part, dmg in stats['damage_received_details'].items():
        stats['damage_received_details'][part] = round(dmg, 1)
    stats['distance_formatted'] = format_distance(stats['pedometer'])
    return stats

def extract_overall_stats(overall_counters):
    """Wyciąga kluczowe statystyki ogólne i oblicza pochodne."""
    stats = {'kills': 0, 'deaths': 0, 'sessions': 0, 'survived_sessions': 0}
    if overall_counters and 'Items' in overall_counters:
        for item in overall_counters['Items']:
            key = item.get('Key'); value = item.get('Value', 0)
            if key:
                try:
                    if key == ['Kills']: stats['kills'] = value
                    elif key == ['Deaths']: stats['deaths'] = value
                    elif key == ['Sessions', 'Pmc']: stats['sessions'] = value # Lub ['Sessions'] jeśli nie ma rozbicia
                    elif key == ['ExitStatus', 'Survived', 'Pmc']: stats['survived_sessions'] = value # Lub ['ExitStatus', 'Survived']
                except TypeError: pass # Ignoruj błędne klucze

    # Oblicz K/D i SR
    stats['kd_ratio'] = f"{stats['kills'] / stats['deaths']:.2f}" if stats['deaths'] > 0 else 'N/A'
    stats['survival_rate'] = f"{(stats['survived_sessions'] / stats['sessions'] * 100):.1f}%" if stats['sessions'] > 0 else 'N/A'
    return stats


def extract_changed_skills(skills_common):
    """Wyciąga umiejętności, które zyskały postęp w sesji."""
    changed = []
    if skills_common:
        for skill in skills_common:
            points_earned = skill.get('PointsEarnedDuringSession', 0)
            if points_earned > 0:
                skill_copy = skill.copy()
                try:
                    skill_copy['PointsEarnedFormatted'] = f"{points_earned:.2f}"
                    skill_copy['ProgressFormatted'] = f"{skill_copy.get('Progress', 0):.2f}"
                    skill_copy['SkillName'] = get_item_name(skill_copy.get('Id'))
                    changed.append(skill_copy)
                except (ValueError, TypeError):
                     print(f"OSTRZEŻENIE: Problem z formatowaniem danych umiejętności: {skill}")
        changed.sort(key=lambda x: x.get('PointsEarnedDuringSession', 0), reverse=True) # Sortuj po zdobytym postępie
    return changed

# --- Główna Trasa Aplikacji ---
@app.route('/')
def display_raid_data():
    data = None
    error_message = None
    processed_data = {}

    try:
        if not os.path.exists(RAID_JSON_FILE_PATH):
            raise FileNotFoundError(f"Plik raportu nie został znaleziony: {RAID_JSON_FILE_PATH}")

        with open(RAID_JSON_FILE_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if data and 'results' in data:
            results = data.get('results', {})
            profile = results.get('profile', {})
            info = profile.get('Info', {})
            stats_eft = profile.get('Stats', {}).get('Eft', {})
            health_info = profile.get('Health', {}) # Pobierz cały obiekt Health

            # --- Podstawowe dane rajdu i gracza ---
            processed_data['server_id'] = data.get('serverId')
            processed_data['raid_result'] = results.get('result')
            processed_data['exit_name'] = results.get('exitName') if results.get('result') != 'Killed' else None
            processed_data['location'] = get_item_name(info.get('EntryPoint')) # Tłumaczenie lokacji
            processed_data['nickname'] = info.get('Nickname')
            processed_data['level'] = info.get('Level')
            processed_data['side'] = info.get('Side')

            # --- Czas i EXP ---
            total_in_game_time = stats_eft.get('TotalInGameTime')
            raid_duration_seconds = total_in_game_time if total_in_game_time is not None else results.get('playTime')
            processed_data['play_time_formatted'] = format_time(raid_duration_seconds)

            processed_data['total_session_exp_from_json'] = stats_eft.get('TotalSessionExperience', 0)
            session_counters = stats_eft.get('SessionCounters')
            processed_data['session_stats'] = extract_session_stats(session_counters)
            exp_sum_from_counters = sum(v for k, v in processed_data['session_stats'].items() if k.startswith('exp_'))
            processed_data['total_session_exp_calculated'] = round(exp_sum_from_counters)

            # --- Informacje o zabójcy ---
            if processed_data['raid_result'] == 'Killed':
                aggressor = stats_eft.get('Aggressor'); death_cause = stats_eft.get('DeathCause')
                damage_history = stats_eft.get('DamageHistory', {})
                if aggressor:
                    processed_data['killer_name'] = aggressor.get('Name')
                    processed_data['killer_side'] = aggressor.get('Side')
                if death_cause:
                     processed_data['killer_weapon_name'] = get_item_name(death_cause.get('WeaponId'))
                processed_data['killed_by_part'] = get_item_name(damage_history.get('LethalDamagePart')) # Tłumaczenie części ciała
                lethal_damage_info = damage_history.get('LethalDamage', {})
                if lethal_damage_info:
                    processed_data['lethal_damage_amount'] = round(lethal_damage_info.get('Amount', 0), 1)
                    processed_data['lethal_damage_type'] = get_item_name(lethal_damage_info.get('Type')) # Tłumaczenie typu obrażeń

            # --- Końcowe zdrowie i witalność ---
            body_parts = health_info.get('BodyParts')
            if body_parts:
                processed_data['final_health'] = {}
                for part, details in body_parts.items():
                     health_details = details.get('Health', {})
                     processed_data['final_health'][get_item_name(part)] = { # Tłumaczenie części ciała
                         'current': round(health_details.get('Current', 0), 1),
                         'maximum': health_details.get('Maximum', 1)
                     }
            else: processed_data['final_health'] = {}
            # Dodaj Energię, Nawodnienie, Temperaturę
            processed_data['final_vitals'] = {
                'Energy': round(health_info.get('Energy', {}).get('Current', 0)),
                'Hydration': round(health_info.get('Hydration', {}).get('Current', 0)),
                'Temperature': round(health_info.get('Temperature', {}).get('Current', 0)),
                'MaxEnergy': health_info.get('Energy', {}).get('Maximum', 110), # Domyślne max
                'MaxHydration': health_info.get('Hydration', {}).get('Maximum', 100)
            }

            # --- Zmienione umiejętności ---
            skills_common = profile.get('Skills', {}).get('Common')
            processed_data['skills_changed'] = extract_changed_skills(skills_common)

            # --- Ofiary gracza ---
            victims_list = stats_eft.get('Victims', [])
            processed_victims = []
            for victim in victims_list:
                 victim_copy = victim.copy()
                 victim_copy['WeaponName'] = get_item_name(victim_copy.get('Weapon'))
                 victim_copy['DistanceFormatted'] = format_distance(victim_copy.get('Distance'))
                 victim_copy['RoleTranslated'] = get_item_name(victim_copy.get('Role'))
                 victim_copy['SideTranslated'] = get_item_name(victim_copy.get('Side'))
                 victim_copy['BodyPartTranslated'] = get_item_name(victim_copy.get('BodyPart')) # Tłumaczenie części ciała
                 processed_victims.append(victim_copy)
            processed_data['victims'] = processed_victims

            # --- Przedmioty ---
            # Sprawdź różne potencjalne klucze dla ID szablonu przedmiotu
            processed_data['transfer_items'] = process_item_list(data.get('transferItems', {}), id_key='_tpl')
            processed_data['found_in_raid_items'] = process_item_list(stats_eft.get('FoundInRaidItems', []), id_key='ItemId') # Sprawdź klucz ID w JSON
            processed_data['lost_insured_items'] = process_item_list(data.get('lostInsuredItems', []), id_key='ItemId') # Sprawdź klucz ID w JSON
            processed_data['carried_quest_items'] = process_item_list(stats_eft.get('CarriedQuestItems', []), id_key='_tpl') # Sprawdź klucz ID w JSON

            # --- Statystyki Ogólne ---
            overall_counters = profile.get('Stats', {}).get('Eft', {}).get('OverallCounters')
            processed_data['overall_stats'] = extract_overall_stats(overall_counters)


    except FileNotFoundError as e:
        error_message = str(e); print(f"BŁĄD: {error_message}")
    except json.JSONDecodeError as e:
        error_message = f"Błąd parsowania pliku raportu ({RAID_JSON_FILENAME}): {e}"; print(f"BŁĄD: {error_message}")
    except Exception as e:
        error_message = f"Nieoczekiwany błąd przetwarzania danych raportu: {e}"; print(f"BŁĄD: {error_message}")
        import traceback; traceback.print_exc()

    return render_template('index.html', data=processed_data, error=error_message, filename=RAID_JSON_FILENAME)

if __name__ == '__main__':
    app.run(debug=True)