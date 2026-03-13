#!/bin/bash
# arXiv 向量数据库启动脚本

set -e

echo "🚀 arXiv 向量数据库 - 小批量测试启动脚本"
echo "========================================"

# 检查Docker
if ! command -v docker &> /dev/null; then
    echo "❌ 错误: 需要安装 Docker"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ 错误: 需要安装 docker-compose"
    exit 1
fi

# 步骤1: 启动PostgreSQL容器
echo ""
echo "📦 步骤1: 启动 PostgreSQL + pgvector 容器..."
docker-compose up -d

# 等待服务就绪
echo ""
echo "⏳ 等待数据库就绪..."
sleep 5

for i in {1..30}; do
    if docker-compose exec -T postgres pg_isready -U valiref -d arxiv_db > /dev/null 2>&1; then
        echo "✅ 数据库已就绪"
        break
    fi
    echo "   等待中... ($i/30)"
    sleep 2
done

# 步骤2: 初始化数据库
echo ""
echo "🔧 步骤2: 初始化数据库表..."
docker-compose exec -T postgres psql -U valiref -d arxiv_db < scripts/setup_pgvector.sql

# 步骤3: 检查数据文件
echo ""
echo "📁 步骤3: 检查数据文件..."
if [ ! -f "/home/cyh/下载/arxiv-metadata-oai-snapshot.json" ]; then
    echo "⚠️  警告: 找不到 arxiv 元数据文件"
    echo "   预期路径: /home/cyh/下载/arxiv-metadata-oai-snapshot.json"
    echo ""
    echo "   请确认文件路径，然后运行:"
    echo "   uv run python scripts/import_metadata.py"
    exit 0
fi

# 步骤4: 导入元数据（小批量测试）
echo ""
echo "📥 步骤4: 导入元数据（小批量: 10000条）..."
uv run python scripts/import_metadata.py

# 步骤5: 生成embedding
echo ""
echo "🧠 步骤5: 生成 embedding（顺序模式，内存友好）..."
uv run python scripts/generate_embeddings.py --sequential --limit 1000

# 步骤6: 创建向量索引
echo ""
echo "🔍 步骤6: 创建向量索引..."
docker-compose exec -T postgres psql -U valiref -d arxiv_db -c "CREATE INDEX IF NOT EXISTS idx_papers_embedding ON papers USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);"

echo ""
echo "========================================"
echo "✅ 小批量测试环境已就绪！"
echo ""
echo "📌 可用命令:"
echo ""
echo "  1. 向量相似度搜索:"
echo "     uv run python scripts/query_papers.py 'transformer architecture' -k 5"
echo ""
echo "  2. 全文搜索:"
echo "     uv run python scripts/query_papers.py 'neural network' --fulltext"
echo ""
echo "  3. 混合搜索:"
echo "     uv run python scripts/query_papers.py 'machine learning' --hybrid"
echo ""
echo "  4. 带过滤的搜索:"
echo "     uv run python scripts/query_papers.py 'deep learning' -c cs.AI -y 2020"
echo ""
echo "  5. 查看Docker状态:"
echo "     docker-compose ps"
echo ""
echo "  6. 进入数据库:"
echo "     docker-compose exec postgres psql -U valiref -d arxiv_db"
echo ""
echo "  7. 停止服务:"
echo "     docker-compose down"
echo ""
