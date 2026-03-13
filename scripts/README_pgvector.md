# arXiv 向量数据库 - 小批量测试

基于 PostgreSQL + pgvector 的 arXiv 论文语义搜索系统，针对 **4GB 内存服务器** 优化。

## 特性

- 🚀 **Docker部署**：隔离环境，易于迁移
- 💾 **全落盘存储**：内存友好，适合小内存服务器
- ⚡ **多进程加速**：并行生成 embedding
- 🔍 **混合搜索**：向量相似度 + 全文搜索
- 🎯 **小批量测试**：1万条数据快速验证

## 架构

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────┐
│  import_metadata│────▶│ PostgreSQL       │────▶│ query_papers│
│  (元数据导入)    │     │ + pgvector       │     │ (查询测试)  │
└─────────────────┘     │ (384维向量)      │     └─────────────┘
                        └──────────────────┘
                                  │
                        ┌──────────────────┐
                        │ generate_embed   │
                        │ (多进程加速)     │
                        └──────────────────┘
```

## 快速开始

### 1. 一键启动

```bash
./scripts/start_pgvector_test.sh
```

这个脚本会：
1. 启动 PostgreSQL + pgvector Docker 容器
2. 初始化数据库表
3. 导入 10,000 条元数据（不含 embedding）
4. 生成 1,000 条 embedding（顺序模式，内存友好）
5. 创建 IVFFlat 向量索引

### 2. 手动分步执行

```bash
# 启动容器
docker-compose up -d

# 初始化表
docker-compose exec -T postgres psql -U valiref -d arxiv_db < scripts/setup_pgvector.sql

# 导入元数据（10,000条）
uv run python scripts/import_metadata.py

# 生成 embedding（顺序模式）
uv run python scripts/generate_embeddings.py --sequential --limit 1000

# 创建向量索引
docker-compose exec postgres psql -U valiref -d arxiv_db -c "CREATE INDEX idx_papers_embedding ON papers USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);"
```

## 查询示例

### 向量相似度搜索
```bash
uv run python scripts/query_papers.py "transformer architecture" -k 5
```

### 全文搜索
```bash
uv run python scripts/query_papers.py "neural network" --fulltext
```

### 混合搜索（推荐）
```bash
uv run python scripts/query_papers.py "machine learning" --hybrid
```

### 带过滤的搜索
```bash
# 只搜索 cs.AI 类别，2020年以后的论文
uv run python scripts/query_papers.py "deep learning" -c cs.AI -y 2020
```

## 配置说明

### 内存配置 (`scripts/postgresql_4g.conf`)

```ini
shared_buffers = 512MB          # 共享缓冲区
effective_cache_size = 2GB      # 有效缓存
work_mem = 64MB                 # 单查询内存
maintenance_work_mem = 256MB    # 维护操作内存
```

### Docker 内存限制 (`docker-compose.yml`)

```yaml
deploy:
  resources:
    limits:
      memory: 1.5G              # 容器内存上限
    reservations:
      memory: 512M              # 预留内存
```

## 加速技巧

### 1. 多进程并行生成 embedding

```bash
# 使用4个进程并行（需要更多内存）
uv run python scripts/generate_embeddings.py -w 4 --limit 10000
```

### 2. 批量导入优化

```python
# import_metadata.py 中的配置
BATCH_SIZE = 500  # 每批导入数量，可根据内存调整
```

### 3. IVFFlat 索引参数

```sql
-- lists 参数影响内存和精度
-- 小内存: lists = 50
-- 大内存: lists = 100-1000
CREATE INDEX idx_papers_embedding
ON papers USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 50);
```

### 4. 查询时调整 probes

```sql
-- 增加 probes 提高精度（稍慢）
SET ivfflat.probes = 10;

-- 减少 probes 提高速度（精度降低）
SET ivfflat.probes = 3;
```

## 文件说明

| 文件 | 说明 |
|------|------|
| `docker-compose.yml` | Docker 配置，内存限制1.5GB |
| `scripts/setup_pgvector.sql` | 数据库初始化脚本 |
| `scripts/import_metadata.py` | 元数据导入（10,000条测试） |
| `scripts/generate_embeddings.py` | Embedding 生成（多进程/顺序模式） |
| `scripts/query_papers.py` | 查询示例（向量/全文/混合） |
| `scripts/postgresql_4g.conf` | PostgreSQL 4GB内存优化配置 |
| `scripts/start_pgvector_test.sh` | 一键启动脚本 |

## 扩展：全量数据导入

小批量测试成功后，可以扩展到全部300万条数据：

### 策略1：分批导入

```python
# 修改 import_metadata.py
MAX_PAPERS = None  # 导入全部
BATCH_SIZE = 1000  # 增大批次

# 运行（需要较长时间）
uv run python scripts/import_metadata.py
```

### 策略2：后台生成 embedding

```bash
# 后台运行，生成全部 embedding
nohup uv run python scripts/generate_embeddings.py --sequential --limit 3000000 > embed.log 2>&1 &
```

### 策略3：只导入特定类别

```bash
# 预处理：只保留 cs.* 类别
grep '"categories": "cs\.' arxiv-metadata-oai-snapshot.json > arxiv-cs-only.jsonl

# 然后导入（约100万条）
```

## 常见问题

### Q: Docker 启动失败？

```bash
# 检查端口占用
sudo lsof -i :5432

# 清理并重启
docker-compose down -v
docker-compose up -d
```

### Q: 导入速度太慢？

- 检查是否在 SSD 上运行
- 增大 `BATCH_SIZE`（内存允许的情况下）
- 使用多进程生成 embedding

### Q: 内存不足？

- 减小 `shared_buffers` 到 `256MB`
- 使用顺序模式生成 embedding
- 减小 Docker 内存限制

### Q: 查询太慢？

- 确保已创建 IVFFlat 索引
- 增加 `ivfflat.probes` 值
- 添加类别/年份过滤减少搜索空间

## 依赖

```toml
[project.dependencies]
asyncpg = ">=0.29.0"
sentence-transformers = ">=2.2.0"
tqdm = ">=4.66.0"
torch = ">=2.0.0"
```

## 参考

- [pgvector GitHub](https://github.com/pgvector/pgvector)
- [pgvector 文档](https://github.com/pgvector/pgvector?tab=readme-ov-file#indexing)
- [sentence-transformers](https://www.sbert.net/)
