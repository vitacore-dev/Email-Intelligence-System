from flask import Blueprint, jsonify, request
from flask_cors import CORS
import logging
import sys
import os
import time

# Добавляем путь к services и middleware
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from services.monitoring_service import MonitoringService
    from middleware.auth_middleware import require_auth, require_admin, optional_auth
    from middleware.logging_middleware import log_request
except ImportError:
    MonitoringService = None
    require_auth = lambda **kwargs: lambda f: f
    require_admin = lambda: lambda f: f
    optional_auth = lambda: lambda f: f
    log_request = lambda f: f

# Try to import NLP components
try:
    from services.nlp_enhanced_analyzer import EnhancedNLPAnalyzer
except ImportError:
    EnhancedNLPAnalyzer = None

logger = logging.getLogger(__name__)

monitoring_bp = Blueprint('monitoring', __name__)
CORS(monitoring_bp)

# Инициализация monitoring service
monitoring_service = MonitoringService() if MonitoringService else None

@monitoring_bp.route('/dashboard', methods=['GET'])
@require_admin()
@log_request
def get_dashboard():
    """Получение данных для дашборда мониторинга (только для администраторов)"""
    if not monitoring_service:
        return jsonify({
            'error': 'Monitoring service unavailable'
        }), 503
    
    try:
        metrics = monitoring_service.get_dashboard_metrics()
        
        return jsonify({
            'dashboard': metrics,
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Ошибка получения данных дашборда: {str(e)}")
        return jsonify({
            'error': 'Ошибка получения данных дашборда'
        }), 500

@monitoring_bp.route('/metrics', methods=['GET'])
@require_auth(permissions=['monitoring'])
@log_request
def get_metrics():
    """Получение основных метрик (для пользователей с соответствующими правами)"""
    if not monitoring_service:
        return jsonify({
            'error': 'Monitoring service unavailable'
        }), 503
    
    try:
        metrics = monitoring_service.get_dashboard_metrics()
        
        # Возвращаем только основные метрики, без детальной информации
        return jsonify({
            'metrics': {
                'requests_24h': metrics.get('stats_24h', {}).get('total_requests', 0),
                'error_rate': metrics.get('stats_24h', {}).get('error_rate', 0),
                'avg_response_time': metrics.get('stats_24h', {}).get('avg_response_time', 0),
                'cache_hit_rate': metrics.get('stats_24h', {}).get('cache_hit_rate', 0),
                'active_users': metrics.get('system_metrics', {}).get('active_users', 0),
                'requests_per_minute': metrics.get('system_metrics', {}).get('requests_per_minute', 0)
            },
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Ошибка получения метрик: {str(e)}")
        return jsonify({
            'error': 'Ошибка получения метрик'
        }), 500

@monitoring_bp.route('/time-series/<metric>', methods=['GET'])
@require_admin()
@log_request
def get_time_series(metric):
    """Получение данных временных рядов для графиков"""
    if not monitoring_service:
        return jsonify({
            'error': 'Monitoring service unavailable'
        }), 503
    
    try:
        hours = request.args.get('hours', 24, type=int)
        if hours > 168:  # Максимум неделя
            hours = 168
        
        valid_metrics = ['requests', 'response_time', 'error_rate', 'cpu_usage', 'memory_usage']
        if metric not in valid_metrics:
            return jsonify({
                'error': f'Неподдерживаемая метрика. Доступные: {", ".join(valid_metrics)}'
            }), 400
        
        data = monitoring_service.get_time_series_data(metric, hours)
        
        return jsonify({
            'metric': metric,
            'hours': hours,
            'data': data,
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Ошибка получения данных временных рядов: {str(e)}")
        return jsonify({
            'error': 'Ошибка получения данных временных рядов'
        }), 500

@monitoring_bp.route('/alerts', methods=['GET'])
@require_admin()
@log_request
def get_alerts():
    """Получение списка алертов"""
    if not monitoring_service:
        return jsonify({
            'error': 'Monitoring service unavailable'
        }), 503
    
    try:
        limit = request.args.get('limit', 50, type=int)
        severity = request.args.get('severity')
        
        if limit > 200:  # Максимум 200 алертов
            limit = 200
        
        alerts = monitoring_service.get_alerts(limit, severity)
        
        return jsonify({
            'alerts': alerts,
            'total': len(alerts),
            'filters': {
                'limit': limit,
                'severity': severity
            },
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Ошибка получения алертов: {str(e)}")
        return jsonify({
            'error': 'Ошибка получения алертов'
        }), 500

@monitoring_bp.route('/alerts/<int:alert_id>/resolve', methods=['POST'])
@require_admin()
@log_request
def resolve_alert(alert_id):
    """Разрешение алерта"""
    if not monitoring_service:
        return jsonify({
            'error': 'Monitoring service unavailable'
        }), 503
    
    try:
        success = monitoring_service.resolve_alert(alert_id)
        
        if success:
            return jsonify({
                'message': f'Алерт {alert_id} успешно разрешен',
                'status': 'success'
            })
        else:
            return jsonify({
                'error': 'Алерт не найден или уже разрешен'
            }), 404
        
    except Exception as e:
        logger.error(f"Ошибка разрешения алерта: {str(e)}")
        return jsonify({
            'error': 'Ошибка разрешения алерта'
        }), 500

@monitoring_bp.route('/cleanup', methods=['POST'])
@require_admin()
@log_request
def cleanup_monitoring_data():
    """Очистка старых данных мониторинга"""
    if not monitoring_service:
        return jsonify({
            'error': 'Monitoring service unavailable'
        }), 503
    
    try:
        result = monitoring_service.cleanup_old_data()
        
        return jsonify({
            'message': 'Очистка данных мониторинга завершена',
            'cleaned': result,
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Ошибка очистки данных мониторинга: {str(e)}")
        return jsonify({
            'error': 'Ошибка очистки данных мониторинга'
        }), 500

@monitoring_bp.route('/health', methods=['GET'])
@log_request
def monitoring_health_check():
    """Проверка состояния системы мониторинга"""
    if not monitoring_service:
        return jsonify({
            'status': 'unhealthy',
            'error': 'Monitoring service unavailable'
        }), 503
    
    try:
        # Получаем базовые метрики для проверки работоспособности
        metrics = monitoring_service.get_dashboard_metrics()
        
        return jsonify({
            'status': 'healthy',
            'monitoring_service_available': True,
            'database_accessible': True,
            'background_tasks_running': True,
            'last_metric_timestamp': metrics.get('timestamp'),
            'total_requests_24h': metrics.get('stats_24h', {}).get('total_requests', 0)
        })
        
    except Exception as e:
        logger.error(f"Ошибка проверки состояния мониторинга: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'error': 'Ошибка доступа к системе мониторинга'
        }), 500

@monitoring_bp.route('/stats/summary', methods=['GET'])
@optional_auth()
@log_request
def get_stats_summary():
    """Получение краткой сводки статистики (доступно всем)"""
    if not monitoring_service:
        return jsonify({
            'error': 'Monitoring service unavailable'
        }), 503
    
    try:
        metrics = monitoring_service.get_dashboard_metrics()
        
        # Возвращаем только публичную статистику
        return jsonify({
            'summary': {
                'total_requests_24h': metrics.get('stats_24h', {}).get('total_requests', 0),
                'avg_response_time_ms': round(metrics.get('stats_24h', {}).get('avg_response_time', 0), 2),
                'service_uptime': 'healthy',
                'cache_hit_rate_percent': round(metrics.get('stats_24h', {}).get('cache_hit_rate', 0), 1)
            },
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Ошибка получения сводки статистики: {str(e)}")
        return jsonify({
            'error': 'Ошибка получения статистики'
        }), 500

@monitoring_bp.route('/export/logs', methods=['GET'])
@require_admin()
@log_request
def export_logs():
    """Экспорт логов (только для администраторов)"""
    if not monitoring_service:
        return jsonify({
            'error': 'Monitoring service unavailable'
        }), 503
    
    try:
        # Параметры экспорта
        hours = request.args.get('hours', 24, type=int)
        format_type = request.args.get('format', 'json')
        
        if hours > 168:  # Максимум неделя
            hours = 168
        
        if format_type not in ['json', 'csv']:
            return jsonify({
                'error': 'Поддерживаемые форматы: json, csv'
            }), 400
        
        # TODO: Реализовать экспорт логов
        return jsonify({
            'message': 'Функция экспорта логов будет реализована в следующей версии',
            'requested_hours': hours,
            'requested_format': format_type
        })
        
    except Exception as e:
        logger.error(f"Ошибка экспорта логов: {str(e)}")
        return jsonify({
            'error': 'Ошибка экспорта логов'
        }), 500

@monitoring_bp.route('/settings', methods=['GET'])
@require_admin()
@log_request
def get_monitoring_settings():
    """Получение настроек мониторинга"""
    if not monitoring_service:
        return jsonify({
            'error': 'Monitoring service unavailable'
        }), 503
    
    try:
        return jsonify({
            'settings': monitoring_service.monitoring_settings,
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Ошибка получения настроек мониторинга: {str(e)}")
        return jsonify({
            'error': 'Ошибка получения настроек'
        }), 500

@monitoring_bp.route('/settings', methods=['PUT'])
@require_admin()
@log_request
def update_monitoring_settings():
    """Обновление настроек мониторинга"""
    if not monitoring_service:
        return jsonify({
            'error': 'Monitoring service unavailable'
        }), 503
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'error': 'Данные не предоставлены'
            }), 400
        
        # Валидация настроек
        valid_settings = [
            'log_retention_days', 'metrics_retention_days', 
            'alert_thresholds', 'sampling_rate'
        ]
        
        updated_settings = {}
        for key, value in data.items():
            if key in valid_settings:
                updated_settings[key] = value
        
        if not updated_settings:
            return jsonify({
                'error': f'Нет валидных настроек для обновления. Доступные: {", ".join(valid_settings)}'
            }), 400
        
        # Обновляем настройки
        monitoring_service.monitoring_settings.update(updated_settings)
        
        return jsonify({
            'message': 'Настройки мониторинга обновлены',
            'updated_settings': updated_settings,
            'current_settings': monitoring_service.monitoring_settings,
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Ошибка обновления настроек мониторинга: {str(e)}")
        return jsonify({
            'error': 'Ошибка обновления настроек'
        }), 500

@monitoring_bp.route('/nlp-status', methods=['GET'])
@optional_auth()
@log_request
def get_nlp_status():
    """Получение статуса NLP системы"""
    try:
        if not EnhancedNLPAnalyzer:
            return jsonify({
                'nlp_available': False,
                'error': 'Enhanced NLP Analyzer not available',
                'status': 'unavailable'
            })
        
        # Создаем экземпляр анализатора для проверки статуса
        nlp_analyzer = EnhancedNLPAnalyzer()
        status = nlp_analyzer.get_nlp_status()
        
        return jsonify({
            'nlp_status': status,
            'status': 'success',
            'timestamp': time.time()
        })
        
    except Exception as e:
        logger.error(f"Ошибка получения статуса NLP: {str(e)}")
        return jsonify({
            'nlp_available': False,
            'error': str(e),
            'status': 'error'
        }), 500

@monitoring_bp.route('/nlp-test', methods=['POST'])
@require_auth(permissions=['monitoring'])
@log_request
def test_nlp_system():
    """Тестирование NLP системы"""
    try:
        if not EnhancedNLPAnalyzer:
            return jsonify({
                'error': 'Enhanced NLP Analyzer not available'
            }), 503
        
        data = request.get_json()
        test_text = data.get('text', 'Профессор Иван Иванович работает в Московском университете. Его email: test@university.ru')
        test_email = data.get('email', 'test@university.ru')
        
        # Создаем экземпляр анализатора
        nlp_analyzer = EnhancedNLPAnalyzer()
        
        # Тестируем анализ
        if nlp_analyzer.is_nlp_initialized:
            # Создаем mock результаты поиска для тестирования
            mock_search_results = [
                {
                    'title': 'Test University Profile',
                    'snippet': test_text,
                    'url': 'https://test.university.edu/profile'
                }
            ]
            
            # Запускаем тестовый анализ
            test_results = nlp_analyzer.analyze_email_search_results(
                test_email, mock_search_results
            )
            
            return jsonify({
                'test_completed': True,
                'test_input': {
                    'text': test_text,
                    'email': test_email
                },
                'test_results': test_results,
                'status': 'success'
            })
        else:
            return jsonify({
                'test_completed': False,
                'error': 'NLP system not properly initialized',
                'status': 'failed'
            }), 503
        
    except Exception as e:
        logger.error(f"Ошибка тестирования NLP: {str(e)}")
        return jsonify({
            'test_completed': False,
            'error': str(e),
            'status': 'error'
        }), 500

