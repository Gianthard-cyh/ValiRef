# ValiRef API Service Dockerfile
FROM python:3.12-slim

WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv
RUN pip install uv

# 先复制 lock 和 toml（利用缓存）
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

# 复制代码
COPY src/ ./src/

# 安装项目
RUN uv sync --frozen

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
