#!/bin/bash
# arXiv 向量数据库 - GPU笔记本一键部署脚本
# 用法: ./setup_gpu_server.sh [数据路径]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DATA_PATH="${1:-$HOME/下载/arxiv-metadata-oai-snapshot.json}"

echo "=========================================="
echo "🚀 arXiv 向量数据库 - GPU部署脚本"
echo "=========================================="
echo ""

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查命令是否存在
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# 步骤1: 检查系统环境
echo "📋 步骤1: 检查系统环境..."

if ! command_exists docker; then
    echo -e "${RED}❌ Docker未安装，请先安装Docker${NC}"
    echo "   安装命令: sudo apt-get install docker.io docker-compose"
    exit 1
fi

if ! command_exists nvidia-smi; then
    echo -e "${YELLOW}⚠️  未检测到NVIDIA驱动，将使用CPU模式${NC}"
    HAS_GPU=false
else
    echo -e "${GREEN}✅ 检测到NVIDIA GPU:${NC}"
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader | head -1
    HAS_GPU=true
fi

# 检查uv
if ! command_exists uv; then
    echo -e "${YELLOW}⚠️  uv未安装，正在安装...${NC}"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
fi

echo -e "${GREEN}✅ 环境检查通过${NC}"
echo ""

# 步骤2: 启动Docker服务
echo "📦 步骤2: 启动PostgreSQL服务..."
cd "$PROJECT_DIR"

sudo systemctl start docker 2>/dev/null || true
sudo docker-compose up -d

# 等待数据库就绪
echo "⏳ 等待数据库就绪..."
for i in {1..30}; do
    if sudo docker-compose exec -T postgres pg_isready -U valiref -d arxiv_db >/dev/null 2>&1; then
        echo -e "${GREEN}✅ 数据库已就绪${NC}"
        break
    fi
    echo "   等待中... ($i/30)"
    sleep 2
done

echo ""

# 步骤3: 检查数据文件
echo "📁 步骤3: 检查数据文件..."
if [ ! -f "$DATA_PATH" ]; then
    echo -e "${RED}❌ 错误: 找不到数据文件: $DATA_PATH${NC}"
    echo "   请指定正确的路径，例如:"
    echo "   ./setup_gpu_server.sh /path/to/arxiv-metadata.json"
    exit 1
fi

FILE_SIZE=$(du -h "$DATA_PATH" | cut -f1)
echo -e "${GREEN}✅ 找到数据文件: $FILE_SIZE${NC}"
echo ""

# 步骤4: 初始化数据库表
echo "🔧 步骤4: 初始化数据库表..."
sudo docker-compose exec -T postgres psql -U valiref -d arxiv_db < "$SCRIPT_DIR/setup_pgvector.sql" 2>/dev/null || true
echo -e "${GREEN}✅ 表结构已就绪${NC}"
echo ""

# 步骤5: 检查是否已有数据
echo "📊 步骤5: 检查现有数据..."
COUNT=$(sudo docker-compose exec -T postgres psql -U valiref -d arxiv_db -t -c "SELECT COUNT(*) FROM papers;" 2>/dev/null | tr -d ' ' || echo "0")

if [ "$COUNT" -gt "0" ]; then
    echo -e "${YELLOW}⚠️  数据库已有 $COUNT 条记录${NC}"
    read -p "是否清空重新导入? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🗑️  清空数据..."
        sudo docker-compose exec -T postgres psql -U valiref -d arxiv_db -c "TRUNCATE TABLE papers;" >/dev/null
        COUNT=0
    else
        echo "跳过导入，使用现有数据"
    fi
fi

# 步骤6: 导入元数据
if [ "$COUNT" -eq "0" ]; then
    echo "📥 步骤6: 导入元数据..."
    echo "   数据路径: $DATA_PATH"
    echo "   这可能需要20-40分钟..."
    echo ""

    # 创建符号链接（脚本内部使用固定路径）
    mkdir -p "$(dirname "$DATA_PATH")"
    if [ ! -f "/home/cyh/下载/arxiv-metadata-oai-snapshot.json" ]; then
        sudo ln -sf "$DATA_PATH" "/home/cyh/下载/arxiv-metadata-oai-snapshot.json" 2>/dev/null || true
    fi

    cd "$PROJECT_DIR"
    uv run python "$SCRIPT_DIR/import_metadata_sync.py"
fi

echo ""

# 步骤7: 生成Embedding（GPU加速）
echo "🧠 步骤7: 生成Embedding..."
echo "   检测设备..."

# 检查PyTorch是否支持CUDA
if $HAS_GPU; then
    CUDA_AVAILABLE=$(uv run python -c "import torch; print('YES' if torch.cuda.is_available() else 'NO')" 2>/dev/null || echo "NO")
    if [ "$CUDA_AVAILABLE" = "YES" ]; then
        echo -e "${GREEN}✅ GPU可用，将使用CUDA加速${NC}"
        DEVICE="cuda"
        # 估算时间：GPU约1-3小时
        echo "   预计时间: 1-3小时（GPU加速）"
    else
        echo -e "${YELLOW}⚠️  检测到GPU但PyTorch未配置CUDA${NC}"
        echo "   尝试安装CUDA版PyTorch..."
        uv pip install torch --index-url https://download.pytorch.org/whl/cu118
        DEVICE="cuda"
    fi
else
    echo -e "${YELLOW}⚠️  使用CPU模式${NC}"
    echo "   预计时间: 40-50小时"
    DEVICE="cpu"
fi

echo ""
read -p "是否现在开始生成Embedding? (Y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    echo "🚀 开始生成Embedding..."
    echo "   提示: 可以用 Ctrl+C 中断，之后重新运行脚本会继续"
    echo ""

    if [ "$DEVICE" = "cuda" ]; then
        uv run python "$SCRIPT_DIR/generate_embeddings_gpu.py"
    else
        uv run python "$SCRIPT_DIR/generate_embeddings_sync.py" --limit 3000000
    fi
else
    echo "跳过Embedding生成"
fi

echo ""

# 步骤8: 创建向量索引
echo "🔍 步骤8: 创建向量索引..."
EMBED_COUNT=$(sudo docker-compose exec -T postgres psql -U valiref -d arxiv_db -t -c "SELECT COUNT(embedding) FROM papers;" 2>/dev/null | tr -d ' ' || echo "0")

if [ "$EMBED_COUNT" -gt "1000" ]; then
    echo "   发现 $EMBED_COUNT 条embedding，创建索引..."
    sudo docker-compose exec -T postgres psql -U valiref -d arxiv_db -c \
        "CREATE INDEX IF NOT EXISTS idx_papers_embedding ON papers USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);" \
        >/dev/null 2>&1 || echo "   索引已存在或创建中"
    echo -e "${GREEN}✅ 向量索引已创建${NC}"
else
    echo -e "${YELLOW}⚠️  embedding数量不足（$EMBED_COUNT条），跳过索引创建${NC}"
fi

echo ""

# 步骤9: 最终统计
echo "📊 步骤9: 数据库统计..."
sudo docker-compose exec -T postgres psql -U valiref -d arxiv_db -c "
SELECT
    COUNT(*) as total_papers,
    COUNT(embedding) as with_embedding,
    ROUND(100.0 * COUNT(embedding) / COUNT(*), 1) as coverage_pct,
    pg_size_pretty(pg_total_relation_size('papers')) as table_size
FROM papers;
" 2>/dev/null || true

echo ""
echo "=========================================="
echo -e "${GREEN}✅ 部署完成！${NC}"
echo "=========================================="
echo ""
echo "📌 常用命令:"
echo ""
echo "  查看数据库状态:"
echo "    sudo docker-compose exec postgres psql -U valiref -d arxiv_db -c 'SELECT COUNT(*) FROM papers;'"
echo ""
echo "  查询论文（向量相似度）:"
echo "    uv run python scripts/query_papers_sync.py 'transformer architecture' -k 5"
echo ""
echo "  查询论文（全文搜索）:"
echo "    uv run python scripts/query_papers_sync.py 'neural network' --fulltext -k 5"
echo ""
echo "  继续生成Embedding（如中断了）:"
if $HAS_GPU; then
    echo "    uv run python scripts/generate_embeddings_gpu.py"
else
    echo "    uv run python scripts/generate_embeddings_sync.py --limit 3000000"
fi
echo ""
echo "  停止服务:"
echo "    sudo docker-compose down"
echo ""
echo "  进入数据库:"
echo "    sudo docker-compose exec postgres psql -U valiref -d arxiv_db"
echo ""
