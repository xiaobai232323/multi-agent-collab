# 🤝 多模型协作系统

**DeepSeek + 千问** — 多 Agent 协同聊天平台

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.30+-red.svg)](https://streamlit.io/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

两个大模型真正互相通信、互相审查、共享上下文，而非"同一个人分饰多角"。

---

## ✨ 功能

| 模式 | 说明 |
|------|------|
| 🔍 **交叉审查** | 两模型各自回答 → 互相挑错打分 → 综合最优答案 |
| 🏃 **接力看图** | 千问分析图片 → DeepSeek 深度推理 |
| ⚔️ **辩论** | 两模型轮流发言、互相质疑，直到达成一致 |
| 🤖 **仅 DeepSeek** | 单模型对话 |
| 🧠 **仅千问** | 单模型对话（支持图片） |

### 特色

- 💰 **用量追踪** — 实时显示花费、token 数，可自定义预算预警
- 💬 **会话管理** — 对话历史自动保存，可切换/删除/清空
- 🖼️ **图片上传** — 拖拽上传，千问视觉分析
- 🎨 **DeepSeek 蓝白主题** — 深蓝配色，简洁现代
- 📝 **GBK 编码启动器** — 桌面双击即用，窗口自动关闭

---

## 🚀 快速开始

### 1. 获取 API Key

- [DeepSeek API Key](https://platform.deepseek.com/api_keys) — ¥1-2/百万 tokens
- [千问 API Key](https://bailian.console.aliyun.com/) — 阿里云百炼平台

### 2. 设置环境变量

```powershell
# Windows (需要管理员权限的终端)
setx DEEPSEEK_API_KEY "sk-xxxxxxxxxxxxxxxx"
setx DASHSCOPE_API_KEY "sk-xxxxxxxxxxxxxxxx"
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 启动

```bash
# 方式一：命令行
streamlit run web_ui.py

# 方式二：Windows 桌面双击
多模型协作.bat
```

浏览器自动打开 `http://localhost:8501`

---

## 📁 项目结构

```
├── web_ui.py           # Streamlit 主界面
├── usage_tracker.py    # API 用量追踪模块
├── requirements.txt    # Python 依赖
├── start.bat           # Windows 桌面启动器
├── .streamlit/
│   └── config.toml     # DeepSeek 蓝白主题配置
├── tests/
│   └── test_usage_tracker.py  # 单元测试
├── history/            # 对话历史 (gitignore)
├── uploads/            # 上传图片 (gitignore)
└── usage.json          # 用量记录 (gitignore)
```

---

## 🧪 运行测试

```bash
python -m pytest tests/ -v
```

---

## ⚙️ 预算设置

侧栏 → `⚙️ 预算设置` 可调整：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| 月预算 | ¥15 | 超过后预警 |
| 预警线 | 80% | 到达后黄色警告 |
| 日限额 | ¥2 | 超过后红色警告 |

---

## 💰 费用参考

| 模型 | 输入价格 | 输出价格 |
|------|----------|----------|
| DeepSeek-Chat | ¥1/M tokens | ¥2/M tokens |
| 千问-Max | ¥20/M tokens | ¥60/M tokens |
| 千问-VL-Max | ¥20/M tokens | ¥60/M tokens |

> 轻度使用月花费约 ¥5-15

---

## 🛠 技术栈

- **前端**: Streamlit
- **后端 API**: OpenAI SDK (DeepSeek) + DashScope SDK (千问)
- **数据**: JSON 文件存储（会话历史、用量记录）
- **环境**: Python 3.10+, Windows

---

## 📄 License

MIT © 2025
