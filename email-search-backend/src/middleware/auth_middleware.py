from functools import wraps
from flask import request, jsonify, g
import logging
import sys
import os

# Добавляем путь к services
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from services.auth_service import AuthService
except ImportError:
    AuthService = None

logger = logging.getLogger(__name__)

# Глобальный экземпляр auth service
auth_service = AuthService() if AuthService else None

def get_client_info():
    """Получение информации о клиенте"""
    return {
        'ip_address': request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR')),
        'user_agent': request.environ.get('HTTP_USER_AGENT', '')
    }

def extract_auth_token():
    """Извлечение токена аутентификации из запроса"""
    # Проверяем заголовок Authorization
    auth_header = request.headers.get('Authorization')
    if auth_header:
        if auth_header.startswith('Bearer '):
            return 'jwt', auth_header[7:]  # JWT токен
        elif auth_header.startswith('ApiKey '):
            return 'api_key', auth_header[7:]  # API ключ
        elif auth_header.startswith('Key '):
            return 'api_key', auth_header[4:]  # Альтернативный формат API ключа
    
    # Проверяем заголовок X-API-Key
    api_key = request.headers.get('X-API-Key')
    if api_key:
        return 'api_key', api_key
    
    # Проверяем параметр запроса
    api_key = request.args.get('api_key')
    if api_key:
        return 'api_key', api_key
    
    return None, None

def require_auth(permissions=None, user_types=None, optional=False):
    """
    Декоратор для требования аутентификации
    
    Args:
        permissions: Список требуемых разрешений
        user_types: Список допустимых типов пользователей
        optional: Если True, аутентификация опциональна (не блокирует запрос)
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not auth_service:
                if optional:
                    g.current_user = None
                    g.auth_info = None
                    return f(*args, **kwargs)
                else:
                    return jsonify({
                        'error': 'Authentication service unavailable'
                    }), 503
            
            try:
                client_info = get_client_info()
                auth_type, token = extract_auth_token()
                
                if not auth_type or not token:
                    if optional:
                        g.current_user = None
                        g.auth_info = None
                        return f(*args, **kwargs)
                    else:
                        return jsonify({
                            'error': 'Authentication required',
                            'message': 'Требуется аутентификация. Используйте заголовок Authorization с Bearer токеном или API ключом.'
                        }), 401
                
                # Аутентификация
                authenticated = False
                auth_info = {}
                
                if auth_type == 'jwt':
                    authenticated, auth_info = auth_service.verify_jwt_token(token)
                elif auth_type == 'api_key':
                    authenticated, auth_info = auth_service.authenticate_api_key(
                        token, client_info['ip_address']
                    )
                
                if not authenticated:
                    if optional:
                        g.current_user = None
                        g.auth_info = None
                        return f(*args, **kwargs)
                    else:
                        return jsonify({
                            'error': 'Authentication failed',
                            'message': auth_info.get('error', 'Неверные учетные данные')
                        }), 401
                
                # Проверяем тип пользователя
                if user_types and auth_info.get('user_type') not in user_types:
                    return jsonify({
                        'error': 'Insufficient privileges',
                        'message': f'Требуется тип пользователя: {", ".join(user_types)}'
                    }), 403
                
                # Проверяем разрешения
                if permissions:
                    user_permissions = auth_info.get('permissions', [])
                    if auth_info.get('auth_method') == 'api_key':
                        # Для API ключей проверяем разрешения ключа
                        user_permissions = auth_info.get('permissions', [])
                    else:
                        # Для JWT токенов проверяем разрешения типа пользователя
                        user_type = auth_info.get('user_type', 'free')
                        user_permissions = auth_service.user_types.get(user_type, {}).get('features', [])
                    
                    missing_permissions = [p for p in permissions if p not in user_permissions]
                    if missing_permissions:
                        return jsonify({
                            'error': 'Insufficient permissions',
                            'message': f'Требуются разрешения: {", ".join(missing_permissions)}',
                            'missing_permissions': missing_permissions
                        }), 403
                
                # Сохраняем информацию об аутентификации в g
                g.current_user = auth_info
                g.auth_info = {
                    'user_id': auth_info.get('user_id'),
                    'username': auth_info.get('username'),
                    'user_type': auth_info.get('user_type'),
                    'auth_method': auth_info.get('auth_method'),
                    'permissions': user_permissions
                }
                
                return f(*args, **kwargs)
                
            except Exception as e:
                logger.error(f"Ошибка в auth middleware: {str(e)}")
                if optional:
                    g.current_user = None
                    g.auth_info = None
                    return f(*args, **kwargs)
                else:
                    return jsonify({
                        'error': 'Authentication error',
                        'message': 'Ошибка аутентификации'
                    }), 500
        
        return decorated_function
    return decorator

def require_admin():
    """Декоратор для требования прав администратора"""
    return require_auth(user_types=['enterprise'], permissions=['admin_access'])

def require_premium():
    """Декоратор для требования premium доступа"""
    return require_auth(user_types=['premium', 'enterprise'])

def optional_auth():
    """Декоратор для опциональной аутентификации"""
    return require_auth(optional=True)

def get_current_user():
    """Получение текущего аутентифицированного пользователя"""
    return getattr(g, 'current_user', None)

def get_auth_info():
    """Получение информации об аутентификации"""
    return getattr(g, 'auth_info', None)

def is_authenticated():
    """Проверка, аутентифицирован ли пользователь"""
    return get_current_user() is not None

def has_permission(permission):
    """Проверка наличия разрешения у текущего пользователя"""
    auth_info = get_auth_info()
    if not auth_info:
        return False
    
    permissions = auth_info.get('permissions', [])
    return permission in permissions

def has_user_type(user_type):
    """Проверка типа пользователя"""
    auth_info = get_auth_info()
    if not auth_info:
        return False
    
    return auth_info.get('user_type') == user_type

def get_user_rate_limit_type():
    """Получение типа пользователя для rate limiting"""
    auth_info = get_auth_info()
    if not auth_info:
        return 'anonymous'
    
    user_type = auth_info.get('user_type', 'free')
    
    # Маппинг типов пользователей на типы rate limiting
    rate_limit_mapping = {
        'free': 'anonymous',
        'premium': 'authenticated', 
        'enterprise': 'premium'
    }
    
    return rate_limit_mapping.get(user_type, 'anonymous')

# Алиас для обратной совместимости - функция-фабрика для создания декораторов
def token_required(*args, **kwargs):
    """Алиас для require_auth с теми же параметрами"""
    if len(args) == 1 and callable(args[0]) and not kwargs:
        # Прямое использование как @token_required
        return require_auth()(args[0])
    else:
        # Использование с параметрами как @token_required(...)
        return require_auth(*args, **kwargs)

