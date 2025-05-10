# mod_api_handler.py
from flask import Blueprint, jsonify, request
import datetime
from datetime import timezone
from data_handler import save_dh_raid_json_data, invalidate_dh_cache 

# Utwórz Blueprint dla API moda
mod_bp = Blueprint('mod_api', __name__, url_prefix='/api/mod')

@mod_bp.route('/connect', methods=['POST'])
def mod_connect_api(): 
    data = request.get_json()
    if not data: 
        print("BŁĄD (mod_api): /connect - Brak danych JSON.")
        return jsonify({"status": "error", "message": "Brak danych JSON"}), 400
    
    mod_name = data.get("mod", "unknown_mod").replace(" ", "_")
    save_dh_raid_json_data(data, "SYSTEM", mod_name, "connect_event") 
    return jsonify({"status": "success", "message": "Zdarzenie połączenia moda zarejestrowane."})

@mod_bp.route('/raid/start', methods=['POST'])
def raid_start_api():
    data = request.get_json()
    if not data: 
        print("BŁĄD (mod_api): /raid/start - Brak danych JSON.")
        return jsonify({"status": "error", "message": "Brak danych JSON"}), 400
    
    session_id = data.get('sessionId', f"unknownS_{datetime.datetime.now().strftime('%f')}")
    player_nick = "UnknownPlayer"
    try: 
        player_nick = data.get('request', {}).get('playerProfile', {}).get('Info', {}).get('Nickname', session_id)
    except: pass 
    
    save_dh_raid_json_data(data, player_nick, session_id, "start")
    return jsonify({"status": "success", "message": "Zdarzenie rozpoczęcia rajdu zarejestrowane."})

@mod_bp.route('/raid/end', methods=['POST']) 
def raid_end_api():
    data = request.get_json()
    if not data: 
        print("BŁĄD (mod_api): /raid/end - Brak danych JSON.")
        return jsonify({"status": "error", "message": "Brak danych JSON"}), 400
    
    session_id = data.get('sessionId')
    player_nick = "UnknownPlayer"
    try:
        profile_node = data.get('request', {}).get('results', {}).get('profile', {})
        profile_info = profile_node.get('Info', {})
        session_id = session_id or profile_node.get('_id') or f"no_sid_end_{datetime.datetime.now().strftime('%f')}"
        player_nick = profile_info.get('Nickname', session_id)
    except:
        session_id = session_id or f"no_sid_end_fb_{datetime.datetime.now().strftime('%f')}"
        if player_nick == "UnknownPlayer" and session_id: player_nick = session_id
            
    save_dh_raid_json_data(data, player_nick, session_id, "end")
    invalidate_dh_cache() # Unieważnij cache, bo przyszły nowe dane
    return jsonify({"status": "success", "message": "Zdarzenie zakończenia rajdu zarejestrowane."})