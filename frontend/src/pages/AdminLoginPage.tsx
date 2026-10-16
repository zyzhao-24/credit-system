import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { Shield } from "lucide-react";
import { errorMessage } from "@/api/client";
import { useAuth } from "@/auth/auth-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/common";

/** 管理员登录页（固定路径 /admin/login，替代 legacy 随机路径）。 */
export function AdminLoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleLogin = async (event: FormEvent) => {
    event.preventDefault();
    setMessage("");
    setSubmitting(true);
    try {
      await login(username.trim(), password, "admin");
      navigate("/admin");
    } catch (error) {
      setMessage(errorMessage(error, "账号或密码错误"));
    } finally {
      setSubmitting(false);
    }
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

        {message ? (
          <p className="mt-4 rounded-md border border-danger/20 bg-danger/10 px-3 py-3 text-center text-[13px] text-danger">
            {message}
          </p>
        ) : null}
      </div>
    </div>
  );
}
