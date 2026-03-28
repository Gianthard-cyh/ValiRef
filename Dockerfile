# ValiRef API Service Dockerfile - 优化版
FROM python:3.12-slim

WORKDIR /app

# 1. 安装系统依赖（这层很少变）
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 2. 安装 uv
RUN pip install uv

# 3. 先只复制依赖定义文件（这层变化频率低）
COPY pyproject.toml uv.lock ./

# 4. 安装项目依赖（不含代码，利用 Docker 缓存）
# --no-install-project 只安装依赖，不安装项目本身
RUN uv sync --frozen --no-install-project

# 5. 复制代码（这层变化频率高）
COPY src/ ./src/

# 6. 安装项目代码（快速，因为依赖已在）
RUN uv sync --frozen

# 设置环境
ENV PYTHONPATH=/app
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
