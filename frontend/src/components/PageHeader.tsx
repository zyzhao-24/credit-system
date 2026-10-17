import type { ReactNode } from "react";
import { useNavigate } from "react-router";
import { ArrowLeft, LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/auth/auth-context";

interface PageHeaderProps {
  title: string;
  homePath: string;
  /** 子页面传入返回目标（如 "/student"），显示返回按钮 */
  backTo?: string;
  extra?: ReactNode;
}

/** 页面顶部：（可选返回按钮 +）标题 + 可选操作 + 退出登录。 */
export function PageHeader({ title, homePath, backTo, extra }: PageHeaderProps) {
  const { logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate(homePath.startsWith("/admin") ? "/admin/login" : "/login");
  };

  return (
    <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
      <div className="flex items-center gap-3">
        {backTo ? (
          <Button variant="secondary" size="sm" onClick={() => navigate(backTo)}>
            <ArrowLeft className="h-4 w-4" />
            返回
          </Button>
        ) : null}
        <h1 className="text-2xl font-bold">{title}</h1>
      </div>
      <div className="flex items-center gap-2">
        {extra}
        <Button variant="danger" size="sm" onClick={handleLogout}>
          <LogOut className="h-4 w-4" />
          退出登录
        </Button>
      </div>
    </div>
  );
}
