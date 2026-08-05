# 🤝 Multi-Agent Collab — 多模型协同推理系统

<div align="center">

**让 DeepSeek 和 千问 真正互相通信、互相审查，而非"同一模型分饰多角"**

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.30+-FF4B4B?logo=streamlit)](https://streamlit.io/)
[![DeepSeek](https://img.shields.io/badge/DeepSeek-API-4D6BFE)](https://platform.deepseek.com/)
[![Qwen](https://img.shields.io/badge/千问-API-FF6A00)](https://bailian.console.aliyun.com/)
[![Tests](https://img.shields.io/badge/tests-pytest-green)](tests/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

</div>

---

## 🎯 项目动机

主流 AI 聊天应用使用**单一模型**回答问题。但当模型存在盲区时，单模型无法自我纠错。本项目实现了：

> **两个异构大模型（DeepSeek + 千问）共享对话上下文，互相审查对方的输出，通过交叉验证提升回答质量。**

核心思想类似软件工程中的 **N-Version Programming** — 多个独立系统分别处理同一问题，通过投票/审查机制产生更可靠的结果。

---

## 🏗 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                   Streamlit Web UI                      │
│  ┌──────────┐  ┌────────────────────────────────────┐  │
│  │  侧栏     │  │         主聊天区                    │  │
│  │  ·会话管理 │  │  ┌─────────────────────────────┐  │  │
│  │  ·模式选择 │  │  │  用户消息 / AI 回复          │  │  │
│  │  ·图片上传 │  │  │  chat_message 组件           │  │  │
│  │  ·用量面板 │  │  └─────────────────────────────┘  │  │
│  │  ·预算设置 │  │  ┌─────────────────────────────┐  │  │
│  └──────────┘  │  │  输入栏 + 发送按钮            │  │  │
│                │  └─────────────────────────────┘  │  │
│                └────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────┤
│                  Orchestrator (编排层)                   │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ 交叉审查模式 │  │  接力协作模式  │  │  辩论模式     │  │
│  │ A→答 B→答   │  │ 千问看图     │  │ A⇄B 互相质疑 │  │
│  │ A审B B审A   │  │ DeepSeek推理 │  │ 直到达成一致  │  │
│  │ 综合最优 ←──│  │              │  │              │  │
│  └─────────────┘  └──────────────┘  └──────────────┘  │
├─────────────────────────────────────────────────────────┤
│                    API 网关层                            │
│  ┌──────────────────┐    ┌──────────────────────────┐  │
│  │ DeepSeek Client   │    │  Qwen Client              │  │
│  │ · OpenAI SDK      │    │  · DashScope SDK          │  │
│  │ · deepseek-chat   │    │  · qwen-max (文本)        │  │
│  │ · deepseek-       │    │  · qwen-vl-max (视觉)     │  │
│  │   reasoner        │    │                           │  │
│  └──────────────────┘    └──────────────────────────┘  │
├─────────────────────────────────────────────────────────┤
│                    基础设施层                            │
│  ┌────────────┐ ┌───────────┐ ┌──────────────────────┐ │
│  │ UsageTracker│ │ Session   │ │  Windows 注册表      │ │
│  │ · 实时计费  │ │ Manager   │ │  · 环境变量自动回退  │ │
│  │ · 预算预警  │ │ · JSON存储│ │  · GBK 编码兼容      │ │
│  └────────────┘ └───────────┘ └──────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

---

## ✨ 核心功能

### 五种协作模式

| # | 模式 | 工作流程 | 适用场景 |
|---|------|----------|----------|
| 1 | 🔍 **交叉审查** | 两模型独立回答 → 互相评分挑错 → 综合最优 | 重要决策、学术写作 |
| 2 | 🏃 **接力协作** | 千问视觉分析图片 → DeepSeek 深度推理 | 图表解读、UI 评审 |
| 3 | ⚔️ **辩论模式** | 轮流发言 → 互相质疑 → 收敛至共识 | 观点分歧、方案选型 |
| 4 | 🤖 **仅 DeepSeek** | 单模型对话 | 代码生成、逻辑推理 |
| 5 | 🧠 **仅千问** | 单模型对话 + 视觉 | 图片分析、中文处理 |

### 工程亮点

| 模块 | 技术点 |
|------|--------|
| 💰 **用量追踪** | 实时 token 计数、多模型分别计价、月度/日度统计 |
| ⚠️ **预算预警** | 三档预警（正常/警告/危险）、自定义阈值、日限额熔断 |
| 💾 **会话管理** | JSON 文件持久化、多会话切换、历史搜索 |
| 🔑 **密钥安全** | 环境变量存储、Windows 注册表自动回退 |
| 🎨 **界面设计** | DeepSeek 蓝白主题、Streamlit 原生组件零 CSS 侵入 |
| 📦 **一键启动** | GBK 编码 .bat 启动器、无窗口后台运行、自动打开浏览器 |

---

## 🚀 快速开始

### 前置条件

- Python 3.10+
- [DeepSeek API Key](https://platform.deepseek.com/api_keys)
- [阿里云百炼 API Key](https://bailian.console.aliyun.com/)（千问）

### 安装

```bash
# 1. 克隆仓库
git clone https://github.com/xiaobai232323/multi-agent-collab.git
cd multi-agent-collab

# 2. 安装依赖
pip install -r requirements.txt

# 3. 设置 API Key（Windows）
setx DEEPSEEK_API_KEY "sk-xxxxxxxxxxxxxxxx"
setx DASHSCOPE_API_KEY "sk-xxxxxxxxxxxxxxxx"

# 4. 启动
streamlit run web_ui.py
```

浏览器自动打开 `http://localhost:8501`，或双击 `多模型协作.bat` 一键启动（Windows）。

---

## 📁 项目结构

```
multi-agent-collab/
├── web_ui.py                # Streamlit 主界面 (~250 行)
├── usage_tracker.py         # API 用量追踪模块 (单例模式)
├── requirements.txt         # Python 依赖
├── start.bat                # Windows 一键启动脚本
├── .streamlit/
│   └── config.toml          # DeepSeek 蓝白主题
├── tests/
│   ├── __init__.py
│   └── test_usage_tracker.py  # 单元测试 (6 用例)
├── history/                 # 对话历史 (gitignore)
├── uploads/                 # 图片缓存 (gitignore)
└── .gitignore
```

---

## 🧪 测试

```bash
pytest tests/ -v
```

覆盖：用量记录、多模型计费、预算预警、最近调用、默认配置自动创建。

---

## 🧩 设计模式

| 模式 | 应用 |
|------|------|
| **Singleton** | `UsageTracker` 全局单例，确保用量数据一致 |
| **Strategy** | 五种协作模式可插拔，通过 `mode_map` 路由 |
| **Facade** | `ds_ask()` / `qw_ask()` / `qw_see()` 封装不同 SDK |
| **Observer** | Streamlit `session_state` 驱动 UI 响应式更新 |

---

## 📊 用量追踪设计

```
每次 API 调用
    │
    ▼
┌──────────────────┐
│  从 response 提取  │
│  · input_tokens   │
│  · output_tokens  │
│  · image_count    │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐     ┌─────────────────┐
│  查价表           │ ──→ │  计算费用        │
│  deepseek: ¥1/M   │     │  cost = tokens   │
│  qwen-max: ¥20/M  │     │  × unit_price    │
│  qwen-vl: ¥20/M   │     └────────┬────────┘
└──────────────────┘              │
                                  ▼
┌─────────────────────────────────────────────┐
│  usage.json                                │
│  { calls: [...], totals: {                  │
│      "2025-08": { cost: 7.23, calls: 23 }, │
│      "2025-08-05": { cost: 1.50, calls: 5 }│
│  }}                                         │
└─────────────────────────────────────────────┘
       │
       ▼
  Streamlit 侧栏实时渲染
  · 月度花费 / 预算百分比
  · 绿/黄/红 三档预警
```

---

## 🛠 技术栈

| 层 | 技术 |
|----|------|
| UI | Streamlit 1.30+, Markdown, chat_message |
| 编排 | Python 3.10+, 策略模式, 会话状态管理 |
| SDK | OpenAI SDK (DeepSeek 兼容), DashScope SDK (千问) |
| 存储 | JSON 文件, 按日期/月份聚合 |
| 测试 | pytest, monkeypatch, tmp_path |
| 工具 | Git, GitHub, Windows 注册表 API |

---

## 📝 License

MIT © 2025 张宏杰

---

<div align="center">

**如果这个项目对你有帮助，请给一个 ⭐ Star！**

</div>
