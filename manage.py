"""管理命令入口：system 账号与 OTP 的离线维护。

用法：
    python manage.py ensure-system                 确保 system 管理员存在（不改动已有账号）
    python manage.py reset-system-password [密码]   重置 system 密码；不传则生成随机强密码并打印一次
    python manage.py reset-system-otp              重置 system 的 OTP，打印密钥并保存二维码 PNG
    python manage.py set-otp <student|admin> <账号>  为任意账号重新生成 OTP（system 请用上面的命令）
    python manage.py show-otp-uri <student|admin> <账号>  打印账号当前的 otpauth URI（排障用）

这些命令直接在服务器本地操作数据库，不经过 Web 接口、不发送邮件。
"""

from __future__ import annotations

import argparse
import secrets
import sys
from pathlib import Path

from backend import create_app
from backend.extensions import db
from backend.models import Admin, Student
from backend.services.otp_service import bind_new_totp, get_totp_secret
from backend.utils.otp import provisioning_uri, qr_png_bytes
from backend.utils.passwords import client_password_digest, hash_password_digest

SYSTEM_ADMIN_ID = "system"
QR_DIR = Path(__file__).resolve().parent / "var"


def _account(user_type: str, account_id: str):
    if user_type == "student":
        return db.session.get(Student, account_id)
    return db.session.get(Admin, account_id)


def _print_otp_material(user_type: str, account_id: str, secret: str) -> None:
    uri = provisioning_uri(secret, account_id)
    QR_DIR.mkdir(exist_ok=True)
    qr_path = QR_DIR / f"otp_{user_type}_{account_id}.png"
    qr_path.write_bytes(qr_png_bytes(uri))
    print("OTP 密钥（Base32，仅显示这一次，请妥善保管）:")
    print(f"    {secret}")
    print("otpauth URI:")
    print(f"    {uri}")
    print(f"二维码已保存: {qr_path}")


def cmd_ensure_system() -> int:
    admin = db.session.get(Admin, SYSTEM_ADMIN_ID)
    if admin is not None:
        print(f"[OK] system 管理员已存在（角色: {admin.role}）")
        if admin.role != "system_admin":
            admin.role = "system_admin"
            db.session.commit()
            print("[OK] 已修正 system 的角色为 system_admin")
        return 0
    admin = Admin(
        admin_id=SYSTEM_ADMIN_ID,
        password_hash=hash_password_digest(client_password_digest("sysadmin")),
        role="system_admin",
        department="",
    )
    db.session.add(admin)
    db.session.commit()
    print("[OK] 已创建 system 管理员（初始密码: sysadmin，请尽快用 reset-system-password 修改）")
    return 0


def cmd_reset_system_password(password: str | None) -> int:
    admin = db.session.get(Admin, SYSTEM_ADMIN_ID)
    if admin is None:
        print("[ERROR] system 管理员不存在，请先运行: python manage.py ensure-system")
        return 1
    if not password:
        password = secrets.token_urlsafe(12)
        print("已生成随机密码（仅显示这一次）:")
        print(f"    {password}")
    admin.password_hash = hash_password_digest(client_password_digest(password))
    db.session.commit()
    print("[OK] system 密码已重置")
    return 0


def cmd_reset_system_otp() -> int:
    admin = db.session.get(Admin, SYSTEM_ADMIN_ID)
    if admin is None:
        print("[ERROR] system 管理员不存在，请先运行: python manage.py ensure-system")
        return 1
    secret, _uri = bind_new_totp(admin)
    db.session.commit()
    print("[OK] system 的 OTP 已重新生成")
    _print_otp_material("admin", SYSTEM_ADMIN_ID, secret)
    return 0


def cmd_set_otp(user_type: str, account_id: str) -> int:
    if user_type == "admin" and account_id == SYSTEM_ADMIN_ID:
        print("[ERROR] system 账号请使用: python manage.py reset-system-otp")
        return 1
    account = _account(user_type, account_id)
    if account is None:
        print(f"[ERROR] 账号不存在: {user_type}/{account_id}")
        return 1
    secret, _uri = bind_new_totp(account)
    db.session.commit()
    print(f"[OK] 已为 {user_type}/{account_id} 重新生成 OTP")
    _print_otp_material(user_type, account_id, secret)
    return 0


def cmd_show_otp_uri(user_type: str, account_id: str) -> int:
    account = _account(user_type, account_id)
    if account is None:
        print(f"[ERROR] 账号不存在: {user_type}/{account_id}")
        return 1
    secret = get_totp_secret(account)
    if not secret:
        print(f"[ERROR] {user_type}/{account_id} 尚未绑定 OTP")
        return 1
    print(provisioning_uri(secret, account_id))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="团校积分系统管理命令")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("ensure-system", help="确保 system 管理员存在")

    password_parser = sub.add_parser("reset-system-password", help="重置 system 密码")
    password_parser.add_argument("password", nargs="?", default=None)

    sub.add_parser("reset-system-otp", help="重置 system 的 OTP")

    set_otp_parser = sub.add_parser("set-otp", help="为任意账号重新生成 OTP")
    set_otp_parser.add_argument("user_type", choices=["student", "admin"])
    set_otp_parser.add_argument("account_id")

    show_parser = sub.add_parser("show-otp-uri", help="打印账号当前的 otpauth URI")
    show_parser.add_argument("user_type", choices=["student", "admin"])
    show_parser.add_argument("account_id")

    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        if args.command == "ensure-system":
            return cmd_ensure_system()
        if args.command == "reset-system-password":
            return cmd_reset_system_password(args.password)
        if args.command == "reset-system-otp":
            return cmd_reset_system_otp()
        if args.command == "set-otp":
            return cmd_set_otp(args.user_type, args.account_id)
        if args.command == "show-otp-uri":
            return cmd_show_otp_uri(args.user_type, args.account_id)
    return 1


if __name__ == "__main__":
    sys.exit(main())
