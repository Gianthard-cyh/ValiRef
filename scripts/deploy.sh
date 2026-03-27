#!/bin/bash
# ValiRef 生产部署脚本

set -e

echo "🚀 ValiRef 生产部署"
echo "==================="

# 1. 检查环境变量
if [ -z "$DEEPSEEK_API_KEY" ]; then
    echo "⚠️  Warning: DEEPSEEK_API_KEY 未设置"
fi

# 2. 构建前端
echo "📦 构建前端..."
docker-compose -f docker-compose.prod.yml run --rm frontend-build

# 3. 启动服务
echo "🐳 启动服务..."
docker-compose -f docker-compose.prod.yml up -d

# 4. 等待服务就绪
echo "⏳ 等待服务就绪..."
sleep 5

# 5. 检查健康状态
echo "✅ 检查服务状态..."
docker-compose -f docker-compose.prod.yml ps

echo ""
echo "🎉 部署完成！"
echo "📍 访问地址: http://localhost"
echo "📚 API 文档: http://localhost/docs"
echo ""
echo "📊 常用命令:"
echo "  查看日志: docker-compose -f docker-compose.prod.yml logs -f"
echo "  扩展 Worker: docker-compose -f docker-compose.prod.yml up -d --scale worker=3"
echo "  停止服务: docker-compose -f docker-compose.prod.yml down"
