# ValiRef API Service Dockerfile
FROM python:3.12-slim

WORKDIR /app

# 1. 系统依赖（变化最少）
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 2. 安装 uv（变化少）
RUN pip install uv

# 3. Python 依赖文件（变化中等）
COPY pyproject.toml uv.lock ./

# 4. 安装所有依赖（利用缓存层）
RUN uv sync --frozen

# 5. 预下载 CrossEncoder 模型（模型固定，放在代码前避免重复下载）
RUN uv run python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"

# 6. 复制代码（变化最频繁）
COPY src/ ./src/

# 7. 安装项目代码（快速）
RUN uv sync --frozen

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
