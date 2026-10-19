"""生成自签名 TLS 证书，用于内网 HTTPS。

证书写入 instance/tls.crt 与 instance/tls.key（instance/ 已被 git 忽略，
私钥不会进入版本库）。SAN 包含 localhost、127.0.0.1、::1 与本机内网 IP。

用法：
    uv run python gen_cert.py            # 证书已存在时不重复生成
    uv run python gen_cert.py --force    # 重签（内网 IP 变化或证书到期时）

生成后重启服务即启用 HTTPS（deploy_server.py 检测到证书即切换）。
自签名证书不受浏览器信任，访问时提示"不安全"属预期，
点"高级 → 继续前往"即可；如需消除警告请改用本地 CA（mkcert）方案。
"""

from __future__ import annotations

import datetime
import ipaddress
import socket
import sys
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

CERT_DAYS = 825  # 自签名证书的常见有效期上限
CERT_PATH = Path("instance/tls.crt")
KEY_PATH = Path("instance/tls.key")


def get_local_ip() -> str | None:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except OSError:
        return None


def _generate() -> None:
    CERT_PATH.parent.mkdir(parents=True, exist_ok=True)
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.datetime.now(datetime.UTC)

    local_ip = get_local_ip()
    san_entries: list[x509.GeneralName] = [
        x509.DNSName("localhost"),
        x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
        x509.IPAddress(ipaddress.ip_address("::1")),
    ]
    if local_ip:
        san_entries.append(x509.IPAddress(ipaddress.ip_address(local_ip)))

    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "credit-system.local")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=CERT_DAYS))
        .add_extension(x509.SubjectAlternativeName(san_entries), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(private_key, hashes.SHA256())
    )

    KEY_PATH.write_bytes(
        private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    CERT_PATH.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    try:
        KEY_PATH.chmod(0o600)
    except OSError:
        pass  # Windows 上权限位不可设置，忽略

    print(f"已生成自签名证书：{CERT_PATH}（私钥 {KEY_PATH}）")
    print(f"有效期：{CERT_DAYS} 天")
    print("SAN：" + "、".join(["localhost", "127.0.0.1", "::1"] + ([local_ip] if local_ip else [])))


def ensure_cert() -> bool:
    """证书不存在时自动生成（deploy_server.py 启动前调用）。返回证书是否可用。"""
    if CERT_PATH.exists() and KEY_PATH.exists():
        return True
    try:
        _generate()
    except Exception as exc:  # 生成失败不阻断启动，回退到明文 HTTP
        print(f"[warn] 自签名证书生成失败，回退到明文 HTTP：{exc}")
        return False
    return True


def main() -> None:
    if CERT_PATH.exists() and KEY_PATH.exists() and "--force" not in sys.argv:
        print(f"证书已存在：{CERT_PATH}；如需重签请使用 --force")
        return
    _generate()
    print("重启服务后生效；浏览器提示“不安全”属预期，点“高级 → 继续前往”即可。")


if __name__ == "__main__":
    main()
