"""
初始化管理员账号

在新后端（SQLite）中创建或重置默认的系统管理员账号。
密码链与线上一致：浏览器摘要 SHA-256 -> 服务端 PBKDF2。
"""
import getpass
import os
import sys

from backend import create_app
from backend.extensions import db
from backend.models.core import Admin
from backend.utils.passwords import client_password_digest, hash_password_digest

DEFAULT_ADMIN_ID = 'system'
DEFAULT_PASSWORD = 'sysadmin'


def main():
    app = create_app()
    with app.app_context():
        admin = db.session.get(Admin, DEFAULT_ADMIN_ID)
        existed = admin is not None

        # 非交互场景可用 INIT_ADMIN_PASSWORD 指定密码（空值=默认密码）
        env_password = os.getenv('INIT_ADMIN_PASSWORD')
        password = env_password or DEFAULT_PASSWORD
        if env_password is None and sys.stdin.isatty():
            prompt = (
                f'{"重置" if existed else "设置"} {DEFAULT_ADMIN_ID} 密码'
                f'（直接回车使用默认 {DEFAULT_PASSWORD}）: '
            )
            entered = getpass.getpass(prompt).strip()
            if entered:
                password = entered

        if admin is None:
            admin = Admin(admin_id=DEFAULT_ADMIN_ID, role='system_admin', department='')
            db.session.add(admin)
        admin.role = 'system_admin'
        admin.password_hash = hash_password_digest(client_password_digest(password))
        db.session.commit()

        if existed:
            print(f'[OK] 系统管理员账号已重置: {DEFAULT_ADMIN_ID}')
        else:
            print(f'[OK] 已创建系统管理员账号: {DEFAULT_ADMIN_ID}')

        print('\n管理员列表:')
        for row in db.session.execute(db.select(Admin).order_by(Admin.admin_id)).scalars():
            role_name = '系统管理员' if row.role == 'system_admin' else '管理员'
            dept_info = f' ({row.department})' if row.department else ''
            print(f'  - {row.admin_id}: {role_name}{dept_info}')


if __name__ == '__main__':
    main()
