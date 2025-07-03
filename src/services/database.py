import sqlite3
import json
import time
import hashlib
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import os

logger = logging.getLogger(__name__)

class DatabaseService:
    """Сервис для работы с базой данных и кэшированием результатов"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            # Создаем папку для базы данных если её нет
            db_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
            os.makedirs(db_dir, exist_ok=True)
            self.db_path = os.path.join(db_dir, 'email_search.db')
        else:
            self.db_path = db_path
        
        self.init_database()
    
    def init_database(self):
        """Инициализация базы данных и создание таблиц"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Таблица для кэширования результатов поиска
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS search_cache (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        email_hash TEXT UNIQUE NOT NULL,
                        email TEXT NOT NULL,
                        search_results TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP NOT NULL,
                        hit_count INTEGER DEFAULT 0,
                        search_method TEXT DEFAULT 'unknown'
                    )
                ''')
                
                # Таблица для логирования запросов
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS search_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        email_hash TEXT NOT NULL,
                        email TEXT NOT NULL,
                        ip_address TEXT,
                        user_agent TEXT,
                        search_method TEXT,
                        results_count INTEGER DEFAULT 0,
                        processing_time REAL DEFAULT 0.0,
                        cache_hit BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        status TEXT DEFAULT 'success',
                        error_message TEXT
                    )
                ''')
                
                # Таблица для статистики
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS search_stats (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        date DATE NOT NULL,
                        total_searches INTEGER DEFAULT 0,
                        cache_hits INTEGER DEFAULT 0,
                        unique_emails INTEGER DEFAULT 0,
                        avg_processing_time REAL DEFAULT 0.0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(date)
                    )
                ''')
                
                # Таблица для rate limiting
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS rate_limits (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ip_address TEXT NOT NULL,
                        email_hash TEXT,
                        request_count INTEGER DEFAULT 1,
                        window_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_request TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        blocked_until TIMESTAMP,
                        UNIQUE(ip_address, email_hash)
                    )
                ''')
                
                # Индексы для оптимизации
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_email_hash ON search_cache(email_hash)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_expires_at ON search_cache(expires_at)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_search_logs_created ON search_logs(created_at)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_rate_limits_ip ON rate_limits(ip_address)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_stats_date ON search_stats(date)')
                
                conn.commit()
                logger.info(f"База данных инициализирована: {self.db_path}")
                
        except Exception as e:
            logger.error(f"Ошибка инициализации базы данных: {str(e)}")
            raise
    
    def _hash_email(self, email: str) -> str:
        """Создание хэша email для безопасного хранения"""
        return hashlib.sha256(email.encode()).hexdigest()
    
    def get_cached_result(self, email: str) -> Optional[Dict[str, Any]]:
        """Получение кэшированного результата поиска"""
        try:
            email_hash = self._hash_email(email)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Проверяем наличие актуального кэша
                cursor.execute('''
                    SELECT search_results, hit_count, created_at 
                    FROM search_cache 
                    WHERE email_hash = ? AND expires_at > CURRENT_TIMESTAMP
                ''', (email_hash,))
                
                result = cursor.fetchone()
                
                if result:
                    # Увеличиваем счетчик обращений
                    cursor.execute('''
                        UPDATE search_cache 
                        SET hit_count = hit_count + 1, updated_at = CURRENT_TIMESTAMP
                        WHERE email_hash = ?
                    ''', (email_hash,))
                    
                    conn.commit()
                    
                    # Парсим JSON результат
                    search_data = json.loads(result[0])
                    search_data['cache_info'] = {
                        'cached': True,
                        'hit_count': result[1] + 1,
                        'cached_at': result[2]
                    }
                    
                    logger.info(f"Найден кэшированный результат для email: {email}")
                    return search_data
                
                return None
                
        except Exception as e:
            logger.error(f"Ошибка получения кэша для email {email}: {str(e)}")
            return None
    
    def cache_search_result(self, email: str, search_data: Dict[str, Any], 
                          cache_duration_hours: int = 24) -> bool:
        """Кэширование результата поиска"""
        try:
            email_hash = self._hash_email(email)
            expires_at = datetime.now() + timedelta(hours=cache_duration_hours)
            
            # Удаляем cache_info если есть, чтобы не сохранять в кэш
            search_data_copy = search_data.copy()
            search_data_copy.pop('cache_info', None)
            
            search_results_json = json.dumps(search_data_copy, ensure_ascii=False)
            search_method = search_data.get('search_metadata', {}).get('search_method', 'unknown')
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Используем INSERT OR REPLACE для обновления существующих записей
                cursor.execute('''
                    INSERT OR REPLACE INTO search_cache 
                    (email_hash, email, search_results, expires_at, search_method, hit_count)
                    VALUES (?, ?, ?, ?, ?, COALESCE(
                        (SELECT hit_count FROM search_cache WHERE email_hash = ?), 0
                    ))
                ''', (email_hash, email, search_results_json, expires_at, search_method, email_hash))
                
                conn.commit()
                logger.info(f"Результат кэширован для email: {email}")
                return True
                
        except Exception as e:
            logger.error(f"Ошибка кэширования для email {email}: {str(e)}")
            return False
    
    def log_search_request(self, email: str, ip_address: str = None, 
                          user_agent: str = None, search_method: str = 'unknown',
                          results_count: int = 0, processing_time: float = 0.0,
                          cache_hit: bool = False, status: str = 'success',
                          error_message: str = None) -> bool:
        """Логирование запроса поиска"""
        try:
            email_hash = self._hash_email(email)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO search_logs 
                    (email_hash, email, ip_address, user_agent, search_method, 
                     results_count, processing_time, cache_hit, status, error_message)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (email_hash, email, ip_address, user_agent, search_method,
                      results_count, processing_time, cache_hit, status, error_message))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Ошибка логирования запроса: {str(e)}")
            return False
    
    def update_daily_stats(self, date: str = None) -> bool:
        """Обновление ежедневной статистики"""
        try:
            if date is None:
                date = datetime.now().strftime('%Y-%m-%d')
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Получаем статистику за день
                cursor.execute('''
                    SELECT 
                        COUNT(*) as total_searches,
                        SUM(CASE WHEN cache_hit = 1 THEN 1 ELSE 0 END) as cache_hits,
                        COUNT(DISTINCT email_hash) as unique_emails,
                        AVG(processing_time) as avg_processing_time
                    FROM search_logs 
                    WHERE DATE(created_at) = ?
                ''', (date,))
                
                stats = cursor.fetchone()
                
                if stats and stats[0] > 0:
                    cursor.execute('''
                        INSERT OR REPLACE INTO search_stats 
                        (date, total_searches, cache_hits, unique_emails, avg_processing_time)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (date, stats[0], stats[1], stats[2], stats[3] or 0.0))
                    
                    conn.commit()
                    logger.info(f"Статистика обновлена для даты: {date}")
                    return True
                
                return False
                
        except Exception as e:
            logger.error(f"Ошибка обновления статистики: {str(e)}")
            return False
    
    def cleanup_expired_cache(self) -> int:
        """Очистка устаревшего кэша"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Удаляем устаревшие записи
                cursor.execute('''
                    DELETE FROM search_cache 
                    WHERE expires_at < CURRENT_TIMESTAMP
                ''')
                
                deleted_count = cursor.rowcount
                conn.commit()
                
                if deleted_count > 0:
                    logger.info(f"Удалено {deleted_count} устаревших записей из кэша")
                
                return deleted_count
                
        except Exception as e:
            logger.error(f"Ошибка очистки кэша: {str(e)}")
            return 0
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Получение статистики кэша"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Общая статистика кэша
                cursor.execute('''
                    SELECT 
                        COUNT(*) as total_cached,
                        COUNT(CASE WHEN expires_at > CURRENT_TIMESTAMP THEN 1 END) as active_cached,
                        SUM(hit_count) as total_hits,
                        AVG(hit_count) as avg_hits_per_entry
                    FROM search_cache
                ''')
                
                cache_stats = cursor.fetchone()
                
                # Статистика по методам поиска
                cursor.execute('''
                    SELECT search_method, COUNT(*) as count
                    FROM search_cache
                    WHERE expires_at > CURRENT_TIMESTAMP
                    GROUP BY search_method
                ''')
                
                method_stats = dict(cursor.fetchall())
                
                return {
                    'total_cached_entries': cache_stats[0] or 0,
                    'active_cached_entries': cache_stats[1] or 0,
                    'total_cache_hits': cache_stats[2] or 0,
                    'average_hits_per_entry': round(cache_stats[3] or 0, 2),
                    'cache_by_method': method_stats,
                    'cache_hit_ratio': self._calculate_cache_hit_ratio()
                }
                
        except Exception as e:
            logger.error(f"Ошибка получения статистики кэша: {str(e)}")
            return {}
    
    def _calculate_cache_hit_ratio(self) -> float:
        """Расчет коэффициента попаданий в кэш"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT 
                        COUNT(*) as total_requests,
                        SUM(CASE WHEN cache_hit = 1 THEN 1 ELSE 0 END) as cache_hits
                    FROM search_logs
                    WHERE created_at >= datetime('now', '-7 days')
                ''')
                
                result = cursor.fetchone()
                
                if result and result[0] > 0:
                    return round((result[1] / result[0]) * 100, 2)
                
                return 0.0
                
        except Exception as e:
            logger.error(f"Ошибка расчета cache hit ratio: {str(e)}")
            return 0.0
    
    def get_search_analytics(self, days: int = 7) -> Dict[str, Any]:
        """Получение аналитики поисковых запросов"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Общая статистика за период
                cursor.execute('''
                    SELECT 
                        COUNT(*) as total_searches,
                        COUNT(DISTINCT email_hash) as unique_emails,
                        AVG(processing_time) as avg_processing_time,
                        SUM(CASE WHEN cache_hit = 1 THEN 1 ELSE 0 END) as cache_hits,
                        COUNT(DISTINCT ip_address) as unique_ips
                    FROM search_logs
                    WHERE created_at >= datetime('now', '-{} days')
                '''.format(days))
                
                general_stats = cursor.fetchone()
                
                # Статистика по дням
                cursor.execute('''
                    SELECT 
                        DATE(created_at) as date,
                        COUNT(*) as searches,
                        COUNT(DISTINCT email_hash) as unique_emails
                    FROM search_logs
                    WHERE created_at >= datetime('now', '-{} days')
                    GROUP BY DATE(created_at)
                    ORDER BY date DESC
                '''.format(days))
                
                daily_stats = [
                    {'date': row[0], 'searches': row[1], 'unique_emails': row[2]}
                    for row in cursor.fetchall()
                ]
                
                # Топ поисковых методов
                cursor.execute('''
                    SELECT search_method, COUNT(*) as count
                    FROM search_logs
                    WHERE created_at >= datetime('now', '-{} days')
                    GROUP BY search_method
                    ORDER BY count DESC
                '''.format(days))
                
                method_stats = dict(cursor.fetchall())
                
                return {
                    'period_days': days,
                    'total_searches': general_stats[0] or 0,
                    'unique_emails': general_stats[1] or 0,
                    'average_processing_time': round(general_stats[2] or 0, 3),
                    'cache_hits': general_stats[3] or 0,
                    'unique_ips': general_stats[4] or 0,
                    'cache_hit_ratio': round(
                        (general_stats[3] / general_stats[0] * 100) if general_stats[0] > 0 else 0, 2
                    ),
                    'daily_breakdown': daily_stats,
                    'search_methods': method_stats
                }
                
        except Exception as e:
            logger.error(f"Ошибка получения аналитики: {str(e)}")
            return {}
    
    def delete_email_data(self, email: str) -> Dict[str, int]:
        """Удаление всех данных для конкретного email"""
        try:
            email_hash = self._hash_email(email)
            deleted_counts = {}
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Удаляем из кэша
                cursor.execute('DELETE FROM search_cache WHERE email_hash = ?', (email_hash,))
                deleted_counts['cache'] = cursor.rowcount
                
                # Удаляем из логов
                cursor.execute('DELETE FROM search_logs WHERE email_hash = ?', (email_hash,))
                deleted_counts['logs'] = cursor.rowcount
                
                # Удаляем из rate limits
                cursor.execute('DELETE FROM rate_limits WHERE email_hash = ?', (email_hash,))
                deleted_counts['rate_limits'] = cursor.rowcount
                
                conn.commit()
                
                total_deleted = sum(deleted_counts.values())
                logger.info(f"Удалены данные для email {email}: {deleted_counts}")
                
                return {
                    'email': email,
                    'total_deleted': total_deleted,
                    'details': deleted_counts
                }
                
        except Exception as e:
            logger.error(f"Ошибка удаления данных для email {email}: {str(e)}")
            return {'error': str(e)}
    
    def delete_all_email_data(self) -> Dict[str, int]:
        """Удаление всех данных email из системы"""
        try:
            deleted_counts = {}
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Удаляем все из кэша
                cursor.execute('DELETE FROM search_cache')
                deleted_counts['cache'] = cursor.rowcount
                
                # Удаляем все логи
                cursor.execute('DELETE FROM search_logs')
                deleted_counts['logs'] = cursor.rowcount
                
                # Удаляем все rate limits
                cursor.execute('DELETE FROM rate_limits')
                deleted_counts['rate_limits'] = cursor.rowcount
                
                # Удаляем статистику
                cursor.execute('DELETE FROM search_stats')
                deleted_counts['stats'] = cursor.rowcount
                
                conn.commit()
                
                total_deleted = sum(deleted_counts.values())
                logger.info(f"Удалены все данные email: {deleted_counts}")
                
                return {
                    'total_deleted': total_deleted,
                    'details': deleted_counts
                }
                
        except Exception as e:
            logger.error(f"Ошибка полной очистки данных email: {str(e)}")
            return {'error': str(e)}
    
    def get_email_data_stats(self) -> Dict[str, Any]:
        """Получение статистики хранимых данных email"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Статистика по таблицам
                stats = {}
                
                # Кэш
                cursor.execute('SELECT COUNT(*), COUNT(DISTINCT email_hash) FROM search_cache')
                cache_stats = cursor.fetchone()
                stats['cache'] = {
                    'total_entries': cache_stats[0],
                    'unique_emails': cache_stats[1]
                }
                
                # Логи
                cursor.execute('SELECT COUNT(*), COUNT(DISTINCT email_hash) FROM search_logs')
                log_stats = cursor.fetchone()
                stats['logs'] = {
                    'total_entries': log_stats[0],
                    'unique_emails': log_stats[1]
                }
                
                # Rate limits
                cursor.execute('SELECT COUNT(*), COUNT(DISTINCT email_hash) FROM rate_limits')
                rate_stats = cursor.fetchone()
                stats['rate_limits'] = {
                    'total_entries': rate_stats[0],
                    'unique_emails': rate_stats[1]
                }
                
                # Общая статистика
                cursor.execute('''
                    SELECT COUNT(DISTINCT email_hash) 
                    FROM (
                        SELECT email_hash FROM search_cache
                        UNION
                        SELECT email_hash FROM search_logs
                        UNION 
                        SELECT email_hash FROM rate_limits WHERE email_hash IS NOT NULL
                    )
                ''')
                
                total_unique = cursor.fetchone()[0]
                stats['total_unique_emails'] = total_unique
                
                return stats
                
        except Exception as e:
            logger.error(f"Ошибка получения статистики данных email: {str(e)}")
            return {'error': str(e)}
    
    def close(self):
        """Закрытие соединения с базой данных"""
        # SQLite автоматически закрывает соединения при использовании context manager
        pass

