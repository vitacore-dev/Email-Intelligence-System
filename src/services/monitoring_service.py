import sqlite3
import json
import time
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import os
import psutil
import threading
from collections import defaultdict, deque

logger = logging.getLogger(__name__)

class MonitoringService:
    """Сервис мониторинга и логирования запросов"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
            os.makedirs(db_dir, exist_ok=True)
            self.db_path = os.path.join(db_dir, 'email_search.db')
        else:
            self.db_path = db_path
        
        # Настройки мониторинга
        self.monitoring_settings = {
            'log_retention_days': 30,
            'metrics_retention_days': 7,
            'alert_thresholds': {
                'error_rate_percent': 5.0,
                'response_time_ms': 5000,
                'memory_usage_percent': 80.0,
                'cpu_usage_percent': 80.0
            },
            'sampling_rate': 1.0  # Логировать все запросы (1.0 = 100%)
        }
        
        # Метрики в памяти для быстрого доступа
        self.metrics_cache = {
            'request_count': defaultdict(int),
            'error_count': defaultdict(int),
            'response_times': defaultdict(list),
            'active_users': set(),
            'recent_requests': deque(maxlen=1000)
        }
        
        # Блокировка для thread-safe операций
        self.metrics_lock = threading.Lock()
        
        self.init_monitoring_tables()
        
        # Запускаем фоновые задачи
        self._start_background_tasks()
    
    def init_monitoring_tables(self):
        """Инициализация таблиц мониторинга"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Таблица логов запросов
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS monitoring_request_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        request_id TEXT,
                        user_id INTEGER,
                        ip_address TEXT,
                        user_agent TEXT,
                        method TEXT NOT NULL,
                        endpoint TEXT NOT NULL,
                        email_searched TEXT,
                        response_status INTEGER,
                        response_time_ms REAL,
                        request_size_bytes INTEGER,
                        response_size_bytes INTEGER,
                        error_message TEXT,
                        metadata TEXT,  -- JSON для дополнительных данных
                        auth_method TEXT,
                        rate_limited BOOLEAN DEFAULT FALSE,
                        cache_hit BOOLEAN DEFAULT FALSE
                    )
                ''')
                
                # Таблица системных метрик
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS monitoring_system_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        cpu_usage_percent REAL,
                        memory_usage_percent REAL,
                        memory_used_mb REAL,
                        disk_usage_percent REAL,
                        active_connections INTEGER,
                        active_users INTEGER,
                        requests_per_minute REAL,
                        error_rate_percent REAL,
                        avg_response_time_ms REAL
                    )
                ''')
                
                # Таблица алертов
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS monitoring_alerts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        alert_type TEXT NOT NULL,
                        severity TEXT NOT NULL,  -- 'low', 'medium', 'high', 'critical'
                        title TEXT NOT NULL,
                        description TEXT,
                        metric_name TEXT,
                        metric_value REAL,
                        threshold_value REAL,
                        is_resolved BOOLEAN DEFAULT FALSE,
                        resolved_at TIMESTAMP,
                        metadata TEXT
                    )
                ''')
                
                # Таблица агрегированной статистики
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS monitoring_stats_hourly (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        hour_timestamp TIMESTAMP NOT NULL,
                        total_requests INTEGER DEFAULT 0,
                        successful_requests INTEGER DEFAULT 0,
                        error_requests INTEGER DEFAULT 0,
                        unique_users INTEGER DEFAULT 0,
                        unique_ips INTEGER DEFAULT 0,
                        avg_response_time_ms REAL,
                        max_response_time_ms REAL,
                        min_response_time_ms REAL,
                        cache_hit_rate REAL,
                        rate_limited_requests INTEGER DEFAULT 0,
                        search_requests INTEGER DEFAULT 0,
                        api_key_requests INTEGER DEFAULT 0,
                        jwt_requests INTEGER DEFAULT 0,
                        UNIQUE(hour_timestamp)
                    )
                ''')
                
                # Индексы для оптимизации
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_request_logs_timestamp ON monitoring_request_logs(timestamp)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_request_logs_user ON monitoring_request_logs(user_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_request_logs_endpoint ON monitoring_request_logs(endpoint)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_request_logs_status ON monitoring_request_logs(response_status)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_system_metrics_timestamp ON monitoring_system_metrics(timestamp)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON monitoring_alerts(timestamp)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_alerts_type ON monitoring_alerts(alert_type)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_stats_hourly_timestamp ON monitoring_stats_hourly(hour_timestamp)')
                
                conn.commit()
                logger.info("Таблицы мониторинга инициализированы")
                
        except Exception as e:
            logger.error(f"Ошибка инициализации таблиц мониторинга: {str(e)}")
            raise
    
    def log_request(self, request_data: Dict[str, Any]):
        """Логирование запроса"""
        try:
            # Проверяем sampling rate
            if self.monitoring_settings['sampling_rate'] < 1.0:
                import random
                if random.random() > self.monitoring_settings['sampling_rate']:
                    return
            
            # Обновляем метрики в памяти
            with self.metrics_lock:
                endpoint = request_data.get('endpoint', 'unknown')
                status = request_data.get('response_status', 0)
                response_time = request_data.get('response_time_ms', 0)
                user_id = request_data.get('user_id')
                
                # Счетчики запросов
                self.metrics_cache['request_count'][endpoint] += 1
                
                # Счетчики ошибок
                if status >= 400:
                    self.metrics_cache['error_count'][endpoint] += 1
                
                # Время ответа
                self.metrics_cache['response_times'][endpoint].append(response_time)
                # Ограничиваем размер списка
                if len(self.metrics_cache['response_times'][endpoint]) > 100:
                    self.metrics_cache['response_times'][endpoint] = \
                        self.metrics_cache['response_times'][endpoint][-100:]
                
                # Активные пользователи
                if user_id:
                    self.metrics_cache['active_users'].add(user_id)
                
                # Последние запросы
                self.metrics_cache['recent_requests'].append({
                    'timestamp': time.time(),
                    'endpoint': endpoint,
                    'status': status,
                    'response_time': response_time,
                    'user_id': user_id
                })
            
            # Сохраняем в базу данных
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                metadata_str = None
                if request_data.get('metadata'):
                    metadata_str = json.dumps(request_data['metadata'])
                
                cursor.execute('''
                    INSERT INTO monitoring_request_logs 
                    (request_id, user_id, ip_address, user_agent, method, endpoint, 
                     email_searched, response_status, response_time_ms, request_size_bytes, 
                     response_size_bytes, error_message, metadata, auth_method, 
                     rate_limited, cache_hit)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    request_data.get('request_id'),
                    request_data.get('user_id'),
                    request_data.get('ip_address'),
                    request_data.get('user_agent'),
                    request_data.get('method'),
                    request_data.get('endpoint'),
                    request_data.get('email_searched'),
                    request_data.get('response_status'),
                    request_data.get('response_time_ms'),
                    request_data.get('request_size_bytes'),
                    request_data.get('response_size_bytes'),
                    request_data.get('error_message'),
                    metadata_str,
                    request_data.get('auth_method'),
                    request_data.get('rate_limited', False),
                    request_data.get('cache_hit', False)
                ))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Ошибка логирования запроса: {str(e)}")
    
    def log_system_metrics(self):
        """Логирование системных метрик"""
        try:
            # Получаем системные метрики
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Получаем метрики приложения
            with self.metrics_lock:
                active_users_count = len(self.metrics_cache['active_users'])
                
                # Вычисляем requests per minute
                current_time = time.time()
                recent_requests = [
                    req for req in self.metrics_cache['recent_requests']
                    if current_time - req['timestamp'] <= 60
                ]
                requests_per_minute = len(recent_requests)
                
                # Вычисляем error rate
                total_requests = sum(self.metrics_cache['request_count'].values())
                total_errors = sum(self.metrics_cache['error_count'].values())
                error_rate = (total_errors / total_requests * 100) if total_requests > 0 else 0
                
                # Вычисляем среднее время ответа
                all_response_times = []
                for times in self.metrics_cache['response_times'].values():
                    all_response_times.extend(times)
                avg_response_time = sum(all_response_times) / len(all_response_times) if all_response_times else 0
            
            # Сохраняем в базу данных
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO monitoring_system_metrics 
                    (cpu_usage_percent, memory_usage_percent, memory_used_mb, 
                     disk_usage_percent, active_connections, active_users, 
                     requests_per_minute, error_rate_percent, avg_response_time_ms)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    cpu_percent,
                    memory.percent,
                    memory.used / 1024 / 1024,  # MB
                    disk.percent,
                    0,  # TODO: Подсчет активных соединений
                    active_users_count,
                    requests_per_minute,
                    error_rate,
                    avg_response_time
                ))
                
                conn.commit()
            
            # Проверяем пороги для алертов
            self._check_alert_thresholds({
                'cpu_usage_percent': cpu_percent,
                'memory_usage_percent': memory.percent,
                'error_rate_percent': error_rate,
                'avg_response_time_ms': avg_response_time
            })
            
        except Exception as e:
            logger.error(f"Ошибка логирования системных метрик: {str(e)}")
    
    def _check_alert_thresholds(self, metrics: Dict[str, float]):
        """Проверка порогов для создания алертов"""
        try:
            thresholds = self.monitoring_settings['alert_thresholds']
            
            for metric_name, value in metrics.items():
                if metric_name in thresholds:
                    threshold = thresholds[metric_name]
                    
                    if value > threshold:
                        # Проверяем, не создавали ли мы уже алерт недавно
                        if not self._has_recent_alert(metric_name):
                            severity = self._get_alert_severity(metric_name, value, threshold)
                            self._create_alert(metric_name, value, threshold, severity)
                        
        except Exception as e:
            logger.error(f"Ошибка проверки порогов алертов: {str(e)}")
    
    def _has_recent_alert(self, metric_name: str, minutes: int = 15) -> bool:
        """Проверка наличия недавнего алерта для метрики"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT COUNT(*) FROM monitoring_alerts 
                    WHERE metric_name = ? AND is_resolved = 0 
                    AND timestamp > datetime('now', '-{} minutes')
                '''.format(minutes), (metric_name,))
                
                return cursor.fetchone()[0] > 0
                
        except Exception as e:
            logger.error(f"Ошибка проверки недавних алертов: {str(e)}")
            return False
    
    def _get_alert_severity(self, metric_name: str, value: float, threshold: float) -> str:
        """Определение серьезности алерта"""
        ratio = value / threshold
        
        if ratio >= 2.0:
            return 'critical'
        elif ratio >= 1.5:
            return 'high'
        elif ratio >= 1.2:
            return 'medium'
        else:
            return 'low'
    
    def _create_alert(self, metric_name: str, value: float, threshold: float, severity: str):
        """Создание алерта"""
        try:
            title = f"Превышен порог для {metric_name}"
            description = f"Значение {value:.2f} превышает порог {threshold:.2f}"
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO monitoring_alerts 
                    (alert_type, severity, title, description, metric_name, 
                     metric_value, threshold_value)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', ('threshold_exceeded', severity, title, description, 
                      metric_name, value, threshold))
                
                conn.commit()
                
            logger.warning(f"Создан алерт [{severity}]: {title} - {description}")
            
        except Exception as e:
            logger.error(f"Ошибка создания алерта: {str(e)}")
    
    def get_dashboard_metrics(self) -> Dict[str, Any]:
        """Получение метрик для дашборда"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Статистика за последние 24 часа
                cursor.execute('''
                    SELECT 
                        COUNT(*) as total_requests,
                        COUNT(CASE WHEN response_status < 400 THEN 1 END) as successful_requests,
                        COUNT(CASE WHEN response_status >= 400 THEN 1 END) as error_requests,
                        COUNT(DISTINCT user_id) as unique_users,
                        COUNT(DISTINCT ip_address) as unique_ips,
                        AVG(response_time_ms) as avg_response_time,
                        MAX(response_time_ms) as max_response_time,
                        COUNT(CASE WHEN cache_hit = 1 THEN 1 END) as cache_hits,
                        COUNT(CASE WHEN rate_limited = 1 THEN 1 END) as rate_limited_requests
                    FROM monitoring_request_logs 
                    WHERE timestamp >= datetime('now', '-1 day')
                ''')
                
                stats_24h = cursor.fetchone()
                
                # Последние системные метрики
                cursor.execute('''
                    SELECT cpu_usage_percent, memory_usage_percent, disk_usage_percent,
                           active_users, requests_per_minute, error_rate_percent, 
                           avg_response_time_ms
                    FROM monitoring_system_metrics 
                    ORDER BY timestamp DESC LIMIT 1
                ''')
                
                system_metrics = cursor.fetchone()
                
                # Активные алерты
                cursor.execute('''
                    SELECT COUNT(*) as total_alerts,
                           COUNT(CASE WHEN severity = 'critical' THEN 1 END) as critical_alerts,
                           COUNT(CASE WHEN severity = 'high' THEN 1 END) as high_alerts
                    FROM monitoring_alerts 
                    WHERE is_resolved = 0
                ''')
                
                alerts = cursor.fetchone()
                
                # Топ endpoints по количеству запросов
                cursor.execute('''
                    SELECT endpoint, COUNT(*) as request_count,
                           AVG(response_time_ms) as avg_response_time,
                           COUNT(CASE WHEN response_status >= 400 THEN 1 END) as error_count
                    FROM monitoring_request_logs 
                    WHERE timestamp >= datetime('now', '-1 day')
                    GROUP BY endpoint
                    ORDER BY request_count DESC
                    LIMIT 10
                ''')
                
                top_endpoints = [
                    {
                        'endpoint': row[0],
                        'request_count': row[1],
                        'avg_response_time': row[2] or 0,
                        'error_count': row[3]
                    }
                    for row in cursor.fetchall()
                ]
                
                # Метрики в памяти
                with self.metrics_lock:
                    memory_metrics = {
                        'active_users_count': len(self.metrics_cache['active_users']),
                        'recent_requests_count': len(self.metrics_cache['recent_requests'])
                    }
                
                return {
                    'stats_24h': {
                        'total_requests': stats_24h[0] or 0,
                        'successful_requests': stats_24h[1] or 0,
                        'error_requests': stats_24h[2] or 0,
                        'unique_users': stats_24h[3] or 0,
                        'unique_ips': stats_24h[4] or 0,
                        'avg_response_time': stats_24h[5] or 0,
                        'max_response_time': stats_24h[6] or 0,
                        'cache_hits': stats_24h[7] or 0,
                        'rate_limited_requests': stats_24h[8] or 0,
                        'cache_hit_rate': (stats_24h[7] / stats_24h[0] * 100) if stats_24h[0] > 0 else 0,
                        'error_rate': (stats_24h[2] / stats_24h[0] * 100) if stats_24h[0] > 0 else 0
                    },
                    'system_metrics': {
                        'cpu_usage_percent': system_metrics[0] if system_metrics else 0,
                        'memory_usage_percent': system_metrics[1] if system_metrics else 0,
                        'disk_usage_percent': system_metrics[2] if system_metrics else 0,
                        'active_users': system_metrics[3] if system_metrics else 0,
                        'requests_per_minute': system_metrics[4] if system_metrics else 0,
                        'error_rate_percent': system_metrics[5] if system_metrics else 0,
                        'avg_response_time_ms': system_metrics[6] if system_metrics else 0
                    },
                    'alerts': {
                        'total_alerts': alerts[0] or 0,
                        'critical_alerts': alerts[1] or 0,
                        'high_alerts': alerts[2] or 0
                    },
                    'top_endpoints': top_endpoints,
                    'memory_metrics': memory_metrics,
                    'timestamp': time.time()
                }
                
        except Exception as e:
            logger.error(f"Ошибка получения метрик дашборда: {str(e)}")
            return {}
    
    def get_time_series_data(self, metric: str, hours: int = 24) -> List[Dict[str, Any]]:
        """Получение данных временных рядов для графиков"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if metric == 'requests':
                    cursor.execute('''
                        SELECT 
                            datetime(timestamp, 'start of hour') as hour,
                            COUNT(*) as value
                        FROM monitoring_request_logs 
                        WHERE timestamp >= datetime('now', '-{} hours')
                        GROUP BY datetime(timestamp, 'start of hour')
                        ORDER BY hour
                    '''.format(hours))
                    
                elif metric == 'response_time':
                    cursor.execute('''
                        SELECT 
                            datetime(timestamp, 'start of hour') as hour,
                            AVG(response_time_ms) as value
                        FROM monitoring_request_logs 
                        WHERE timestamp >= datetime('now', '-{} hours')
                        GROUP BY datetime(timestamp, 'start of hour')
                        ORDER BY hour
                    '''.format(hours))
                    
                elif metric == 'error_rate':
                    cursor.execute('''
                        SELECT 
                            datetime(timestamp, 'start of hour') as hour,
                            COUNT(CASE WHEN response_status >= 400 THEN 1 END) * 100.0 / COUNT(*) as value
                        FROM monitoring_request_logs 
                        WHERE timestamp >= datetime('now', '-{} hours')
                        GROUP BY datetime(timestamp, 'start of hour')
                        ORDER BY hour
                    '''.format(hours))
                    
                elif metric == 'cpu_usage':
                    cursor.execute('''
                        SELECT 
                            datetime(timestamp, 'start of hour') as hour,
                            AVG(cpu_usage_percent) as value
                        FROM monitoring_system_metrics 
                        WHERE timestamp >= datetime('now', '-{} hours')
                        GROUP BY datetime(timestamp, 'start of hour')
                        ORDER BY hour
                    '''.format(hours))
                    
                elif metric == 'memory_usage':
                    cursor.execute('''
                        SELECT 
                            datetime(timestamp, 'start of hour') as hour,
                            AVG(memory_usage_percent) as value
                        FROM monitoring_system_metrics 
                        WHERE timestamp >= datetime('now', '-{} hours')
                        GROUP BY datetime(timestamp, 'start of hour')
                        ORDER BY hour
                    '''.format(hours))
                    
                else:
                    return []
                
                return [
                    {'timestamp': row[0], 'value': row[1] or 0}
                    for row in cursor.fetchall()
                ]
                
        except Exception as e:
            logger.error(f"Ошибка получения данных временных рядов: {str(e)}")
            return []
    
    def get_alerts(self, limit: int = 50, severity: str = None) -> List[Dict[str, Any]]:
        """Получение списка алертов"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                query = '''
                    SELECT id, timestamp, alert_type, severity, title, description,
                           metric_name, metric_value, threshold_value, is_resolved, resolved_at
                    FROM monitoring_alerts 
                '''
                params = []
                
                if severity:
                    query += ' WHERE severity = ?'
                    params.append(severity)
                
                query += ' ORDER BY timestamp DESC LIMIT ?'
                params.append(limit)
                
                cursor.execute(query, params)
                
                return [
                    {
                        'id': row[0],
                        'timestamp': row[1],
                        'alert_type': row[2],
                        'severity': row[3],
                        'title': row[4],
                        'description': row[5],
                        'metric_name': row[6],
                        'metric_value': row[7],
                        'threshold_value': row[8],
                        'is_resolved': bool(row[9]),
                        'resolved_at': row[10]
                    }
                    for row in cursor.fetchall()
                ]
                
        except Exception as e:
            logger.error(f"Ошибка получения алертов: {str(e)}")
            return []
    
    def resolve_alert(self, alert_id: int) -> bool:
        """Разрешение алерта"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    UPDATE monitoring_alerts 
                    SET is_resolved = 1, resolved_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (alert_id,))
                
                conn.commit()
                return cursor.rowcount > 0
                
        except Exception as e:
            logger.error(f"Ошибка разрешения алерта: {str(e)}")
            return False
    
    def cleanup_old_data(self) -> Dict[str, int]:
        """Очистка старых данных мониторинга"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Очищаем старые логи запросов
                log_cutoff = datetime.now() - timedelta(days=self.monitoring_settings['log_retention_days'])
                cursor.execute('''
                    DELETE FROM monitoring_request_logs 
                    WHERE timestamp < ?
                ''', (log_cutoff,))
                logs_deleted = cursor.rowcount
                
                # Очищаем старые системные метрики
                metrics_cutoff = datetime.now() - timedelta(days=self.monitoring_settings['metrics_retention_days'])
                cursor.execute('''
                    DELETE FROM monitoring_system_metrics 
                    WHERE timestamp < ?
                ''', (metrics_cutoff,))
                metrics_deleted = cursor.rowcount
                
                # Удаляем разрешенные алерты старше 7 дней
                alerts_cutoff = datetime.now() - timedelta(days=7)
                cursor.execute('''
                    DELETE FROM monitoring_alerts 
                    WHERE is_resolved = 1 AND resolved_at < ?
                ''', (alerts_cutoff,))
                alerts_deleted = cursor.rowcount
                
                conn.commit()
                
                logger.info(f"Очищено: {logs_deleted} логов, {metrics_deleted} метрик, {alerts_deleted} алертов")
                
                return {
                    'logs_deleted': logs_deleted,
                    'metrics_deleted': metrics_deleted,
                    'alerts_deleted': alerts_deleted
                }
                
        except Exception as e:
            logger.error(f"Ошибка очистки старых данных: {str(e)}")
            return {}
    
    def _start_background_tasks(self):
        """Запуск фоновых задач мониторинга"""
        def system_metrics_collector():
            while True:
                try:
                    self.log_system_metrics()
                    time.sleep(60)  # Каждую минуту
                except Exception as e:
                    logger.error(f"Ошибка в сборщике системных метрик: {str(e)}")
                    time.sleep(60)
        
        def cleanup_task():
            while True:
                try:
                    time.sleep(3600)  # Каждый час
                    self.cleanup_old_data()
                except Exception as e:
                    logger.error(f"Ошибка в задаче очистки: {str(e)}")
        
        # Запускаем в отдельных потоках
        metrics_thread = threading.Thread(target=system_metrics_collector, daemon=True)
        cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
        
        metrics_thread.start()
        cleanup_thread.start()
        
        logger.info("Фоновые задачи мониторинга запущены")

