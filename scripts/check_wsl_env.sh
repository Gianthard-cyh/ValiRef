#!/bin/bash
# arXiv 向量数据库 - WSL 环境检测脚本
# 在 WSL (Windows Subsystem for Linux) 中运行

set -e

echo "=========================================="
echo "🔍 arXiv 向量数据库 - WSL环境检测"
echo "=========================================="
echo ""

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# 检测 WSL 版本
echo "🪟 0. WSL 环境检测"
if grep -q "microsoft" /proc/version 2>/dev/null || grep -q "Microsoft" /proc/version 2>/dev/null; then
    WSL_VERSION=$(uname -r | grep -oE 'WSL[0-9]' || echo "WSL")
    check_pass "检测到 $WSL_VERSION 环境"

    # 检查 WSL 版本
    if [ -f /proc/sys/kernel/osrelease ]; then
        if grep -q "WSL2" /proc/sys/kernel/osrelease 2>/dev/null || uname -r | grep -q "WSL2"; then
            check_pass "WSL2 已启用（支持Docker和GPU）"
        else
            check_warn "检测到 WSL1，建议升级到 WSL2"
            echo "   升级命令（在PowerShell管理员模式）:"
            echo "   wsl --set-version <发行版名称> 2"
        fi
    fi
else
    check_warn "未检测到 WSL 环境，将在普通 Linux 模式运行"
fi
echo ""

# 1. 检查操作系统
echo "📋 1. 系统信息"
echo "   内核: $(uname -r)"
echo "   发行版: $(lsb_release -d 2>/dev/null | cut -f2 || cat /etc/os-release | grep PRETTY_NAME | cut -d'"' -f2)"
echo ""

# 2. 检查Docker（WSL特殊处理）
echo "🐳 2. Docker检查"

# 检查 Docker Desktop for Windows
if command -v docker &> /dev/null; then
    check_pass "Docker CLI 已安装"
    docker --version

    # 检查 Docker 守护进程
    if docker info &> /dev/null; then
        check_pass "Docker 守护进程可连接"

        # 检查是否为 Docker Desktop
        if docker info 2>/dev/null | grep -q "Docker Desktop"; then
            check_pass "Docker Desktop for Windows 已安装"
            echo "   ℹ️  使用 Docker Desktop 的后端"
        fi
    else
        check_fail "Docker 守护进程未运行"
        echo "   请确保 Docker Desktop 已启动："
        echo "   1. 打开 Docker Desktop"
        echo "   2. 在 Settings > Resources > WSL Integration 中启用此发行版"
        echo "   3. 点击 Apply & Restart"
    fi
else
    check_fail "Docker CLI 未安装"
    echo "   WSL 中建议使用 Docker Desktop for Windows:"
    echo "   1. 下载安装: https://www.docker.com/products/docker-desktop"
    echo "   2. 在设置中启用 WSL2 后端"
    echo "   3. 在 WSL Integration 中启用此发行版"
fi

# 检查 docker-compose
if command -v docker-compose &> /dev/null || docker compose version &> /dev/null; then
    check_pass "Docker Compose 已安装"
else
    check_warn "Docker Compose 未找到（Docker Desktop 通常自带）"
fi
echo ""

# 3. 检查 NVIDIA 驱动和 CUDA（WSL2 GPU支持）
echo "🎮 3. GPU检查（WSL2）"

# WSL2 GPU 需要特定的驱动
if [ -d /usr/lib/wsl ]; then
    check_pass "检测到 WSL2 GPU 支持目录"
fi

if command -v nvidia-smi &> /dev/null; then
    check_pass "NVIDIA 驱动已安装"
    echo "   GPU信息:"
    nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>/dev/null | head -1 | sed 's/^/     /'

    # 检查是否为 WSL 版驱动
    if nvidia-smi 2>&1 | grep -q "WSL"; then
        check_pass "检测到 WSL 版 NVIDIA 驱动"
    fi
else
    check_warn "未检测到 nvidia-smi"
    echo "   在 WSL2 中使用 GPU 需要："
    echo "   1. Windows 主机安装 NVIDIA 驱动（不是 WSL 内部）"
    echo "   2. 驱动下载: https://www.nvidia.com/Download/index.aspx"
    echo "   3. 确保是支持 WSL 的版本（>= 465.21）"
    echo ""
    echo "   安装后，WSL2 会自动使用主机的 GPU"
fi

# 检查 CUDA（可选）
if command -v nvcc &> /dev/null; then
    check_pass "CUDA 已安装"
    nvcc --version | grep "release" | sed 's/^/     /'
else
    check_warn "CUDA 未安装（PyTorch 会自动下载 CUDA runtime）"
    echo "   如需手动安装 CUDA in WSL:"
    echo "   https://docs.nvidia.com/cuda/wsl-user-guide/index.html"
fi
echo ""

# 4. 检查Python
echo "🐍 4. Python检查"
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    check_pass "Python已安装: $PYTHON_VERSION"

    # 检查版本
    if python3 -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" 2>/dev/null; then
        check_pass "Python版本符合要求 (>=3.10)"
    else
        check_warn "Python版本过低"
    fi
else
    check_fail "Python未安装"
    echo "   Ubuntu/Debian: sudo apt-get install -y python3 python3-pip"
fi
echo ""

# 5. 检查uv
echo "📦 5. uv包管理器检查"
if command -v uv &> /dev/null; then
    check_pass "uv已安装"
    uv --version
else
    check_warn "uv未安装"
    echo "   安装命令: curl -LsSf https://astral.sh/uv/install.sh | sh"
fi
echo ""

# 6. 检查数据文件（WSL路径特殊处理）
echo "📁 6. 数据文件检查"

# WSL 中的 Windows 路径
WINDOWS_DOWNLOADS="/mnt/c/Users/$(whoami)/Downloads/arxiv-metadata-oai-snapshot.json"
LINUX_DOWNLOADS="$HOME/Downloads/arxiv-metadata-oai-snapshot.json"
LINUX_CN_DOWNLOADS="$HOME/下载/arxiv-metadata-oai-snapshot.json"

DATA_PATHS=(
    "$LINUX_CN_DOWNLOADS"
    "$LINUX_DOWNLOADS"
    "$WINDOWS_DOWNLOADS"
    "/tmp/arxiv-metadata-oai-snapshot.json"
)

DATA_FOUND=false
for path in "${DATA_PATHS[@]}"; do
    if [ -f "$path" ]; then
        check_pass "找到数据文件: $path"
        FILE_SIZE=$(du -h "$path" | cut -f1)
        echo "   文件大小: $FILE_SIZE"
        DATA_FOUND=true
        DATA_PATH="$path"
        break
    fi
done

if [ "$DATA_FOUND" = false ]; then
    check_warn "未找到数据文件"
    echo ""
    echo "   📥 数据文件位置选项:"
    echo ""
    echo "   选项A: 放在 WSL Linux 文件系统（推荐，性能更好）:"
    echo "      ~/Downloads/arxiv-metadata-oai-snapshot.json"
    echo "      ~/下载/arxiv-metadata-oai-snapshot.json"
    echo ""
    echo "   选项B: 放在 Windows 目录（可从 Windows 直接访问）:"
    echo "      C:/Users/$(whoami)/Downloads/arxiv-metadata-oai-snapshot.json"
    echo "      在 WSL 中路径为: $WINDOWS_DOWNLOADS"
    echo ""
    echo "   复制命令示例:"
    echo "      cp /mnt/c/Users/<用户名>/Downloads/arxiv-metadata-oai-snapshot.json ~/Downloads/"
fi
echo ""

# 7. 检查磁盘空间
echo "💾 7. 磁盘空间检查"
# WSL 磁盘空间检查
if df -h . &> /dev/null; then
    DISK_AVAIL=$(df -h . | tail -1 | awk '{print $4}')
    echo "   WSL 可用空间: $DISK_AVAIL"

    # 检查 Windows C 盘（如果是从 WSL 访问）
    if [ -d /mnt/c ]; then
        WIN_AVAIL=$(df -h /mnt/c 2>/dev/null | tail -1 | awk '{print $4}')
        echo "   Windows C盘可用: $WIN_AVAIL"
    fi

    DISK_AVAIL_KB=$(df . | tail -1 | awk '{print $4}')
    if [ "$DISK_AVAIL_KB" -gt 20971520 ]; then
        check_pass "磁盘空间充足（建议 >20GB）"
    else
        check_warn "磁盘空间可能不足"
    fi
fi
echo ""

# 8. 检查内存
echo "🧠 8. 内存检查"
if command -v free &> /dev/null; then
    MEM_TOTAL=$(free -h | awk '/^Mem:/{print $2}')
    MEM_AVAIL=$(free -h | awk '/^Mem:/{print $7}')
    echo "   总内存: $MEM_TOTAL"
    echo "   可用内存: $MEM_AVAIL"

    MEM_KB=$(free | awk '/^Mem:/{print $2}')
    if [ "$MEM_KB" -gt 4194304 ]; then
        check_pass "内存充足 (>4GB)"
    else
        check_warn "内存不足4GB"
        echo "   WSL 默认内存有限，可在 .wslconfig 中增加"
    fi
fi

# WSL 内存配置提示
if [ -f /mnt/c/Users/$USER/.wslconfig ] || [ -f $HOME/.wslconfig ]; then
    check_pass "检测到 WSL 配置文件"
else
    info "如需调整 WSL 内存限制，创建 %USERPROFILE%\.wslconfig:"
    echo "   [wsl2]"
    echo "   memory=8GB"
    echo "   processors=4"
fi
echo ""

# 总结
echo "=========================================="
echo "📊 检测结果总结"
echo "=========================================="

if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}✅ WSL 环境已就绪！${NC}"
    echo ""
    echo "🚀 开始部署:"
    if [ "$DATA_FOUND" = true ]; then
        echo "   ./scripts/setup_wsl.sh $DATA_PATH"
    else
        echo "   ./scripts/setup_wsl.sh ~/Downloads/arxiv-metadata-oai-snapshot.json"
    fi
elif [ $ERRORS -eq 0 ]; then
    echo -e "${YELLOW}⚠️  环境基本就绪，有 $WARNINGS 个警告${NC}"
    echo ""
    echo "🚀 可以尝试部署"
else
    echo -e "${RED}❌ 环境未就绪，有 $ERRORS 个错误${NC}"
    if [ $WARNINGS -gt 0 ]; then
        echo "   还有 $WARNINGS 个警告"
    fi
    exit 1
fi
echo ""

# WSL 特有提示
echo "💡 WSL 提示:"
echo ""
echo "   1. 文件系统性能:"
echo "      - Linux 文件系统 (~/) 比 Windows (/mnt/c) 更快"
echo "      - 建议将数据放在 ~/Downloads/ 而非 C:\"
echo ""
echo "   2. Docker 设置:"
echo "      - 在 Docker Desktop > Settings > Resources > WSL Integration"
echo "      - 启用 'Enable integration with my default WSL distro'"
echo ""
echo "   3. GPU 支持:"
echo "      - 确保 Windows 主机安装了最新 NVIDIA 驱动"
echo "      - WSL2 会自动共享主机的 GPU"
echo ""
echo "   4. 常见问题:"
echo "      - 如果遇到路径问题，使用 Linux 风格的路径"
echo "      - Docker 权限问题: sudo usermod -aG docker $USER"
echo ""
