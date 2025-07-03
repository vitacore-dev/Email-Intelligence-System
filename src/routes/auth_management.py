from flask import Blueprint, jsonify, request
from flask_cors import CORS
import logging
import sys
import os

# Добавляем путь к services и middleware
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from services.auth_service import AuthService
    from middleware.auth_middleware import (
        require_auth, require_admin, optional_auth, 
        get_current_user, get_auth_info, get_client_info
    )
except ImportError:
    AuthService = None
    require_auth = lambda **kwargs: lambda f: f
    require_admin = lambda: lambda f: f
    optional_auth = lambda: lambda f: f
    get_current_user = lambda: None
    get_auth_info = lambda: None
    get_client_info = lambda: {}

logger = logging.getLogger(__name__)

auth_management_bp = Blueprint('auth_management', __name__)
CORS(auth_management_bp)

# Инициализация auth service
auth_service = AuthService() if AuthService else None

@auth_management_bp.route('/register', methods=['POST'])
def register():
    """Регистрация нового пользователя"""
    if not auth_service:
        return jsonify({
            'error': 'Authentication service unavailable'
        }), 503
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'error': 'Данные не предоставлены'
            }), 400
        
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')
        user_type = data.get('user_type', 'free')
        
        # Валидация
        if not username or len(username) < 3:
            return jsonify({
                'error': 'Имя пользователя должно содержать минимум 3 символа'
            }), 400
        
        if not email or '@' not in email:
            return jsonify({
                'error': 'Некорректный email адрес'
            }), 400
        
        if not password or len(password) < 6:
            return jsonify({
                'error': 'Пароль должен содержать минимум 6 символов'
            }), 400
        
        if user_type not in ['free', 'premium', 'enterprise']:
            user_type = 'free'
        
        # Регистрируем пользователя
        success, result = auth_service.register_user(username, email, password, user_type)
        
        if success:
            return jsonify({
                'message': 'Пользователь успешно зарегистрирован',
                'user': {
                    'user_id': result['user_id'],
                    'username': result['username'],
                    'email': result['email'],
                    'user_type': result['user_type'],
                    'api_key': result['api_key']
                }
            }), 201
        else:
            return jsonify({
                'error': result.get('error', 'Ошибка регистрации')
            }), 400
            
    except Exception as e:
        logger.error(f"Ошибка регистрации: {str(e)}")
        return jsonify({
            'error': 'Внутренняя ошибка сервера'
        }), 500

@auth_management_bp.route('/login', methods=['POST'])
def login():
    """Вход пользователя"""
    if not auth_service:
        return jsonify({
            'error': 'Authentication service unavailable'
        }), 503
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'error': 'Данные не предоставлены'
            }), 400
        
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            return jsonify({
                'error': 'Необходимо указать имя пользователя и пароль'
            }), 400
        
        client_info = get_client_info()
        
        # Аутентифицируем пользователя
        success, result = auth_service.authenticate_user(
            username, password, 
            client_info.get('ip_address'), 
            client_info.get('user_agent')
        )
        
        if success:
            return jsonify({
                'message': 'Успешный вход',
                'user': {
                    'user_id': result['user_id'],
                    'username': result['username'],
                    'email': result['email'],
                    'user_type': result['user_type']
                },
                'tokens': {
                    'access_token': result['access_token'],
                    'refresh_token': result['refresh_token'],
                    'expires_in': result['expires_in']
                }
            })
        else:
            return jsonify({
                'error': result.get('error', 'Ошибка аутентификации')
            }), 401
            
    except Exception as e:
        logger.error(f"Ошибка входа: {str(e)}")
        return jsonify({
            'error': 'Внутренняя ошибка сервера'
        }), 500

@auth_management_bp.route('/profile', methods=['GET'])
@require_auth()
def get_profile():
    """Получение профиля текущего пользователя"""
    if not auth_service:
        return jsonify({
            'error': 'Authentication service unavailable'
        }), 503
    
    try:
        current_user = get_current_user()
        user_id = current_user.get('user_id')
        
        user_info = auth_service.get_user_info(user_id)
        if not user_info:
            return jsonify({
                'error': 'Пользователь не найден'
            }), 404
        
        return jsonify({
            'profile': user_info
        })
        
    except Exception as e:
        logger.error(f"Ошибка получения профиля: {str(e)}")
        return jsonify({
            'error': 'Ошибка получения профиля'
        }), 500

@auth_management_bp.route('/api-keys', methods=['GET'])
@require_auth()
def get_api_keys():
    """Получение API ключей пользователя"""
    if not auth_service:
        return jsonify({
            'error': 'Authentication service unavailable'
        }), 503
    
    try:
        current_user = get_current_user()
        user_id = current_user.get('user_id')
        
        user_info = auth_service.get_user_info(user_id)
        if not user_info:
            return jsonify({
                'error': 'Пользователь не найден'
            }), 404
        
        return jsonify({
            'api_keys': user_info.get('api_keys', []),
            'limits': user_info.get('permissions', {})
        })
        
    except Exception as e:
        logger.error(f"Ошибка получения API ключей: {str(e)}")
        return jsonify({
            'error': 'Ошибка получения API ключей'
        }), 500

@auth_management_bp.route('/api-keys', methods=['POST'])
@require_auth()
def create_api_key():
    """Создание нового API ключа"""
    if not auth_service:
        return jsonify({
            'error': 'Authentication service unavailable'
        }), 503
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'error': 'Данные не предоставлены'
            }), 400
        
        name = data.get('name', '').strip()
        permissions = data.get('permissions', ['search'])
        
        if not name:
            return jsonify({
                'error': 'Необходимо указать название ключа'
            }), 400
        
        current_user = get_current_user()
        user_id = current_user.get('user_id')
        user_type = current_user.get('user_type', 'free')
        
        # Проверяем доступные разрешения для типа пользователя
        available_features = auth_service.user_types.get(user_type, {}).get('features', [])
        invalid_permissions = [p for p in permissions if p not in available_features]
        
        if invalid_permissions:
            return jsonify({
                'error': f'Недоступные разрешения для вашего типа аккаунта: {", ".join(invalid_permissions)}',
                'available_permissions': available_features
            }), 400
        
        # Создаем API ключ
        api_key = auth_service.generate_api_key(user_id, name, permissions)
        
        return jsonify({
            'message': 'API ключ успешно создан',
            'api_key': api_key,
            'name': name,
            'permissions': permissions,
            'warning': 'Сохраните этот ключ в безопасном месте. Он больше не будет показан.'
        }), 201
        
    except Exception as e:
        logger.error(f"Ошибка создания API ключа: {str(e)}")
        return jsonify({
            'error': str(e) if 'лимит' in str(e) else 'Ошибка создания API ключа'
        }), 400

@auth_management_bp.route('/verify-token', methods=['POST'])
def verify_token():
    """Проверка JWT токена"""
    if not auth_service:
        return jsonify({
            'error': 'Authentication service unavailable'
        }), 503
    
    try:
        data = request.get_json()
        if not data or 'token' not in data:
            return jsonify({
                'error': 'Токен не предоставлен'
            }), 400
        
        token = data['token']
        token_type = data.get('type', 'access')
        
        success, result = auth_service.verify_jwt_token(token, token_type)
        
        if success:
            return jsonify({
                'valid': True,
                'user': {
                    'user_id': result['user_id'],
                    'username': result['username'],
                    'email': result['email'],
                    'user_type': result['user_type']
                }
            })
        else:
            return jsonify({
                'valid': False,
                'error': result.get('error', 'Неверный токен')
            }), 401
            
    except Exception as e:
        logger.error(f"Ошибка проверки токена: {str(e)}")
        return jsonify({
            'error': 'Ошибка проверки токена'
        }), 500

@auth_management_bp.route('/verify-api-key', methods=['POST'])
def verify_api_key():
    """Проверка API ключа"""
    if not auth_service:
        return jsonify({
            'error': 'Authentication service unavailable'
        }), 503
    
    try:
        data = request.get_json()
        if not data or 'api_key' not in data:
            return jsonify({
                'error': 'API ключ не предоставлен'
            }), 400
        
        api_key = data['api_key']
        client_info = get_client_info()
        
        success, result = auth_service.authenticate_api_key(
            api_key, client_info.get('ip_address')
        )
        
        if success:
            return jsonify({
                'valid': True,
                'user': {
                    'user_id': result['user_id'],
                    'username': result['username'],
                    'email': result['email'],
                    'user_type': result['user_type'],
                    'api_key_name': result['api_key_name'],
                    'permissions': result['permissions']
                }
            })
        else:
            return jsonify({
                'valid': False,
                'error': result.get('error', 'Неверный API ключ')
            }), 401
            
    except Exception as e:
        logger.error(f"Ошибка проверки API ключа: {str(e)}")
        return jsonify({
            'error': 'Ошибка проверки API ключа'
        }), 500

@auth_management_bp.route('/stats', methods=['GET'])
@require_admin()
def get_auth_stats():
    """Получение статистики аутентификации (только для администраторов)"""
    if not auth_service:
        return jsonify({
            'error': 'Authentication service unavailable'
        }), 503
    
    try:
        stats = auth_service.get_auth_stats()
        return jsonify({
            'authentication_statistics': stats
        })
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики аутентификации: {str(e)}")
        return jsonify({
            'error': 'Ошибка получения статистики'
        }), 500

@auth_management_bp.route('/cleanup', methods=['POST'])
@require_admin()
def cleanup_auth_data():
    """Очистка старых данных аутентификации (только для администраторов)"""
    if not auth_service:
        return jsonify({
            'error': 'Authentication service unavailable'
        }), 503
    
    try:
        cleaned_count = auth_service.cleanup_expired_sessions()
        
        return jsonify({
            'message': f'Очищено {cleaned_count} записей',
            'cleaned_sessions': cleaned_count
        })
        
    except Exception as e:
        logger.error(f"Ошибка очистки данных аутентификации: {str(e)}")
        return jsonify({
            'error': 'Ошибка очистки данных'
        }), 500

@auth_management_bp.route('/health', methods=['GET'])
def auth_health_check():
    """Проверка состояния системы аутентификации"""
    if not auth_service:
        return jsonify({
            'status': 'unhealthy',
            'error': 'Authentication service unavailable'
        }), 503
    
    try:
        # Проверяем доступность базы данных
        stats = auth_service.get_auth_stats()
        
        return jsonify({
            'status': 'healthy',
            'auth_service_available': True,
            'database_accessible': True,
            'total_users': stats.get('users', {}).get('total', 0),
            'active_sessions': stats.get('activity', {}).get('active_sessions', 0)
        })
        
    except Exception as e:
        logger.error(f"Ошибка проверки состояния аутентификации: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'error': 'Ошибка доступа к системе аутентификации'
        }), 500

@auth_management_bp.route('/user-types', methods=['GET'])
def get_user_types():
    """Получение информации о типах пользователей"""
    if not auth_service:
        return jsonify({
            'error': 'Authentication service unavailable'
        }), 503
    
    try:
        return jsonify({
            'user_types': auth_service.user_types
        })
        
    except Exception as e:
        logger.error(f"Ошибка получения типов пользователей: {str(e)}")
        return jsonify({
            'error': 'Ошибка получения типов пользователей'
        }), 500

