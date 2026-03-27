# ValiRef 开发指南

## 环境配置

ValiRef 使用 Docker Compose 管理基础设施服务（Postgres + RabbitMQ），代码在宿主机直接运行。

### 为什么这样设计？

- **开发效率**：代码修改即时生效，无需 rebuild 镜像
- **调试方便**：可以直接用 IDE 调试，查看完整错误堆栈
- **简单明了**：`docker-compose.yml` 只包含基础设施，不混合应用服务

---

## 快速开始

### 1. 启动基础设施

```bash
# 一键启动 Postgres + RabbitMQ
./scripts/dev-setup.sh
```

或者手动：

```bash
docker-compose up -d
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，设置 DEEPSEEK_API_KEY
```

### 3. 启动 API 服务

```bash
# 使用 uv 在宿主机运行
uv run uvicorn src.api.main:app --reload
```

API 将运行在 http://localhost:8000

### 4. 启动 Worker（在另一个终端）

```bash
uv run python -m src.api.worker.consumer
```

---

## 开发工作流

```bash
# 1. 确保基础设施运行
docker-compose ps

# 2. 修改代码（src/ 下的任何文件）
# 保存后 API 自动重载

# 3. Worker 修改后需要手动重启
# Ctrl+C 然后重新运行

# 4. 查看 RabbitMQ 管理界面
open http://localhost:15672  # guest/guest

# 5. 查看数据库
open http://localhost:8080   # Adminer
```

---

## 生产部署

```bash
# 使用生产配置（所有服务容器化）
docker-compose -f docker-compose.prod.yml up -d

# 横向扩展 worker
docker-compose -f docker-compose.prod.yml up -d --scale worker=3
```

---

## 服务端口

| 服务 | 端口 | 说明 |
|------|------|------|
| API | 8000 | FastAPI 服务 |
| Postgres | 5432 | ParadeDB 数据库 |
| RabbitMQ | 5672 | AMQP 协议 |
| RabbitMQ UI | 15672 | 管理界面 |
| Adminer | 8080 | 数据库管理 |

---

## 常用命令

```bash
# 查看基础设施日志
docker-compose logs -f

# 停止基础设施
docker-compose down

# 完全重置（删除数据卷）
docker-compose down -v

# 重启单个服务
docker-compose restart rabbitmq

# 进入数据库
docker-compose exec postgres psql -U valiref -d arxiv_db
```
