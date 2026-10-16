# 团校积分系统

一个完整的学分管理系统，采用 Windows 11 风格界面设计。

## 快速开始

```bash
# 1. 安装后端依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env   # 编辑 SECRET_KEY（生产必须）

# 3. 初始化管理员（默认账号：system，密码：sysadmin，可用 INIT_ADMIN_PASSWORD 覆盖）
python init_admin.py

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

- **后端**：Flask 3.0 + Flask-SQLAlchemy + Waitress + PyJWT
- **前端**：React 19 + TypeScript + Vite + Tailwind CSS 4 + Radix + axios + react-router
- **数据存储**：SQLite（WAL 模式，事务写入）
- **密码安全**：浏览器 SHA-256 摘要 → 服务端 PBKDF2（600k 轮）
- **UI 设计**：Windows 11 Fluent Design

## 与旧版本的有意行为差异

1. **密码哈希存储**：数据库不再保存明文密码，学生 CSV 导出也不再包含密码列。
2. **管理员登录路径固定**：`/admin/login`，不再使用每次启动随机生成的路径
   （在 SPA 形态下随机路径没有实际安全收益）。
3. **批量导入不再静默重置密码**：已存在的学生只有显式提供第三列密码时才更新密码。
4. **认证方式**：session cookie 改为 JWT bearer token（`POST /api/auth/token`，
   OAuth2 Password 风格表单），12 小时过期。
5. **CORS 收紧**：生产同源部署默认不开放跨域；开发仅放行 Vite 来源（`CORS_ORIGINS`）。

## 生产部署注意

- 必须设置强随机 `SECRET_KEY`（生产缺省时拒绝启动）。
- **务必通过反向代理启用 HTTPS/TLS**：浏览器发送的是密码的 SHA-256 摘要而非原密码，
  明文 HTTP 下摘要和 JWT 都可能被嗅探重放。
- SMTP 密码使用由 `SECRET_KEY` 派生的 Fernet 密钥加密存储；更换 `SECRET_KEY`
  会使已保存的 SMTP 密码无法解密，需要重新录入。

## 文档

- **使用指南.md** - 详细使用步骤和常见问题
- **系统功能说明.md** - 完整功能说明和API文档
- **问卷系统完整功能说明.md** - 问卷功能详细说明

---

**版本：** v3.0（工程化重构）
**最后更新：** 2026-10-17
