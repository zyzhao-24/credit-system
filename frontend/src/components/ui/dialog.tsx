import * as React from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

const Dialog = DialogPrimitive.Root;
const DialogClose = DialogPrimitive.Close;

const DialogContent = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content> & { title?: string }
>(({ className, children, title, ...props }, ref) => (
  <DialogPrimitive.Portal>
    <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/45 data-[state=open]:animate-in data-[state=open]:fade-in-0" />
    <DialogPrimitive.Content
      ref={ref}
      className={cn(
        "fixed left-1/2 top-1/2 z-50 w-[92%] max-w-lg -translate-x-1/2 -translate-y-1/2",
        "rounded-xl bg-white p-6 shadow-xl max-h-[88vh] overflow-y-auto",
        "data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95",
        className,
      )}
      {...props}
    >
      {title ? (
        <DialogPrimitive.Title className="text-lg font-semibold mb-4">
          {title}
        </DialogPrimitive.Title>
      ) : (
        <DialogPrimitive.Title className="sr-only">对话框</DialogPrimitive.Title>
      )}
      {children}
      <DialogPrimitive.Close asChild>
        <button
          aria-label="关闭"
          className="absolute right-4 top-4 rounded-md p-1 text-[#888] hover:bg-black/5 hover:text-[#333] cursor-pointer"
        >
          <X className="h-4 w-4" />
        </button>
      </DialogPrimitive.Close>
    </DialogPrimitive.Content>
  </DialogPrimitive.Portal>
));
DialogContent.displayName = "DialogContent";

export { Dialog, DialogContent, DialogClose };
