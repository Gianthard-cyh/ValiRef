#!/bin/bash
# arXiv 向量数据库 - 环境检测脚本
# 在GPU笔记本上运行，检查部署环境是否就绪

set -e

echo "=========================================="
echo "🔍 arXiv 向量数据库 - 环境检测"
echo "=========================================="
echo ""

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ERRORS=0
WARNINGS=0

# 检查函数
check_pass() {
    echo -e "${GREEN}✅ $1${NC}"
}

check_fail() {
    echo -e "${RED}❌ $1${NC}"
    ((ERRORS++))
}

check_warn() {
    echo -e "${YELLOW}⚠️  $1${NC}"
    ((WARNINGS++))
}

# 1. 检查操作系统
echo "📋 1. 操作系统信息"
echo "   系统: $(uname -s)"
echo "   架构: $(uname -m)"
echo "   版本: $(cat /etc/os-release 2>/dev/null | grep PRETTY_NAME | cut -d'"' -f2 || echo 'Unknown')"
echo ""

# 2. 检查Docker
echo "🐳 2. Docker检查"
if command -v docker &> /dev/null; then
    check_pass "Docker已安装"
    docker --version

    if command -v docker-compose &> /dev/null; then
        check_pass "Docker Compose已安装"
        docker-compose --version
    else
        check_fail "Docker Compose未安装"
        echo "   安装命令: sudo apt-get install docker-compose-plugin"
    fi

    # 检查Docker服务
    if sudo systemctl is-active --quiet docker 2>/dev/null; then
        check_pass "Docker服务运行中"
    else
        check_warn "Docker服务未运行，将尝试启动"
        sudo systemctl start docker 2>/dev/null || check_fail "无法启动Docker服务"
    fi
else
    check_fail "Docker未安装"
    echo "   安装命令:"
    echo "   sudo apt-get update"
    echo "   sudo apt-get install -y docker.io docker-compose-plugin"
fi
echo ""

# 3. 检查NVIDIA驱动和CUDA
echo "🎮 3. GPU检查"
if command -v nvidia-smi &> /dev/null; then
    check_pass "NVIDIA驱动已安装"
    echo "   GPU信息:"
    nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader | head -1 | sed 's/^/     /'

    # 检查CUDA
    if command -v nvcc &> /dev/null; then
        check_pass "CUDA已安装"
        nvcc --version | grep "release" | sed 's/^/     /'
    else
        check_warn "CUDA未安装（PyTorch会自动下载CUDA runtime）"
    fi
else
    check_warn "未检测到NVIDIA驱动，将使用CPU模式（慢10-20倍）"
    echo "   如需GPU加速，请安装驱动:"
    echo "   sudo apt-get install -y nvidia-driver-535"
fi
echo ""

# 4. 检查Python
echo "🐍 4. Python检查"
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    check_pass "Python已安装: $PYTHON_VERSION"

    # 检查版本是否>=3.10
    if python3 -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" 2>/dev/null; then
        check_pass "Python版本符合要求 (>=3.10)"
    else
        check_warn "Python版本过低，建议>=3.10"
    fi
else
    check_fail "Python未安装"
    echo "   安装命令: sudo apt-get install -y python3 python3-pip"
fi
echo ""

# 5. 检查uv
echo "📦 5. uv包管理器检查"
if command -v uv &> /dev/null; then
    check_pass "uv已安装"
    uv --version
else
    check_warn "uv未安装，将自动安装"
    echo "   安装命令: curl -LsSf https://astral.sh/uv/install.sh | sh"
fi
echo ""

# 6. 检查数据文件
echo "📁 6. 数据文件检查"
DATA_PATHS=(
    "$HOME/下载/arxiv-metadata-oai-snapshot.json"
    "$HOME/Downloads/arxiv-metadata-oai-snapshot.json"
    "/tmp/arxiv-metadata-oai-snapshot.json"
)

DATA_FOUND=false
for path in "${DATA_PATHS[@]}"; do
    if [ -f "$path" ]; then
        check_pass "找到数据文件: $path"
        FILE_SIZE=$(du -h "$path" | cut -f1)
        echo "   文件大小: $FILE_SIZE"
        DATA_FOUND=true
        break
    fi
done

if [ "$DATA_FOUND" = false ]; then
    check_warn "未找到数据文件"
    echo "   请从原机器复制数据:"
    echo "   scp user@<原机器IP>:/home/cyh/下载/arxiv-metadata-oai-snapshot.json ~/Downloads/"
fi
echo ""

# 7. 检查磁盘空间
echo "💾 7. 磁盘空间检查"
DISK_USAGE=$(df -h . | tail -1 | awk '{print $4}')
DISK_AVAIL=$(df . | tail -1 | awk '{print $4}')
echo "   可用空间: $DISK_USAGE"

# 需要约20GB（数据4.8GB + Docker镜像 + 数据库）
if [ "$DISK_AVAIL" -gt 20971520 ]; then  # 20GB = 20*1024*1024 KB
    check_pass "磁盘空间充足"
else
    check_warn "磁盘空间可能不足，建议至少20GB可用"
fi
echo ""

# 8. 检查内存
echo "🧠 8. 内存检查"
if command -v free &> /dev/null; then
    MEM_TOTAL=$(free -h | awk '/^Mem:/{print $2}')
    MEM_AVAIL=$(free -h | awk '/^Mem:/{print $7}')
    echo "   总内存: $MEM_TOTAL"
    echo "   可用内存: $MEM_AVAIL"

    # 检查是否>=4GB
    MEM_KB=$(free | awk '/^Mem:/{print $2}')
    if [ "$MEM_KB" -gt 4194304 ]; then  # 4GB
        check_pass "内存充足"
    else
        check_warn "内存不足4GB，可能影响性能"
    fi
fi
echo ""

# 总结
echo "=========================================="
echo "📊 检测结果总结"
echo "=========================================="
if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}✅ 所有检查通过！环境已就绪${NC}"
    echo ""
    echo "🚀 可以开始部署:"
    echo "   ./scripts/setup_gpu_server.sh"
elif [ $ERRORS -eq 0 ]; then
    echo -e "${YELLOW}⚠️  环境基本就绪，但有警告项${NC}"
    echo "   警告数: $WARNINGS"
    echo ""
    echo "🚀 可以尝试部署，但可能需要处理警告项"
else
    echo -e "${RED}❌ 环境未就绪，请先修复错误${NC}"
    echo "   错误数: $ERRORS"
    echo "   警告数: $WARNINGS"
    exit 1
fi
echo ""

# 提供下一步建议
echo "📖 下一步:"
if ! command -v docker &> /dev/null; then
    echo "   1. 安装Docker:"
    echo "      sudo apt-get update"
    echo "      sudo apt-get install -y docker.io docker-compose-plugin"
fi

if ! command -v nvidia-smi &> /dev/null; then
    echo "   2. (可选)安装NVIDIA驱动以启用GPU:"
    echo "      sudo apt-get install -y nvidia-driver-535"
    echo "      sudo reboot"
fi

if [ "$DATA_FOUND" = false ]; then
    echo "   3. 复制数据文件到 ~/Downloads/"
fi

echo "   4. 运行部署脚本:"
echo "      ./scripts/setup_gpu_server.sh"
echo ""
