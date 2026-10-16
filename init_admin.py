"""
初始化管理员账号

创建默认的系统管理员账号
"""
from database import Database
from models import Admin
import hashlib

db = Database()

# 创建默认系统管理员
default_admin_id = 'system'
default_password = 'sysadmin'

# 覆盖已有的系统管理员
existed = default_admin_id in db.admins
db.admins[default_admin_id] = Admin(
    admin_id=default_admin_id,
    password=default_password,
    role='system_admin',
    department=''
)
db.save_data()

if existed:
    print(f'✓ 系统管理员账号已重置: {default_admin_id}')
else:
    print(f'✓ 已创建系统管理员账号: {default_admin_id}')
print(f'  密码: {default_password}')

print('\n管理员列表:')
for aid, admin in db.admins.items():
    role_name = '系统管理员' if admin.role == 'system_admin' else '管理员'
    dept_info = f' ({admin.department})' if admin.department else ''
    print(f'  - {aid}: {role_name}{dept_info}')
