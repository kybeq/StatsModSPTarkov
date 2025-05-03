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
# Usunięto konkretny plik JSON - będziemy skanować folder
TRANSLATION_FILENAME = 'pl.json'

# Wzorzec nazwy plików logów rajdów (dostosuj w razie potrzeby)
# Zakładamy, że nazwa zawiera timestamp w milisekundach na końcu
RAID_FILE_PATTERN = 'onEndLocalRaidRequest_request_*.json'

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

# --- Funkcje Pomocnicze (bez zmian, skopiowane z oryginału) ---
def get_item_name(item_id):
    if not translations or not item_id: return str(item_id)
    short_name_key = f"{item_id} ShortName"; name_key = f"{item_id} Name"; plain_id_key = str(item_id)
    return translations.get(short_name_key, translations.get(name_key, translations.get(plain_id_key, str(item_id))))

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

def process_item_list(items_dict_or_list, count_key='count', id_key='_tpl'):
    processed_items = []; item_counts = defaultdict(int)
    items_to_process = []
    if isinstance(items_dict_or_list, dict): items_to_process = items_dict_or_list.values()
    elif isinstance(items_dict_or_list, list): items_to_process = items_dict_or_list
    for item in items_to_process:
        tpl_id = item.get(id_key) or item.get('ItemId')
        if tpl_id:
            count = item.get('upd', {}).get('StackObjectsCount', 1) if 'upd' in item else item.get(count_key, 1)
            item_counts[tpl_id] += count
    for tpl_id, count in item_counts.items():
        processed_items.append({'id': tpl_id, 'name': get_item_name(tpl_id), 'count': count})
    processed_items.sort(key=lambda x: x['name'])
    return processed_items

def extract_session_stats(session_counters):
    stats = {'damage_dealt': 0, 'body_parts_destroyed': 0, 'pedometer': 0, 'exp_kill': 0, 'exp_looting': 0, 'exp_exit_status': 0, 'deaths': 0, 'blood_loss': 0, 'damage_received_total': 0, 'damage_received_details': {}}
    if session_counters and 'Items' in session_counters:
        for item in session_counters['Items']:
            key = item.get('Key'); value = item.get('Value', 0)
            if key:
                try:
                    key_str = "_".join(map(str, key))
                    if "CombatDamage" in key_str: stats['damage_dealt'] += value
                    elif key[0] == "BodyPartDamage" and len(key) > 1:
                        part_name = get_item_name(key[1])
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
    for part, dmg in stats['damage_received_details'].items(): stats['damage_received_details'][part] = round(dmg, 1)
    stats['distance_formatted'] = format_distance(stats['pedometer'])
    return stats

def extract_overall_stats(overall_counters):
    stats = {'kills': 0, 'deaths': 0, 'sessions': 0, 'survived_sessions': 0}
    if overall_counters and 'Items' in overall_counters:
        for item in overall_counters['Items']:
            key = item.get('Key'); value = item.get('Value', 0)
            if key:
                try:
                    if key == ['Kills']: stats['kills'] = value
                    elif key == ['Deaths']: stats['deaths'] = value
                    elif key == ['Sessions', 'Pmc']: stats['sessions'] = value
                    elif key == ['ExitStatus', 'Survived', 'Pmc']: stats['survived_sessions'] = value
                except TypeError: pass
    stats['kd_ratio'] = f"{stats['kills'] / stats['deaths']:.2f}" if stats['deaths'] > 0 else 'N/A'
    stats['survival_rate'] = f"{(stats['survived_sessions'] / stats['sessions'] * 100):.1f}%" if stats['sessions'] > 0 else 'N/A'
    return stats

def extract_changed_skills(skills_common):
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
                except (ValueError, TypeError): print(f"OSTRZEŻENIE: Problem z formatowaniem danych umiejętności: {skill}")
        changed.sort(key=lambda x: x.get('PointsEarnedDuringSession', 0), reverse=True)
    return changed

# --- Funkcja do ekstrakcji timestampu z nazwy pliku ---
def get_timestamp_from_filename(filename):
    """Próbuje wyciągnąć timestamp (w milisekundach) z końca nazwy pliku."""
    try:
        # Przykład: onEndLocalRaidRequest_request_..._1746269594425.json
        base_name = os.path.splitext(filename)[0] # Usuń .json
        timestamp_ms_str = base_name.split('_')[-1]
        timestamp_ms = int(timestamp_ms_str)
        # Przekonwertuj milisekundy na sekundy dla obiektu datetime
        return datetime.datetime.fromtimestamp(timestamp_ms / 1000)
    except (IndexError, ValueError, TypeError):
        # Jeśli format nazwy jest inny lub timestamp jest nieprawidłowy
        print(f"OSTRZEŻENIE: Nie można wyekstrahować timestampu z nazwy pliku: {filename}")
        # Zwróć bardzo starą datę, aby takie pliki były na początku
        return datetime.datetime.min

# --- Funkcja przetwarzająca JEDEN plik raportu ---
def process_single_raid_file(filepath):
    """Wczytuje i przetwarza dane z jednego pliku JSON raportu rajdu."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"BŁĄD: Plik nie znaleziony: {filepath}")
        return None, f"Plik nie znaleziony: {os.path.basename(filepath)}"
    except json.JSONDecodeError as e:
        print(f"BŁĄD: Błąd parsowania JSON w pliku {os.path.basename(filepath)}: {e}")
        return None, f"Błąd parsowania JSON w pliku {os.path.basename(filepath)}: {e}"
    except Exception as e:
        print(f"BŁĄD: Nieoczekiwany błąd podczas wczytywania pliku {os.path.basename(filepath)}: {e}")
        return None, f"Nieoczekiwany błąd wczytywania pliku {os.path.basename(filepath)}: {e}"

    processed_data = {}
    error_message = None

    try:
        if not data or 'results' not in data:
            raise ValueError("Brak klucza 'results' w danych JSON.")

        results = data.get('results', {})
        profile = results.get('profile', {})
        info = profile.get('Info', {})
        stats_eft = profile.get('Stats', {}).get('Eft', {})
        health_info = profile.get('Health', {})

        # --- Podstawowe dane rajdu i gracza ---
        processed_data['filename'] = os.path.basename(filepath) # Zapisz nazwę pliku jako ID rajdu
        processed_data['timestamp'] = get_timestamp_from_filename(processed_data['filename'])
        processed_data['server_id'] = data.get('serverId')
        processed_data['raid_result'] = results.get('result')
        processed_data['exit_name'] = results.get('exitName') if results.get('result') != 'Killed' else None
        processed_data['location_id'] = info.get('EntryPoint') # Przechowaj ID dla filtrowania
        processed_data['location'] = get_item_name(processed_data['location_id'])
        processed_data['nickname'] = info.get('Nickname')
        processed_data['level'] = info.get('Level')
        processed_data['side'] = info.get('Side')

        # --- Czas i EXP ---
        total_in_game_time = stats_eft.get('TotalInGameTime')
        raid_duration_seconds = total_in_game_time if total_in_game_time is not None else results.get('playTime')
        processed_data['play_time_seconds'] = raid_duration_seconds # Przechowaj surową wartość
        processed_data['play_time_formatted'] = format_time(raid_duration_seconds)

        processed_data['total_session_exp_from_json'] = stats_eft.get('TotalSessionExperience', 0)
        session_counters = stats_eft.get('SessionCounters')
        processed_data['session_stats'] = extract_session_stats(session_counters)
        exp_sum_from_counters = sum(v for k, v in processed_data['session_stats'].items() if k.startswith('exp_'))
        processed_data['total_session_exp_calculated'] = round(exp_sum_from_counters)

        # --- Informacje o zabójcy (jeśli dotyczy) ---
        processed_data['killer_info'] = None
        if processed_data['raid_result'] == 'Killed':
            aggressor = stats_eft.get('Aggressor'); death_cause = stats_eft.get('DeathCause')
            damage_history = stats_eft.get('DamageHistory', {})
            killer_data = {}
            if aggressor:
                killer_data['name'] = aggressor.get('Name')
                killer_data['side'] = aggressor.get('Side')
            if death_cause:
                 killer_data['weapon_name'] = get_item_name(death_cause.get('WeaponId'))
            killer_data['killed_by_part'] = get_item_name(damage_history.get('LethalDamagePart'))
            lethal_damage_info = damage_history.get('LethalDamage', {})
            if lethal_damage_info:
                killer_data['lethal_damage_amount'] = round(lethal_damage_info.get('Amount', 0), 1)
                killer_data['lethal_damage_type'] = get_item_name(lethal_damage_info.get('Type'))
            processed_data['killer_info'] = killer_data

        # --- Końcowe zdrowie i witalność ---
        body_parts = health_info.get('BodyParts')
        processed_data['final_health'] = {}
        if body_parts:
            for part, details in body_parts.items():
                 health_details = details.get('Health', {})
                 processed_data['final_health'][get_item_name(part)] = {
                     'current': round(health_details.get('Current', 0), 1),
                     'maximum': health_details.get('Maximum', 1)
                 }
        processed_data['final_vitals'] = {
            'Energy': round(health_info.get('Energy', {}).get('Current', 0)),
            'Hydration': round(health_info.get('Hydration', {}).get('Current', 0)),
            'Temperature': round(health_info.get('Temperature', {}).get('Current', 0)),
            'MaxEnergy': health_info.get('Energy', {}).get('Maximum', 110),
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
             victim_copy['BodyPartTranslated'] = get_item_name(victim_copy.get('BodyPart'))
             processed_victims.append(victim_copy)
        processed_data['victims'] = processed_victims
        processed_data['kills_count'] = len(processed_victims) # Liczba zabójstw w rajdzie

        # --- Przedmioty ---
        processed_data['transfer_items'] = process_item_list(data.get('transferItems', {}), id_key='_tpl')
        processed_data['found_in_raid_items'] = process_item_list(stats_eft.get('FoundInRaidItems', []), id_key='ItemId')
        processed_data['lost_insured_items'] = process_item_list(data.get('lostInsuredItems', []), id_key='ItemId')
        processed_data['carried_quest_items'] = process_item_list(stats_eft.get('CarriedQuestItems', []), id_key='_tpl') # Sprawdź klucz ID

        # --- Statystyki Ogólne (z profilu po rajdzie) ---
        overall_counters = profile.get('Stats', {}).get('Eft', {}).get('OverallCounters')
        processed_data['overall_stats'] = extract_overall_stats(overall_counters)

        # --- Liczba graczy w rajdzie (jeśli dostępna, często jej nie ma w tym pliku) ---
        # To jest trudne, bo `onEndLocalRaidRequest` dotyczy tylko *jednego* gracza.
        # Możemy spróbować zgadnąć na podstawie `server_id` i `timestamp`,
        # ale to zawodne. Na razie ustawmy na 1.
        processed_data['player_count_in_raid'] = 1 # Placeholder

    except ValueError as e:
        error_message = f"Błąd przetwarzania danych w pliku {os.path.basename(filepath)}: {e}"
        print(f"BŁĄD: {error_message}")
    except Exception as e:
        error_message = f"Nieoczekiwany błąd przetwarzania danych raportu {os.path.basename(filepath)}: {e}"
        print(f"BŁĄD: {error_message}")
        import traceback; traceback.print_exc()

    # Zwracamy przetworzone dane LUB None jeśli wystąpił błąd krytyczny
    return processed_data if not error_message else None, error_message


# --- Funkcja do ładowania i agregowania danych ze WSZYSTKICH plików ---
# UWAGA: To może być wolne przy dużej liczbie plików. Rozważ caching/bazę danych w przyszłości.
def load_all_raid_data():
    """Skanuje folder logów, przetwarza wszystkie pliki rajdów i agreguje dane."""
    all_processed_raids = []
    players_summary = {} # Klucz: nickname, Wartość: {'latest_level': X, 'latest_side': Y, 'raid_ids': [...]}
    errors = []

    raid_files = glob.glob(os.path.join(DEBUG_LOGS_FOLDER, RAID_FILE_PATTERN))

    # Sortuj pliki po timestampie (najnowsze na końcu)
    raid_files.sort(key=lambda f: get_timestamp_from_filename(os.path.basename(f)))

    for filepath in raid_files:
        processed_data, error = process_single_raid_file(filepath)
        if error:
            errors.append(error)
        if processed_data:
            all_processed_raids.append(processed_data)
            nickname = processed_data.get('nickname')
            if nickname:
                if nickname not in players_summary:
                    players_summary[nickname] = {'raid_ids': []}
                # Aktualizuj ostatnie znane dane gracza
                players_summary[nickname]['latest_level'] = processed_data.get('level')
                players_summary[nickname]['latest_side'] = processed_data.get('side')
                players_summary[nickname]['raid_ids'].append(processed_data['filename'])

    # Dodaj liczbę rajdów do podsumowania graczy
    for nick, data in players_summary.items():
        data['raid_count'] = len(data['raid_ids'])

    return all_processed_raids, players_summary, errors

# --- Funkcja do udostępnienia 'now' w szablonach ---
@app.context_processor
def inject_now():
    return {'now': datetime.datetime.utcnow} # Użyj UTC dla spójności lub now() dla lokalnego czasu serwera

# --- Trasy Aplikacji ---

@app.route('/')
def index():
    all_raids, players, errors = load_all_raid_data()
    latest_raid = all_raids[-1] if all_raids else None
    sorted_players = sorted(players.items(), key=lambda item: item[0].lower())
    return render_template('index.html',
                           latest_raid=latest_raid,
                           players=sorted_players,
                           errors=errors)

@app.route('/player/<nickname>')
def player_details(nickname):
    all_raids, players, errors = load_all_raid_data()
    player_info = players.get(nickname)
    if not player_info:
        abort(404, description="Gracz nie znaleziony")

    player_raids = [raid for raid in all_raids if raid.get('nickname') == nickname]
    player_raids.sort(key=lambda r: r.get('timestamp', datetime.datetime.min), reverse=True)

    simplified_raids = []
    for raid in player_raids:
        simplified_raids.append({
            'filename': raid['filename'],
            'timestamp': raid['timestamp'],
            'location': raid['location'],
            'result': raid['raid_result'],
            'play_time_formatted': raid['play_time_formatted'],
            'kills': raid.get('kills_count', 0),
            'exp': raid.get('total_session_exp_calculated', 0)
        })

    return render_template('player_details.html',
                           nickname=nickname,
                           player_info=player_info,
                           raids=simplified_raids,
                           errors=errors)

@app.route('/raid/<path:filename>') # Używamy path, aby obsłużyć potencjalne znaki specjalne w nazwie pliku
def raid_details(filename):
    """Strona szczegółów konkretnego rajdu."""
    filepath = os.path.join(DEBUG_LOGS_FOLDER, filename)

    if not os.path.exists(filepath):
         # Dodatkowe sprawdzenie, czy plik pasuje do wzorca, aby uniknąć prób dostępu do innych plików
         if not glob.glob(os.path.join(DEBUG_LOGS_FOLDER, filename)):
              abort(404, description="Plik rajdu nie znaleziony lub nieprawidłowy.")

    processed_data, error = process_single_raid_file(filepath)

    expected_prefix = os.path.join(DEBUG_LOGS_FOLDER, '') # Normalizuj ścieżkę folderu
    if not os.path.exists(filepath) or not os.path.abspath(filepath).startswith(os.path.abspath(expected_prefix)):
         abort(404, description="Plik rajdu nie znaleziony lub ścieżka jest nieprawidłowa.")

    processed_data, error = process_single_raid_file(filepath)

    # Zwróć kod 404 jeśli plik nie istnieje lub nie udało się go sparsować poprawnie
    if not processed_data and not error: # Sytuacja, gdy plik jest pusty lub ma zły format
        error = "Nie można załadować danych z pliku. Może być uszkodzony lub w nieprawidłowym formacie."

    if not processed_data and error:
         # Można zwrócić 404 lub 500 w zależności od błędu
         # Jeśli błąd jest np. FileNotFoundError, 404 jest ok. Jeśli JSONDecodeError, może być 500.
         # Dla uproszczenia zostawmy 500 dla błędów przetwarzania.
         print(f"Błąd przetwarzania pliku {filename}: {error}") # Loguj błąd po stronie serwera
         # Użyjemy tego samego szablonu, ale z informacją o błędzie i kodem 500
         return render_template('raid_details.html', data=None, error=error, filename=filename), 500

    # Jeśli wszystko OK, renderuj normalnie
    return render_template('raid_details.html', data=processed_data, error=None, filename=filename)


# Uruchomienie aplikacji
if __name__ == '__main__':
    load_translations()
    app.run(debug=True)