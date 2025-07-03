from flask import Blueprint, jsonify, request
from flask_cors import CORS
import logging
import sys
import os

# Добавляем путь к services
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from services.database import DatabaseService
except ImportError:
    DatabaseService = None

logger = logging.getLogger(__name__)

cache_management_bp = Blueprint('cache_management', __name__)
CORS(cache_management_bp)

# Инициализация сервиса базы данных
db_service = DatabaseService() if DatabaseService else None

@cache_management_bp.route('/stats', methods=['GET'])
def get_cache_stats():
    """Получение статистики кэша"""
    if not db_service:
        return jsonify({
            'error': 'Сервис базы данных недоступен'
        }), 503
    
    try:
        stats = db_service.get_cache_stats()
        return jsonify({
            'cache_statistics': stats,
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики кэша: {str(e)}")
        return jsonify({
            'error': 'Ошибка получения статистики'
        }), 500

@cache_management_bp.route('/analytics', methods=['GET'])
def get_search_analytics():
    """Получение аналитики поисковых запросов"""
    if not db_service:
        return jsonify({
            'error': 'Сервис базы данных недоступен'
        }), 503
    
    try:
        days = request.args.get('days', 7, type=int)
        if days < 1 or days > 365:
            days = 7
        
        analytics = db_service.get_search_analytics(days)
        return jsonify({
            'analytics': analytics,
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Ошибка получения аналитики: {str(e)}")
        return jsonify({
            'error': 'Ошибка получения аналитики'
        }), 500

@cache_management_bp.route('/cleanup', methods=['POST'])
def cleanup_expired_cache():
    """Очистка устаревшего кэша"""
    if not db_service:
        return jsonify({
            'error': 'Сервис базы данных недоступен'
        }), 503
    
    try:
        deleted_count = db_service.cleanup_expired_cache()
        return jsonify({
            'deleted_entries': deleted_count,
            'message': f'Удалено {deleted_count} устаревших записей',
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Ошибка очистки кэша: {str(e)}")
        return jsonify({
            'error': 'Ошибка очистки кэша'
        }), 500

@cache_management_bp.route('/clear', methods=['POST'])
def clear_all_cache():
    """Полная очистка кэша (только для администраторов)"""
    if not db_service:
        return jsonify({
            'error': 'Сервис базы данных недоступен'
        }), 503
    
    try:
        # В будущем здесь должна быть проверка прав администратора
        
        import sqlite3
        with sqlite3.connect(db_service.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM search_cache')
            deleted_count = cursor.rowcount
            conn.commit()
        
        return jsonify({
            'deleted_entries': deleted_count,
            'message': f'Кэш полностью очищен. Удалено {deleted_count} записей',
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Ошибка полной очистки кэша: {str(e)}")
        return jsonify({
            'error': 'Ошибка очистки кэша'
        }), 500

@cache_management_bp.route('/health', methods=['GET'])
def cache_health_check():
    """Проверка состояния системы кэширования"""
    if not db_service:
        return jsonify({
            'status': 'unhealthy',
            'error': 'Сервис базы данных недоступен'
        }), 503
    
    try:
        # Проверяем доступность базы данных
        stats = db_service.get_cache_stats()
        
        return jsonify({
            'status': 'healthy',
            'database_available': True,
            'cache_enabled': True,
            'active_entries': stats.get('active_cached_entries', 0),
            'total_hits': stats.get('total_cache_hits', 0)
        })
        
    except Exception as e:
        logger.error(f"Ошибка проверки состояния кэша: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'error': 'Ошибка доступа к базе данных'
        }), 500

@cache_management_bp.route('/update-stats', methods=['POST'])
def update_daily_stats():
    """Обновление ежедневной статистики"""
    if not db_service:
        return jsonify({
            'error': 'Сервис базы данных недоступен'
        }), 503
    
    try:
        date = request.json.get('date') if request.json else None
        success = db_service.update_daily_stats(date)
        
        if success:
            return jsonify({
                'message': 'Статистика успешно обновлена',
                'status': 'success'
            })
        else:
            return jsonify({
                'message': 'Нет данных для обновления статистики',
                'status': 'no_data'
            })
        
    except Exception as e:
        logger.error(f"Ошибка обновления статистики: {str(e)}")
        return jsonify({
            'error': 'Ошибка обновления статистики'
        }), 500

@cache_management_bp.route('/email-data/delete', methods=['POST'])
def delete_email_data():
    """Удаление всех данных для конкретного email"""
    if not db_service:
        return jsonify({
            'error': 'Сервис базы данных недоступен'
        }), 503
    
    try:
        data = request.get_json()
        if not data or 'email' not in data:
            return jsonify({
                'error': 'Email не указан'
            }), 400
        
        email = data['email']
        if not email or '@' not in email:
            return jsonify({
                'error': 'Некорректный формат email'
            }), 400
        
        result = db_service.delete_email_data(email)
        
        if 'error' in result:
            return jsonify({
                'error': result['error']
            }), 500
        
        return jsonify({
            'message': f'Данные для email {email} успешно удалены',
            'result': result,
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Ошибка удаления данных email: {str(e)}")
        return jsonify({
            'error': 'Ошибка удаления данных email'
        }), 500

@cache_management_bp.route('/email-data/delete-all', methods=['POST'])
def delete_all_email_data():
    """Полная очистка всех данных email (только для администраторов)"""
    if not db_service:
        return jsonify({
            'error': 'Сервис базы данных недоступен'
        }), 503
    
    try:
        # В будущем здесь должна быть проверка прав администратора
        data = request.get_json()
        confirm = data.get('confirm', False) if data else False
        
        if not confirm:
            return jsonify({
                'error': 'Требуется подтверждение операции (confirm: true)'
            }), 400
        
        result = db_service.delete_all_email_data()
        
        if 'error' in result:
            return jsonify({
                'error': result['error']
            }), 500
        
        return jsonify({
            'message': 'Все данные email успешно удалены',
            'result': result,
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Ошибка полной очистки данных email: {str(e)}")
        return jsonify({
            'error': 'Ошибка полной очистки данных email'
        }), 500

@cache_management_bp.route('/email-data/stats', methods=['GET'])
def get_email_data_stats():
    """Получение статистики хранимых данных email"""
    if not db_service:
        return jsonify({
            'error': 'Сервис базы данных недоступен'
        }), 503
    
    try:
        stats = db_service.get_email_data_stats()
        
        if 'error' in stats:
            return jsonify({
                'error': stats['error']
            }), 500
        
        return jsonify({
            'email_data_statistics': stats,
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики данных email: {str(e)}")
        return jsonify({
            'error': 'Ошибка получения статистики'
        }), 500

