"""
初始化管理员账号（兼容旧用法）。

现在只是 manage.py 的薄封装：确保内置 system 管理员存在。
密码与 OTP 的维护请使用独立命令：

    python manage.py reset-system-password [密码]
    python manage.py reset-system-otp
"""

import subprocess
import sys


if __name__ == '__main__':
    sys.exit(subprocess.call([sys.executable, "manage.py", "ensure-system"]))
