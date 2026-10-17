import type { AdminOtpBundle } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/common";

/** 创建/重置 OTP 后一次性展示二维码与密钥，关闭后无法再次查看。 */
export function OtpBundleDialog({
  bundle,
  onOpenChange,
}: {
  bundle: AdminOtpBundle | null;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={bundle !== null} onOpenChange={onOpenChange}>
      <DialogContent title="绑定动态验证码（OTP）" className="max-w-[420px]">
        {bundle ? (
          <>
            <p className="text-[13px] text-danger -mt-2 mb-3 leading-relaxed">
              ⚠️ 此二维码与密钥仅显示这一次，请立即用验证器应用扫码绑定，或抄写密钥妥善保存。
            </p>
            <div className="flex justify-center mb-4">
              <img
                src={bundle.otp_qr}
                alt="OTP 绑定二维码"
                className="h-[220px] w-[220px] rounded-md border border-[#e0e0e0]"
              />
            </div>
            <Field label="手动输入密钥">
              <Input value={bundle.otp_secret} readOnly className="font-mono bg-[#f5f5f5]" />
            </Field>
            <Button className="w-full mt-2" onClick={() => onOpenChange(false)}>
              我已完成绑定
            </Button>
          </>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
