# app.py
from flask import Flask
import locale
import os
import datetime
from datetime import timezone

import config
from data_handler import ensure_dh_dir_exists, load_dh_translations, get_dh_item_name, format_dh_exp, format_dh_decimal_one

def create_app():
    app_instance = Flask(__name__,
                         template_folder=config.TEMPLATES_FOLDER_NAME,
                         static_folder=config.STATIC_FOLDER_NAME)
    app_instance.json.ensure_ascii = False
    app_instance.config['DEBUG'] = config.DEBUG_MODE

    try:
        locale.setlocale(locale.LC_ALL, 'pl_PL.UTF-8')
    except locale.Error:
        try: locale.setlocale(locale.LC_ALL, 'Polish_Poland.1250')
        except locale.Error: print("OSTRZEŻENIE (app.py): Nie można ustawić polskiego locale.")

    ensure_dh_dir_exists(config.JSON_RAID_DATA_ROOT_DIR)
    load_dh_translations() # Ładuje tłumaczenia dla data_handler

    # Context processor dla funkcji dostępnych w szablonach
    with app_instance.app_context():
        @app_instance.context_processor
        def inject_utilities_for_templates(): # Zmieniona nazwa dla jasności
            from flask import url_for # Importuj wewnątrz, aby uniknąć problemów z kontekstem
            def get_map_image_url_for_template(location_name_from_data):
                map_key = location_name_from_data
                if map_key not in config.MAP_IMAGES:
                    map_key = get_dh_item_name(location_name_from_data)
                filename = config.MAP_IMAGES.get(map_key, config.MAP_IMAGES["unknown"])
                try: # Dodano try-except dla url_for
                    return url_for('static', filename=f"images/maps/{filename}")
                except RuntimeError: # Poza kontekstem aplikacji (np. podczas testów)
                     return f"/{config.STATIC_FOLDER_NAME}/images/maps/{filename}"


            return dict(
                get_item_name=get_dh_item_name, # Użyj tłumaczeń z data_handler
                format_exp=format_dh_exp,
                get_map_image_url=get_map_image_url_for_template,
                format_decimal_one=format_dh_decimal_one,
                now=datetime.datetime.now(timezone.utc)
            )

        # Import i rejestracja Blueprintów
        from routes import bp as main_routes_bp
        from mod_api_handler import mod_bp as mod_api_bp

        app_instance.register_blueprint(main_routes_bp)
        app_instance.register_blueprint(mod_api_bp) # Rejestrujemy nowy blueprint dla API moda

    return app_instance

if __name__ == '__main__':
    app = create_app()
    print(f"INFO (app.py): Dane JSON będą zapisywane w: {config.JSON_RAID_DATA_ROOT_DIR}")
    print(f"INFO (app.py): Serwer nasłuchuje na http://{config.HOST}:{config.PORT}")
    print(f"INFO (app.py): Tryb debugowania: {'Włączony' if app.config['DEBUG'] else 'Wyłączony'}")
    app.run(host=config.HOST, port=config.PORT, use_reloader=config.USE_RELOADER)