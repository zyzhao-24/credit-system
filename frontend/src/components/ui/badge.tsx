import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded px-2 py-0.5 text-xs font-medium whitespace-nowrap",
  {
    variants: {
      variant: {
        default: "bg-[#e8e8e8] text-[#333]",
        qualified: "bg-[#d4edda] text-[#155724]",
        unqualified: "bg-[#f8d7da] text-[#721c24]",
        waitlist: "bg-[#fff3e0] text-[#e65100]",
        ended: "bg-[#9e9e9e] text-white",
        info: "bg-[#e3f2fd] text-[#1565c0]",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
