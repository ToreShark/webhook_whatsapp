FROM python:3.11-slim

WORKDIR /app

# Настройка китайских зеркал для ускорения apt
RUN sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources

# Установка системных зависимостей
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Настройка pip для использования китайского зеркала
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple/ && \
    pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn

# Копируем requirements и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код
COPY . .

# Открываем порт
EXPOSE 8000

# Запускаем FastAPI сервер
CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000"]