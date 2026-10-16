import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";

interface ConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title?: string;
  message: string;
  confirmText?: string;
  danger?: boolean;
  onConfirm: () => void;
}

/** 替代 window.confirm 的确认对话框。 */
export function ConfirmDialog({
  open,
  onOpenChange,
  title = "确认操作",
  message,
  confirmText = "确定",
  danger = true,
  onConfirm,
}: ConfirmDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title={title} className="max-w-sm">
        <p className="text-sm text-[#555] whitespace-pre-wrap">{message}</p>
        <div className="flex gap-3 mt-6">
          <Button
            variant={danger ? "danger" : "default"}
            className="flex-1"
            onClick={() => {
              onConfirm();
              onOpenChange(false);
            }}
          >
            {confirmText}
          </Button>
          <Button variant="secondary" className="flex-1" onClick={() => onOpenChange(false)}>
            取消
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
