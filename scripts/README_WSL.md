# arXiv 向量数据库 - WSL 部署指南

> **Agent请注意**：目标环境是 **Windows + WSL2**，不是原生 Linux！

## 🪟 WSL 环境说明

- **WSL2**: 完整 Linux 内核，支持 Docker 和 GPU
- **WSL1**: 不支持 Docker 和 GPU（如果检测到 WSL1，建议升级）
- **路径差异**: WSL 可以访问 Windows 文件（`/mnt/c/`），但性能较慢

## ⚡ 前置要求

### Windows 主机端

1. **Windows 版本**: Windows 10 版本 2004+ 或 Windows 11
2. **WSL2**: 已启用
3. **Docker Desktop**: 安装并配置 WSL2 后端
4. **NVIDIA 驱动**（GPU 模式）: Windows 主机安装最新驱动

### 检查命令

在 Windows PowerShell（管理员）中运行：

```powershell
# 检查 WSL 版本
wsl --list --verbose

# 确保是 WSL2
wsl --set-version <发行版名称> 2

# 设置默认 WSL 版本
wsl --set-default-version 2
```

## 🚀 快速部署

### 步骤1: 环境检测

```bash
# 在 WSL 中运行
cd ValiRef
./scripts/check_wsl_env.sh
```

此脚本会检测：
- ✅ WSL 版本（WSL1/WSL2）
- ✅ Docker Desktop 连接
- ✅ NVIDIA GPU 驱动
- ✅ 数据文件位置
- ✅ 磁盘/内存空间

### 步骤2: 复制数据文件

**方式A: 从原机器复制（推荐）**

```bash
# 在 WSL 中执行
mkdir -p ~/Downloads
scp user@<原机器IP>:/home/cyh/下载/arxiv-metadata-oai-snapshot.json ~/Downloads/
```

**方式B: 从 Windows 复制**

```bash
# Windows 文件在 WSL 中的路径
WIN_PATH="/mnt/c/Users/$(whoami)/Downloads/arxiv-metadata-oai-snapshot.json"

# 复制到 Linux 文件系统（性能更好）
cp "$WIN_PATH" ~/Downloads/
```

### 步骤3: 一键部署

```bash
./scripts/setup_wsl.sh ~/Downloads/arxiv-metadata-oai-snapshot.json
```

或分步执行：

```bash
# 1. 启动数据库
docker-compose up -d

# 2. 安装依赖
uv sync

# 3. 导入元数据
uv run python scripts/import_metadata_sync.py --data ~/Downloads/arxiv-metadata-oai-snapshot.json

# 4. 生成 Embedding（GPU自动检测）
uv run python scripts/generate_embeddings_gpu.py

# 5. 创建索引
docker-compose exec postgres psql -U valiref -d arxiv_db -c "CREATE INDEX idx_papers_embedding ON papers USING ivfflat (embedding vector_cosine_ops);"
```

## 🔧 常见问题

### Docker 连接失败

**问题**: `Cannot connect to the Docker daemon`

**解决**:
1. 确保 Docker Desktop 已启动
2. 在 Docker Desktop > Settings > Resources > WSL Integration 中启用你的发行版
3. 重启 WSL: `wsl --shutdown`

### GPU 未检测到

**问题**: WSL 中 `nvidia-smi` 找不到或 PyTorch 无法使用 CUDA

**解决**:
1. Windows 主机安装 WSL 版 NVIDIA 驱动:
   https://developer.nvidia.com/cuda/wsl

2. 确保驱动版本 >= 465.21

3. 检查 GPU 是否可用:
   ```bash
   nvidia-smi
   ```

### 内存不足

**问题**: WSL 默认只使用部分内存

**解决**:

在 Windows 用户目录创建 `.wslconfig` 文件:

```ini
# %USERPROFILE%\.wslconfig
[wsl2]
memory=8GB
processors=4
swap=4GB
```

然后重启 WSL:
```powershell
wsl --shutdown
```

### 磁盘空间不足

**问题**: WSL 虚拟磁盘占满

**解决**:
1. 清理 Docker:
   ```bash
   docker system prune -a
   ```

2. 压缩 WSL 虚拟磁盘（Windows PowerShell）:
   ```powershell
   # 关闭 WSL
   wsl --shutdown

   # 找到 ext4.vhdx 并压缩
   # 通常位于: %LOCALAPPDATA%\Packages\<发行版>\LocalState\ext4.vhdx
   ```

### 文件路径问题

**问题**: Windows 路径和 Linux 路径混淆

**解决**:
- Linux 路径: `~/Downloads/file.json` 或 `/home/user/file.json`
- Windows 路径: `/mnt/c/Users/user/Downloads/file.json`

**建议**: 始终将数据放在 Linux 文件系统（`~`）而非 Windows（`/mnt/c`）

## 📊 性能对比

| 配置 | 元数据导入 | Embedding生成 |
|------|-----------|---------------|
| WSL2 + GPU | ~30分钟 | **1-3小时** ✅ |
| WSL2 + CPU | ~30分钟 | 40-50小时 |
| WSL1 | 不支持 ❌ | 不支持 ❌ |

## 💡 WSL 最佳实践

### 1. 文件系统选择
```bash
# ✅ 推荐：Linux 文件系统（性能更好）
~/Downloads/arxiv-data.json

# ⚠️ 避免：Windows 文件系统（慢 5-10x）
/mnt/c/Users/.../arxiv-data.json
```

### 2. IDE 集成
```bash
# 在 WSL 中打开 VS Code
code .

# Windows 中的 VS Code 会自动连接到 WSL
```

### 3. 后台运行
```bash
# 使用 tmux 保持会话
tmux new -s arxiv
# 运行你的命令...
# Ctrl+B 然后 D 分离会话

# 重新连接
tmux attach -t arxiv
```

### 4. 自动启动 Docker
Docker Desktop 可以设置为 Windows 启动时自动启动，这样 WSL 中始终可用。

## 📁 文件清单

| 文件 | 说明 |
|------|------|
| `scripts/check_wsl_env.sh` | **WSL 环境检测** |
| `scripts/setup_wsl.sh` | **WSL 一键部署** |
| `scripts/README_FOR_AGENT.md` | 通用部署指南 |
| `docker-compose.yml` | Docker 配置 |

## 🆘 故障排除

遇到问题时运行：
```bash
./scripts/check_wsl_env.sh
```

它会给出针对性的修复建议。

---
**Agent任务**:
1. 在 WSL 中运行 `./scripts/check_wsl_env.sh` 检查环境
2. 根据提示修复问题
3. 运行 `./scripts/setup_wsl.sh` 完成部署
4. 验证: `SELECT COUNT(*) FROM papers;` 应返回 3,000,000
