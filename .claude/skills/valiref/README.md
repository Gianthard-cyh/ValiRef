# ValiRef Skill

这是一个用于 Claude Code 的 Skill，提供 AI 驱动的学术论文引用验证功能。

## 功能

- 验证 PDF 文档中的参考文献
- 检测幻觉引用（伪造的论文）
- 检查作者归属错误
- 识别引用内容与论文实际内容不匹配的情况
- 多源交叉验证（ArXiv、Google Scholar、Semantic Scholar、OpenReview、OpenAlex）

## 安装

### 方法 1：本地安装（推荐开发使用）

```bash
# 在项目目录下创建 skill 链接
mkdir -p ~/.claude/skills
cp -r .claude/skills/valiref ~/.claude/skills/
```

### 方法 2：从 GitHub 安装

```bash
# 添加到 Claude Code 配置
claude config skills.add https://github.com/Gianthard-cyh/ValiRef
```

### 方法 3：Marketplace 安装（发布后）

```bash
# 通过 Claude Code marketplace 安装
claude plugins install valiref
```

## 配置

1. 设置环境变量：

```bash
export DEEPSEEK_API_KEY=your_api_key_here
```

2. 可选配置（增强搜索）：

```bash
export SERPAPI_API_KEY=your_key
export SEMANTIC_SCHOLAR_API_KEY=your_key
```

## 使用

安装后，Claude 会自动在以下场景使用此 skill：

- 用户要求验证 PDF 中的引用
- 用户怀疑论文有幻觉引用
- 用户需要检查参考文献的真实性

### 示例用法

```
用户: 帮我检查这个 paper.pdf 的引用是否真实
Claude: 我将使用 ValiRef 验证这个 PDF 中的引用...

用户: /valiref validate paper.pdf
Claude: 正在验证 citations...
```

## 项目结构

```
.claude/skills/valiref/
├── SKILL.md           # Skill 定义和文档
├── LICENSE.txt        # MIT 许可证
└── marketplace.json   # Marketplace 配置
```

## 发布到 Marketplace

### 步骤 1：准备发布

确保所有文件都已更新：
- `SKILL.md` - 包含完整的 skill 文档
- `LICENSE.txt` - 许可证文件
- `marketplace.json` - 配置信息正确

### 步骤 2：提交到 Anthropic Marketplace

1. Fork [claude-plugins-public](https://github.com/anthropics/claude-plugins-public) 仓库
2. 在 `skills/` 目录下创建 `valiref/` 文件夹
3. 复制以下文件：
   - `SKILL.md`
   - `LICENSE.txt`
4. 提交 PR

### 步骤 3：等待审核

Anthropic 团队会审核你的 skill，审核通过后会合并到 marketplace。

## 开发

### 本地测试

```bash
# 安装 valiref 包
pip install -e .

# 运行测试
pytest tests/
```

### 更新 Skill

修改 `SKILL.md` 后，重新复制到技能目录：

```bash
cp .claude/skills/valiref/SKILL.md ~/.claude/skills/valiref/
```

## 依赖

- Python 3.12+
- valiref 包
- DeepSeek API 密钥

## 许可证

MIT

## 链接

- 项目主页：https://github.com/Gianthard-cyh/ValiRef
- PyPI：https://pypi.org/project/valiref
- 问题反馈：https://github.com/Gianthard-cyh/ValiRef/issues
