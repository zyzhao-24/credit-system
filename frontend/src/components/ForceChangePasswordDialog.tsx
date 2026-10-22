import { useState } from "react";
import { toast } from "sonner";
import { errorMessage } from "@/api/client";
import { changeAdminPassword, changeStudentPassword } from "@/api/service";
import { sha256Hex } from "@/lib/sha256";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/common";

/** 首次登录强制改密：账号带初始密码标记时，登录成功后弹出且不可跳过。
 *  改密成功后旧令牌已被服务端吊销，调用方应回到登录表单让用户用新密码重新登录。 */
export function ForceChangePasswordDialog({
  open,
  userType,
  oldPassword,
  onChanged,
}: {
  open: boolean;
  userType: "student" | "admin";
  oldPassword: string;
  onChanged: () => void;
}) {
  const [newPassword, setNewPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const submit = async () => {
    if (!newPassword) return toast.error("请设置新密码");
    if (newPassword.length < 6) return toast.error("新密码至少需要6位字符");
    if (newPassword === oldPassword) return toast.error("新密码不能与初始密码相同");
    if (newPassword !== confirm) return toast.error("两次输入的密码不一致");
    setSubmitting(true);
    try {
      const oldDigest = await sha256Hex(oldPassword);
      const change =
        userType === "student" ? changeStudentPassword : changeAdminPassword;
      const result = await change(oldDigest, newPassword);
      if (result.success) {
        toast.success("密码修改成功，请使用新密码重新登录");
        setNewPassword("");
        setConfirm("");
        onChanged();
      } else {
        toast.error(result.message || "修改失败");
      }
    } catch (error) {
      toast.error(errorMessage(error, "修改失败"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    // 不可关闭：必须完成改密（onOpenChange 为空操作，阻止 Esc/点击遮罩跳过）
    <Dialog open={open} onOpenChange={() => undefined}>
      <DialogContent title="首次登录请修改初始密码" className="max-w-[420px]">
        <p className="text-[13px] text-[#666] -mt-2 mb-4 leading-relaxed">
          您当前使用的是系统生成的初始密码，为保障账号安全，请立即设置新密码。
          修改成功后需用新密码重新登录。
        </p>
        <Field label="新密码" required>
          <Input
            type="password"
            value={newPassword}
            onChange={(event) => setNewPassword(event.target.value)}
            placeholder="至少6位字符"
            autoComplete="new-password"
            autoFocus
          />
        </Field>
        <Field label="确认新密码" required>
          <Input
            type="password"
            value={confirm}
            onChange={(event) => setConfirm(event.target.value)}
            placeholder="请再次输入新密码"
            autoComplete="new-password"
          />
        </Field>
        <Button className="w-full mt-3" onClick={submit} disabled={submitting}>
          {submitting ? "提交中..." : "修改密码"}
        </Button>
      </DialogContent>
    </Dialog>
  );
}
