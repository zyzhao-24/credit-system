"""测试邮件打桩：捕获外发邮件而不是真实 SMTP 发送。

独立成模块是为了让 conftest 和测试文件共享同一份 SENT_MAIL 列表：
pytest 会以 `conftest` 为模块名加载 conftest.py，若测试文件再
`from tests.conftest import SENT_MAIL` 会得到第二个模块实例，
导致打桩写入的列表与断言读取的列表不是同一对象。
"""

SENT_MAIL: list[dict] = []


def stub_send_email(to_email, subject, body, attachments=None, html=None, inline_images=None):
    """send_email 的测试替身：记录参数并假装成功。"""
    SENT_MAIL.append(
        {
            "to": to_email,
            "subject": subject,
            "body": body,
            "html": html or "",
            "attachments": attachments or [],
            "inline_images": inline_images or [],
        }
    )
    return True, "邮件发送成功（测试环境，未真实发送）"
