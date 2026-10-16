import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { GraduationCap } from "lucide-react";
import { errorMessage } from "@/api/client";
import { forgotPassword, registerStudent } from "@/api/service";
import { useAuth } from "@/auth/auth-context";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Input, Textarea } from "@/components/ui/input";
import { Field } from "@/components/common";

const PHONE_PATTERN = /^1[3-9]\d{9}$/;

/** 学生登录页：登录 + 注册 + 忘记密码。 */
export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const [registerOpen, setRegisterOpen] = useState(false);
  const [forgotOpen, setForgotOpen] = useState(false);

  const handleLogin = async (event: FormEvent) => {
    event.preventDefault();
    setMessage("");
    setSubmitting(true);
    try {
      await login(username.trim(), password, "student");
      navigate("/student");
    } catch (error) {
      setMessage(errorMessage(error, "学号或密码错误"));
    } finally {
      setSubmitting(false);
    }
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
    suggestion: "",
  });
  const [submitting, setSubmitting] = useState(false);

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
      suggestion: "",
    });
  };

  const submit = async () => {
    const { name, student_id, phone, wechat, password, confirm, suggestion } = form;
    if (!name.trim()) return toast.error("请输入姓名");
    if (!student_id.trim()) return toast.error("请输入学号");
    if (!/^\d+$/.test(student_id.trim())) return toast.error("学号只能包含数字");
    if (!phone.trim()) return toast.error("请输入手机号码");
    if (!PHONE_PATTERN.test(phone.trim())) return toast.error("请输入正确的11位手机号码");
    if (!wechat.trim()) return toast.error("请输入微信号");
    if (!password) return toast.error("请设置密码");
    if (password.length < 6) return toast.error("密码至少需要6位字符");
    if (password !== confirm) return toast.error("两次输入的密码不一致");

    setSubmitting(true);
    try {
      const result = await registerStudent({
        name: name.trim(),
        student_id: student_id.trim(),
        phone: phone.trim(),
        wechat: wechat.trim(),
        password,
        suggestion: suggestion.trim(),
      });
      if (result.success) {
        toast.success("注册成功！请使用学号和密码登录");
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
