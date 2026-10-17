import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { GraduationCap } from "lucide-react";
import { errorMessage } from "@/api/client";
import {
  forgotPassword,
  loginWithToken,
  registerStudent,
  sendRegistrationCode,
  verifyOtpCode,
} from "@/api/service";
import { isOtpRequired } from "@/api/types";
import { useAuth } from "@/auth/auth-context";
import { sha256Hex } from "@/lib/sha256";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Input, Textarea } from "@/components/ui/input";
import { Field } from "@/components/common";

const PHONE_PATTERN = /^1[3-9]\d{9}$/;
const OTP_PATTERN = /^\d{6}$/;
const CODE_COUNTDOWN_SECONDS = 60;

/** 学生登录页：登录（密码 + 动态验证码两步） + 注册 + 忘记密码。 */
export function LoginPage() {
  const { finishLogin } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // 第二步：OTP 验证码（otpTicket 非空时切换到验证码表单）
  const [otpTicket, setOtpTicket] = useState("");
  const [otpHint, setOtpHint] = useState("");
  const [otpCode, setOtpCode] = useState("");

  const [registerOpen, setRegisterOpen] = useState(false);
  const [forgotOpen, setForgotOpen] = useState(false);

  const handleLogin = async (event: FormEvent) => {
    event.preventDefault();
    setMessage("");
    setSubmitting(true);
    try {
      const digest = await sha256Hex(password);
      const result = await loginWithToken(username.trim(), digest, "student");
      if (isOtpRequired(result)) {
        // 密码正确，进入动态验证码步骤；首次登录的学生此时已收到绑定邮件
        setOtpTicket(result.otp_ticket);
        setOtpHint(result.message);
        setOtpCode("");
        return;
      }
      finishLogin(result, username.trim());
      navigate("/student");
    } catch (error) {
      setMessage(errorMessage(error, "学号或密码错误"));
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
      navigate("/student");
    } catch (error) {
      setMessage(errorMessage(error, "验证码错误或已过期"));
    } finally {
      setSubmitting(false);
    }
  };

  const backToPassword = () => {
    setOtpTicket("");
    setOtpCode("");
    setOtpHint("");
    setMessage("");
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-white px-4">
      <div className="w-full max-w-[520px] rounded-xl bg-white p-8 shadow-[0_8px_32px_rgba(0,0,0,0.08)]">
        <div className="text-center mb-8">
          <div className="mx-auto mb-5 flex h-20 w-20 items-center justify-center rounded-[20px] bg-gradient-to-br from-primary to-[#00bcf2] text-white shadow-[0_8px_24px_rgba(0,120,212,0.3)]">
            <GraduationCap className="h-11 w-11" />
          </div>
          <h1 className="text-[28px] font-semibold">团校积分系统</h1>
          <p className="mt-3 text-[15px] text-[#616161]">学生登录</p>
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
            {otpHint ? (
              <p className="mt-2 text-[13px] text-[#616161] leading-relaxed">{otpHint}</p>
            ) : null}
            <Button type="submit" className="w-full h-12 text-base mt-3" disabled={submitting}>
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
            <Field label="学号">
              <Input
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                required
                placeholder="请输入学号"
                autoComplete="username"
                pattern="[0-9]*"
                inputMode="numeric"
                className="h-12 text-base"
              />
            </Field>
            <Field label="密码">
              <Input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
                placeholder="请输入密码"
                autoComplete="current-password"
                className="h-12 text-base"
              />
            </Field>
            <Button type="submit" className="w-full h-12 text-base mt-3" disabled={submitting}>
              {submitting ? "登录中..." : "登录"}
            </Button>
            <div className="mt-4 flex justify-between px-1 text-sm">
              <button
                type="button"
                className="text-primary hover:underline cursor-pointer"
                onClick={() => setForgotOpen(true)}
              >
                忘记密码？
              </button>
              <button
                type="button"
                className="text-primary hover:underline cursor-pointer"
                onClick={() => setRegisterOpen(true)}
              >
                还没有账号？立即注册
              </button>
            </div>
          </form>
        )}

        {message ? (
          <p className="mt-4 rounded-md border border-danger/20 bg-danger/10 px-3 py-3 text-center text-[13px] text-danger">
            {message}
          </p>
        ) : null}
      </div>

      <RegisterDialog
        open={registerOpen}
        onOpenChange={setRegisterOpen}
        onRegistered={(studentId) => setUsername(studentId)}
      />
      <ForgotPasswordDialog open={forgotOpen} onOpenChange={setForgotOpen} />
    </div>
  );
}

function RegisterDialog({
  open,
  onOpenChange,
  onRegistered,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onRegistered: (studentId: string) => void;
}) {
  const [form, setForm] = useState({
    name: "",
    student_id: "",
    phone: "",
    wechat: "",
    password: "",
    confirm: "",
    email_code: "",
    suggestion: "",
  });
  const [submitting, setSubmitting] = useState(false);
  const [sendingCode, setSendingCode] = useState(false);
  const [countdown, setCountdown] = useState(0);

  // 发送验证码后的倒计时，期间禁止重复发送
  useEffect(() => {
    if (countdown <= 0) return;
    const timer = setTimeout(() => setCountdown((value) => value - 1), 1000);
    return () => clearTimeout(timer);
  }, [countdown]);

  const set = (key: keyof typeof form) => (value: string) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const reset = () => {
    setForm({
      name: "",
      student_id: "",
      phone: "",
      wechat: "",
      password: "",
      confirm: "",
      email_code: "",
      suggestion: "",
    });
    setCountdown(0);
  };

  const sendCode = async () => {
    const name = form.name.trim();
    const studentId = form.student_id.trim();
    if (!name) return toast.error("请先填写姓名");
    if (!studentId) return toast.error("请先填写学号");
    if (!/^\d+$/.test(studentId)) return toast.error("学号只能包含数字");
    setSendingCode(true);
    try {
      const result = await sendRegistrationCode(studentId, name);
      if (result.success) {
        toast.success(result.message || "验证码已发送");
        setCountdown(CODE_COUNTDOWN_SECONDS);
      } else {
        toast.error(result.message || "发送失败");
      }
    } catch (error) {
      toast.error(errorMessage(error, "发送失败"));
    } finally {
      setSendingCode(false);
    }
  };

  const submit = async () => {
    const { name, student_id, phone, wechat, password, confirm, email_code, suggestion } = form;
    if (!name.trim()) return toast.error("请输入姓名");
    if (!student_id.trim()) return toast.error("请输入学号");
    if (!/^\d+$/.test(student_id.trim())) return toast.error("学号只能包含数字");
    if (!phone.trim()) return toast.error("请输入手机号码");
    if (!PHONE_PATTERN.test(phone.trim())) return toast.error("请输入正确的11位手机号码");
    if (!wechat.trim()) return toast.error("请输入微信号");
    if (!password) return toast.error("请设置密码");
    if (password.length < 6) return toast.error("密码至少需要6位字符");
    if (password !== confirm) return toast.error("两次输入的密码不一致");
    if (!email_code.trim()) return toast.error("请输入邮箱验证码");

    setSubmitting(true);
    try {
      const result = await registerStudent({
        name: name.trim(),
        student_id: student_id.trim(),
        phone: phone.trim(),
        wechat: wechat.trim(),
        password,
        email_code: email_code.trim(),
        suggestion: suggestion.trim(),
      });
      if (result.success) {
        toast.success(result.message || "注册成功！请查收邮箱中的动态验证码绑定二维码");
        onOpenChange(false);
        reset();
        onRegistered(student_id.trim());
      } else {
        toast.error(result.message || "注册失败");
      }
    } catch (error) {
      toast.error(errorMessage(error, "注册失败"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title="初级团校报名注册" className="max-w-[500px]">
        <p className="text-[13px] text-[#666] -mt-2 mb-4">请填写以下信息完成注册</p>
        <Field label="您的姓名" required>
          <Input value={form.name} onChange={(e) => set("name")(e.target.value)} placeholder="请输入真实姓名" />
        </Field>
        <Field label="您的学号" required>
          <Input
            value={form.student_id}
            onChange={(e) => set("student_id")(e.target.value)}
            placeholder="请输入学号"
            pattern="[0-9]*"
            inputMode="numeric"
          />
        </Field>
        <Field label="您的手机号码" required>
          <Input
            type="tel"
            value={form.phone}
            onChange={(e) => set("phone")(e.target.value)}
            placeholder="请输入11位手机号"
            inputMode="numeric"
          />
        </Field>
        <Field label="您的微信号" required>
          <Input value={form.wechat} onChange={(e) => set("wechat")(e.target.value)} placeholder="请输入微信号" />
        </Field>
        <Field label="请设置初始密码" required>
          <Input
            type="password"
            value={form.password}
            onChange={(e) => set("password")(e.target.value)}
            placeholder="至少6位字符"
          />
        </Field>
        <Field label="确认密码" required>
          <Input
            type="password"
            value={form.confirm}
            onChange={(e) => set("confirm")(e.target.value)}
            placeholder="请再次输入密码"
          />
        </Field>
        <Field label="邮箱验证码" required>
          <div className="flex gap-2">
            <Input
              value={form.email_code}
              onChange={(e) => set("email_code")(e.target.value)}
              placeholder="学号邮箱收到的6位验证码"
              inputMode="numeric"
              maxLength={6}
              className="flex-1"
            />
            <Button
              type="button"
              variant="secondary"
              onClick={sendCode}
              disabled={sendingCode || countdown > 0}
              className="shrink-0"
            >
              {countdown > 0 ? `${countdown}s后重发` : sendingCode ? "发送中..." : "发送验证码"}
            </Button>
          </div>
          <p className="mt-1 text-[12px] text-[#888]">验证码将发送到您的学号邮箱</p>
        </Field>
        <Field label="您对今年的初级团校活动有什么建议呢？">
          <Textarea
            rows={3}
            value={form.suggestion}
            onChange={(e) => set("suggestion")(e.target.value)}
            placeholder="请输入您的建议（选填）"
          />
        </Field>
        <div className="flex gap-3 mt-5">
          <Button className="flex-1" onClick={submit} disabled={submitting}>
            {submitting ? "提交中..." : "提交注册"}
          </Button>
          <Button variant="secondary" className="flex-1" onClick={() => onOpenChange(false)}>
            取消
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function ForgotPasswordDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [studentId, setStudentId] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const submit = async () => {
    const value = studentId.trim();
    if (!value) return toast.error("请输入学号");
    if (!/^\d+$/.test(value)) return toast.error("学号只能包含数字");

    setSubmitting(true);
    try {
      const result = await forgotPassword(value);
      if (result.success) {
        toast.success(result.message || "重置邮件已发送");
        onOpenChange(false);
        setStudentId("");
      } else if (result.already_requested) {
        toast.warning(result.message);
      } else {
        toast.error(result.message || "操作失败");
      }
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title="忘记密码" className="max-w-[400px]">
        <p className="text-[13px] text-[#666] -mt-2 mb-4 leading-relaxed">
          请输入您的学号，系统将发送新密码到您的邮箱
        </p>
        <Field label="学号">
          <Input
            value={studentId}
            onChange={(event) => setStudentId(event.target.value)}
            placeholder="请输入学号"
            pattern="[0-9]*"
            inputMode="numeric"
          />
        </Field>
        <div className="flex gap-3 mt-5">
          <Button className="flex-1" onClick={submit} disabled={submitting}>
            {submitting ? "发送中..." : "发送重置邮件"}
          </Button>
          <Button variant="secondary" className="flex-1" onClick={() => onOpenChange(false)}>
            取消
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
