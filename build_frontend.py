"""用 uv 项目环境自带的 Node.js 构建前端，无需系统安装 Node/npm。

`uv sync` 会安装 nodejs-wheel（Node 24 + npm 11 的二进制包），本脚本
把虚拟环境的 bin 目录放到 PATH 最前，然后执行 npm ci && npm run build。

用法：
    uv run python build_frontend.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"


def main() -> None:
    if not FRONTEND.is_dir():
        sys.exit("未找到 frontend/ 目录")
    # uv run 下 sys.executable 即 .venv 里的 python，node/npm 与其同目录
    bin_dir = str(Path(sys.executable).parent)
    env = {**os.environ, "PATH": bin_dir + os.pathsep + os.environ.get("PATH", "")}

    for title, cmd in [("安装前端依赖 (npm ci)", "npm ci"),
                       ("构建前端 (npm run build)", "npm run build")]:
        print(f"==> {title}", flush=True)
        # shell=True 以兼容 Windows 上的 npm.cmd
        result = subprocess.run(cmd, shell=True, cwd=FRONTEND, env=env)
        if result.returncode != 0:
            sys.exit(f"步骤失败（退出码 {result.returncode}）：{title}")
    print("前端构建完成：frontend/dist")


if __name__ == "__main__":
    main()
