# GitHub Actions 部署指南

## 概述

项目已配置 GitHub Actions 自动部署，使用**腾讯云容器镜像服务 (TCR)**，适合国内服务器：
- **CI/CD 分离** - 测试 → 构建 → 部署
- **环境管理** - 使用 GitHub Environment
- **SSH/SCP 操作** - 使用 appleboy 的 action
- **镜像管理** - 推送到腾讯云 TCR，国内服务器快速拉取

## 触发条件

- **Push 到 main** - 自动构建并部署
- **打 Tag (v*)** - 构建对应版本并部署
- **手动触发** - 在 Actions 页面点击 "Run workflow"
- **PR 到 main** - 仅运行测试

## 配置步骤

### 1. 配置腾讯云 TCR

1. 登录 [腾讯云控制台](https://console.cloud.tencent.com/tcr)
2. 创建/选择容器镜像服务（个人版免费）
3. 创建命名空间，例如 `valiref`
4. 在**访问凭证**中获取：
   - **用户名**：通常是账号 ID（1000xxxxx）
   - **密码**：点击生成/重置密码

### 2. 配置 GitHub Secrets

在 GitHub 仓库 Settings > Secrets and variables > Actions 添加：

| Secret | 说明 | 示例 |
|--------|------|------|
| `DEPLOY_HOST` | 服务器 IP 或域名 | `123.45.67.89` |
| `DEPLOY_USER` | SSH 用户名 | `ubuntu` 或 `root` |
| `DEPLOY_SSH_KEY` | SSH 私钥 | 完整私钥内容 |
| `TENCENT_CLOUD_USERNAME` | 腾讯云账号 ID | `100012345678` |
| `TENCENT_CLOUD_PASSWORD` | TCR 仓库密码 | `xxxxxxxx` |
| `TCR_NAMESPACE` | 命名空间 | `valiref` |
| `TCR_REGISTRY` | 仓库地址（可选）| `ccr.ccs.tencentyun.com` |

#### 生成 SSH 密钥

```bash
ssh-keygen -t ed25519 -C "github-actions" -f ~/.ssh/github_actions

# 公钥添加到服务器
cat ~/.ssh/github_actions.pub | ssh root@server "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"

# 私钥复制到 GitHub Secrets
cat ~/.ssh/github_actions
```

### 3. 服务器准备

```bash
# 1. 安装 Docker 和 Compose
curl -fsSL https://get.docker.com | sh

# 2. 创建部署目录
mkdir -p /var/www/ValiRef

# 3. 创建环境变量文件
cat > /var/www/ValiRef/.env << 'EOF'
DEEPSEEK_API_KEY=your_api_key_here
DB_PASSWORD=your_db_password

# 腾讯云镜像配置
DOCKER_REGISTRY=ccr.ccs.tencentyun.com
DOCKER_NAMESPACE=your-namespace
DOCKER_IMAGE=valiref-backend
IMAGE_TAG=latest
EOF

# 4. 确保目录权限正确
chmod 600 /var/www/ValiRef/.env
```

### 4. 配置 GitHub Environment（可选）

在 GitHub 仓库 Settings > Environments 创建 `production` 环境：
- 可以设置部署保护规则（需要审批）
- 可以设置环境专属的 Secrets

## 部署流程

```
Push to main / Tag
│
├─ Job: test
│  └─ 运行单元测试
│
├─ Job: build-frontend
│  └─ pnpm build → artifact
│
├─ Job: build-api
│  └─ docker build → push to 腾讯云 TCR
│
└─ Job: deploy (needs: [build-frontend, build-api])
   ├─ 下载 frontend artifact
   ├─ SSH: 创建部署目录
   ├─ SCP: 上传 compose/env/frontend 文件
   ├─ SSH: docker login 腾讯云 → pull → up -d
   └─ HTTP: 健康检查
```

## 触发部署

### 方式一：推送代码

```bash
git push origin main
# 自动触发 CI/CD
```

### 方式二：打标签发布

```bash
git tag v1.0.0
git push origin v1.0.0
# 自动构建 v1.0.0 镜像并部署
```

### 方式三：手动触发

1. 进入 GitHub 仓库
2. 点击 Actions > CI/CD Pipeline
3. 点击 "Run workflow"
4. 选择分支，点击 Run

## 服务器操作

```bash
# 查看服务状态
cd /var/www/ValiRef
sudo docker compose -f docker-compose.prod.yml ps

# 查看日志
sudo docker compose -f docker-compose.prod.yml logs -f api
sudo docker compose -f docker-compose.prod.yml logs -f worker

# 重启服务
sudo docker compose -f docker-compose.prod.yml restart

# 扩缩容 worker
sudo docker compose -f docker-compose.prod.yml up -d --scale worker=3
```

## 故障排查

### 1. SSH 连接失败

```bash
# 检查密钥
ssh -i ~/.ssh/github_actions root@server

# 检查 authorized_keys
cat ~/.ssh/authorized_keys | grep github-actions
```

### 2. 镜像拉取失败

```bash
# 在服务器上手动测试登录
docker login ccr.ccs.tencentyun.com -u 1000xxxxxx -p your_password

# 检查镜像是否存在
docker pull ccr.ccs.tencentyun.com/valiref/valiref-backend:latest

# 检查镜像地址是否正确
cat /var/www/ValiRef/.env | grep DOCKER
```

常见问题：
- **密码错误**：在腾讯云控制台重置 TCR 访问凭证密码
- **命名空间不存在**：确保 TCR 中已创建对应的命名空间
- **网络问题**：国内服务器应该能正常访问腾讯云，如果失败检查 DNS

### 3. 前端文件未更新

```bash
# 检查服务器上的文件
ls -la /var/www/ValiRef/frontend/.output/public/

# 手动同步
scp -r frontend/.output/public/* root@server:/var/www/ValiRef/frontend/.output/public/
```

### 4. 环境变量未生效

```bash
# 检查 .env 文件
cat /var/www/ValiRef/.env

# 重启服务使配置生效
cd /var/www/ValiRef
sudo docker compose -f docker-compose.prod.yml down
sudo docker compose -f docker-compose.prod.yml up -d
```

## 自定义配置

### 修改部署目录

编辑 `.github/workflows/deploy.yml`：

```yaml
- name: Create deployment directory
  uses: appleboy/ssh-action@v1.0.0
  with:
    script: |
      mkdir -p /your/custom/path  # 修改这里
```

### 使用其他镜像仓库（阿里云、华为云等）

编辑 `.github/workflows/deploy.yml`：

```yaml
env:
  REGISTRY: registry.cn-hangzhou.aliyuncs.com  # 阿里云示例
  TCR_NAMESPACE: your-namespace
  IMAGE_NAME: valiref-backend
```

并添加对应的登录 secrets。

### Worker 扩容

GitHub Actions 不会自动处理 worker 数量。需要在服务器上手动执行：

```bash
cd /var/www/ValiRef
sudo docker compose -f docker-compose.prod.yml up -d --scale worker=5
```

## 安全建议

1. **SSH 密钥** - 专用部署密钥，不要和个人密钥混用
2. **环境变量** - 敏感信息只存在服务器 `.env`，不要提交到仓库
3. **镜像仓库** - GHCR 是私有的，确保仓库设置正确
4. **部署保护** - 生产环境建议开启 Environment protection rules
