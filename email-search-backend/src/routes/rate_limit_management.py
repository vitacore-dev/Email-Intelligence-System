from flask import Blueprint, jsonify, request
from flask_cors import CORS
import logging
import sys
import os

# Добавляем путь к services и middleware
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from services.rate_limiter import RateLimiter
    from middleware.rate_limit_middleware import rate_limit_status, get_client_ip
except ImportError:
    RateLimiter = None
    rate_limit_status = None
    get_client_ip = None

logger = logging.getLogger(__name__)

rate_limit_management_bp = Blueprint('rate_limit_management', __name__)
CORS(rate_limit_management_bp)

# Инициализация rate limiter
rate_limiter = RateLimiter() if RateLimiter else None

@rate_limit_management_bp.route('/status', methods=['GET'])
def get_rate_limit_status():
    """Получение текущего статуса rate limiting для клиента"""
    if not rate_limiter or not rate_limit_status:
        return jsonify({
            'error': 'Rate limiting недоступен'
        }), 503
    
    try:
        status = rate_limit_status()
        return jsonify({
            'rate_limit_status': status,
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Ошибка получения статуса rate limiting: {str(e)}")
        return jsonify({
            'error': 'Ошибка получения статуса'
        }), 500

@rate_limit_management_bp.route('/stats', methods=['GET'])
def get_rate_limit_stats():
    """Получение общей статистики rate limiting"""
    if not rate_limiter:
        return jsonify({
            'error': 'Rate limiter недоступен'
        }), 503
    
    try:
        stats = rate_limiter.get_rate_limit_stats()
        return jsonify({
            'rate_limit_statistics': stats,
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики rate limiting: {str(e)}")
        return jsonify({
            'error': 'Ошибка получения статистики'
        }), 500

@rate_limit_management_bp.route('/limits', methods=['GET'])
def get_rate_limits():
    """Получение конфигурации лимитов"""
    if not rate_limiter:
        return jsonify({
            'error': 'Rate limiter недоступен'
        }), 503
    
    try:
        return jsonify({
            'default_limits': rate_limiter.default_limits,
            'user_type_limits': rate_limiter.user_type_limits,
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Ошибка получения лимитов: {str(e)}")
        return jsonify({
            'error': 'Ошибка получения лимитов'
        }), 500

@rate_limit_management_bp.route('/cleanup', methods=['POST'])
def cleanup_rate_limit_records():
    """Очистка старых записей rate limiting"""
    if not rate_limiter:
        return jsonify({
            'error': 'Rate limiter недоступен'
        }), 503
    
    try:
        days_to_keep = request.json.get('days_to_keep', 7) if request.json else 7
        
        if days_to_keep < 1 or days_to_keep > 365:
            return jsonify({
                'error': 'Некорректное количество дней (должно быть от 1 до 365)'
            }), 400
        
        deleted_count = rate_limiter.cleanup_old_records(days_to_keep)
        
        return jsonify({
            'deleted_records': deleted_count,
            'days_kept': days_to_keep,
            'message': f'Удалено {deleted_count} старых записей',
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Ошибка очистки записей rate limiting: {str(e)}")
        return jsonify({
            'error': 'Ошибка очистки записей'
        }), 500

@rate_limit_management_bp.route('/unblock', methods=['POST'])
def unblock_ip_or_email():
    """Разблокировка IP адреса или email (только для администраторов)"""
    if not rate_limiter:
        return jsonify({
            'error': 'Rate limiter недоступен'
        }), 503
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'error': 'Данные не предоставлены'
            }), 400
        
        ip_address = data.get('ip_address')
        email = data.get('email')
        
        if not ip_address and not email:
            return jsonify({
                'error': 'Необходимо указать ip_address или email'
            }), 400
        
        # В будущем здесь должна быть проверка прав администратора
        
        import sqlite3
        with sqlite3.connect(rate_limiter.db_path) as conn:
            cursor = conn.cursor()
            
            # Деактивируем блокировки
            if ip_address:
                cursor.execute('''
                    UPDATE rate_limit_blocks 
                    SET is_active = 0 
                    WHERE ip_address = ? AND is_active = 1
                ''', (ip_address,))
                
            if email:
                email_hash = rate_limiter._hash_email(email)
                cursor.execute('''
                    UPDATE rate_limit_blocks 
                    SET is_active = 0 
                    WHERE email_hash = ? AND is_active = 1
                ''', (email_hash,))
            
            affected_rows = cursor.rowcount
            conn.commit()
        
        return jsonify({
            'unblocked_entries': affected_rows,
            'ip_address': ip_address,
            'email': email if email else None,
            'message': f'Разблокировано {affected_rows} записей',
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Ошибка разблокировки: {str(e)}")
        return jsonify({
            'error': 'Ошибка разблокировки'
        }), 500

@rate_limit_management_bp.route('/health', methods=['GET'])
def rate_limit_health_check():
    """Проверка состояния системы rate limiting"""
    if not rate_limiter:
        return jsonify({
            'status': 'unhealthy',
            'error': 'Rate limiter недоступен'
        }), 503
    
    try:
        # Проверяем доступность базы данных
        stats = rate_limiter.get_rate_limit_stats()
        
        return jsonify({
            'status': 'healthy',
            'rate_limiter_available': True,
            'database_accessible': True,
            'active_blocks': stats.get('active_blocks', 0),
            'unique_ips_24h': stats.get('unique_ips_24h', 0)
        })
        
    except Exception as e:
        logger.error(f"Ошибка проверки состояния rate limiting: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'error': 'Ошибка доступа к системе rate limiting'
        }), 500

@rate_limit_management_bp.route('/test', methods=['POST'])
def test_rate_limit():
    """Тестирование rate limiting (для разработки)"""
    if not rate_limiter or not get_client_ip:
        return jsonify({
            'error': 'Rate limiting недоступен'
        }), 503
    
    try:
        client_ip = get_client_ip()
        test_email = request.json.get('email') if request.json else None
        
        # Проверяем rate limit без записи
        allowed, info = rate_limiter.check_rate_limit(
            ip_address=client_ip,
            email=test_email,
            user_type='anonymous'
        )
        
        return jsonify({
            'client_ip': client_ip,
            'test_email': test_email,
            'allowed': allowed,
            'rate_limit_info': info,
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Ошибка тестирования rate limiting: {str(e)}")
        return jsonify({
            'error': 'Ошибка тестирования'
        }), 500

