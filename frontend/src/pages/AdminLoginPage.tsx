import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { Shield } from "lucide-react";
import { errorMessage } from "@/api/client";
import { loginWithToken, verifyOtpCode } from "@/api/service";
import { isOtpRequired } from "@/api/types";
import { useAuth } from "@/auth/auth-context";
import { sha256Hex } from "@/lib/sha256";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/common";

const OTP_PATTERN = /^\d{6}$/;

/** 管理员登录页（固定路径 /admin/login，替代 legacy 随机路径；密码 + 动态验证码两步）。 */
export function AdminLoginPage() {
  const { finishLogin } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // 第二步：OTP 验证码（otpTicket 非空时切换到验证码表单）
  const [otpTicket, setOtpTicket] = useState("");
  const [otpCode, setOtpCode] = useState("");

  const handleLogin = async (event: FormEvent) => {
    event.preventDefault();
    setMessage("");
    setSubmitting(true);
    try {
      const digest = await sha256Hex(password);
      const result = await loginWithToken(username.trim(), digest, "admin");
      if (isOtpRequired(result)) {
        setOtpTicket(result.otp_ticket);
        setOtpCode("");
        return;
      }
      finishLogin(result, username.trim());
      navigate("/admin");
    } catch (error) {
      setMessage(errorMessage(error, "账号或密码错误"));
    } finally {
      setSubmitting(false);
    }
  };

  const handleVerify = async (event: FormEvent) => {
    event.preventDefault();
    setMessage("");
    if (!OTP_PATTERN.test(otpCode.trim())) {
      setMessage("请输入6位数字动态验证码");
      return;
    }
    setSubmitting(true);
    try {
      const result = await verifyOtpCode(otpTicket, otpCode.trim());
      finishLogin(result, username.trim());
      navigate("/admin");
    } catch (error) {
      setMessage(errorMessage(error, "验证码错误或已过期"));
    } finally {
      setSubmitting(false);
    }
  };

  const backToPassword = () => {
    setOtpTicket("");
    setOtpCode("");
    setMessage("");
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-white px-4">
      <div className="w-full max-w-[520px] rounded-xl bg-white p-8 shadow-[0_8px_32px_rgba(0,0,0,0.08)]">
        <div className="text-center mb-8">
          <div className="mx-auto mb-5 flex h-20 w-20 items-center justify-center rounded-[20px] bg-gradient-to-br from-danger to-[#ff6b6b] text-white shadow-[0_8px_24px_rgba(209,52,56,0.3)]">
            <Shield className="h-11 w-11" />
          </div>
          <h1 className="text-[28px] font-semibold">团校积分系统</h1>
          <p className="mt-3 text-[15px] text-[#616161]">管理员登录</p>
        </div>

        {otpTicket ? (
          <form onSubmit={handleVerify}>
            <Field label="动态验证码">
              <Input
                value={otpCode}
                onChange={(event) => setOtpCode(event.target.value)}
                required
                placeholder="请输入验证器中的6位验证码"
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={6}
                autoFocus
                className="h-12 text-base tracking-[0.5em] text-center"
              />
            </Field>
            <Button
              type="submit"
              variant="danger"
              className="w-full h-12 text-base mt-3"
              disabled={submitting}
            >
              {submitting ? "验证中..." : "验证并登录"}
            </Button>
            <div className="mt-4 text-center text-sm">
              <button
                type="button"
                className="text-primary hover:underline cursor-pointer"
                onClick={backToPassword}
              >
                返回重新输入密码
              </button>
            </div>
          </form>
        ) : (
          <form onSubmit={handleLogin}>
            <Field label="管理员账号">
              <Input
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                required
                placeholder="请输入管理员账号"
                autoComplete="username"
                autoFocus
                className="h-12 text-base"
              />
            </Field>
            <Field label="管理员密码">
              <Input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
                placeholder="请输入管理员密码"
                autoComplete="current-password"
                className="h-12 text-base"
              />
            </Field>
            <Button
              type="submit"
              variant="danger"
              className="w-full h-12 text-base mt-3"
              disabled={submitting}
            >
              {submitting ? "登录中..." : "登录"}
            </Button>
          </form>
        )}

        {message ? (
          <p className="mt-4 rounded-md border border-danger/20 bg-danger/10 px-3 py-3 text-center text-[13px] text-danger">
            {message}
          </p>
        ) : null}
      </div>
    </div>
  );
}
