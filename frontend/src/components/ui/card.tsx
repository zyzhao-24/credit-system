import * as React from "react";
import { cn } from "@/lib/utils";

const Card = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn("rounded-xl bg-white p-5 shadow-[0_2px_8px_rgba(0,0,0,0.08)]", className)}
      {...props}
    />
  ),
);
Card.displayName = "Card";

const CardTitle = React.forwardRef<HTMLHeadingElement, React.HTMLAttributes<HTMLHeadingElement>>(
  ({ className, ...props }, ref) => (
    <h3 ref={ref} className={cn("text-lg font-semibold mb-3", className)} {...props} />
  ),
);
CardTitle.displayName = "CardTitle";

export { Card, CardTitle };
