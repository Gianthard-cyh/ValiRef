<table>
  <tr>
    <td width="80%" style="border: none;">
      <h1>ValiRef</h1>
    </td>
    <td width="20%" align="center" style="border: none;">
      <img src="assets/SVG/Square.svg" width="150" />
    </td>
  </tr>
</table>

> [!IMPORTANT]
> 🚧WIP🚧

ValiRef 是一个用于检测论文引用中是否存在幻觉引用的工具。

ValiRef 支持检测多种类型的引用错误，包括：
- 引用不存在的论文
- 引用论文的标题 / 作者不符
- 引用论文的内容与文中的描述不符

# 目录结构

```
ValiRef/
├── src/
│   ├── api/   # API 接口模块
│   ├── bench/ # 基准测试模块
│   ├── core/  # 引用检测智能体
│
├── tests/
│   ├── test_valiref.py
├── README.md
├── requirements.txt
```