"""HTML email layout shared by all outbound messages.

Email clients only reliably support inline styles and table layout, so the
template below deliberately avoids classes, flexbox and external assets.
"""

from __future__ import annotations

import html as _html


def esc(value: str) -> str:
    return _html.escape(value, quote=True)


def render_mail_html(title: str, body_html: str) -> str:
    """Wrap content blocks in the system-branded email layout."""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f5f6f8;">
  <div style="background:#f5f6f8;padding:32px 12px;font-family:'Microsoft YaHei','Segoe UI',system-ui,sans-serif;">
    <div style="max-width:560px;margin:0 auto;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
      <div style="background:linear-gradient(135deg,#0078d4,#00bcf2);padding:22px 28px;">
        <div style="color:#ffffff;font-size:18px;font-weight:600;letter-spacing:1px;">团校积分系统</div>
        <div style="color:rgba(255,255,255,0.85);font-size:12px;margin-top:4px;">{esc(title)}</div>
      </div>
      <div style="padding:28px;color:#1f1f1f;font-size:14px;line-height:1.8;">
        {body_html}
      </div>
      <div style="padding:16px 28px;border-top:1px solid #f0f0f0;color:#999999;font-size:12px;line-height:1.7;">
        本邮件由团校积分系统自动发送，请勿直接回复。<br>
        如非本人操作，请立即联系管理员。
      </div>
    </div>
  </div>
</body>
</html>"""


def greeting(name: str) -> str:
    return f'<p style="margin:0 0 16px;">您好，<strong>{esc(name)}</strong> 同学：</p>'


def code_block(code: str) -> str:
    """Large verification-code block."""
    return (
        '<div style="margin:20px 0;text-align:center;background:#f5f6f8;border:1px dashed #c8c8c8;'
        'border-radius:10px;padding:18px;">'
        f'<span style="font-family:Consolas,Menlo,monospace;font-size:30px;font-weight:700;'
        f'letter-spacing:10px;color:#0078d4;">{esc(code)}</span></div>'
    )


def secret_block(secret: str) -> str:
    """Monospace block for manually entered OTP secrets."""
    return (
        '<div style="margin:12px 0;text-align:center;background:#f5f6f8;border:1px dashed #c8c8c8;'
        'border-radius:10px;padding:14px;">'
        f'<span style="font-family:Consolas,Menlo,monospace;font-size:16px;font-weight:600;'
        f'letter-spacing:3px;color:#1f1f1f;word-break:break-all;">{esc(secret)}</span></div>'
    )


def qr_image(cid: str, note: str = "使用验证器应用扫描此二维码") -> str:
    """Inline QR image referencing an attached Content-ID."""
    return (
        '<div style="margin:16px 0;text-align:center;">'
        f'<img src="cid:{cid}" alt="OTP 二维码" width="200" height="200" '
        'style="border:1px solid #e0e0e0;border-radius:10px;padding:8px;background:#ffffff;">'
        f'<div style="color:#888888;font-size:12px;margin-top:8px;">{esc(note)}</div></div>'
    )


def hint(text: str) -> str:
    return f'<p style="margin:14px 0 0;color:#888888;font-size:12px;line-height:1.7;">{esc(text)}</p>'


def paragraph(text: str) -> str:
    return f'<p style="margin:0 0 12px;">{esc(text)}</p>'
