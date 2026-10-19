# 团校积分系统

一个完整的学分管理系统，采用 Windows 11 风格界面设计。

## 快速开始

后端环境用 [uv](https://docs.astral.sh/uv/) 管理（`pyproject.toml` + `uv.lock`）：

```bash
# 1. 安装后端依赖（自动创建 .venv 并安装全部依赖，含 pytest）
uv sync

# 2. 配置环境变量
cp .env.example .env   # 编辑 SECRET_KEY（生产必须）

# 3. 初始化管理员：无需脚本。首次启动时自动创建内置 system 账号
#    （密码不落盘、不打印），启动服务后在服务器本机用浏览器访问
#    http://localhost:5002/local/system 设置 system 密码并绑定 OTP（登录强制两步验证）

# 4. 构建前端（用 uv 环境自带的 Node 24，无需系统安装 Node/npm）
uv run python build_frontend.py

# 5. 启动系统
uv run python run.py             # 开发环境（Flask dev server，端口 5000）
start_server.bat                 # 生产环境（Windows，Waitress）
./start_server.sh                # 生产环境（Linux，Waitress）

# 前端开发模式（可选，Vite 端口 5173，/api 自动代理到 5000）
cd frontend && npm run dev
```

访问系统：

- 学生登录：http://localhost:5000/login
- 管理员登录：http://localhost:5000/admin/login（固定路径）

## 服务架构与 HTTPS（自签名证书）

生产形态（`deploy_server.py`）由三个纯 Python 组件组成，全部依赖由 uv 安装：

- **tls_proxy**（`tls_proxy.py`，纯标准库）：监听 `0.0.0.0:5000`，做首字节
  协议嗅探的双协议入口——**localhost 一律 HTTP，LAN 一律 HTTPS**（LAN 说
  HTTP 会被拒绝）。TLS 握手在每个连接的独立线程中完成，卡死的握手不会
  堵死全站 accept（cheroot 单线程握手曾导致校园网环境下随机全站卡死）。
- **主应用 waitress**：只监听 `127.0.0.1:5001`，外部无法直连。
- **本机维护台**：独立 app 监听 `127.0.0.1:5002`，与主应用端口级隔离，
  绝不对外暴露；仅本机（或 SSH 隧道）可访问。

证书仍由 `gen_cert.py` 在启动时自动生成（`instance/tls.crt` / `tls.key`，
SAN 含 localhost 与本机内网 IP）；证书不可用时 LAN 入口拒绝启动
（fail-closed，安全底线是 LAN 必须 HTTPS），localhost HTTP 不受影响。
手动管理：

```bash
uv run python gen_cert.py --force  # 重签（内网 IP 变化或证书到期时）
```

自签名证书不受浏览器信任，访问时提示“不安全”属预期，点“高级 → 继续前往”即可
（Firefox 可永久记住例外）；私钥在 `instance/` 下，不会进入版本库。
如需彻底消除警告，可用域名 + Let's Encrypt DNS-01（内网 IP 也可签发）。

## 架构

- **后端**：`backend/` —— Flask application factory + Blueprint 拆分（`backend/api/`），
  SQLAlchemy 2 + SQLite（WAL、busy_timeout、foreign_keys），JWT 认证（HS256，12 小时）。
- **前端**：`frontend/` —— React 19 + TypeScript + Vite + Tailwind CSS 4 + Radix。
  生产模式由 Flask 直接托管 `frontend/dist` 并做 SPA fallback。
- **运行脚本**：`run.py`（开发）、`deploy_server.py` + `start/status/logs/stop/cleanup` 脚本（生产）。
- **测试**：`uv run pytest`（配置在 `pyproject.toml`，含 pythonpath 与 testpaths）

## 两步验证（OTP）

登录强制“密码 + TOTP 动态验证码”两步：

- 第一步 `POST /api/auth/token`（密码）返回短期 `otp_ticket`（10 分钟）；
- 第二步 `POST /api/auth/token/verify`（otp_ticket + 6 位验证码）换取正式 JWT。

OTP 绑定/重置统一遵循“验证才生效”原则：凡需要人手持新密钥的场景，系统只签发
10 分钟有效的**待生效票据**（候选密钥 Fernet 加密后随 JWT 下发），用户在弹窗中
扫码并输入验证码确认后，候选密钥才写入账号；中途放弃则一切不变：

- **学生注册**：先通过学号邮箱验证码（`/api/student/register/send_code`）才予注册；
  注册成功后立即弹窗绑定 OTP（`POST /api/auth/otp/bind/confirm` 验证生效），
  跳过则按未绑定处理。
- **学生忘记密码**：与注册同构——邮箱验证码 + 自设新密码，验证通过才重置；
  成功后同样可选弹窗重绑 OTP，跳过则原有 OTP 不变。
- **OTP 被管理员重置的学生**：登录密码通过后自动重新生成 OTP 并把二维码
  （内嵌图片 + 密钥）发到学号邮箱，立即生效（这是唯一的找回通道）。
- **学生主动重置**：学生端“账号安全”页弹出二维码，验证码确认才生效。
- **管理员**：无邮箱。创建账号时接口一次性返回二维码与 Base32 密钥（仅本次可见）；
  未绑定 OTP 的管理员无法登录，由系统管理员在后台”重置 OTP”生成二维码转交
  （弹窗带导出：下载二维码/复制密钥，二次确认后才写入目标账号）。
- **system 账号**：内置固定存在且是唯一的系统管理员，接口禁止创建/删除/修改它，
  也不允许再创建或提升其他 `system_admin`；首次启动建号时使用不落盘、不打印的
  随机密码（无人知晓），初始配置通过**本机专用维护页**完成：在服务器本机访问
  `http://localhost:5002/local/system`（独立端口、仅绑定回环地址，表单带签名令牌防跨站提交；
  密码可自定义、至少 8 位，留空则随机生成，均仅显示一次；OTP 与学生主动重置一致，
  扫码后输入验证码确认才生效）。

所有外发邮件均为带品牌排版的 HTML 邮件（含纯文本备选），OTP 二维码以内嵌图片呈现。

## 核心功能

### 学生端

- 查看个人学分和活动列表
- 修改密码、忘记密码（邮件重置）
- 活动报名（支持自定义问卷）
- 导出学分报告PDF

### 管理员端

- 学生管理（添加/删除/修改/批量导入）
- 活动管理（创建/编辑/删除/权限控制）
- 学分录入（单个/批量添加）
- 问卷管理（创建问卷、查看报名、候补机制）
- 数据统计和导出（Excel/PDF）
- 智能学分分配（DFS算法）

### 系统管理员

- 管理员账号管理
- 部门管理
- 类别和总学分设置

### 本机维护页（仅服务器 localhost 可访问）

`http://localhost:5002/local/system`：system 密码重置、system OTP 重置、邮件服务配置
（SMTP 账号/明文密码/学生邮箱后缀）与测试发送。**这三类信息只出现在此页面**，
Web 管理后台不提供邮箱配置入口。

## 技术栈

- **后端**：Flask 3.0 + Flask-SQLAlchemy + Waitress + PyJWT + PyOTP（TOTP 两步验证）
- **前端**：React 19 + TypeScript + Vite + Tailwind CSS 4 + Radix + axios + react-router
- **数据存储**：SQLite（WAL 模式，事务写入）
- **密码安全**：浏览器 SHA-256 摘要 → 服务端 PBKDF2（600k 轮）
- **UI 设计**：Windows 11 Fluent Design

## 与旧版本的有意行为差异

1. **密码哈希存储**：数据库不再保存明文密码，学生 CSV 导出也不再包含密码列。
2. **管理员登录路径固定**：`/admin/login`，不再使用每次启动随机生成的路径
   （在 SPA 形态下随机路径没有实际安全收益）。
3. **批量导入不再静默重置密码**：已存在的学生只有显式提供第三列密码时才更新密码。
4. **认证方式**：session cookie 改为 JWT bearer token，且登录强制密码 + TOTP 两步验证
   （见上文“两步验证（OTP）”）；OTP 密钥与 SMTP 密码一样用 `SECRET_KEY` 派生的
   Fernet 密钥加密存储。
5. **CORS 收紧**：生产同源部署默认不开放跨域；开发仅放行 Vite 来源（`CORS_ORIGINS`）。
6. **学生注册需邮箱验证**：注册前须先获取学号邮箱验证码；注册成功后立即弹窗
   绑定 OTP（验证才生效），忘记密码同样走邮箱验证码 + 自设新密码。
7. **注册问卷并入学生档案**：手机号/微信号/建议直接存放在 `students` 表
   （`phone`/`wechat`/`suggestion`/`info_updated_at`），不再是独立问卷实体；
   旧 `registration_questionnaires` 表在启动时被删除，其历史数据不保留
   （重新从 data.json 迁移会把联系方式映射到学生列）。学生端在“报名信息”页
   （`/student/profile`）维护，管理端在“学生管理”标签页查看/编辑/导出。

## 生产部署注意

- 必须设置强随机 `SECRET_KEY`（生产缺省时拒绝启动）。
- **LAN 一律 HTTPS**：tls_proxy 会拒绝外部地址的明文 HTTP（返回 403）；
  浏览器发送的是密码的 SHA-256 摘要而非原密码，叠加 TLS 后摘要与 JWT 均不可被嗅探。
- SMTP 密码使用由 `SECRET_KEY` 派生的 Fernet 密钥加密存储；更换 `SECRET_KEY`
  会使已保存的 SMTP 密码无法解密，需要重新录入。
- 邮件服务配置与 system 密码/OTP 只出现在本机维护台（`127.0.0.1:5002` 独立端口）；
  远程服务器上通过 SSH 隧道访问：`ssh -L 5002:127.0.0.1:5002 <服务器>`，
  然后浏览器打开 `http://localhost:5002/local/system`。

## 文档

`docs/` 目录：

- **使用指南.md** - 部署、初始配置、邮箱与批量操作、常见问题
- **系统功能说明.md** - 完整功能说明、权限模型、数据模型和API文档
- **问卷系统完整功能说明.md** - 问卷功能详细说明（含候补与签到）
- **自定义问卷功能使用指南.md** - 自定义问卷操作指南

---

**版本：** v3.0（工程化重构）
**最后更新：** 2026-10-19
