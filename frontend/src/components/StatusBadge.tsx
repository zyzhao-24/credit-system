import type { FeedbackItem } from "@/api/types";
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

/** 问卷报名状态徽章：已取消 > 已截止（成功/失败）> 候补 > 成功。 */
export function RegistrationBadge({ status, isEnded, isSelected, isWaitlist }: RegistrationStatusProps) {
  if (status === "cancelled") {
    return <Badge variant="unqualified">已取消</Badge>;
  }
  if (isEnded) {
    return isSelected ? (
      <Badge variant="qualified">✓ 成功</Badge>
    ) : (
      <Badge variant="unqualified">失败</Badge>
    );
  }
  if (isWaitlist) {
    return <Badge variant="waitlist">候补</Badge>;
  }
  return <Badge variant="qualified">成功</Badge>;
}

/** 反馈处理状态徽章：待处理 > 已拒绝 > 已记录 > 已处理。 */
export function FeedbackOutcomeBadge({ item }: { item: FeedbackItem }) {
  if (item.status === "pending") {
    return <Badge variant="info">待处理</Badge>;
  }
  if (item.outcome === "rejected") {
    return <Badge variant="unqualified">已拒绝</Badge>;
  }
  if (item.outcome === "recorded") {
    return <Badge variant="qualified">已记录</Badge>;
  }
  return <Badge variant="qualified">已处理</Badge>;
}

type CheckinState = "absent" | "none" | "pending" | "valid";

/** 签到状态徽章：缺席 > 已签到（候补待确认/已生效）> 未签到。 */
export function CheckinBadge({
  state,
  checkedInAt,
}: {
  state: CheckinState;
  checkedInAt: string;
}) {
  if (state === "absent") {
    return <Badge variant="unqualified">缺席</Badge>;
  }
  if (state === "valid") {
    return (
      <Badge variant="qualified" title={checkedInAt ? `签到时间：${checkedInAt}` : undefined}>
        ✓ 已签到
      </Badge>
    );
  }
  if (state === "pending") {
    return (
      <Badge variant="waitlist" title={checkedInAt ? `签到时间：${checkedInAt}，待管理员确认` : undefined}>
        待确认
      </Badge>
    );
  }
  return <span className="text-muted-foreground text-xs">-</span>;
}
