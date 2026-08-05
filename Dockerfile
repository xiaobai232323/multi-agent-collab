FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY web_ui.py usage_tracker.py ./
COPY .streamlit/ .streamlit/

# Streamlit 端口
EXPOSE 8501

# 健康检查
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501')" || exit 1

# 启动
CMD ["streamlit", "run", "web_ui.py", "--server.port=8501", "--server.address=0.0.0.0"]
