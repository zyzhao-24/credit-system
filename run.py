"""开发入口：Flask 开发服务器 + 新后端（frontend 由 Vite dev server 代理 /api）。

运行方式：
    python run.py
"""

from backend import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
