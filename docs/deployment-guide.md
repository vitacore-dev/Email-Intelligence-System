# Email Search Service v2.0 - Руководство по развертыванию

## 🚀 Варианты развертывания

### 1. Docker (Рекомендуется)

#### Быстрый запуск
```bash
# Клонирование проекта
git clone <repository-url>
cd email-search-service-v2

# Настройка конфигурации
cp email-search-backend/.env.example email-search-backend/.env
# Отредактируйте .env файл с вашими настройками

# Запуск с Docker Compose
cd email-search-backend
docker-compose up -d
```

#### Ручная сборка Docker образа
```bash
cd email-search-backend

# Сборка образа
docker build -t email-search-service:v2.0 .

# Запуск контейнера
docker run -d \
  --name email-search-service \
  -p 5000:5000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  --env-file .env \
  email-search-service:v2.0
```

### 2. Ручная установка

#### Системные требования
- Ubuntu 20.04+ / CentOS 8+ / Debian 11+
- Python 3.8+
- Node.js 16+
- nginx (опционально)
- 2GB RAM минимум
- 10GB свободного места

#### Установка зависимостей
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3 python3-pip python3-venv nodejs npm nginx

# CentOS/RHEL
sudo yum install python3 python3-pip nodejs npm nginx
```

#### Настройка проекта
```bash
# Создание пользователя для сервиса
sudo useradd -r -s /bin/false emailsearch
sudo mkdir -p /opt/email-search-service
sudo chown emailsearch:emailsearch /opt/email-search-service

# Копирование файлов
sudo cp -r email-search-backend/* /opt/email-search-service/
sudo chown -R emailsearch:emailsearch /opt/email-search-service

# Переход в директорию
cd /opt/email-search-service

# Создание виртуального окружения
sudo -u emailsearch python3 -m venv venv
sudo -u emailsearch venv/bin/pip install -r requirements.txt

# Настройка конфигурации
sudo -u emailsearch cp .env.example .env
sudo nano .env  # Отредактируйте настройки
```

#### Создание systemd сервиса
```bash
sudo tee /etc/systemd/system/email-search.service > /dev/null <<EOF
[Unit]
Description=Email Search Service v2.0
After=network.target

[Service]
Type=simple
User=emailsearch
Group=emailsearch
WorkingDirectory=/opt/email-search-service
Environment=PATH=/opt/email-search-service/venv/bin
EnvironmentFile=/opt/email-search-service/.env
ExecStart=/opt/email-search-service/venv/bin/python src/main.py
Restart=always
RestartSec=10

# Безопасность
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/email-search-service/data
ReadWritePaths=/opt/email-search-service/logs

[Install]
WantedBy=multi-user.target
EOF

# Активация сервиса
sudo systemctl daemon-reload
sudo systemctl enable email-search
sudo systemctl start email-search
sudo systemctl status email-search
```

### 3. Настройка nginx (Reverse Proxy)

```bash
# Создание конфигурации nginx
sudo tee /etc/nginx/sites-available/email-search > /dev/null <<EOF
server {
    listen 80;
    server_name your-domain.com;  # Замените на ваш домен

    # Редирект на HTTPS
    return 301 https://\$server_name\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;  # Замените на ваш домен

    # SSL сертификаты (настройте Let's Encrypt или загрузите свои)
    ssl_certificate /etc/ssl/certs/your-domain.crt;
    ssl_certificate_key /etc/ssl/private/your-domain.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;
    ssl_prefer_server_ciphers off;

    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains";

    # Rate limiting
    limit_req_zone \$binary_remote_addr zone=api:10m rate=10r/s;

    location / {
        limit_req zone=api burst=20 nodelay;
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Health check
    location /health {
        access_log off;
        proxy_pass http://127.0.0.1:5000/api/email/health;
    }

    # Логи
    access_log /var/log/nginx/email-search-access.log;
    error_log /var/log/nginx/email-search-error.log;
}
EOF

# Активация конфигурации
sudo ln -s /etc/nginx/sites-available/email-search /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 4. SSL сертификаты с Let's Encrypt

```bash
# Установка Certbot
sudo apt install certbot python3-certbot-nginx

# Получение сертификата
sudo certbot --nginx -d your-domain.com

# Автоматическое обновление
sudo crontab -e
# Добавьте строку:
# 0 12 * * * /usr/bin/certbot renew --quiet
```

## 🔧 Настройка поисковых API

### Google Custom Search API

1. **Создание проекта в Google Cloud Console:**
   ```
   https://console.cloud.google.com/
   ```

2. **Включение Custom Search API:**
   - Перейдите в "APIs & Services" > "Library"
   - Найдите "Custom Search API"
   - Нажмите "Enable"

3. **Создание API ключа:**
   - Перейдите в "APIs & Services" > "Credentials"
   - Нажмите "Create Credentials" > "API Key"
   - Скопируйте ключ в переменную `GOOGLE_API_KEY`

4. **Настройка Custom Search Engine:**
   ```
   https://cse.google.com/cse/
   ```
   - Создайте новый поисковик
   - Добавьте сайты для поиска или выберите "Search the entire web"
   - Скопируйте Search Engine ID в `GOOGLE_SEARCH_ENGINE_ID`

### Bing Search API

1. **Создание ресурса в Azure:**
   ```
   https://portal.azure.com/
   ```

2. **Создание Bing Search v7:**
   - Перейдите в "Create a resource"
   - Найдите "Bing Search v7"
   - Создайте ресурс

3. **Получение API ключа:**
   - Перейдите в созданный ресурс
   - В разделе "Keys and Endpoint" скопируйте ключ
   - Добавьте в переменную `BING_API_KEY`

## 📊 Мониторинг и логирование

### Настройка логирования

```bash
# Создание директорий для логов
sudo mkdir -p /var/log/email-search
sudo chown emailsearch:emailsearch /var/log/email-search

# Настройка logrotate
sudo tee /etc/logrotate.d/email-search > /dev/null <<EOF
/var/log/email-search/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 emailsearch emailsearch
    postrotate
        systemctl reload email-search
    endscript
}
EOF
```

### Мониторинг с помощью systemd

```bash
# Просмотр статуса
sudo systemctl status email-search

# Просмотр логов
sudo journalctl -u email-search -f

# Просмотр логов приложения
sudo tail -f /opt/email-search-service/data/logs/app.log
```

### Настройка мониторинга с Prometheus (опционально)

```bash
# Установка node_exporter
wget https://github.com/prometheus/node_exporter/releases/download/v1.6.1/node_exporter-1.6.1.linux-amd64.tar.gz
tar xvfz node_exporter-1.6.1.linux-amd64.tar.gz
sudo mv node_exporter-1.6.1.linux-amd64/node_exporter /usr/local/bin/
sudo useradd -rs /bin/false node_exporter

# Создание systemd сервиса для node_exporter
sudo tee /etc/systemd/system/node_exporter.service > /dev/null <<EOF
[Unit]
Description=Node Exporter
After=network.target

[Service]
User=node_exporter
Group=node_exporter
Type=simple
ExecStart=/usr/local/bin/node_exporter

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable node_exporter
sudo systemctl start node_exporter
```

## 🔒 Безопасность

### Настройка файрвола

```bash
# UFW (Ubuntu)
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable

# firewalld (CentOS/RHEL)
sudo firewall-cmd --permanent --add-service=ssh
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

### Настройка fail2ban

```bash
# Установка
sudo apt install fail2ban

# Конфигурация для nginx
sudo tee /etc/fail2ban/jail.local > /dev/null <<EOF
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5

[nginx-http-auth]
enabled = true

[nginx-limit-req]
enabled = true
filter = nginx-limit-req
action = iptables-multiport[name=ReqLimit, port="http,https", protocol=tcp]
logpath = /var/log/nginx/email-search-error.log
maxretry = 10
findtime = 600
bantime = 7200
EOF

sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

## 🔄 Обновление

### Обновление через Docker

```bash
# Остановка текущего контейнера
docker-compose down

# Обновление образа
docker-compose pull

# Запуск обновленного контейнера
docker-compose up -d
```

### Ручное обновление

```bash
# Остановка сервиса
sudo systemctl stop email-search

# Резервное копирование
sudo cp -r /opt/email-search-service /opt/email-search-service.backup

# Обновление кода
sudo -u emailsearch git pull origin main

# Обновление зависимостей
sudo -u emailsearch venv/bin/pip install -r requirements.txt

# Запуск сервиса
sudo systemctl start email-search
```

## 🔧 Устранение неполадок

### Частые проблемы

1. **Сервис не запускается:**
   ```bash
   sudo journalctl -u email-search -n 50
   ```

2. **Ошибки базы данных:**
   ```bash
   sudo -u emailsearch ls -la /opt/email-search-service/data/
   sudo -u emailsearch chmod 755 /opt/email-search-service/data/
   ```

3. **Проблемы с правами доступа:**
   ```bash
   sudo chown -R emailsearch:emailsearch /opt/email-search-service/
   ```

4. **Высокое потребление памяти:**
   ```bash
   # Мониторинг ресурсов
   htop
   # Проверка логов
   sudo tail -f /opt/email-search-service/data/logs/app.log
   ```

### Диагностические команды

```bash
# Проверка статуса сервиса
curl -s http://localhost:5000/api/email/health | jq

# Проверка подключения к базе данных
sudo -u emailsearch sqlite3 /opt/email-search-service/data/email_search.db ".tables"

# Проверка логов
sudo tail -f /opt/email-search-service/data/logs/app.log

# Проверка сетевых соединений
sudo netstat -tlnp | grep :5000
```

## 📈 Масштабирование

### Горизонтальное масштабирование

```bash
# Использование Docker Swarm
docker swarm init
docker service create \
  --name email-search-service \
  --replicas 3 \
  --publish 5000:5000 \
  email-search-service:v2.0
```

### Настройка балансировщика нагрузки

```nginx
upstream email_search_backend {
    server 127.0.0.1:5001;
    server 127.0.0.1:5002;
    server 127.0.0.1:5003;
}

server {
    listen 80;
    location / {
        proxy_pass http://email_search_backend;
    }
}
```

## 📞 Поддержка

### Контакты
- **Email:** support@email-search-service.com
- **GitHub:** https://github.com/your-org/email-search-service
- **Документация:** https://docs.email-search-service.com

### Сбор диагностической информации

```bash
#!/bin/bash
# Скрипт для сбора диагностической информации

echo "=== Email Search Service Diagnostics ===" > diagnostics.txt
echo "Date: $(date)" >> diagnostics.txt
echo "" >> diagnostics.txt

echo "=== System Info ===" >> diagnostics.txt
uname -a >> diagnostics.txt
cat /etc/os-release >> diagnostics.txt
echo "" >> diagnostics.txt

echo "=== Service Status ===" >> diagnostics.txt
systemctl status email-search >> diagnostics.txt
echo "" >> diagnostics.txt

echo "=== Recent Logs ===" >> diagnostics.txt
journalctl -u email-search -n 100 >> diagnostics.txt
echo "" >> diagnostics.txt

echo "=== Resource Usage ===" >> diagnostics.txt
free -h >> diagnostics.txt
df -h >> diagnostics.txt
echo "" >> diagnostics.txt

echo "Диагностическая информация сохранена в diagnostics.txt"
```

---

**Email Search Service v2.0** - Production-ready развертывание 🚀

