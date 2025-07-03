from functools import wraps
from flask import request, jsonify, g
import logging
import sys
import os

# Добавляем путь к services
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from services.rate_limiter import RateLimiter
except ImportError:
    RateLimiter = None

logger = logging.getLogger(__name__)

# Глобальный экземпляр rate limiter
rate_limiter = RateLimiter() if RateLimiter else None

def safe_validate_email(email_address):
    """Безопасная валидация email без конфликтов имен"""
    import re
    if not email_address:
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email_address) is not None

def get_client_ip():
    """Получение IP адреса клиента"""
    # Проверяем заголовки прокси
    if request.environ.get('HTTP_X_FORWARDED_FOR'):
        # Берем первый IP из списка (реальный клиент)
        return request.environ['HTTP_X_FORWARDED_FOR'].split(',')[0].strip()
    elif request.environ.get('HTTP_X_REAL_IP'):
        return request.environ['HTTP_X_REAL_IP']
    else:
        return request.environ.get('REMOTE_ADDR', '127.0.0.1')

def get_user_type():
    """Определение типа пользователя"""
    # В будущем здесь будет логика определения типа пользователя
    # на основе аутентификации
    return 'anonymous'

def rate_limit(per_minute=None, per_hour=None, per_day=None, 
               user_types=None, check_email=True):
    """
    Декоратор для применения rate limiting к endpoint'ам
    
    Args:
        per_minute: Лимит запросов в минуту (переопределяет настройки по умолчанию)
        per_hour: Лимит запросов в час
        per_day: Лимит запросов в день
        user_types: Список типов пользователей, к которым применяется лимит
        check_email: Проверять ли лимиты по email (для поисковых endpoint'ов)
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not rate_limiter:
                # Если rate limiter недоступен, пропускаем проверку
                logger.warning("Rate limiter недоступен, пропускаем проверку")
                return f(*args, **kwargs)
            
            try:
                # Получаем информацию о клиенте
                client_ip = get_client_ip()
                user_type = get_user_type()
                
                # Проверяем, применяется ли лимит к данному типу пользователя
                if user_types and user_type not in user_types:
                    return f(*args, **kwargs)
                
                # Получаем email из запроса если нужно
                email = None
                if check_email and request.json and 'email' in request.json:
                    email = request.json['email']
                    # Валидируем email безопасно
                    if not safe_validate_email(email):
                        return jsonify({
                            'error': 'Invalid email format',
                            'message': 'Неверный формат email адреса'
                        }), 400
                
                # Проверяем rate limit
                allowed, info = rate_limiter.check_rate_limit(
                    ip_address=client_ip,
                    email=email,
                    user_type=user_type
                )
                
                if not allowed:
                    # Формируем ответ об ошибке rate limit
                    error_response = {
                        'error': 'Rate limit exceeded',
                        'message': info.get('reason', 'Превышен лимит запросов'),
                        'retry_after': info.get('retry_after', 60),
                        'limit_info': {
                            'window_type': info.get('window_type'),
                            'limit': info.get('limit'),
                            'current': info.get('current')
                        }
                    }
                    
                    # Добавляем заголовки для клиента
                    response = jsonify(error_response)
                    response.status_code = 429  # Too Many Requests
                    response.headers['Retry-After'] = str(info.get('retry_after', 60))
                    response.headers['X-RateLimit-Limit'] = str(info.get('limit', 'unknown'))
                    response.headers['X-RateLimit-Remaining'] = str(max(0, info.get('limit', 0) - info.get('current', 0)))
                    
                    logger.warning(f"Rate limit exceeded for IP {client_ip}: {info.get('reason')}")
                    return response
                
                # Сохраняем информацию о лимитах в g для использования в endpoint'е
                g.rate_limit_info = info
                g.client_ip = client_ip
                g.user_type = user_type
                
                # Выполняем оригинальную функцию
                response = f(*args, **kwargs)
                
                # Добавляем заголовки с информацией о лимитах
                if hasattr(response, 'headers') and 'limits' in info:
                    limits = info['limits']
                    current_usage = info.get('current_usage', {})
                    
                    response.headers['X-RateLimit-Limit-Minute'] = str(limits.get('requests_per_minute', 'unknown'))
                    response.headers['X-RateLimit-Limit-Hour'] = str(limits.get('requests_per_hour', 'unknown'))
                    response.headers['X-RateLimit-Limit-Day'] = str(limits.get('requests_per_day', 'unknown'))
                    
                    response.headers['X-RateLimit-Remaining-Minute'] = str(
                        max(0, limits.get('requests_per_minute', 0) - current_usage.get('ip_minute', 0))
                    )
                    response.headers['X-RateLimit-Remaining-Hour'] = str(
                        max(0, limits.get('requests_per_hour', 0) - current_usage.get('ip_hour', 0))
                    )
                    response.headers['X-RateLimit-Remaining-Day'] = str(
                        max(0, limits.get('requests_per_day', 0) - current_usage.get('ip_day', 0))
                    )
                
                return response
                
            except Exception as e:
                logger.error(f"Ошибка в rate limit middleware: {str(e)}")
                # В случае ошибки пропускаем проверку
                return f(*args, **kwargs)
        
        return decorated_function
    return decorator

def rate_limit_status():
    """Функция для получения статуса rate limiting"""
    if not rate_limiter:
        return {
            'enabled': False,
            'error': 'Rate limiter недоступен'
        }
    
    try:
        client_ip = get_client_ip()
        user_type = get_user_type()
        
        # Получаем текущее состояние без записи запроса
        current_time = rate_limiter.datetime.now()
        current_usage = rate_limiter._get_current_usage(client_ip, None, current_time)
        limits = rate_limiter.user_type_limits.get(user_type, rate_limiter.default_limits)
        reset_times = rate_limiter._get_reset_times(current_time)
        
        return {
            'enabled': True,
            'ip_address': client_ip,
            'user_type': user_type,
            'limits': limits,
            'current_usage': current_usage,
            'reset_times': reset_times,
            'blocked': rate_limiter._is_blocked(client_ip)
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения статуса rate limiting: {str(e)}")
        return {
            'enabled': True,
            'error': str(e)
        }

# Middleware для автоматического применения базового rate limiting
def apply_basic_rate_limiting():
    """Применение базового rate limiting ко всем запросам"""
    if not rate_limiter:
        return
    
    try:
        # Пропускаем статические файлы и health check'и
        if (request.endpoint and 
            (request.endpoint.startswith('static') or 
             'health' in request.endpoint.lower() or
             request.path.startswith('/static/'))):
            return
        
        client_ip = get_client_ip()
        user_type = get_user_type()
        
        # Применяем очень мягкие лимиты для общих запросов
        basic_limits = {
            'requests_per_minute': 60,
            'requests_per_hour': 1000,
            'requests_per_day': 10000,
            'burst_limit': 20,
            'burst_window': 10
        }
        
        # Проверяем только IP лимиты для базовой защиты
        allowed, info = rate_limiter.check_rate_limit(
            ip_address=client_ip,
            email=None,
            user_type='basic'
        )
        
        if not allowed:
            error_response = {
                'error': 'Too many requests',
                'message': 'Слишком много запросов с вашего IP адреса',
                'retry_after': info.get('retry_after', 60)
            }
            
            response = jsonify(error_response)
            response.status_code = 429
            response.headers['Retry-After'] = str(info.get('retry_after', 60))
            
            logger.warning(f"Basic rate limit exceeded for IP {client_ip}")
            return response
            
    except Exception as e:
        logger.error(f"Ошибка в базовом rate limiting: {str(e)}")
        # В случае ошибки пропускаем проверку

