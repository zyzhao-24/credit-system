import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { errorMessage } from "@/api/client";
import {
  getAdminActivities,
  getAdminCategories,
  getAdminFeedback,
  getActivityRecords,
  handleFeedback,
  setMissingFeedbackOpen,
} from "@/api/service";
import type { AdminActivity, AdminRecord, FeedbackItem } from "@/api/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Textarea } from "@/components/ui/input";
import { CheckboxGroup } from "@/components/CheckboxGroup";
import { EmptyState, Field } from "@/components/common";
import { Markdown } from "@/components/Markdown";
import { FeedbackOutcomeBadge } from "@/components/StatusBadge";

/** 管理端反馈版块：待处理优先；BUG 回复结案；漏录核定修改后记录或拒绝。
 * 顶部可开关集中活动反馈（开启期间学生才能提交漏录申请；BUG 反馈常驻）。
 */
export function FeedbackSection() {
  const [feedbacks, setFeedbacks] = useState<FeedbackItem[] | null>(null);
  const [categoryOptions, setCategoryOptions] = useState<string[]>([]);
  const [activities, setActivities] = useState<AdminActivity[]>([]);
  const [missingOpen, setMissingOpen] = useState(false);
  const [toggleBusy, setToggleBusy] = useState(false);

  const load = useCallback(() => {
    getAdminFeedback()
      .then((data) => {
        if (data.success) {
          setFeedbacks(data.feedbacks);
          setMissingOpen(data.missing_open);
        } else {
          toast.error("加载反馈失败");
        }
      })
      .catch((error) => toast.error(errorMessage(error, "加载反馈失败")));
  }, []);

  useEffect(load, [load]);

  useEffect(() => {
    getAdminCategories()
      .then((data) => {
        if (data.success) setCategoryOptions(data.categories.map((c) => c.name));
      })
      .catch(() => undefined);
    getAdminActivities()
      .then((data) => {
        if (data.success) setActivities(data.activities);
      })
      .catch(() => undefined);
  }, []);

  const toggleMissingOpen = async () => {
    setToggleBusy(true);
    try {
      const result = await setMissingFeedbackOpen(!missingOpen);
      if (result.success) {
        toast.success(result.message || "已更新");
        setMissingOpen(!missingOpen);
      } else {
        toast.error(result.message || "操作失败");
      }
    } catch (error) {
      toast.error(errorMessage(error, "操作失败"));
    } finally {
      setToggleBusy(false);
    }
  };

  return (
    <section>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <h2 className="text-xl font-semibold">学生反馈</h2>
        <div className="ml-auto flex items-center gap-2">
          <Button
            size="sm"
            variant={missingOpen ? "success" : "secondary"}
            disabled={toggleBusy}
            onClick={toggleMissingOpen}
          >
            集中活动反馈：{missingOpen ? "已开启" : "已关闭"}
          </Button>
          <Button size="sm" variant="secondary" onClick={load}>
            刷新
          </Button>
        </div>
      </div>
      {feedbacks === null ? (
        <p className="py-10 text-center text-[#999]">加载中...</p>
      ) : feedbacks.length === 0 ? (
        <EmptyState icon="📭" text="暂无反馈" />
      ) : (
        <div className="flex flex-col gap-3">
          {feedbacks.map((item) => (
            <FeedbackCard
              key={item.feedback_id}
              item={item}
              categoryOptions={categoryOptions}
              activities={activities}
              onChanged={load}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function FeedbackCard({
  item,
  categoryOptions,
  activities,
  onChanged,
}: {
  item: FeedbackItem;
  categoryOptions: string[];
  activities: AdminActivity[];
  onChanged: () => void;
}) {
  const pending = item.status === "pending";
  return (
    <Card className="p-4">
      <div className="mb-2 flex flex-wrap items-center gap-2 text-sm">
        <Badge variant={item.type === "bug" ? "unqualified" : "waitlist"}>{item.type_text}</Badge>
        <FeedbackOutcomeBadge item={item} />
        <span className="font-medium">
          {item.student_name}（{item.student_id}）
        </span>
        <span className="ml-auto text-xs text-[#999]">
          {item.created_at}
          {item.handled_at ? ` · ${item.handled_by} 处理于 ${item.handled_at}` : ""}
        </span>
      </div>

      {item.type === "bug" ? (
        <div className="rounded-md bg-[#fafafa] px-3 py-2">
          <Markdown text={item.content} />
        </div>
      ) : (
        <MissingDetail item={item} />
      )}

      {pending ? (
        item.type === "bug" ? (
          <BugHandleForm item={item} onChanged={onChanged} />
        ) : (
          <MissingHandleForm
            key={item.feedback_id}
            item={item}
            categoryOptions={categoryOptions}
            activities={activities}
            onChanged={onChanged}
          />
        )
      ) : (
        <ResolvedBlock item={item} onChanged={onChanged} />
      )}
    </Card>
  );
}

/** 漏录申请的结构化展示：申请内容 + 可选证据 + 字符匹配提示。 */
function MissingDetail({ item }: { item: FeedbackItem }) {
  return (
    <div className="rounded-md bg-[#fafafa] px-3 py-2 text-sm leading-6">
      <div>
        <strong>申请：</strong>
        {item.activity_name} / {item.record_name || "（未指定记录）"} / {item.credits} 学分 /{" "}
        {item.categories.join("、")}
      </div>
      {item.evidence ? (
        <div>
          <strong>参与证据：</strong>
          {item.evidence}
        </div>
      ) : null}
      {item.match_hint.length > 0 ? (
        <div className="text-[#e65100]">
          <strong>重合提示：</strong>
          {item.match_hint
            .map((match) => `「${match.name}」（匹配率 ${Math.round(match.rate * 100)}%）`)
            .join("、")}
          ，是否重复由人工判断
        </div>
      ) : null}
    </div>
  );
}

/** BUG 反馈处理：回复并结案。 */
function BugHandleForm({ item, onChanged }: { item: FeedbackItem; onChanged: () => void }) {
  const [reply, setReply] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!reply.trim()) {
      toast.error("请先填写回复内容");
      return;
    }
    setBusy(true);
    try {
      const result = await handleFeedback(item.feedback_id, {
        action: "reply",
        reply: reply.trim(),
      });
      if (result.success) {
        toast.success("已处理");
        onChanged();
      } else {
        toast.error(result.message || "操作失败");
      }
    } catch (error) {
      toast.error(errorMessage(error, "操作失败"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mt-3">
      <Textarea
        value={reply}
        onChange={(event) => setReply(event.target.value)}
        rows={2}
        placeholder="回复学生（支持 Markdown）…"
      />
      <div className="mt-2">
        <Button size="sm" variant="success" disabled={busy} onClick={submit}>
          回复并标记已处理
        </Button>
      </div>
    </div>
  );
}

/** 漏录申请处理：核定修改后记录（默认带入学生申请值），或填写理由拒绝。
 * 活动名/记录名为可自由填写的选择框：列出已有项供选择，也可输入新名称，
 * 提交时后端会自动创建不存在的活动/记录、追加缺失的记录类别并录入条目。
 */
function MissingHandleForm({
  item,
  categoryOptions,
  activities,
  onChanged,
}: {
  item: FeedbackItem;
  categoryOptions: string[];
  activities: AdminActivity[];
  onChanged: () => void;
}) {
  const [activityName, setActivityName] = useState(item.activity_name);
  const [recordName, setRecordName] = useState(item.record_name);
  const [credits, setCredits] = useState(String(item.credits));
  const [categories, setCategories] = useState<string[]>(item.categories);
  const [reply, setReply] = useState("");
  const [busy, setBusy] = useState(false);
  // 记录候选与其所属活动一起保存，活动名切换后旧候选立即失效（不使用过期数据）
  const [recordState, setRecordState] = useState<{
    activityId: string;
    records: AdminRecord[];
  } | null>(null);

  const matchedActivity = activities.find((a) => a.name === activityName.trim()) ?? null;
  const records =
    recordState && matchedActivity && recordState.activityId === matchedActivity.activity_id
      ? recordState.records
      : [];

  const loadRecords = (activity: AdminActivity, forRecordName: string) => {
    getActivityRecords(activity.activity_id)
      .then((data) => {
        if (data.success) {
          setRecordState({ activityId: activity.activity_id, records: data.records });
          const record = data.records.find((r) => r.record_name === forRecordName.trim());
          if (record) {
            setCategories((prev) => prev.filter((c) => record.categories.includes(c)));
          }
        }
      })
      .catch(() => undefined);
  };

  // 活动名变化时加载该活动的记录候选（事件/异步回调中 setState）
  const onActivityNameChange = (name: string) => {
    setActivityName(name);
    const activity = activities.find((a) => a.name === name.trim());
    if (!activity) {
      setRecordState(null);
      return;
    }
    loadRecords(activity, recordName);
  };

  // 初始带入的学生申请活动可能已存在：挂载后补一次记录候选
  useEffect(() => {
    const activity = activities.find((a) => a.name === item.activity_name);
    if (activity) loadRecords(activity, item.record_name);
  }, [activities, item.activity_name, item.record_name]);

  const activityExists = matchedActivity !== null;
  const matchedRecord = activityExists
    ? (records.find((r) => r.record_name === recordName.trim()) ?? null)
    : null;
  const recordExists = matchedRecord !== null;

  // 已有记录：类别只能从该记录的可行类别中选择
  const feasibleCategories = matchedRecord ? matchedRecord.categories : categoryOptions;

  // 记录变化时剔除不在可行类别中的已选项（事件/异步回调中 setState）
  const constrainCategories = (record: AdminRecord | null) => {
    if (record) {
      setCategories((prev) => prev.filter((c) => record.categories.includes(c)));
    }
  };

  const onRecordNameChange = (name: string) => {
    setRecordName(name);
    constrainCategories(records.find((r) => r.record_name === name.trim()) ?? null);
  };

  const submit = async (action: "record" | "reject") => {
    if (!reply.trim()) {
      toast.error("请先填写回复内容");
      return;
    }
    setBusy(true);
    try {
      const result = await handleFeedback(item.feedback_id, {
        action,
        reply: reply.trim(),
        adjustment:
          action === "record"
            ? {
                activity_name: activityName.trim(),
                record_name: recordName.trim(),
                credits: parseFloat(credits) || 0,
                categories,
              }
            : undefined,
      });
      if (result.success) {
        toast.success(result.message || "已处理");
        onChanged();
      } else {
        toast.error(result.message || "操作失败");
      }
    } catch (error) {
      toast.error(errorMessage(error, "操作失败"));
    } finally {
      setBusy(false);
    }
  };

  const activityListId = `fb-admin-act-${item.feedback_id}`;
  const recordListId = `fb-admin-rec-${item.feedback_id}`;

  return (
    <div className="mt-3 rounded-md border border-[#e5e5e5] p-3">
      <p className="mb-2 text-xs text-[#999]">
        核定为合理情况（可修改学生申请的各项）并记录，或拒绝该申请。
        活动/记录不存在时将自动创建；已有记录时类别只能从该记录的可行类别中选择；
        核定后自动为该学生录入条目（完全相同的已有条目不重复录入）。
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="活动名称" required>
          <Input
            list={activityListId}
            value={activityName}
            onChange={(e) => onActivityNameChange(e.target.value)}
          />
          <datalist id={activityListId}>
            {activities.map((a) => (
              <option key={a.activity_id} value={a.name} />
            ))}
          </datalist>
          {activityName.trim() && !activityExists ? (
            <p className="mt-1 text-xs text-[#e65100]">该活动不存在，记录时将自动创建</p>
          ) : null}
        </Field>
        <Field label="记录名称" required>
          <Input
            list={recordListId}
            value={recordName}
            onChange={(e) => onRecordNameChange(e.target.value)}
          />
          <datalist id={recordListId}>
            {records.map((r) => (
              <option key={r.record_id} value={r.record_name} />
            ))}
          </datalist>
          {recordName.trim() && activityExists && !recordExists ? (
            <p className="mt-1 text-xs text-[#e65100]">该记录不存在，记录时将自动创建</p>
          ) : null}
        </Field>
        <Field label="学分量" required>
          <Input
            type="number"
            step="0.1"
            min="0"
            value={credits}
            onChange={(e) => setCredits(e.target.value)}
          />
        </Field>
        <Field
          label={matchedRecord ? "类别（限该记录的可行类别，可多选）" : "类别（可多选）"}
          required
        >
          <CheckboxGroup
            options={feasibleCategories}
            selected={categories}
            onChange={setCategories}
            idPrefix={`fb-admin-cat-${item.feedback_id}`}
          />
          {matchedRecord && matchedRecord.categories.length === 0 ? (
            <p className="mt-1 text-xs text-[#e65100]">
              该记录没有可行类别，无法核定到该记录
            </p>
          ) : null}
        </Field>
      </div>
      <Field label="回复学生" required>
        <Textarea
          value={reply}
          onChange={(event) => setReply(event.target.value)}
          rows={2}
          placeholder="记录或拒绝的理由（支持 Markdown）…"
        />
      </Field>
      <div className="mt-2 flex gap-2">
        <Button size="sm" variant="success" disabled={busy} onClick={() => submit("record")}>
          核定并记录
        </Button>
        <Button size="sm" variant="danger" disabled={busy} onClick={() => submit("reject")}>
          拒绝
        </Button>
      </div>
    </div>
  );
}

/** 已结案视图：回复与核定结果 + 重新打开。 */
function ResolvedBlock({ item, onChanged }: { item: FeedbackItem; onChanged: () => void }) {
  const [busy, setBusy] = useState(false);

  const reopen = async () => {
    setBusy(true);
    try {
      const result = await handleFeedback(item.feedback_id, { action: "reopen" });
      if (result.success) {
        toast.success("已重新打开");
        onChanged();
      } else {
        toast.error(result.message || "操作失败");
      }
    } catch (error) {
      toast.error(errorMessage(error, "操作失败"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mt-3">
      {item.adjustment ? (
        <div className="mb-2 rounded-md bg-[#e3f2fd] px-3 py-2 text-sm">
          <span className="text-xs text-[#666]">核定记录：</span>
          {item.adjustment.activity_name} / {item.adjustment.record_name} /{" "}
          {item.adjustment.credits} 学分 / {item.adjustment.categories.join("、")}
        </div>
      ) : null}
      {item.reply ? (
        <div className="rounded-md border-l-4 border-success bg-[#f1f8e9] px-3 py-2 text-sm">
          <Markdown text={item.reply} />
        </div>
      ) : null}
      <div className="mt-2 flex items-center gap-2">
        <Button size="sm" variant="secondary" disabled={busy} onClick={reopen}>
          重新打开
        </Button>
        {item.outcome === "recorded" ? (
          <span className="text-xs text-[#999]">
            重新打开将自动删除核定录入的对应条目（不影响活动与记录）
          </span>
        ) : null}
      </div>
    </div>
  );
}
