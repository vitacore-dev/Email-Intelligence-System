from functools import wraps
from flask import request, g
import time
import uuid
import logging
import sys
import os

# Добавляем путь к services
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from services.monitoring_service import MonitoringService
except ImportError:
    MonitoringService = None

logger = logging.getLogger(__name__)

# Глобальный экземпляр monitoring service
monitoring_service = MonitoringService() if MonitoringService else None

def get_request_size():
    """Получение размера запроса в байтах"""
    try:
        if request.content_length:
            return request.content_length
        elif request.data:
            return len(request.data)
        elif request.form:
            return len(str(request.form))
        else:
            return 0
    except:
        return 0

def get_response_size(response):
    """Получение размера ответа в байтах"""
    try:
        if hasattr(response, 'content_length') and response.content_length:
            return response.content_length
        elif hasattr(response, 'data'):
            return len(response.data)
        else:
            return 0
    except:
        return 0

def extract_email_from_request():
    """Извлечение email из запроса для логирования"""
    try:
        if request.is_json:
            data = request.get_json()
            if data and 'email' in data:
                return data['email']
        elif request.form:
            return request.form.get('email')
        elif request.args:
            return request.args.get('email')
        return None
    except:
        return None

def log_request(f):
    """Декоратор для логирования запросов"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not monitoring_service:
            return f(*args, **kwargs)
        
        # Генерируем уникальный ID запроса
        request_id = str(uuid.uuid4())
        g.request_id = request_id
        
        # Записываем время начала
        start_time = time.time()
        g.start_time = start_time
        
        # Получаем информацию о запросе
        request_size = get_request_size()
        email_searched = extract_email_from_request()
        
        # Получаем информацию об аутентификации
        auth_info = getattr(g, 'auth_info', None)
        user_id = auth_info.get('user_id') if auth_info else None
        auth_method = auth_info.get('auth_method') if auth_info else None
        
        # Выполняем основную функцию
        try:
            response = f(*args, **kwargs)
            
            # Записываем время окончания
            end_time = time.time()
            response_time_ms = (end_time - start_time) * 1000
            
            # Получаем информацию об ответе
            status_code = getattr(response, 'status_code', 200)
            response_size = get_response_size(response)
            
            # Проверяем, был ли запрос ограничен rate limiting
            rate_limited = getattr(g, 'rate_limited', False)
            
            # Проверяем, был ли cache hit
            cache_hit = getattr(g, 'cache_hit', False)
            
            # Логируем запрос
            request_data = {
                'request_id': request_id,
                'user_id': user_id,
                'ip_address': request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR')),
                'user_agent': request.environ.get('HTTP_USER_AGENT', ''),
                'method': request.method,
                'endpoint': request.endpoint or request.path,
                'email_searched': email_searched,
                'response_status': status_code,
                'response_time_ms': response_time_ms,
                'request_size_bytes': request_size,
                'response_size_bytes': response_size,
                'auth_method': auth_method,
                'rate_limited': rate_limited,
                'cache_hit': cache_hit,
                'metadata': {
                    'url': request.url,
                    'referrer': request.referrer,
                    'args': dict(request.args) if request.args else None
                }
            }
            
            monitoring_service.log_request(request_data)
            
            return response
            
        except Exception as e:
            # Логируем ошибку
            end_time = time.time()
            response_time_ms = (end_time - start_time) * 1000
            
            error_message = str(e)
            status_code = getattr(e, 'code', 500)
            
            request_data = {
                'request_id': request_id,
                'user_id': user_id,
                'ip_address': request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR')),
                'user_agent': request.environ.get('HTTP_USER_AGENT', ''),
                'method': request.method,
                'endpoint': request.endpoint or request.path,
                'email_searched': email_searched,
                'response_status': status_code,
                'response_time_ms': response_time_ms,
                'request_size_bytes': request_size,
                'response_size_bytes': 0,
                'error_message': error_message,
                'auth_method': auth_method,
                'rate_limited': getattr(g, 'rate_limited', False),
                'cache_hit': False,
                'metadata': {
                    'url': request.url,
                    'referrer': request.referrer,
                    'args': dict(request.args) if request.args else None,
                    'error_type': type(e).__name__
                }
            }
            
            monitoring_service.log_request(request_data)
            
            # Перебрасываем исключение
            raise
    
    return decorated_function

def get_request_id():
    """Получение ID текущего запроса"""
    return getattr(g, 'request_id', None)

def get_request_start_time():
    """Получение времени начала запроса"""
    return getattr(g, 'start_time', None)

def mark_cache_hit():
    """Отметка о cache hit для текущего запроса"""
    g.cache_hit = True

def mark_rate_limited():
    """Отметка о rate limiting для текущего запроса"""
    g.rate_limited = True

def add_request_metadata(key, value):
    """Добавление метаданных к текущему запросу"""
    if not hasattr(g, 'request_metadata'):
        g.request_metadata = {}
    g.request_metadata[key] = value

