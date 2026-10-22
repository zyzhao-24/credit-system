import { useRef, useState } from "react";
import { toast } from "sonner";
import { Download, Copy } from "lucide-react";
import type { AdminOtpBundle } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/common";

const OTP_PATTERN = /^\d{6}$/;

type Activation =
  | { type: "verify"; onVerify: (code: string) => Promise<boolean> }
  | { type: "confirm"; onConfirm: () => Promise<boolean> };

/** OTP 二维码弹窗。
 *  - 默认仅展示（创建管理员后转交二维码）；
 *  - activation=verify：扫码后输入验证码，验证通过才生效（注册/学生自助重置）；
 *  - activation=confirm：系统管理员二次确认后才生效（重置管理员 OTP）。
 *  关闭弹窗即放弃，候选密钥不会生效；未完成激活而关闭时触发 onSkip。 */
export function OtpBundleDialog({
  bundle,
  onOpenChange,
  onSkip,
  activation,
  title = "绑定动态验证码（OTP）",
}: {
  bundle: AdminOtpBundle | null;
  onOpenChange: (open: boolean) => void;
  /** 未验证/确认就关闭时回调（成功后正常关闭不会触发） */
  onSkip?: () => void;
  activation?: Activation;
  title?: string;
}) {
  // 用 ref 而非 state 记录完成状态：submit 闭包持有的是旧渲染的回调，
  // state 在 onVerify 内的更新不会反映到本次关闭判断中
  const completedRef = useRef(false);

  const handleOpenChange = (open: boolean) => {
    if (!open) {
      if (!completedRef.current) onSkip?.();
      completedRef.current = false;
    }
    onOpenChange(open);
  };

  return (
    <Dialog open={bundle !== null} onOpenChange={handleOpenChange}>
      <DialogContent title={title} className="max-w-[420px]">
        {bundle ? (
          <OtpBundleBody
            bundle={bundle}
            activation={activation}
            onOpenChange={handleOpenChange}
            completedRef={completedRef}
          />
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

function OtpBundleBody({
  bundle,
  activation,
  onOpenChange,
  completedRef,
}: {
  bundle: AdminOtpBundle;
  activation?: Activation;
  onOpenChange: (open: boolean) => void;
  completedRef: { current: boolean };
}) {
  const [code, setCode] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const copySecret = async () => {
    try {
      await navigator.clipboard.writeText(bundle.otp_secret);
      toast.success("密钥已复制");
    } catch {
      toast.error("复制失败，请手动抄录");
    }
  };

  const submit = async () => {
    if (!activation) return;
    setSubmitting(true);
    try {
      let succeeded = false;
      if (activation.type === "verify") {
        if (!OTP_PATTERN.test(code.trim())) {
          toast.error("请输入6位数字验证码");
          return;
        }
        succeeded = await activation.onVerify(code.trim());
      } else {
        succeeded = await activation.onConfirm();
      }
      if (succeeded) {
        completedRef.current = true;
        onOpenChange(false);
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <p className="text-[13px] text-danger -mt-2 mb-3 leading-relaxed">
        ⚠️ 此二维码与密钥仅显示这一次，请立即用验证器应用扫码绑定，或抄写密钥妥善保存。
      </p>
      {bundle.initial_password ? (
        <div className="mb-3 rounded-md border border-danger/30 bg-danger/5 px-3 py-2">
          <p className="text-[13px] text-danger mb-2 leading-relaxed">
            该账号使用系统生成的随机初始密码（同样仅显示这一次），首次登录需用它登录并修改密码：
          </p>
          <Input value={bundle.initial_password} readOnly className="font-mono bg-white" />
        </div>
      ) : null}
      <div className="flex justify-center mb-3">
        <img
          src={bundle.otp_qr}
          alt="OTP 绑定二维码"
          className="h-[220px] w-[220px] rounded-md border border-[#e0e0e0]"
        />
      </div>
      <div className="flex justify-center gap-2 mb-4">
        <a href={bundle.otp_qr} download="otp-qrcode.png">
          <Button type="button" variant="secondary" size="sm">
            <Download className="h-4 w-4" />
            下载二维码
          </Button>
        </a>
        <Button type="button" variant="secondary" size="sm" onClick={copySecret}>
          <Copy className="h-4 w-4" />
          复制密钥
        </Button>
      </div>
      <Field label="手动输入密钥">
        <Input value={bundle.otp_secret} readOnly className="font-mono bg-[#f5f5f5]" />
      </Field>
      {activation?.type === "verify" ? (
        <>
          <Field label="输入验证器中的 6 位验证码以完成绑定" required>
            <Input
              value={code}
              onChange={(event) => setCode(event.target.value)}
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              placeholder="6 位数字"
              className="text-center tracking-[0.5em]"
            />
          </Field>
          <Button className="w-full mt-2" onClick={submit} disabled={submitting}>
            {submitting ? "验证中..." : "验证并绑定"}
          </Button>
          <p className="mt-2 text-center text-[12px] text-[#888]">
            关闭本窗口即放弃绑定，动态验证码不会变更
          </p>
        </>
      ) : activation?.type === "confirm" ? (
        <>
          <p className="text-[13px] text-[#616161] leading-relaxed">
            请先将二维码转交给对应管理员完成扫码，然后点击下方按钮二次确认，
            新验证码才会生效；取消则一切保持不变。
          </p>
          <div className="flex gap-3 mt-2">
            <Button className="flex-1" onClick={submit} disabled={submitting}>
              {submitting ? "生效中..." : "确认生效"}
            </Button>
            <Button variant="secondary" className="flex-1" onClick={() => onOpenChange(false)}>
              取消
            </Button>
          </div>
        </>
      ) : (
        <Button className="w-full mt-2" onClick={() => onOpenChange(false)}>
          我已完成绑定
        </Button>
      )}
    </>
  );
}
