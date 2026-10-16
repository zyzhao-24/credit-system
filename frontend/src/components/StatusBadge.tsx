import { Badge } from "@/components/ui/badge";

/** 合格状态徽章（与 legacy 页面一致的配色）。 */
export function QualifiedBadge({ qualified, mark = false }: { qualified: boolean; mark?: boolean }) {
  return (
    <Badge variant={qualified ? "qualified" : "unqualified"}>
      {qualified ? `${mark ? "✓ " : ""}已合格` : `${mark ? "✗ " : ""}未合格`}
    </Badge>
  );
}

interface RegistrationStatusProps {
  status: "active" | "cancelled";
  isEnded: boolean;
  isSelected: boolean;
  isWaitlist: boolean;
}

/** 问卷报名状态徽章：已取消 > 已截止（入选/未入选）> 候补 > 已报名。 */
export function RegistrationBadge({ status, isEnded, isSelected, isWaitlist }: RegistrationStatusProps) {
  if (status === "cancelled") {
    return <Badge variant="unqualified">已取消</Badge>;
  }
  if (isEnded) {
    return isSelected ? (
      <Badge variant="qualified">✓ 已入选</Badge>
    ) : (
      <Badge variant="unqualified">未入选</Badge>
    );
  }
  if (isWaitlist) {
    return <Badge variant="waitlist">候补</Badge>;
  }
  return <Badge variant="qualified">已报名</Badge>;
}
