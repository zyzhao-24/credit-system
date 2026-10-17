"""
初始化管理员账号（兼容旧用法）。

现在只是 manage.py 的薄封装：确保内置 system 管理员存在。
密码与 OTP 的维护请使用本机专用页面（推荐，无需命令行）：

    启动服务后在服务器本机访问 http://localhost:5000/local/system
"""

import subprocess
import sys


if __name__ == '__main__':
    sys.exit(subprocess.call([sys.executable, "manage.py", "ensure-system"]))
