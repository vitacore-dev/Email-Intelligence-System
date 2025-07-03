import sqlite3
import time
import hashlib
import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import os

logger = logging.getLogger(__name__)

class RateLimiter:
    """Сервис для ограничения частоты запросов (Rate Limiting)"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            # Используем ту же базу данных, что и для кэширования
            db_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
            os.makedirs(db_dir, exist_ok=True)
            self.db_path = os.path.join(db_dir, 'email_search.db')
        else:
            self.db_path = db_path
        
        # Настройки по умолчанию
        self.default_limits = {
            'requests_per_minute': 10,
            'requests_per_hour': 100,
            'requests_per_day': 1000,
            'burst_limit': 5,  # Максимум запросов в течение 10 секунд
            'burst_window': 10  # Окно для burst limit в секундах
        }
        
        # Настройки для разных типов пользователей
        self.user_type_limits = {
            'anonymous': {
                'requests_per_minute': 30,  # Увеличено для тестирования
                'requests_per_hour': 300,
                'requests_per_day': 1000,
                'burst_limit': 15,
                'burst_window': 10
            },
            'authenticated': {
                'requests_per_minute': 60,
                'requests_per_hour': 1000,
                'requests_per_day': 10000,
                'burst_limit': 25,
                'burst_window': 10
            },
            'premium': {
                'requests_per_minute': 200,
                'requests_per_hour': 5000,
                'requests_per_day': 50000,
                'burst_limit': 100,
                'burst_window': 10
            }
        }
        
        self.init_rate_limit_tables()
    
    def init_rate_limit_tables(self):
        """Инициализация таблиц для rate limiting"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Таблица для отслеживания запросов по IP
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS rate_limit_ip (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ip_address TEXT NOT NULL,
                        window_start TIMESTAMP NOT NULL,
                        window_type TEXT NOT NULL,  -- 'minute', 'hour', 'day', 'burst'
                        request_count INTEGER DEFAULT 1,
                        last_request TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        blocked_until TIMESTAMP,
                        user_type TEXT DEFAULT 'anonymous',
                        UNIQUE(ip_address, window_start, window_type)
                    )
                ''')
                
                # Таблица для отслеживания запросов по email
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS rate_limit_email (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        email_hash TEXT NOT NULL,
                        ip_address TEXT NOT NULL,
                        window_start TIMESTAMP NOT NULL,
                        window_type TEXT NOT NULL,
                        request_count INTEGER DEFAULT 1,
                        last_request TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        blocked_until TIMESTAMP,
                        UNIQUE(email_hash, ip_address, window_start, window_type)
                    )
                ''')
                
                # Таблица для блокировок
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS rate_limit_blocks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ip_address TEXT NOT NULL,
                        email_hash TEXT,
                        block_reason TEXT NOT NULL,
                        blocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        blocked_until TIMESTAMP NOT NULL,
                        block_count INTEGER DEFAULT 1,
                        is_active BOOLEAN DEFAULT TRUE
                    )
                ''')
                
                # Индексы для оптимизации
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_rate_limit_ip_addr ON rate_limit_ip(ip_address)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_rate_limit_ip_window ON rate_limit_ip(window_start, window_type)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_rate_limit_email_hash ON rate_limit_email(email_hash)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_rate_limit_blocks_ip ON rate_limit_blocks(ip_address)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_rate_limit_blocks_active ON rate_limit_blocks(is_active)')
                
                conn.commit()
                logger.info("Таблицы rate limiting инициализированы")
                
        except Exception as e:
            logger.error(f"Ошибка инициализации таблиц rate limiting: {str(e)}")
            raise
    
    def _hash_email(self, email: str) -> str:
        """Создание хэша email для безопасного хранения"""
        return hashlib.sha256(email.encode()).hexdigest()
    
    def _get_window_start(self, window_type: str, current_time: datetime = None) -> datetime:
        """Получение начала временного окна"""
        if current_time is None:
            current_time = datetime.now()
        
        if window_type == 'minute':
            return current_time.replace(second=0, microsecond=0)
        elif window_type == 'hour':
            return current_time.replace(minute=0, second=0, microsecond=0)
        elif window_type == 'day':
            return current_time.replace(hour=0, minute=0, second=0, microsecond=0)
        elif window_type == 'burst':
            # Для burst окна используем 10-секундные интервалы
            seconds = (current_time.second // 10) * 10
            return current_time.replace(second=seconds, microsecond=0)
        else:
            raise ValueError(f"Неизвестный тип окна: {window_type}")
    
    def check_rate_limit(self, ip_address: str, email: str = None, 
                        user_type: str = 'anonymous') -> Tuple[bool, Dict[str, Any]]:
        """
        Проверка ограничений частоты запросов
        
        Returns:
            Tuple[bool, Dict]: (allowed, info)
            - allowed: True если запрос разрешен, False если заблокирован
            - info: Информация о лимитах и текущем состоянии
        """
        try:
            current_time = datetime.now()
            limits = self.user_type_limits.get(user_type, self.default_limits)
            
            # Проверяем активные блокировки
            if self._is_blocked(ip_address, email):
                return False, {
                    'blocked': True,
                    'reason': 'IP или email заблокированы',
                    'retry_after': self._get_block_retry_time(ip_address, email)
                }
            
            # Проверяем лимиты по IP
            ip_check_result = self._check_ip_limits(ip_address, current_time, limits, user_type)
            if not ip_check_result['allowed']:
                return False, ip_check_result
            
            # Проверяем лимиты по email если указан
            if email:
                email_check_result = self._check_email_limits(
                    ip_address, email, current_time, limits
                )
                if not email_check_result['allowed']:
                    return False, email_check_result
            
            # Записываем успешный запрос
            self._record_request(ip_address, email, current_time, user_type)
            
            return True, {
                'allowed': True,
                'limits': limits,
                'current_usage': self._get_current_usage(ip_address, email, current_time),
                'reset_times': self._get_reset_times(current_time)
            }
            
        except Exception as e:
            logger.error(f"Ошибка проверки rate limit: {str(e)}")
            # В случае ошибки разрешаем запрос
            return True, {'allowed': True, 'error': str(e)}
    
    def _is_blocked(self, ip_address: str, email: str = None) -> bool:
        """Проверка активных блокировок"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Проверяем блокировку по IP
                cursor.execute('''
                    SELECT COUNT(*) FROM rate_limit_blocks 
                    WHERE ip_address = ? AND is_active = 1 
                    AND blocked_until > CURRENT_TIMESTAMP
                ''', (ip_address,))
                
                if cursor.fetchone()[0] > 0:
                    return True
                
                # Проверяем блокировку по email если указан
                if email:
                    email_hash = self._hash_email(email)
                    cursor.execute('''
                        SELECT COUNT(*) FROM rate_limit_blocks 
                        WHERE email_hash = ? AND is_active = 1 
                        AND blocked_until > CURRENT_TIMESTAMP
                    ''', (email_hash,))
                    
                    if cursor.fetchone()[0] > 0:
                        return True
                
                return False
                
        except Exception as e:
            logger.error(f"Ошибка проверки блокировок: {str(e)}")
            return False
    
    def _check_ip_limits(self, ip_address: str, current_time: datetime, 
                        limits: Dict[str, int], user_type: str) -> Dict[str, Any]:
        """Проверка лимитов по IP адресу"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Проверяем все типы окон
                for window_type, limit_key in [
                    ('burst', 'burst_limit'),
                    ('minute', 'requests_per_minute'),
                    ('hour', 'requests_per_hour'),
                    ('day', 'requests_per_day')
                ]:
                    window_start = self._get_window_start(window_type, current_time)
                    limit = limits[limit_key]
                    
                    # Получаем текущее количество запросов в окне
                    cursor.execute('''
                        SELECT request_count FROM rate_limit_ip 
                        WHERE ip_address = ? AND window_start = ? AND window_type = ?
                    ''', (ip_address, window_start, window_type))
                    
                    result = cursor.fetchone()
                    current_count = result[0] if result else 0
                    
                    if current_count >= limit:
                        # Блокируем на время до следующего окна
                        block_duration = self._get_block_duration(window_type)
                        self._add_block(ip_address, None, f'Превышен лимит {window_type}', block_duration)
                        
                        return {
                            'allowed': False,
                            'reason': f'Превышен лимит запросов за {window_type}',
                            'limit': limit,
                            'current': current_count,
                            'window_type': window_type,
                            'retry_after': block_duration
                        }
                
                return {'allowed': True}
                
        except Exception as e:
            logger.error(f"Ошибка проверки IP лимитов: {str(e)}")
            return {'allowed': True, 'error': str(e)}
    
    def _check_email_limits(self, ip_address: str, email: str, 
                           current_time: datetime, limits: Dict[str, int]) -> Dict[str, Any]:
        """Проверка лимитов по email"""
        try:
            email_hash = self._hash_email(email)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Проверяем лимиты по email (более строгие)
                email_limits = {
                    'minute': limits['requests_per_minute'] // 2,  # Половина от IP лимита
                    'hour': limits['requests_per_hour'] // 2,
                    'day': limits['requests_per_day'] // 2
                }
                
                for window_type, limit in email_limits.items():
                    window_start = self._get_window_start(window_type, current_time)
                    
                    cursor.execute('''
                        SELECT request_count FROM rate_limit_email 
                        WHERE email_hash = ? AND ip_address = ? 
                        AND window_start = ? AND window_type = ?
                    ''', (email_hash, ip_address, window_start, window_type))
                    
                    result = cursor.fetchone()
                    current_count = result[0] if result else 0
                    
                    if current_count >= limit:
                        block_duration = self._get_block_duration(window_type)
                        self._add_block(ip_address, email_hash, f'Превышен email лимит {window_type}', block_duration)
                        
                        return {
                            'allowed': False,
                            'reason': f'Превышен лимит запросов для email за {window_type}',
                            'limit': limit,
                            'current': current_count,
                            'window_type': window_type,
                            'retry_after': block_duration
                        }
                
                return {'allowed': True}
                
        except Exception as e:
            logger.error(f"Ошибка проверки email лимитов: {str(e)}")
            return {'allowed': True, 'error': str(e)}
    
    def _record_request(self, ip_address: str, email: str = None, 
                       current_time: datetime = None, user_type: str = 'anonymous'):
        """Запись успешного запроса"""
        try:
            if current_time is None:
                current_time = datetime.now()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Записываем по IP
                for window_type in ['burst', 'minute', 'hour', 'day']:
                    window_start = self._get_window_start(window_type, current_time)
                    
                    cursor.execute('''
                        INSERT OR REPLACE INTO rate_limit_ip 
                        (ip_address, window_start, window_type, request_count, last_request, user_type)
                        VALUES (?, ?, ?, 
                            COALESCE((SELECT request_count FROM rate_limit_ip 
                                     WHERE ip_address = ? AND window_start = ? AND window_type = ?), 0) + 1,
                            ?, ?)
                    ''', (ip_address, window_start, window_type, 
                          ip_address, window_start, window_type, current_time, user_type))
                
                # Записываем по email если указан
                if email:
                    email_hash = self._hash_email(email)
                    for window_type in ['minute', 'hour', 'day']:
                        window_start = self._get_window_start(window_type, current_time)
                        
                        cursor.execute('''
                            INSERT OR REPLACE INTO rate_limit_email 
                            (email_hash, ip_address, window_start, window_type, request_count, last_request)
                            VALUES (?, ?, ?, ?, 
                                COALESCE((SELECT request_count FROM rate_limit_email 
                                         WHERE email_hash = ? AND ip_address = ? AND window_start = ? AND window_type = ?), 0) + 1,
                                ?)
                        ''', (email_hash, ip_address, window_start, window_type,
                              email_hash, ip_address, window_start, window_type, current_time))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Ошибка записи запроса: {str(e)}")
    
    def _add_block(self, ip_address: str, email_hash: str = None, 
                   reason: str = '', duration_minutes: int = 15):
        """Добавление блокировки"""
        try:
            blocked_until = datetime.now() + timedelta(minutes=duration_minutes)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO rate_limit_blocks 
                    (ip_address, email_hash, block_reason, blocked_until)
                    VALUES (?, ?, ?, ?)
                ''', (ip_address, email_hash, reason, blocked_until))
                
                conn.commit()
                logger.warning(f"Добавлена блокировка для IP {ip_address}: {reason}")
                
        except Exception as e:
            logger.error(f"Ошибка добавления блокировки: {str(e)}")
    
    def _get_block_duration(self, window_type: str) -> int:
        """Получение длительности блокировки в минутах"""
        durations = {
            'burst': 1,    # 1 минута
            'minute': 5,   # 5 минут
            'hour': 15,    # 15 минут
            'day': 60      # 1 час
        }
        return durations.get(window_type, 15)
    
    def _get_block_retry_time(self, ip_address: str, email: str = None) -> int:
        """Получение времени до разблокировки в секундах"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                query = '''
                    SELECT MIN(CAST((julianday(blocked_until) - julianday('now')) * 86400 AS INTEGER))
                    FROM rate_limit_blocks 
                    WHERE ip_address = ? AND is_active = 1 AND blocked_until > CURRENT_TIMESTAMP
                '''
                params = [ip_address]
                
                if email:
                    email_hash = self._hash_email(email)
                    query += ' OR (email_hash = ? AND is_active = 1 AND blocked_until > CURRENT_TIMESTAMP)'
                    params.append(email_hash)
                
                cursor.execute(query, params)
                result = cursor.fetchone()
                
                return max(result[0] if result and result[0] else 0, 0)
                
        except Exception as e:
            logger.error(f"Ошибка получения времени блокировки: {str(e)}")
            return 0
    
    def _get_current_usage(self, ip_address: str, email: str = None, 
                          current_time: datetime = None) -> Dict[str, int]:
        """Получение текущего использования лимитов"""
        try:
            if current_time is None:
                current_time = datetime.now()
            
            usage = {}
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Получаем использование по IP
                for window_type in ['minute', 'hour', 'day']:
                    window_start = self._get_window_start(window_type, current_time)
                    
                    cursor.execute('''
                        SELECT request_count FROM rate_limit_ip 
                        WHERE ip_address = ? AND window_start = ? AND window_type = ?
                    ''', (ip_address, window_start, window_type))
                    
                    result = cursor.fetchone()
                    usage[f'ip_{window_type}'] = result[0] if result else 0
                
                # Получаем использование по email если указан
                if email:
                    email_hash = self._hash_email(email)
                    for window_type in ['minute', 'hour', 'day']:
                        window_start = self._get_window_start(window_type, current_time)
                        
                        cursor.execute('''
                            SELECT request_count FROM rate_limit_email 
                            WHERE email_hash = ? AND ip_address = ? 
                            AND window_start = ? AND window_type = ?
                        ''', (email_hash, ip_address, window_start, window_type))
                        
                        result = cursor.fetchone()
                        usage[f'email_{window_type}'] = result[0] if result else 0
            
            return usage
            
        except Exception as e:
            logger.error(f"Ошибка получения текущего использования: {str(e)}")
            return {}
    
    def _get_reset_times(self, current_time: datetime = None) -> Dict[str, str]:
        """Получение времени сброса лимитов"""
        if current_time is None:
            current_time = datetime.now()
        
        return {
            'minute': (current_time.replace(second=0, microsecond=0) + timedelta(minutes=1)).isoformat(),
            'hour': (current_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)).isoformat(),
            'day': (current_time.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)).isoformat()
        }
    
    def get_rate_limit_stats(self) -> Dict[str, Any]:
        """Получение статистики rate limiting"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Общая статистика
                cursor.execute('''
                    SELECT 
                        COUNT(DISTINCT ip_address) as unique_ips,
                        SUM(request_count) as total_requests,
                        COUNT(*) as total_windows
                    FROM rate_limit_ip
                    WHERE window_start >= datetime('now', '-1 day')
                ''')
                
                general_stats = cursor.fetchone()
                
                # Активные блокировки
                cursor.execute('''
                    SELECT COUNT(*) FROM rate_limit_blocks 
                    WHERE is_active = 1 AND blocked_until > CURRENT_TIMESTAMP
                ''')
                
                active_blocks = cursor.fetchone()[0]
                
                # Топ IP по запросам
                cursor.execute('''
                    SELECT ip_address, SUM(request_count) as total_requests
                    FROM rate_limit_ip
                    WHERE window_start >= datetime('now', '-1 day')
                    GROUP BY ip_address
                    ORDER BY total_requests DESC
                    LIMIT 10
                ''')
                
                top_ips = [
                    {'ip': row[0], 'requests': row[1]}
                    for row in cursor.fetchall()
                ]
                
                return {
                    'unique_ips_24h': general_stats[0] or 0,
                    'total_requests_24h': general_stats[1] or 0,
                    'active_blocks': active_blocks,
                    'top_ips': top_ips,
                    'limits_configured': len(self.user_type_limits)
                }
                
        except Exception as e:
            logger.error(f"Ошибка получения статистики rate limiting: {str(e)}")
            return {}
    
    def cleanup_old_records(self, days_to_keep: int = 7) -> int:
        """Очистка старых записей rate limiting"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Удаляем старые записи IP лимитов
                cursor.execute('''
                    DELETE FROM rate_limit_ip 
                    WHERE window_start < ?
                ''', (cutoff_date,))
                
                ip_deleted = cursor.rowcount
                
                # Удаляем старые записи email лимитов
                cursor.execute('''
                    DELETE FROM rate_limit_email 
                    WHERE window_start < ?
                ''', (cutoff_date,))
                
                email_deleted = cursor.rowcount
                
                # Деактивируем старые блокировки
                cursor.execute('''
                    UPDATE rate_limit_blocks 
                    SET is_active = 0 
                    WHERE blocked_until < CURRENT_TIMESTAMP
                ''')
                
                blocks_deactivated = cursor.rowcount
                
                conn.commit()
                
                total_deleted = ip_deleted + email_deleted
                logger.info(f"Очищено {total_deleted} старых записей rate limiting, деактивировано {blocks_deactivated} блокировок")
                
                return total_deleted
                
        except Exception as e:
            logger.error(f"Ошибка очистки старых записей: {str(e)}")
            return 0

