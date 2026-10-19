import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { errorMessage } from "@/api/client";
import {
  editFeedback,
  getFeedbackActivityOptions,
  getMyFeedback,
  getStudentCategories,
  matchFeedbackActivities,
  submitFeedback,
} from "@/api/service";
import type { FeedbackActivityOption, FeedbackItem } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Select, Textarea } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CheckboxGroup } from "@/components/CheckboxGroup";
import { EmptyState, Field } from "@/components/common";
import { Markdown } from "@/components/Markdown";
import { FeedbackOutcomeBadge } from "@/components/StatusBadge";

const MANUAL_ACTIVITY = "__manual__";

/** 学生端反馈版块：BUG 反馈（常驻）与活动漏录（集中反馈开启期间可提交）分栏。 */
export function StudentFeedbackSection() {
  const [feedbacks, setFeedbacks] = useState<FeedbackItem[] | null>(null);
  const [missingOpen, setMissingOpen] = useState(false);

  const load = useCallback(() => {
    getMyFeedback()
      .then((data) => {
        if (data.success) {
          setFeedbacks(data.feedbacks);
          setMissingOpen(data.missing_open);
        }
      })
      .catch((error) => toast.error(errorMessage(error, "加载反馈失败")));
  }, []);

  useEffect(load, [load]);

  const pendingBug =
    feedbacks?.find((item) => item.type === "bug" && item.status === "pending") ?? null;
  const bugItems = feedbacks?.filter((item) => item.type === "bug") ?? null;
  const missingItems = feedbacks?.filter((item) => item.type === "missing") ?? null;

  return (
    <Tabs defaultValue="bug">
      <TabsList>
        <TabsTrigger value="bug">BUG 反馈</TabsTrigger>
        <TabsTrigger value="missing">活动漏录</TabsTrigger>
      </TabsList>

      <TabsContent value="bug">
        <div className="flex flex-col gap-4">
          <BugCard key={pendingBug?.feedback_id ?? "new"} pendingBug={pendingBug} onChanged={load} />
          <HistoryCard items={bugItems} emptyText="还没有提交过 BUG 反馈" />
        </div>
      </TabsContent>

      <TabsContent value="missing">
        <div className="flex flex-col gap-4">
          {missingOpen ? (
            <MissingCard onChanged={load} />
          ) : (
            <Card>
              <h3 className="mb-1 font-semibold">活动漏录申请</h3>
              <p className="text-sm text-[#999]">
                当前未开放集中活动反馈，开放期间才能提交漏录申请；已提交申请的处理结果见下方记录。
              </p>
            </Card>
          )}
          <HistoryCard items={missingItems} emptyText="还没有提交过活动漏录申请" />
        </div>
      </TabsContent>
    </Tabs>
  );
}

/** BUG 反馈：每人一条待处理帖；已有时展示原文并可修改。 */
function BugCard({
  pendingBug,
  onChanged,
}: {
  pendingBug: FeedbackItem | null;
  onChanged: () => void;
}) {
  const [content, setContent] = useState(pendingBug?.content ?? "");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!content.trim()) {
      toast.error("请填写反馈内容");
      return;
    }
    setBusy(true);
    try {
      const result = pendingBug
        ? await editFeedback(pendingBug.feedback_id, content.trim())
        : await submitFeedback({ type: "bug", content: content.trim() });
      if (result.success) {
        toast.success(result.message || "已提交");
        if (!pendingBug) setContent("");
        onChanged();
      } else {
        toast.error(result.message || "提交失败");
      }
    } catch (error) {
      toast.error(errorMessage(error, "提交失败"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <h3 className="mb-1 font-semibold">BUG 反馈</h3>
      <p className="mb-3 text-xs text-[#999]">
        每人同时只保留一条待处理的反馈，处理完成前可以直接修改内容
      </p>
      <Field label={pendingBug ? "我的待处理反馈（可修改）" : "问题描述"} required>
        <Textarea
          value={content}
          onChange={(event) => setContent(event.target.value)}
          rows={4}
          placeholder="例如：点击导出 PDF 后页面白屏…"
        />
      </Field>
      <Button onClick={submit} disabled={busy}>
        {busy ? "提交中..." : pendingBug ? "保存修改" : "提交反馈"}
      </Button>
    </Card>
  );
}

/**
 * 活动漏录申请：
 * - 活动在系统中：选择活动后可选择记录（类别限该记录可行类别），或不选记录（自选类别）
 * - 活动不在系统中：手动填写活动名，此时不需要也不能填记录，自选类别
 */
function MissingCard({ onChanged }: { onChanged: () => void }) {
  const [activityKey, setActivityKey] = useState("");
  const [manualName, setManualName] = useState("");
  const [recordId, setRecordId] = useState("");
  const [credits, setCredits] = useState("");
  const [categories, setCategories] = useState<string[]>([]);
  const [categoryOptions, setCategoryOptions] = useState<string[]>([]);
  const [activityOptions, setActivityOptions] = useState<FeedbackActivityOption[]>([]);
  const [evidence, setEvidence] = useState("");
  const [matches, setMatches] = useState<{ name: string; rate: number }[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getStudentCategories()
      .then((data) => {
        if (data.success) setCategoryOptions(data.categories.map((c) => c.name));
      })
      .catch(() => undefined);
    getFeedbackActivityOptions()
      .then((data) => {
        if (data.success) setActivityOptions(data.activities);
      })
      .catch(() => undefined);
  }, []);

  const manual = activityKey === MANUAL_ACTIVITY;
  const activity = activityOptions.find((a) => a.activity_id === activityKey) ?? null;
  const record = activity?.records.find((r) => r.record_id === recordId) ?? null;
  const feasibleCategories = record ? record.categories : categoryOptions;

  // 手动填写活动名时做朴素字符匹配，提示可能与已有活动重合（判断交给人）
  useEffect(() => {
    if (!manual) return;
    const name = manualName.trim();
    const timer = setTimeout(() => {
      if (!name) {
        setMatches([]);
        return;
      }
      matchFeedbackActivities(name)
        .then((data) => {
          if (data.success) setMatches(data.matches);
        })
        .catch(() => undefined);
    }, 400);
    return () => clearTimeout(timer);
  }, [manual, manualName]);

  const onActivityChange = (key: string) => {
    setActivityKey(key);
    setRecordId("");
    setCategories([]);
    setMatches([]);
  };

  const onRecordChange = (id: string) => {
    setRecordId(id);
    const next = activity?.records.find((r) => r.record_id === id) ?? null;
    if (next) {
      setCategories((prev) => prev.filter((c) => next.categories.includes(c)));
    }
  };

  const submit = async () => {
    setBusy(true);
    try {
      const result = await submitFeedback({
        type: "missing",
        activity_name: manual ? manualName.trim() : (activity?.name ?? ""),
        record_name: manual ? "" : (record?.record_name ?? ""),
        credits: parseFloat(credits) || 0,
        categories,
        evidence: evidence.trim(),
      });
      if (result.success) {
        toast.success(result.message || "已提交");
        setActivityKey("");
        setManualName("");
        setRecordId("");
        setCredits("");
        setCategories([]);
        setEvidence("");
        setMatches([]);
        onChanged();
      } else {
        toast.error(result.message || "提交失败");
      }
    } catch (error) {
      toast.error(errorMessage(error, "提交失败"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <h3 className="mb-1 font-semibold">活动漏录申请</h3>
      <p className="mb-3 text-xs text-[#999]">
        学分条目缺失、或整个活动没有录入系统时填写；是否属实由管理员人工核定
      </p>
      <Field label="活动" required>
        <Select value={activityKey} onChange={(event) => onActivityChange(event.target.value)}>
          <option value="">请选择活动</option>
          {activityOptions.map((option) => (
            <option key={option.activity_id} value={option.activity_id}>
              {option.name}
            </option>
          ))}
          <option value={MANUAL_ACTIVITY}>活动不在列表中（手动填写）</option>
        </Select>
      </Field>

      {manual ? (
        <Field label="活动名称" required>
          <Input
            value={manualName}
            onChange={(event) => setManualName(event.target.value)}
            placeholder="活动全称"
          />
          {matches.length > 0 ? (
            <p className="mt-1 text-xs text-[#e65100]">
              与已有活动可能重合：
              {matches
                .map((match) => `「${match.name}」（重合率 ${Math.round(match.rate * 100)}%）`)
                .join("、")}
              ，如即该活动请改从上方列表选择
            </p>
          ) : null}
        </Field>
      ) : null}

      {activity ? (
        <Field label="记录（可选）">
          <Select value={recordId} onChange={(event) => onRecordChange(event.target.value)}>
            <option value="">不选择记录（自行选择类别）</option>
            {activity.records.map((option) => (
              <option key={option.record_id} value={option.record_id}>
                {option.record_name}
              </option>
            ))}
          </Select>
        </Field>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="学分量" required>
          <Input
            type="number"
            step="0.1"
            min="0"
            value={credits}
            onChange={(event) => setCredits(event.target.value)}
          />
        </Field>
        <Field
          label={record ? "类别（限该记录的可行类别，可多选）" : "类别（可多选）"}
          required
        >
          <CheckboxGroup
            options={feasibleCategories}
            selected={categories}
            onChange={setCategories}
            idPrefix="fb-missing-cat"
          />
          {record && record.categories.length === 0 ? (
            <p className="mt-1 text-xs text-[#e65100]">该记录没有可行类别，请改选其他记录或不选记录</p>
          ) : null}
        </Field>
      </div>
      <Field label="参与证据（可选）">
        <Textarea
          value={evidence}
          onChange={(event) => setEvidence(event.target.value)}
          rows={2}
          placeholder="例如：签到记录、现场照片说明、获奖证书等"
        />
      </Field>
      <Button onClick={submit} disabled={busy}>
        {busy ? "提交中..." : "提交漏录申请"}
      </Button>
    </Card>
  );
}

function HistoryCard({ items, emptyText }: { items: FeedbackItem[] | null; emptyText: string }) {
  return (
    <Card>
      <h3 className="mb-3 font-semibold">我的反馈</h3>
      {items === null ? (
        <p className="py-4 text-center text-sm text-[#999]">加载中...</p>
      ) : items.length === 0 ? (
        <EmptyState icon="📭" text={emptyText} />
      ) : (
        <div className="flex flex-col gap-3">
          {items.map((item) => (
            <FeedbackRow key={item.feedback_id} item={item} />
          ))}
        </div>
      )}
    </Card>
  );
}

function FeedbackRow({ item }: { item: FeedbackItem }) {
  return (
    <div className="rounded-md border border-[#e5e5e5] p-3">
      <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-[#999]">
        <FeedbackOutcomeBadge item={item} />
        <span className="ml-auto">{item.created_at}</span>
      </div>
      {item.type === "bug" ? (
        <Markdown text={item.content} />
      ) : (
        <div className="text-sm leading-6">
          <div>
            <strong>活动：</strong>
            {item.activity_name}
            {item.record_name ? (
              <>
                {" · "}
                <strong>记录：</strong>
                {item.record_name}
              </>
            ) : null}
          </div>
          <div>
            <strong>学分：</strong>
            {item.credits}
            {" · "}
            <strong>类别：</strong>
            {item.categories.join("、")}
          </div>
          {item.evidence ? (
            <div>
              <strong>参与证据：</strong>
              {item.evidence}
            </div>
          ) : null}
        </div>
      )}
      {item.adjustment ? (
        <div className="mt-2 rounded-md bg-[#e3f2fd] px-3 py-2 text-sm">
          <span className="text-xs text-[#666]">管理员核定：</span>
          {item.adjustment.activity_name} / {item.adjustment.record_name} /{" "}
          {item.adjustment.credits} 学分 / {item.adjustment.categories.join("、")}
        </div>
      ) : null}
      {item.reply ? (
        <div className="mt-2 rounded-md border-l-4 border-success bg-[#f1f8e9] px-3 py-2 text-sm">
          <span className="text-xs text-[#666]">
            管理员回复{item.handled_at ? `（${item.handled_at}）` : ""}：
          </span>
          <Markdown text={item.reply} />
        </div>
      ) : null}
    </div>
  );
}
