#!/bin/bash
# arXiv 向量数据库 - WSL 一键部署脚本
# 适用于 Windows Subsystem for Linux (WSL2)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# 数据路径处理（支持 Windows 和 Linux 路径）
DATA_PATH="${1:-$HOME/Downloads/arxiv-metadata-oai-snapshot.json}"

# 如果路径不存在，尝试转换 Windows 路径
if [ ! -f "$DATA_PATH" ]; then
    # 尝试 Windows Downloads 目录
    WIN_USER=$(whoami)
    WIN_PATH="/mnt/c/Users/$WIN_USER/Downloads/arxiv-metadata-oai-snapshot.json"
    if [ -f "$WIN_PATH" ]; then
        echo "📁 在 Windows 目录找到数据文件"
        echo "   建议复制到 Linux 目录以获得更好性能..."
        cp "$WIN_PATH" "$HOME/Downloads/" 2>/dev/null || true
        DATA_PATH="$HOME/Downloads/arxiv-metadata-oai-snapshot.json"
    fi
fi

echo "=========================================="
echo "🚀 arXiv 向量数据库 - WSL 部署脚本"
echo "=========================================="
echo ""

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info() {
    echo -e "${BLUE}$1${NC}"
}

warn() {
    echo -e "${YELLOW}$1${NC}"
}

error() {
    echo -e "${RED}$1${NC}"
}

success() {
    echo -e "${GREEN}$1${NC}"
}

# WSL 检测
if ! grep -q "microsoft\|Microsoft" /proc/version 2>/dev/null; then
    warn "⚠️  未检测到 WSL 环境"
    warn "   此脚本针对 WSL 优化，但也可以在普通 Linux 运行"
    read -p "是否继续? (Y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        exit 0
    fi
else
    info "✅ 检测到 WSL 环境"
    # 提示使用 Linux 文件系统
    info "💡 提示: 在 WSL 中使用 Linux 文件系统 (~/) 比 Windows (/mnt/c) 性能更好"
fi
echo ""

# 步骤1: 检查 Docker
echo "📦 步骤1: 检查 Docker..."
if ! command -v docker &> /dev/null; then
    error "❌ Docker 未安装"
    echo ""
    echo "   WSL 中推荐使用 Docker Desktop:"
    echo "   1. 下载: https://www.docker.com/products/docker-desktop"
    echo "   2. 安装时勾选 'Use WSL 2 instead of Hyper-V'"
    echo "   3. 在 Settings > Resources > WSL Integration 中启用此发行版"
    exit 1
fi

# 检查 Docker 是否在运行
if ! docker info &> /dev/null; then
    error "❌ Docker 守护进程未连接"
    echo ""
    echo "   请确保:"
    echo "   1. Docker Desktop 已启动"
    echo "   2. 在 Docker Desktop 设置中启用了 WSL 集成"
    exit 1
fi

success "✅ Docker 已就绪"
echo ""

# 步骤2: 安装 uv（如果未安装）
echo "📥 步骤2: 检查 uv..."
if ! command -v uv &> /dev/null; then
    warn "uv 未安装，正在安装..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
    # 添加到 .bashrc（如果未添加）
    if ! grep -q ".cargo/bin" "$HOME/.bashrc" 2>/dev/null; then
        echo 'export PATH="$HOME/.cargo/bin:$PATH"' >> "$HOME/.bashrc"
        info "已将 uv 添加到 PATH，请运行: source ~/.bashrc"
    fi
fi

# 确保 PATH 中有 uv
export PATH="$HOME/.cargo/bin:$PATH"

if command -v uv &> /dev/null; then
    success "✅ uv 已安装: $(uv --version)"
else
    error "❌ uv 安装失败"
    exit 1
fi
echo ""

# 步骤3: 启动 PostgreSQL
echo "🐳 步骤3: 启动 PostgreSQL..."
cd "$PROJECT_DIR"

# WSL 中 Docker Compose 可能有不同名称
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
elif docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
else
    error "❌ 未找到 docker-compose"
    exit 1
fi

$DOCKER_COMPOSE up -d

# 等待数据库就绪
echo "⏳ 等待数据库就绪..."
for i in {1..30}; do
    if $DOCKER_COMPOSE exec -T postgres pg_isready -U valiref -d arxiv_db >/dev/null 2>&1; then
        success "✅ 数据库已就绪"
        break
    fi
    echo "   等待中... ($i/30)"
    sleep 2
done

echo ""

# 步骤4: 检查数据文件
echo "📁 步骤4: 检查数据文件..."
if [ ! -f "$DATA_PATH" ]; then
    error "❌ 错误: 找不到数据文件: $DATA_PATH"
    echo ""
    echo "   请从原机器复制数据:"
    echo "   scp user@<原机器IP>:/home/cyh/下载/arxiv-metadata-oai-snapshot.json ~/Downloads/"
    echo ""
    echo "   或指定其他路径:"
    echo "   ./setup_wsl.sh /path/to/arxiv-metadata.json"
    exit 1
fi

FILE_SIZE=$(du -h "$DATA_PATH" | cut -f1)
success "✅ 找到数据文件: $FILE_SIZE"
echo "   路径: $DATA_PATH"

# 建议移动到 Linux 文件系统以获得更好性能
if [[ "$DATA_PATH" == /mnt/* ]]; then
    warn "⚠️  数据文件在 Windows 分区 (/mnt/*)"
    warn "   建议移动到 Linux 文件系统以获得更好性能"
    LINUX_PATH="$HOME/Downloads/arxiv-metadata-oai-snapshot.json"
    if [ ! -f "$LINUX_PATH" ]; then
        echo "   正在复制到 $LINUX_PATH..."
        cp "$DATA_PATH" "$LINUX_PATH"
        DATA_PATH="$LINUX_PATH"
        success "✅ 已复制到 Linux 目录"
    else
        DATA_PATH="$LINUX_PATH"
        info "   使用已存在的 Linux 目录文件"
    fi
fi
echo ""

# 步骤5: 初始化数据库
echo "🔧 步骤5: 初始化数据库..."
$DOCKER_COMPOSE exec -T postgres psql -U valiref -d arxiv_db < "$SCRIPT_DIR/setup_pgvector.sql" 2>/dev/null || true
success "✅ 数据库表结构已就绪"
echo ""

# 步骤6: 检查现有数据
echo "📊 步骤6: 检查现有数据..."
COUNT=$($DOCKER_COMPOSE exec -T postgres psql -U valiref -d arxiv_db -t -c "SELECT COUNT(*) FROM papers;" 2>/dev/null | tr -d ' ' | head -1 || echo "0")

if [ "$COUNT" -gt "0" ]; then
    warn "⚠️  数据库已有 $COUNT 条记录"
    read -p "是否清空重新导入? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🗑️  清空数据..."
        $DOCKER_COMPOSE exec -T postgres psql -U valiref -d arxiv_db -c "TRUNCATE TABLE papers;" >/dev/null
        COUNT=0
    else
        echo "跳过导入，使用现有数据"
    fi
fi

# 步骤7: 导入元数据
if [ "$COUNT" -eq "0" ]; then
    echo "📥 步骤7: 导入元数据..."
    echo "   数据路径: $DATA_PATH"
    echo "   这可能需要20-40分钟..."
    echo ""

    cd "$PROJECT_DIR"
    uv run python "$SCRIPT_DIR/import_metadata_sync.py" --data "$DATA_PATH"
fi
echo ""

# 步骤8: 检测 GPU 并生成 Embedding
echo "🧠 步骤8: 生成 Embedding..."

# 检测 CUDA
if command -v nvidia-smi &> /dev/null && nvidia-smi &> /dev/null; then
    success "✅ 检测到 NVIDIA GPU"
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader | head -1
    DEVICE="cuda"

    # 检查 PyTorch CUDA 支持
    CUDA_AVAILABLE=$(uv run python -c "import torch; print('YES' if torch.cuda.is_available() else 'NO')" 2>/dev/null || echo "NO")
    if [ "$CUDA_AVAILABLE" != "YES" ]; then
        warn "⚠️  PyTorch 未配置 CUDA，尝试安装..."
        uv pip install torch --index-url https://download.pytorch.org/whl/cu118 2>/dev/null || true
    fi

    echo ""
    echo "   GPU 模式预计时间: 1-3小时"
else
    warn "⚠️  未检测到 GPU，将使用 CPU 模式"
    warn "   CPU 模式预计时间: 40-50小时"
    DEVICE="cpu"
fi

echo ""
read -p "是否现在开始生成 Embedding? (Y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    echo "🚀 开始生成 Embedding..."

    if [ "$DEVICE" = "cuda" ]; then
        uv run python "$SCRIPT_DIR/generate_embeddings_gpu.py"
    else
        uv run python "$SCRIPT_DIR/generate_embeddings_sync.py" --limit 3000000
    fi
else
    echo "跳过 Embedding 生成"
fi
echo ""

# 步骤9: 创建向量索引
echo "🔍 步骤9: 创建向量索引..."
EMBED_COUNT=$($DOCKER_COMPOSE exec -T postgres psql -U valiref -d arxiv_db -t -c "SELECT COUNT(embedding) FROM papers;" 2>/dev/null | tr -d ' ' | head -1 || echo "0")

if [ "$EMBED_COUNT" -gt "1000" ]; then
    echo "   发现 $EMBED_COUNT 条 embedding，创建索引..."
    $DOCKER_COMPOSE exec -T postgres psql -U valiref -d arxiv_db -c \
        "CREATE INDEX IF NOT EXISTS idx_papers_embedding ON papers USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);" \
        >/dev/null 2>&1 || warn "索引创建可能需要更长时间"
    success "✅ 向量索引已创建"
else
    warn "⚠️  embedding 数量不足（$EMBED_COUNT 条），跳过索引创建"
fi
echo ""

# 步骤10: 最终统计
echo "📊 步骤10: 数据库统计..."
$DOCKER_COMPOSE exec -T postgres psql -U valiref -d arxiv_db -c "
SELECT
    COUNT(*) as total_papers,
    COUNT(embedding) as with_embedding,
    ROUND(100.0 * COUNT(embedding) / COUNT(*), 1) as coverage_pct,
    pg_size_pretty(pg_total_relation_size('papers')) as table_size
FROM papers;
" 2>/dev/null || true

echo ""
echo "=========================================="
success "✅ WSL 部署完成！"
echo "=========================================="
echo ""
echo "📌 常用命令:"
echo ""
echo "  查看数据库状态:"
echo "    cd $PROJECT_DIR"
echo "    $DOCKER_COMPOSE exec postgres psql -U valiref -d arxiv_db -c 'SELECT COUNT(*) FROM papers;'"
echo ""
echo "  查询论文（向量相似度）:"
echo "    uv run python scripts/query_papers_sync.py 'transformer architecture' -k 5"
echo ""
echo "  查询论文（全文搜索）:"
echo "    uv run python scripts/query_papers_sync.py 'neural network' --fulltext -k 5"
echo ""
echo "  继续生成 Embedding（如中断了）:"
if [ "$DEVICE" = "cuda" ]; then
    echo "    uv run python scripts/generate_embeddings_gpu.py"
else
    echo "    uv run python scripts/generate_embeddings_sync.py --limit 3000000"
fi
echo ""
echo "  停止服务:"
echo "    $DOCKER_COMPOSE down"
echo ""
echo "💡 WSL 提示:"
echo "   - 使用 code . 可在 VS Code 中打开项目"
echo "   - 文件放在 ~/ 比 /mnt/c/ 性能更好"
echo "   - Docker Desktop 需要保持运行"
echo ""
