import os
import sys
# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, send_from_directory
from flask_cors import CORS
from src.models.user import db
from src.routes.user import user_bp
from src.routes.email_search import email_search_bp
from src.routes.cache_management import cache_management_bp
from src.routes.rate_limit_management import rate_limit_management_bp
from src.routes.auth_management import auth_management_bp
from src.routes.monitoring import monitoring_bp
from src.routes.scientific_api import scientific_api_bp

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))
app.config['SECRET_KEY'] = 'asdf#FGSgvasgf$5$WGT'

# Включаем CORS для всех доменов
CORS(app)

app.register_blueprint(user_bp, url_prefix='/api')
app.register_blueprint(email_search_bp, url_prefix='/api/email')
app.register_blueprint(cache_management_bp, url_prefix='/api/cache')
app.register_blueprint(rate_limit_management_bp, url_prefix='/api/rate-limit')
app.register_blueprint(auth_management_bp, url_prefix='/api/auth')
app.register_blueprint(monitoring_bp, url_prefix='/api/monitoring')
app.register_blueprint(scientific_api_bp, url_prefix='/api/scientific')

# uncomment if you need to use database
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(os.path.dirname(__file__), 'database', 'app.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)
with app.app_context():
    db.create_all()

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    static_folder_path = app.static_folder
    if static_folder_path is None:
            return "Static folder not configured", 404

    if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)
    else:
        # Сначала проверяем расширенный интерфейс
        enhanced_path = os.path.join(static_folder_path, 'enhanced_index.html')
        if os.path.exists(enhanced_path):
            return send_from_directory(static_folder_path, 'enhanced_index.html')
        
        # Затем обычный интерфейс
        index_path = os.path.join(static_folder_path, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, 'index.html')
        else:
            return "index.html not found", 404

@app.route('/enhanced')
def enhanced_interface():
    """Маршрут для расширенного интерфейса с анализом веб-страниц"""
    static_folder_path = app.static_folder
    if static_folder_path is None:
        return "Static folder not configured", 404
    
    enhanced_path = os.path.join(static_folder_path, 'enhanced_index.html')
    if os.path.exists(enhanced_path):
        return send_from_directory(static_folder_path, 'enhanced_index.html')
    else:
        return "Enhanced interface not found", 404

@app.route('/react')
@app.route('/react/<path:path>')
def react_interface(path=''):
    """Маршрут для React приложения"""
    static_folder_path = app.static_folder
    if static_folder_path is None:
        return "Static folder not configured", 404
    
    # Проверяем, существует ли запрашиваемый файл
    if path and os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)
    
    # Если файл не найден или путь пустой, отдаем index.html для React Router
    react_index_path = os.path.join(static_folder_path, 'react_index.html')
    if os.path.exists(react_index_path):
        return send_from_directory(static_folder_path, 'react_index.html')
    else:
        return "React application not found", 404


if __name__ == '__main__':
    import argparse
    from dotenv import load_dotenv
    
    # Загружаем переменные окружения
    load_dotenv()
    
    # Получаем настройки из переменных окружения
    default_port = int(os.getenv('FLASK_PORT', 5001))
    default_host = os.getenv('FLASK_HOST', '0.0.0.0')
    default_debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    parser = argparse.ArgumentParser(description='Email Search Backend Server')
    parser.add_argument('--port', type=int, default=default_port, help=f'Port to run the server on (default: {default_port})')
    parser.add_argument('--host', type=str, default=default_host, help=f'Host to run the server on (default: {default_host})')
    parser.add_argument('--debug', action='store_true', default=default_debug, help='Enable debug mode')
    
    args = parser.parse_args()
    
    print(f"Starting Email Search Backend Server on {args.host}:{args.port}")
    print(f"Debug mode: {'enabled' if args.debug else 'disabled'}")
    
    app.run(host=args.host, port=args.port, debug=args.debug)
