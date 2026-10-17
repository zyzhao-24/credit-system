# 团校积分系统

一个完整的学分管理系统，采用 Windows 11 风格界面设计。

## 快速开始

```bash
# 1. 安装后端依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env   # 编辑 SECRET_KEY（生产必须）

# 3. 初始化管理员（确保内置 system 账号存在；首次创建时随机生成密码并打印一次）
python init_admin.py

# 3b. 首次部署后设置 system 的密码与 OTP（登录强制两步验证）：
#     启动服务后在服务器本机用浏览器访问 http://localhost:5000/local/system

# 4. 构建前端
cd frontend && npm install && npm run build && cd ..

# 5. 启动系统
python run.py                      # 开发环境（Flask dev server，端口 5000）
start_server.bat                   # 生产环境（Windows，Waitress）
./start_server.sh                  # 生产环境（Linux，Waitress）

# 前端开发模式（可选，Vite 端口 5173，/api 自动代理到 5000）
cd frontend && npm run dev
```

访问系统：

- 学生登录：http://localhost:5000/login
- 管理员登录：http://localhost:5000/admin/login（固定路径）

## 架构

- **后端**：`backend/` —— Flask application factory + Blueprint 拆分（`backend/api/`），
  SQLAlchemy 2 + SQLite（WAL、busy_timeout、foreign_keys），JWT 认证（HS256，12 小时）。
- **前端**：`frontend/` —— React 19 + TypeScript + Vite + Tailwind CSS 4 + Radix。
  生产模式由 Flask 直接托管 `frontend/dist` 并做 SPA fallback。
- **遗留代码**：`legacy/` —— 重构前的单体 `app.py`、`database.py`、`models.py`、
  `routes/`、模板和旧 JS，仅供审计与回滚参考，不再运行。
- **脚本**：
  - `scripts/migrate_json_to_sqlite.py` —— data.json → SQLite 迁移
  - `scripts/verify_migration.py` —— 三层迁移验证
  - `scripts/dump_sqlite_to_json.py` —— SQLite 导出为 legacy JSON 形状（回滚/审计）
  - `scripts/compare_routes.py` —— legacy 与重构后 API 路由覆盖比对
  - `scripts/smoke_api.py` —— 双角色 API 冒烟测试
- **测试**：`python -m pytest tests/ -v`

## 两步验证（OTP）

登录强制“密码 + TOTP 动态验证码”两步：

- 第一步 `POST /api/auth/token`（密码）返回短期 `otp_ticket`（10 分钟）；
- 第二步 `POST /api/auth/token/verify`（otp_ticket + 6 位验证码）换取正式 JWT。
- **学生**：注册时需先通过学号邮箱验证码（`/api/student/register/send_code`），
  注册成功后 OTP 绑定二维码以邮件附件发送到学号邮箱；存量学生首次密码登录时
  自动绑定并发送二维码；忘记密码会同时重置密码与 OTP。
- **管理员**：无邮箱，创建账号时接口一次性返回二维码与 Base32 密钥（仅本次可见）；
  系统管理员可在后台“重置 OTP”普通管理员的绑定。
- **system 账号**：内置固定存在且是唯一的系统管理员，接口禁止创建/删除/修改它，
  也不允许再创建或提升其他 `system_admin`；首次启动建号时随机生成密码并打印一次。
  其密码与 OTP 通过**本机专用维护页**维护：在服务器本机访问
  `http://localhost:5000/local/system`（非本机访问返回 404，表单带签名令牌防跨站提交，
  密码只能随机生成、仅显示一次）。无头服务器可选 manage.py 命令完成同样操作。

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
- 邮箱配置

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
6. **学生注册需邮箱验证**：注册前须先获取学号邮箱验证码；注册成功后登录所需的
   OTP 二维码通过邮件下发。
7. **注册问卷并入学生档案**：手机号/微信号/建议直接存放在 `students` 表
   （`phone`/`wechat`/`suggestion`/`info_updated_at`），不再是独立问卷实体；
   旧 `registration_questionnaires` 表在启动时被删除，其历史数据不保留
   （重新从 data.json 迁移会把联系方式映射到学生列）。学生端在“报名信息”页
   （`/student/profile`）维护，管理端在“学生管理”标签页查看/编辑/导出。

## 生产部署注意

- 必须设置强随机 `SECRET_KEY`（生产缺省时拒绝启动）。
- **务必通过反向代理启用 HTTPS/TLS**：浏览器发送的是密码的 SHA-256 摘要而非原密码，
  明文 HTTP 下摘要和 JWT 都可能被嗅探重放。
- SMTP 密码使用由 `SECRET_KEY` 派生的 Fernet 密钥加密存储；更换 `SECRET_KEY`
  会使已保存的 SMTP 密码无法解密，需要重新录入。

## 文档

`docs/` 目录（内容为重构前版本编写，细节以当前代码为准）：

- **使用指南.md** - 详细使用步骤和常见问题
- **系统功能说明.md** - 完整功能说明和API文档
- **问卷系统完整功能说明.md** - 问卷功能详细说明
- **自定义问卷功能使用指南.md** - 自定义问卷功能说明

---

**版本：** v3.0（工程化重构）
**最后更新：** 2026-10-17
