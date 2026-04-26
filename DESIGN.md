# Design

## Visual Theme

**Notion-inspired minimalism** —— 大量留白，克制的灰度层次，用排版而非装饰建立信息层级。

物理场景：研究人员在 27 英寸显示器或笔记本上，可能是在明亮的办公室或深夜的实验室，需要一个不会引起视觉疲劳、能让人长时间专注的界面。

主题决策：**支持深色模式优先**（深灰色系而非纯黑），浅色模式作为日间选择。深色模式不是"酷炫"，而是对深夜写作场景的实际回应。

## Color Palette

**策略：Restrained** —— 中性灰度为主，语义色仅用于结果状态。

### 基础色（OKLCH 空间）

```
Surface Light:  #ffffff     (white)
Surface Secondary Light: #fafafa  (oklch(98% 0 0))
Surface Tertiary Light:  #f5f5f5  (oklch(96% 0 0))

Surface Dark:   #0a0a0a     (oklch(5% 0 0) — 非纯黑，深炭灰)
Surface Secondary Dark: #171717  (oklch(10% 0 0))
Surface Tertiary Dark:  #262626  (oklch(18% 0 0))

Text Primary Light:   #171717  (oklch(15% 0 0))
Text Secondary Light: #525252  (oklch(40% 0 0))
Text Tertiary Light:  #737373  (oklch(55% 0 0))
Text Muted Light:     #a3a3a3  (oklch(70% 0 0))

Text Primary Dark:    #fafafa  (oklch(98% 0 0))
Text Secondary Dark:  #e5e5e5  (oklch(90% 0 0))
Text Tertiary Dark:   #a3a3a3  (oklch(70% 0 0))
```

### 语义色（仅用于结果类型）

```
Real (通过):          #10b981  (emerald, oklch(70% 0.18 155))
Fabrication (伪造):    #f43f5e  (rose, oklch(65% 0.25 15))
Attribution (作者错误): #f59e0b  (amber, oklch(75% 0.15 75))
Irrelevance (不相关):  #3b82f6  (blue, oklch(65% 0.18 250))
Counter (反事实):      #8b5cf6  (violet, oklch(60% 0.22 290))
```

**使用规则**：
- 语义色仅用于结果状态标签、图标和细微的背景着色
- 深色模式下语义色提高亮度 10-15% 以保持可读性
- 不使用渐变色，不使用透明度过高的背景

## Typography

**字体栈**：
- 正文字体：Inter, system-ui, sans-serif
- 衬线展示：Newsreader (用于大标题，带来学术/编辑感)
- 等宽字体：JetBrains Mono, ui-monospace (用于代码、数据展示)

**字号比例**（1.25 比例）：

```
3xl (Display):  1.875rem / 30px  → 大标题
2xl (Hero):     1.5rem   / 24px
xl (Heading):   1.25rem  / 20px  → 区块标题
lg (Title):     1.125rem / 18px  → 卡片标题
base (Body):    1rem     / 16px  → 正文
sm (Small):     0.875rem / 14px  → 辅助文字
caption (xs):   0.75rem  / 12px  → 标签、元数据
```

**行高**：
- 紧凑：1.2（大标题）
- 正常：1.35（区块标题）
- 宽松：1.5（正文）
- 阅读：1.65（长文本段落）

**正文长度**：最大 65ch，确保阅读舒适。

## Components

### Card

- 边框：1px solid border
- 圆角：0.5rem (8px)
- 背景：surface
- 悬停：边框加深 + 轻微阴影（仅交互卡片）
- 无左侧色条装饰

### Button

**Primary**:
- 背景：text-primary / 文字：surface
- 圆角：0.5rem
- 悬停：opacity 0.9
- 激活：scale 0.98

**Outline**:
- 背景：transparent / 边框：border-strong
- 悬停：bg-surface-secondary

**Ghost**:
- 背景：transparent
- 悬停：bg-surface-secondary

所有按钮禁用态：opacity 0.4，cursor not-allowed，无交互反馈。

### Input

- 背景：surface
- 边框：1px solid border
- 圆角：0.5rem
- Focus：边框加深 + ring
- 占位符颜色：text-muted

### 结果状态标签

- 圆角 pill shape (full)
- 小号文字 + 中等字重
- 左边带对应语义色的图标
- 背景为该颜色的 10% 透明度

## Layout

**容器**：
- 最大内容宽度：max-w-5xl (64rem / 1024px)
- 结果页面可全宽：无 max-width

**间距节奏**：
```
xs:  0.25rem  (4px)
sm:  0.5rem   (8px)
md:  1rem     (16px)
lg:  1.5rem   (24px)
xl:  2rem     (32px)
2xl: 3rem     (48px)
```

**避免**：
- 相同间距的重复堆叠（单调）
- 嵌套卡片
- 不必要的包装容器

## Motion

**曲线**：ease-out 指数曲线
- 标准：`cubic-bezier(0.4, 0, 0.2, 1)`（200ms）
- 快速：`cubic-bezier(0.4, 0, 0.2, 1)`（150ms）
- 慢速：`cubic-bezier(0.4, 0, 0.2, 1)`（300ms）

**禁用**：
- 弹簧/弹性动画
- 布局属性动画（width, height, top, left）
- 纯装饰性动画

**尊重**：`prefers-reduced-motion` 应禁用所有过渡。

## Elevation

- 不使用 drop-shadow 作为主要层次工具
- 层次通过：背景色差异 > 边框 > 轻微阴影
- 阴影仅用于悬停状态的交互卡片：
  - sm: `0 1px 2px 0 rgb(0 0 0 / 0.05)`
  - md: `0 4px 6px -1px rgb(0 0 0 / 0.1)`

## Dark Mode

完整支持，通过 `.dark` 类切换。

关键调整：
- 表面色使用深灰而非纯黑（减少对比疲劳）
- 语义色提高亮度保持可读性
- 阴影更 subtle（更高的透明度）
- 选择文字：反色显示（bg=text, color=surface）
