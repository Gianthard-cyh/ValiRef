# arXiv 向量数据库 - GPU笔记本部署指南

> **Agent请注意**：这是用于在GPU笔记本上部署arXiv向量数据库的完整指南。

## 📋 环境要求

- **OS**: Linux (Ubuntu 20.04+) / macOS / Windows with WSL2
- **Docker**: Docker + Docker Compose
- **GPU**: NVIDIA GPU (推荐RTX 3060以上，显存6GB+）
- **Python**: 3.10+
- **uv**: Python包管理器
- **数据**: `arxiv-metadata-oai-snapshot.json` (4.8GB)

## 🚀 快速开始

### 步骤1: 克隆项目

```bash
git clone <你的仓库地址> ValiRef
cd ValiRef
```

### 步骤2: 复制数据文件

从原机器复制数据文件：
```bash
# 在原机器上执行
scp /home/cyh/下载/arxiv-metadata-oai-snapshot.json user@<笔记本IP>:~/Downloads/
```

或直接下载到笔记本。

### 步骤3: 一键部署

```bash
# 使用一键脚本（推荐）
./scripts/setup_gpu_server.sh ~/Downloads/arxiv-metadata-oai-snapshot.json

# 或分步执行，见下方
```

## 🔧 分步部署

### 1. 启动数据库

```bash
cd ValiRef
sudo docker-compose up -d
sleep 5  # 等待数据库就绪
```

### 2. 安装Python依赖

```bash
# 安装uv（如果没有）
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.cargo/env

# 同步项目依赖
uv sync

# 如果使用GPU，确保安装CUDA版PyTorch
uv pip install torch --index-url https://download.pytorch.org/whl/cu118
```

### 3. 导入元数据

```bash
uv run python scripts/import_metadata_sync.py --data ~/Downloads/arxiv-metadata-oai-snapshot.json
```

**预计时间**: ~30分钟 (300万条)

### 4. 生成Embedding（GPU加速）

```bash
# 自动检测GPU并使用CUDA
uv run python scripts/generate_embeddings_gpu.py

# 后台运行（推荐）
nohup uv run python scripts/generate_embeddings_gpu.py > embed.log 2>&1 &
tail -f embed.log  # 查看进度
```

**预计时间**:
- GPU (RTX 3060): ~3小时
- GPU (RTX 4090): ~1小时
- CPU: ~40-50小时

### 5. 创建向量索引

```bash
sudo docker-compose exec -T postgres psql -U valiref -d arxiv_db -c \
  "CREATE INDEX IF NOT EXISTS idx_papers_embedding ON papers USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);"
```

## 📊 验证部署

```bash
# 查看数据库统计
sudo docker-compose exec -T postgres psql -U valiref -d arxiv_db -c \
  "SELECT COUNT(*) as papers, COUNT(embedding) as with_embedding FROM papers;"

# 预期输出: 3000000 | 3000000
```

## 🔍 使用查询

```bash
# 向量相似度搜索
uv run python scripts/query_papers_sync.py "transformer architecture" -k 5

# 全文搜索
uv run python scripts/query_papers_sync.py "neural network" --fulltext -k 5

# 混合搜索（推荐）
uv run python scripts/query_papers_sync.py "machine learning" --hybrid -k 5
```

## 🛠️ 故障排除

### GPU未检测到
```bash
# 检查NVIDIA驱动
nvidia-smi

# 如果PyTorch没有CUDA支持
uv pip uninstall torch
uv pip install torch --index-url https://download.pytorch.org/whl/cu118
```

### 内存不足
```bash
# 减小批次大小
uv run python scripts/generate_embeddings_gpu.py --batch-size 128
```

### Docker连接失败
```bash
# 检查Docker状态
sudo systemctl status docker
sudo systemctl start docker
```

### 数据库连接失败
```bash
# 检查容器状态
sudo docker-compose ps

# 重启容器
sudo docker-compose restart
```

## 📁 文件说明

| 文件 | 说明 |
|------|------|
| `scripts/setup_gpu_server.sh` | **一键部署脚本** |
| `scripts/import_metadata_sync.py` | 元数据导入（支持命令行参数） |
| `scripts/generate_embeddings_gpu.py` | GPU加速embedding生成 |
| `scripts/generate_embeddings_sync.py` | CPU版embedding生成 |
| `scripts/query_papers_sync.py` | 查询工具（向量/全文/混合） |
| `docker-compose.yml` | Docker配置 |
| `scripts/setup_pgvector.sql` | 数据库初始化 |

## 💡 提示

1. **中断恢复**: embedding生成支持中断恢复，重新运行会自动跳过已有embedding的记录
2. **分批处理**: 如果一次处理不完，可以分多次运行`generate_embeddings_gpu.py`
3. **后台运行**: 使用`nohup`或`tmux`保持进程在后台运行
4. **监控进度**: 使用`tail -f embed.log`实时查看进度

## 📞 联系

如有问题，请联系项目维护者。

---
**Agent任务**: 执行上述步骤完成部署，确保数据库统计达到 3,000,000 条记录。
