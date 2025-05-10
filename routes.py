# routes.py
from flask import Blueprint, jsonify, request, render_template, abort, current_app 
import os
import datetime
from datetime import timezone

from data_handler import (
    get_dh_cached_data, 
    prepare_modal_data,
    ACHIEVEMENTS_DATA_DICT, 
    get_dh_item_name,
    load_dh_json_file
)
import config

bp = Blueprint('main_routes', __name__)

@bp.route('/')
def index_route():
    cache = get_dh_cached_data()
    processed_recent_raids = []
    for summary_row in cache['all_raids_summary'][:20]:
        player_s = cache['players_summary'].get(summary_row.get('player_nickname'), {})
        display_raid = dict(summary_row) 
        display_raid['raid_count_for_player'] = player_s.get('raid_count', 'N/A')
        display_raid['timestamp_formatted_local'] = summary_row.get('timestamp_formatted', 'N/A')
        processed_recent_raids.append(display_raid)
    latest_raid_display = processed_recent_raids[0] if processed_recent_raids else None
    return render_template('index.html', 
                           latest_raid=latest_raid_display, 
                           recent_raids=processed_recent_raids, 
                           errors=cache.get('errors', []))

@bp.route('/players')
def players_list_route():
    cache = get_dh_cached_data()
    sorted_players = sorted(cache['players_summary'].values(), key=lambda p: (p.get('nickname','_')).lower())
    return render_template('gracze.html', 
                           players_list=sorted_players, 
                           errors=cache.get('errors', []))

@bp.route('/player/<nickname>')
def player_details_route(nickname):
    cache = get_dh_cached_data()
    player_info_summary = cache['players_summary'].get(nickname)
    if not player_info_summary: abort(404)

    player_stats_for_template = {
        'sessions': player_info_summary.get('raid_count', 0),
        'survived_sessions': player_info_summary.get('total_survived', 0),
        'deaths': player_info_summary.get('total_deaths', 0),
        'kills': player_info_summary.get('total_kills', 0),
        'survival_rate': player_info_summary.get('survival_rate', 'N/A'),
        'kd_ratio': player_info_summary.get('calculated_kd', 'N/A')
    }
    player_raids_for_template = [rs for rs in cache['all_raids_summary'] if rs.get('player_nickname') == nickname]
    latest_raid_for_template = player_raids_for_template[0] if player_raids_for_template else None
    
    skills = []; achievements_for_template = []
    if latest_raid_for_template and latest_raid_for_template.get('json_file_path_relative'):
        full_json_path = os.path.join(config.JSON_RAID_DATA_ROOT_DIR, latest_raid_for_template['json_file_path_relative'])
        raid_full_data = load_dh_json_file(full_json_path)
        if raid_full_data:
            profile_data = raid_full_data.get('request', {}).get('results', {}).get('profile', {})
            skills_raw = profile_data.get('Skills', {})
            if isinstance(skills_raw.get('Common'), list):
                for skill_data in skills_raw['Common']:
                    if isinstance(skill_data, dict):
                        prog = float(skill_data.get('Progress', 0.0) or 0.0); max_prog = 5100.0 
                        perc = min((prog / max_prog) * 100.0, 100.0) if max_prog > 0 else 0.0
                        skills.append({'SkillName': get_dh_item_name(skill_data.get('Id')), 'Progress': f"{prog:.2f}", 'PointsEarnedFormatted': f"{float(skill_data.get('PointsEarnedDuringSession', 0.0) or 0.0):.2f}", 'SkillType': 'Common', 'ProgressPercentage': perc, 'ProgressDisplay': f"{prog:.2f}"})
            if isinstance(skills_raw.get('Mastering'), list):
                 for skill_data in skills_raw['Mastering']:
                    if isinstance(skill_data, dict):
                        prog_mastering = float(skill_data.get('Progress', 0.0) or 0.0); max_prog_mastering = 100.0 
                        perc_mastering = min((prog_mastering / max_prog_mastering) * 100.0, 100.0) if max_prog_mastering > 0 else 0.0
                        skills.append({'SkillName': get_dh_item_name(skill_data.get('Id')),'Progress': f"{prog_mastering:.2f}",'PointsEarnedFormatted': 'N/A','SkillType': 'Mastering','ProgressPercentage': perc_mastering,'ProgressDisplay': f"{prog_mastering:.2f}"})
            player_achievements_from_profile = profile_data.get('Achievements', {})
            if isinstance(player_achievements_from_profile, dict):
                for ach_id_player_has, timestamp_val in player_achievements_from_profile.items():
                    ach_definition = ACHIEVEMENTS_DATA_DICT.get(ach_id_player_has)
                    image_filename_to_use = f"{ach_id_player_has}.png"; id_for_html = ach_id_player_has 
                    if ach_definition and isinstance(ach_definition.get('imageUrl'), str) and ach_definition['imageUrl']:
                        potential_filename = os.path.basename(ach_definition['imageUrl'])
                        if potential_filename: image_filename_to_use = potential_filename; id_for_html = image_filename_to_use.rsplit('.', 1)[0] if '.' in image_filename_to_use else image_filename_to_use
                    translated_name = get_dh_item_name(ach_id_player_has)
                    if translated_name == ach_id_player_has: pass
                    ach_timestamp_str = 'N/A'
                    if isinstance(timestamp_val, (int, float)) and timestamp_val > 0:
                        try: ach_timestamp_str = datetime.datetime.fromtimestamp(timestamp_val, tz=timezone.utc).strftime('%d.%m.%Y %H:%M')
                        except: pass
                    achievements_for_template.append({'id': id_for_html, 'name': translated_name, 'timestamp': ach_timestamp_str})
    return render_template('profil.html', nickname=nickname, player_info=player_info_summary, player_stats=player_stats_for_template, latest_raid=latest_raid_for_template, player_raids=player_raids_for_template, skills=skills, achievements=achievements_for_template, errors=cache.get('errors', []))

@bp.route('/api/raid_details_json')
def api_raid_details_json_route():
    filepath_relative = request.args.get('path')
    if not filepath_relative: return jsonify(error="Brak parametru 'path'", data=None), 400
    safe_base = os.path.abspath(config.JSON_RAID_DATA_ROOT_DIR); filepath_relative_cleaned = filepath_relative.lstrip('/\\'); full_filepath = os.path.abspath(os.path.join(config.JSON_RAID_DATA_ROOT_DIR, filepath_relative_cleaned))
    if not full_filepath.startswith(safe_base) or ".." in filepath_relative_cleaned: return jsonify(error="Nieprawidłowa ścieżka pliku.", data=None), 400
    if not os.path.exists(full_filepath) or not os.path.isfile(full_filepath): return jsonify(error=f"Plik JSON nie znaleziony: {filepath_relative_cleaned}", data=None), 404
    processed_data_dict, error_msg = prepare_modal_data(filepath_relative_cleaned)
    if error_msg: return jsonify(error=error_msg, data=None), 500
    if not processed_data_dict: return jsonify(error="Nie udało się przetworzyć danych rajdu dla modala.", data=None), 500
    return jsonify(error=None, data=processed_data_dict)