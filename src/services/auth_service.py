import sqlite3
import hashlib
import secrets
import jwt
import time
import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import os

logger = logging.getLogger(__name__)

class AuthService:
    """Сервис аутентификации и авторизации"""
    
    def __init__(self, db_path: str = None, jwt_secret: str = None):
        if db_path is None:
            db_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
            os.makedirs(db_dir, exist_ok=True)
            self.db_path = os.path.join(db_dir, 'email_search.db')
        else:
            self.db_path = db_path
        
        # JWT секрет для подписи токенов
        self.jwt_secret = jwt_secret or os.environ.get('JWT_SECRET', 'default-secret-change-in-production')
        
        # Настройки токенов
        self.token_settings = {
            'access_token_expire_hours': 24,
            'refresh_token_expire_days': 30,
            'api_key_expire_days': 365
        }
        
        # Типы пользователей и их права
        self.user_types = {
            'free': {
                'max_requests_per_day': 100,
                'max_api_keys': 1,
                'features': ['basic_search', 'cache_access']
            },
            'premium': {
                'max_requests_per_day': 1000,
                'max_api_keys': 5,
                'features': ['basic_search', 'advanced_search', 'cache_access', 'analytics']
            },
            'enterprise': {
                'max_requests_per_day': 10000,
                'max_api_keys': 20,
                'features': ['basic_search', 'advanced_search', 'cache_access', 'analytics', 'admin_access']
            }
        }
        
        self.init_auth_tables()
    
    def init_auth_tables(self):
        """Инициализация таблиц аутентификации"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Таблица пользователей
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS auth_users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        email TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL,
                        user_type TEXT DEFAULT 'free',
                        is_active BOOLEAN DEFAULT TRUE,
                        is_verified BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_login TIMESTAMP,
                        login_count INTEGER DEFAULT 0,
                        metadata TEXT  -- JSON для дополнительных данных
                    )
                ''')
                
                # Таблица API ключей
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS auth_api_keys (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        key_hash TEXT UNIQUE NOT NULL,
                        key_prefix TEXT NOT NULL,  -- Первые 8 символов для идентификации
                        name TEXT NOT NULL,
                        permissions TEXT,  -- JSON список разрешений
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_used TIMESTAMP,
                        expires_at TIMESTAMP,
                        usage_count INTEGER DEFAULT 0,
                        FOREIGN KEY (user_id) REFERENCES auth_users (id)
                    )
                ''')
                
                # Таблица сессий/токенов
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS auth_sessions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        session_token TEXT UNIQUE NOT NULL,
                        refresh_token TEXT UNIQUE,
                        ip_address TEXT,
                        user_agent TEXT,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP NOT NULL,
                        FOREIGN KEY (user_id) REFERENCES auth_users (id)
                    )
                ''')
                
                # Таблица логов аутентификации
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS auth_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        action TEXT NOT NULL,  -- login, logout, api_key_used, etc.
                        ip_address TEXT,
                        user_agent TEXT,
                        success BOOLEAN NOT NULL,
                        error_message TEXT,
                        metadata TEXT,  -- JSON для дополнительных данных
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Индексы для оптимизации
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_auth_users_email ON auth_users(email)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_auth_users_username ON auth_users(username)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_auth_api_keys_hash ON auth_api_keys(key_hash)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_auth_api_keys_user ON auth_api_keys(user_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_auth_sessions_token ON auth_sessions(session_token)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_auth_sessions_user ON auth_sessions(user_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_auth_logs_user ON auth_logs(user_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_auth_logs_timestamp ON auth_logs(timestamp)')
                
                conn.commit()
                
                # Создаем администратора по умолчанию если его нет
                self._create_default_admin()
                
                logger.info("Таблицы аутентификации инициализированы")
                
        except Exception as e:
            logger.error(f"Ошибка инициализации таблиц аутентификации: {str(e)}")
            raise
    
    def _create_default_admin(self):
        """Создание администратора по умолчанию"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Проверяем, есть ли уже администратор
                cursor.execute('SELECT COUNT(*) FROM auth_users WHERE user_type = ?', ('enterprise',))
                if cursor.fetchone()[0] > 0:
                    return
                
                # Создаем администратора
                admin_password = 'admin123'  # В production должен быть изменен
                password_hash = self._hash_password(admin_password)
                
                cursor.execute('''
                    INSERT INTO auth_users (username, email, password_hash, user_type, is_active, is_verified)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', ('admin', 'admin@emailsearch.local', password_hash, 'enterprise', True, True))
                
                admin_id = cursor.lastrowid
                conn.commit()  # Коммитим создание пользователя
                
                # Теперь создаем API ключ для администратора
                api_key = self.generate_api_key(admin_id, 'Default Admin Key', ['admin', 'search', 'analytics'])
                
                logger.info(f"Создан администратор по умолчанию. API ключ: {api_key}")
                
        except Exception as e:
            logger.error(f"Ошибка создания администратора: {str(e)}")
    
    def _hash_password(self, password: str) -> str:
        """Хэширование пароля"""
        salt = secrets.token_hex(16)
        password_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return f"{salt}:{password_hash.hex()}"
    
    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Проверка пароля"""
        try:
            salt, stored_hash = password_hash.split(':')
            password_hash_check = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
            return stored_hash == password_hash_check.hex()
        except:
            return False
    
    def _hash_api_key(self, api_key: str) -> str:
        """Хэширование API ключа"""
        return hashlib.sha256(api_key.encode()).hexdigest()
    
    def register_user(self, username: str, email: str, password: str, 
                     user_type: str = 'free') -> Tuple[bool, Dict[str, Any]]:
        """Регистрация нового пользователя"""
        try:
            if user_type not in self.user_types:
                return False, {'error': 'Неверный тип пользователя'}
            
            password_hash = self._hash_password(password)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Проверяем уникальность
                cursor.execute('SELECT COUNT(*) FROM auth_users WHERE username = ? OR email = ?', 
                             (username, email))
                if cursor.fetchone()[0] > 0:
                    return False, {'error': 'Пользователь с таким именем или email уже существует'}
                
                # Создаем пользователя
                cursor.execute('''
                    INSERT INTO auth_users (username, email, password_hash, user_type)
                    VALUES (?, ?, ?, ?)
                ''', (username, email, password_hash, user_type))
                
                user_id = cursor.lastrowid
                
                # Создаем API ключ по умолчанию
                api_key = self.generate_api_key(user_id, 'Default API Key', ['search'])
                
                conn.commit()
                
                # Логируем регистрацию
                self._log_auth_event(user_id, 'register', None, None, True)
                
                return True, {
                    'user_id': user_id,
                    'username': username,
                    'email': email,
                    'user_type': user_type,
                    'api_key': api_key
                }
                
        except Exception as e:
            logger.error(f"Ошибка регистрации пользователя: {str(e)}")
            return False, {'error': 'Ошибка регистрации'}
    
    def authenticate_user(self, username: str, password: str, 
                         ip_address: str = None, user_agent: str = None) -> Tuple[bool, Dict[str, Any]]:
        """Аутентификация пользователя по логину и паролю"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Ищем пользователя
                cursor.execute('''
                    SELECT id, username, email, password_hash, user_type, is_active, is_verified
                    FROM auth_users 
                    WHERE (username = ? OR email = ?) AND is_active = 1
                ''', (username, username))
                
                user = cursor.fetchone()
                if not user:
                    self._log_auth_event(None, 'login_failed', ip_address, user_agent, False, 'User not found')
                    return False, {'error': 'Неверные учетные данные'}
                
                user_id, username, email, password_hash, user_type, is_active, is_verified = user
                
                # Проверяем пароль
                if not self._verify_password(password, password_hash):
                    self._log_auth_event(user_id, 'login_failed', ip_address, user_agent, False, 'Invalid password')
                    return False, {'error': 'Неверные учетные данные'}
                
                # Создаем сессию
                access_token = self._generate_jwt_token(user_id, 'access')
                refresh_token = self._generate_jwt_token(user_id, 'refresh')
                
                # Сохраняем сессию
                expires_at = datetime.now() + timedelta(hours=self.token_settings['access_token_expire_hours'])
                cursor.execute('''
                    INSERT INTO auth_sessions 
                    (user_id, session_token, refresh_token, ip_address, user_agent, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (user_id, access_token, refresh_token, ip_address, user_agent, expires_at))
                
                # Обновляем статистику пользователя
                cursor.execute('''
                    UPDATE auth_users 
                    SET last_login = CURRENT_TIMESTAMP, login_count = login_count + 1
                    WHERE id = ?
                ''', (user_id,))
                
                conn.commit()
                
                # Логируем успешный вход
                self._log_auth_event(user_id, 'login_success', ip_address, user_agent, True)
                
                return True, {
                    'user_id': user_id,
                    'username': username,
                    'email': email,
                    'user_type': user_type,
                    'access_token': access_token,
                    'refresh_token': refresh_token,
                    'expires_in': self.token_settings['access_token_expire_hours'] * 3600
                }
                
        except Exception as e:
            logger.error(f"Ошибка аутентификации: {str(e)}")
            self._log_auth_event(None, 'login_error', ip_address, user_agent, False, str(e))
            return False, {'error': 'Ошибка аутентификации'}
    
    def authenticate_api_key(self, api_key: str, ip_address: str = None) -> Tuple[bool, Dict[str, Any]]:
        """Аутентификация по API ключу"""
        try:
            key_hash = self._hash_api_key(api_key)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Ищем API ключ
                cursor.execute('''
                    SELECT ak.id, ak.user_id, ak.name, ak.permissions, ak.expires_at,
                           u.username, u.email, u.user_type, u.is_active
                    FROM auth_api_keys ak
                    JOIN auth_users u ON ak.user_id = u.id
                    WHERE ak.key_hash = ? AND ak.is_active = 1 AND u.is_active = 1
                    AND (ak.expires_at IS NULL OR ak.expires_at > CURRENT_TIMESTAMP)
                ''', (key_hash,))
                
                result = cursor.fetchone()
                if not result:
                    self._log_auth_event(None, 'api_key_failed', ip_address, None, False, 'Invalid API key')
                    return False, {'error': 'Неверный API ключ'}
                
                key_id, user_id, key_name, permissions, expires_at, username, email, user_type, is_active = result
                
                # Обновляем статистику использования ключа
                cursor.execute('''
                    UPDATE auth_api_keys 
                    SET last_used = CURRENT_TIMESTAMP, usage_count = usage_count + 1
                    WHERE id = ?
                ''', (key_id,))
                
                conn.commit()
                
                # Логируем использование API ключа
                self._log_auth_event(user_id, 'api_key_used', ip_address, None, True, f'Key: {key_name}')
                
                return True, {
                    'user_id': user_id,
                    'username': username,
                    'email': email,
                    'user_type': user_type,
                    'api_key_name': key_name,
                    'permissions': permissions.split(',') if permissions else [],
                    'auth_method': 'api_key'
                }
                
        except Exception as e:
            logger.error(f"Ошибка аутентификации API ключа: {str(e)}")
            self._log_auth_event(None, 'api_key_error', ip_address, None, False, str(e))
            return False, {'error': 'Ошибка аутентификации'}
    
    def verify_jwt_token(self, token: str, token_type: str = 'access') -> Tuple[bool, Dict[str, Any]]:
        """Проверка JWT токена"""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=['HS256'])
            
            if payload.get('type') != token_type:
                return False, {'error': 'Неверный тип токена'}
            
            user_id = payload.get('user_id')
            if not user_id:
                return False, {'error': 'Неверный токен'}
            
            # Проверяем активность сессии
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT s.id, u.username, u.email, u.user_type, u.is_active
                    FROM auth_sessions s
                    JOIN auth_users u ON s.user_id = u.id
                    WHERE s.session_token = ? AND s.is_active = 1 
                    AND s.expires_at > CURRENT_TIMESTAMP AND u.is_active = 1
                ''', (token,))
                
                result = cursor.fetchone()
                if not result:
                    return False, {'error': 'Сессия недействительна'}
                
                session_id, username, email, user_type, is_active = result
                
                # Обновляем время последней активности
                cursor.execute('''
                    UPDATE auth_sessions 
                    SET last_activity = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (session_id,))
                
                conn.commit()
                
                return True, {
                    'user_id': user_id,
                    'username': username,
                    'email': email,
                    'user_type': user_type,
                    'session_id': session_id,
                    'auth_method': 'jwt_token'
                }
                
        except jwt.ExpiredSignatureError:
            return False, {'error': 'Токен истек'}
        except jwt.InvalidTokenError:
            return False, {'error': 'Неверный токен'}
        except Exception as e:
            logger.error(f"Ошибка проверки JWT токена: {str(e)}")
            return False, {'error': 'Ошибка проверки токена'}
    
    def generate_api_key(self, user_id: int, name: str, permissions: list = None) -> str:
        """Генерация нового API ключа"""
        try:
            # Генерируем ключ
            api_key = f"es_{secrets.token_urlsafe(32)}"
            key_hash = self._hash_api_key(api_key)
            key_prefix = api_key[:12]  # Первые 12 символов для идентификации
            
            permissions_str = ','.join(permissions) if permissions else ''
            expires_at = datetime.now() + timedelta(days=self.token_settings['api_key_expire_days'])
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Проверяем лимит ключей для пользователя
                cursor.execute('SELECT user_type FROM auth_users WHERE id = ?', (user_id,))
                user_result = cursor.fetchone()
                if not user_result:
                    raise Exception(f'Пользователь с ID {user_id} не найден')
                user_type = user_result[0]
                
                cursor.execute('SELECT COUNT(*) FROM auth_api_keys WHERE user_id = ? AND is_active = 1', (user_id,))
                current_keys = cursor.fetchone()[0]
                
                max_keys = self.user_types.get(user_type, {}).get('max_api_keys', 1)
                if current_keys >= max_keys:
                    raise Exception(f'Превышен лимит API ключей ({max_keys})')
                
                # Создаем ключ
                cursor.execute('''
                    INSERT INTO auth_api_keys 
                    (user_id, key_hash, key_prefix, name, permissions, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (user_id, key_hash, key_prefix, name, permissions_str, expires_at))
                
                conn.commit()
                
                # Логируем создание ключа
                self._log_auth_event(user_id, 'api_key_created', None, None, True, f'Key: {name}')
                
                return api_key
                
        except Exception as e:
            logger.error(f"Ошибка генерации API ключа: {str(e)}")
            raise
    
    def _generate_jwt_token(self, user_id: int, token_type: str) -> str:
        """Генерация JWT токена"""
        now = datetime.utcnow()
        
        if token_type == 'access':
            exp = now + timedelta(hours=self.token_settings['access_token_expire_hours'])
        elif token_type == 'refresh':
            exp = now + timedelta(days=self.token_settings['refresh_token_expire_days'])
        else:
            raise ValueError(f"Неизвестный тип токена: {token_type}")
        
        payload = {
            'user_id': user_id,
            'type': token_type,
            'iat': now,
            'exp': exp
        }
        
        return jwt.encode(payload, self.jwt_secret, algorithm='HS256')
    
    def _log_auth_event(self, user_id: int, action: str, ip_address: str = None, 
                       user_agent: str = None, success: bool = True, 
                       error_message: str = None, metadata: dict = None):
        """Логирование событий аутентификации"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                metadata_str = None
                if metadata:
                    import json
                    metadata_str = json.dumps(metadata)
                
                cursor.execute('''
                    INSERT INTO auth_logs 
                    (user_id, action, ip_address, user_agent, success, error_message, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (user_id, action, ip_address, user_agent, success, error_message, metadata_str))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Ошибка логирования события аутентификации: {str(e)}")
    
    def get_user_info(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получение информации о пользователе"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT username, email, user_type, is_active, is_verified, 
                           created_at, last_login, login_count
                    FROM auth_users WHERE id = ?
                ''', (user_id,))
                
                result = cursor.fetchone()
                if not result:
                    return None
                
                username, email, user_type, is_active, is_verified, created_at, last_login, login_count = result
                
                # Получаем API ключи пользователя
                cursor.execute('''
                    SELECT key_prefix, name, created_at, last_used, usage_count, is_active
                    FROM auth_api_keys WHERE user_id = ?
                    ORDER BY created_at DESC
                ''', (user_id,))
                
                api_keys = [
                    {
                        'prefix': row[0],
                        'name': row[1],
                        'created_at': row[2],
                        'last_used': row[3],
                        'usage_count': row[4],
                        'is_active': bool(row[5])
                    }
                    for row in cursor.fetchall()
                ]
                
                return {
                    'user_id': user_id,
                    'username': username,
                    'email': email,
                    'user_type': user_type,
                    'is_active': bool(is_active),
                    'is_verified': bool(is_verified),
                    'created_at': created_at,
                    'last_login': last_login,
                    'login_count': login_count,
                    'api_keys': api_keys,
                    'permissions': self.user_types.get(user_type, {})
                }
                
        except Exception as e:
            logger.error(f"Ошибка получения информации о пользователе: {str(e)}")
            return None
    
    def get_auth_stats(self) -> Dict[str, Any]:
        """Получение статистики аутентификации"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Общая статистика пользователей
                cursor.execute('''
                    SELECT 
                        COUNT(*) as total_users,
                        COUNT(CASE WHEN is_active = 1 THEN 1 END) as active_users,
                        COUNT(CASE WHEN user_type = 'free' THEN 1 END) as free_users,
                        COUNT(CASE WHEN user_type = 'premium' THEN 1 END) as premium_users,
                        COUNT(CASE WHEN user_type = 'enterprise' THEN 1 END) as enterprise_users
                    FROM auth_users
                ''')
                
                user_stats = cursor.fetchone()
                
                # Статистика API ключей
                cursor.execute('''
                    SELECT 
                        COUNT(*) as total_keys,
                        COUNT(CASE WHEN is_active = 1 THEN 1 END) as active_keys,
                        SUM(usage_count) as total_usage
                    FROM auth_api_keys
                ''')
                
                key_stats = cursor.fetchone()
                
                # Статистика входов за последние 24 часа
                cursor.execute('''
                    SELECT COUNT(*) FROM auth_logs 
                    WHERE action = 'login_success' 
                    AND timestamp >= datetime('now', '-1 day')
                ''')
                
                logins_24h = cursor.fetchone()[0]
                
                # Активные сессии
                cursor.execute('''
                    SELECT COUNT(*) FROM auth_sessions 
                    WHERE is_active = 1 AND expires_at > CURRENT_TIMESTAMP
                ''')
                
                active_sessions = cursor.fetchone()[0]
                
                return {
                    'users': {
                        'total': user_stats[0],
                        'active': user_stats[1],
                        'by_type': {
                            'free': user_stats[2],
                            'premium': user_stats[3],
                            'enterprise': user_stats[4]
                        }
                    },
                    'api_keys': {
                        'total': key_stats[0],
                        'active': key_stats[1],
                        'total_usage': key_stats[2]
                    },
                    'activity': {
                        'logins_24h': logins_24h,
                        'active_sessions': active_sessions
                    }
                }
                
        except Exception as e:
            logger.error(f"Ошибка получения статистики аутентификации: {str(e)}")
            return {}
    
    def cleanup_expired_sessions(self) -> int:
        """Очистка истекших сессий"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Деактивируем истекшие сессии
                cursor.execute('''
                    UPDATE auth_sessions 
                    SET is_active = 0 
                    WHERE expires_at <= CURRENT_TIMESTAMP AND is_active = 1
                ''')
                
                expired_count = cursor.rowcount
                
                # Удаляем старые неактивные сессии (старше 30 дней)
                cursor.execute('''
                    DELETE FROM auth_sessions 
                    WHERE is_active = 0 AND created_at < datetime('now', '-30 days')
                ''')
                
                deleted_count = cursor.rowcount
                
                conn.commit()
                
                logger.info(f"Деактивировано {expired_count} истекших сессий, удалено {deleted_count} старых сессий")
                
                return expired_count + deleted_count
                
        except Exception as e:
            logger.error(f"Ошибка очистки сессий: {str(e)}")
            return 0

