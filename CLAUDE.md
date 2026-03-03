# ValiRef 项目备忘

## 项目管理

- **包管理器**: uv (不是pip)
- **添加依赖**: `uv add <package>`
- **运行**: `uv run python -m src.cli ...`

## 当前开发任务

### 工具API调用监控

使用blink信号实现工具调用的监控和统计：

1. **前置测试**: 先测试Rich Live是否能正常工作
   ```bash
   python test_live_display.py
   ```

2. **依赖安装**:
   ```bash
   uv add blinker
   ```

3. **关键文件**:
   - `src/core/tool_monitor.py` - 信号定义和收集器
   - `src/core/tools.py` - 在SearchTool中发布信号
   - `src/cli_callbacks.py` - Rich Live实时显示

## 开发工作流

由于benchmark可能正在运行，使用worktree：

```bash
# 创建worktree
git worktree add ../ValiRef-dev <branch-name>
cd ../ValiRef-dev

# 开发完成后
cd /home/cyh/ValiRef
git worktree remove ValiRef-dev
```

## 架构约定

- 使用 **blinker** 进行事件发布订阅（不自己实现事件总线）
- 使用 **Rich Live** 进行实时监控展示
- 优先使用成熟开源方案，不造轮子
- 保持代码清晰解耦
