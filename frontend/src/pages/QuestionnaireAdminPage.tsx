import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { ChevronDown, ChevronRight, FileDown } from "lucide-react";
import { downloadFile, errorMessage } from "@/api/client";
import {
  createQuestionnaireTemplate,
  deleteQuestionnaireTemplate,
  deleteResponse,
  getActivityCategories,
  getAdminActivities,
  getAllQuestionnaires,
  getQuestionnaireResponses,
  updateQuestionnaireTemplate,
  updateResponse,
} from "@/api/service";
import type {
  AdminActivity,
  AdminQuestionnaireTemplate,
  AdminResponse,
  CustomQuestion,
} from "@/api/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Input, Select } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { PageHeader } from "@/components/PageHeader";
import { QuestionBuilder } from "@/components/QuestionBuilder";
import { validateQuestions } from "@/lib/questions";
import { EmptyState, Field } from "@/components/common";
import { RegistrationBadge } from "@/components/StatusBadge";

const PHONE_PATTERN = /^1[3-9]\d{9}$/;

/** 问卷管理页（系统管理员）：活动问卷模板。注册问卷已并入“学生管理”标签页。 */
export function QuestionnaireAdminPage() {
  const navigate = useNavigate();
  const [templates, setTemplates] = useState<AdminQuestionnaireTemplate[]>([]);
  const [activities, setActivities] = useState<AdminActivity[]>([]);
  const [actSearch, setActSearch] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [editTemplateTarget, setEditTemplateTarget] = useState<AdminQuestionnaireTemplate | null>(null);
  const [deleteTemplateTarget, setDeleteTemplateTarget] = useState<AdminQuestionnaireTemplate | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const load = useCallback(() => {
    getAllQuestionnaires()
      .then((data) => {
        if (data.success) {
          setTemplates(
            data.questionnaires.filter(
              (q): q is AdminQuestionnaireTemplate => q.questionnaire_type === "activity_template",
            ),
          );
        } else {
          toast.error("加载失败");
        }
      })
      .catch((error) => toast.error(errorMessage(error, "加载失败")));
    getAdminActivities()
      .then((data) => {
        if (data.success) setActivities(data.activities);
      })
      .catch(() => undefined);
  }, []);

  useEffect(load, [load, reloadKey]);

  const actQuery = actSearch.trim().toLowerCase();
  const filteredTemplates = actQuery
    ? templates.filter(
        (q) =>
          (q.title ?? "").toLowerCase().includes(actQuery) ||
          (q.activity_name ?? "").toLowerCase().includes(actQuery),
      )
    : templates;

  return (
    <div className="mx-auto max-w-6xl px-4 py-6">
      <PageHeader
        title="问卷管理"
        homePath="/admin"
        extra={
          <Button variant="secondary" size="sm" onClick={() => navigate("/admin")}>
            返回管理后台
          </Button>
        }
      />

      {/* 活动问卷模板 */}
      <section>
        <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
          <h2 className="text-xl font-semibold">活动问卷模板</h2>
          <div className="flex gap-2">
            <Button size="sm" onClick={() => setCreateOpen(true)}>
              ➕ 创建问卷
            </Button>
            <Input
              value={actSearch}
              onChange={(event) => setActSearch(event.target.value)}
              placeholder="搜索问卷标题、活动名称..."
              className="w-64"
            />
          </div>
        </div>

        <div className="mb-4 rounded-lg border-l-4 border-[#ff9800] bg-[#fff3e0] px-3 py-3 text-sm">
          <strong>统计：</strong>总数：{templates.length}
          {filteredTemplates.length !== templates.length ? (
            <span className="ml-5">筛选结果：{filteredTemplates.length}</span>
          ) : null}
        </div>

        {filteredTemplates.length === 0 ? (
          <EmptyState
            icon="📋"
            text={templates.length === 0 ? "暂无活动问卷" : "没有符合条件的记录"}
          />
        ) : (
          filteredTemplates.map((template) => (
            <TemplateCard
              key={template.questionnaire_id}
              template={template}
              onEdit={() => setEditTemplateTarget(template)}
              onDelete={() => setDeleteTemplateTarget(template)}
              onChanged={() => setReloadKey((key) => key + 1)}
            />
          ))
        )}
      </section>

      <TemplateFormDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        activities={activities}
        onDone={() => setReloadKey((key) => key + 1)}
      />
      <TemplateFormDialog
        open={editTemplateTarget !== null}
        onOpenChange={(open) => !open && setEditTemplateTarget(null)}
        activities={activities}
        existing={editTemplateTarget ?? undefined}
        onDone={() => setReloadKey((key) => key + 1)}
      />
      <ConfirmDialog
        open={deleteTemplateTarget !== null}
        onOpenChange={(open) => !open && setDeleteTemplateTarget(null)}
        message="确定要删除这个问卷模板吗？删除后学生将无法填写此问卷。"
        onConfirm={async () => {
          if (!deleteTemplateTarget) return;
          try {
            const result = await deleteQuestionnaireTemplate(deleteTemplateTarget.questionnaire_id);
            if (result.success) {
              toast.success("删除成功");
              setReloadKey((key) => key + 1);
            } else {
              toast.error(result.message || "删除失败");
            }
          } catch (error) {
            toast.error(errorMessage(error, "删除失败"));
          }
        }}
      />
    </div>
  );
}

// ========== 活动问卷模板卡片与报名记录 ==========

function TemplateCard({
  template,
  onEdit,
  onDelete,
  onChanged,
}: {
  template: AdminQuestionnaireTemplate;
  onEdit: () => void;
  onDelete: () => void;
  onChanged: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [responses, setResponses] = useState<AdminResponse[] | null>(null);
  const [detailTarget, setDetailTarget] = useState<AdminResponse | null>(null);
  const [editTarget, setEditTarget] = useState<AdminResponse | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<AdminResponse | null>(null);

  const loadResponses = useCallback(() => {
    getQuestionnaireResponses(template.questionnaire_id)
      .then((data) => {
        if (data.success) setResponses(data.responses);
        else toast.error(data.message || "加载填写记录失败");
      })
      .catch((error) => toast.error(errorMessage(error, "加载填写记录失败")));
  }, [template.questionnaire_id]);

  const toggle = () => {
    const next = !expanded;
    setExpanded(next);
    if (next && responses === null) loadResponses();
  };

  const maxText = template.max_participants > 0 ? template.max_participants : "不限";
  const waitlistCount =
    template.max_participants > 0 ? Math.max(0, template.response_count - template.max_participants) : 0;
  const isFull = template.max_participants > 0 && template.response_count >= template.max_participants;

  return (
    <Card className="mb-4">
      <div className="flex items-start justify-between mb-3">
        <div>
          <button
            className="flex items-center gap-1 text-lg font-semibold text-[#1976d2] cursor-pointer mb-1.5"
            onClick={toggle}
          >
            {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
            {template.title}
          </button>
          <div className="text-sm text-[#666]">
            <strong>活动：</strong>
            {template.activity_name || "未知活动"} ｜ <strong>时间：</strong>
            {template.start_time} ~ {template.end_time}
          </div>
        </div>
        {template.is_ended ? (
          <Badge variant="ended">已截止</Badge>
        ) : template.status === "active" ? (
          <Badge variant="qualified">进行中</Badge>
        ) : (
          <Badge variant="unqualified">已关闭</Badge>
        )}
      </div>

      <div className="text-sm text-[#666] mb-4">
        <strong>人数限制：</strong>
        {maxText} ｜ <strong>已报名：</strong>
        {template.response_count}
        {isFull ? <span className="text-[#ff9800]">（已满，候补{waitlistCount}人）</span> : null}
      </div>

      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant="secondary" onClick={onEdit}>
          编辑
        </Button>
        <Button size="sm" variant="danger" onClick={onDelete}>
          删除
        </Button>
        <Button
          size="sm"
          variant="success"
          onClick={() =>
            downloadFile(
              `/api/admin/questionnaire/responses/${template.questionnaire_id}/export`,
              `${template.title}_填写记录.csv`,
            )
          }
        >
          <FileDown className="h-4 w-4" />
          导出记录
        </Button>
      </div>

      {expanded ? (
        <div className="mt-4 border-t-2 border-[#e0e0e0] pt-4">
          {responses === null ? (
            <p className="text-center text-[#999] py-5">加载中...</p>
          ) : responses.length === 0 ? (
            <p className="text-center text-[#999] py-5">暂无填写记录</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="text-center w-16">排名</TableHead>
                  <TableHead>学号</TableHead>
                  <TableHead>姓名</TableHead>
                  <TableHead>手机号</TableHead>
                  <TableHead>微信号</TableHead>
                  <TableHead>意向类别</TableHead>
                  <TableHead>提交时间</TableHead>
                  <TableHead className="text-center">状态</TableHead>
                  <TableHead className="text-center">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {responses.map((response) => (
                  <TableRow key={response.response_id}>
                    <TableCell className="text-center">
                      {response.rank > 0 ? response.rank : "-"}
                    </TableCell>
                    <TableCell>{response.student_id}</TableCell>
                    <TableCell>{response.student_name}</TableCell>
                    <TableCell>{response.phone || "-"}</TableCell>
                    <TableCell>{response.wechat || "-"}</TableCell>
                    <TableCell>{response.intended_category || "-"}</TableCell>
                    <TableCell>{response.submit_time}</TableCell>
                    <TableCell className="text-center">
                      <RegistrationBadge
                        status={response.status}
                        isEnded={response.is_ended}
                        isSelected={response.is_selected}
                        isWaitlist={response.is_waitlist}
                      />
                    </TableCell>
                    <TableCell className="text-center">
                      <div className="flex justify-center gap-1.5">
                        <Button size="sm" variant="secondary" onClick={() => setDetailTarget(response)}>
                          详情
                        </Button>
                        <Button size="sm" variant="secondary" onClick={() => setEditTarget(response)}>
                          编辑
                        </Button>
                        <Button size="sm" variant="danger" onClick={() => setDeleteTarget(response)}>
                          删除
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </div>
      ) : null}

      <ResponseDetailDialog
        response={detailTarget}
        template={template}
        onOpenChange={(open) => !open && setDetailTarget(null)}
      />
      <EditResponseDialog
        response={editTarget}
        template={template}
        onOpenChange={(open) => !open && setEditTarget(null)}
        onDone={() => {
          loadResponses();
          onChanged();
        }}
      />
      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
        message="确定要删除这条报名记录吗？"
        onConfirm={async () => {
          if (!deleteTarget) return;
          try {
            const result = await deleteResponse(deleteTarget.response_id);
            if (result.success) {
              toast.success("删除成功");
              loadResponses();
              onChanged();
            } else {
              toast.error(result.message || "删除失败");
            }
          } catch (error) {
            toast.error(errorMessage(error, "删除失败"));
          }
        }}
      />
    </Card>
  );
}

function ResponseDetailDialog({
  response,
  template,
  onOpenChange,
}: {
  response: AdminResponse | null;
  template: AdminQuestionnaireTemplate;
  onOpenChange: (open: boolean) => void;
}) {
  const questions = template.custom_questions ?? [];

  return (
    <Dialog open={response !== null} onOpenChange={onOpenChange}>
      <DialogContent title="报名详情" className="max-w-2xl">
        {response ? (
          <>
            <div className="grid grid-cols-2 gap-4 text-sm mb-5">
              <div>
                <strong>学号：</strong>
                {response.student_id}
              </div>
              <div>
                <strong>姓名：</strong>
                {response.student_name}
              </div>
              <div>
                <strong>手机号：</strong>
                {response.phone || "-"}
              </div>
              <div>
                <strong>微信号：</strong>
                {response.wechat || "-"}
              </div>
              <div>
                <strong>意向类别：</strong>
                {response.intended_category || "-"}
              </div>
              <div>
                <strong>提交时间：</strong>
                {response.submit_time}
              </div>
              <div>
                <strong>排名：</strong>
                {response.rank > 0 ? response.rank : "-"}
              </div>
              <div>
                <strong>状态：</strong>
                {response.status === "active" ? "已报名" : "已取消"}
              </div>
            </div>

            {questions.length > 0 ? (
              <div className="border-t-2 border-[#e0e0e0] pt-5">
                <h3 className="font-semibold mb-3">自定义题目答案</h3>
                {questions
                  .filter((question) => question.question_type !== "description")
                  .map((question, index) => {
                    const answer = response.custom_answers?.[question.question_id]?.answer;
                    return (
                      <div key={question.question_id || index} className="mb-4 rounded-lg bg-[#f5f5f5] p-4">
                        <div className="font-medium text-[#1976d2] mb-2">
                          {index + 1}. {question.question_text}
                        </div>
                        <div className="rounded bg-white p-2.5 text-sm whitespace-pre-wrap">
                          {answer === undefined || answer === "" || (Array.isArray(answer) && answer.length === 0) ? (
                            <span className="text-[#999]">未填写</span>
                          ) : Array.isArray(answer) ? (
                            answer.join("、")
                          ) : (
                            answer
                          )}
                        </div>
                      </div>
                    );
                  })}
              </div>
            ) : null}

            <Button variant="secondary" className="w-full mt-2" onClick={() => onOpenChange(false)}>
              关闭
            </Button>
          </>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

function EditResponseDialog({
  response,
  template,
  onOpenChange,
  onDone,
}: {
  response: AdminResponse | null;
  template: AdminQuestionnaireTemplate;
  onOpenChange: (open: boolean) => void;
  onDone: () => void;
}) {
  return (
    <Dialog open={response !== null} onOpenChange={onOpenChange}>
      <DialogContent title="编辑报名记录">
        {response ? (
          <EditResponseForm
            response={response}
            template={template}
            onOpenChange={onOpenChange}
            onDone={onDone}
          />
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

function EditResponseForm({
  response,
  template,
  onOpenChange,
  onDone,
}: {
  response: AdminResponse;
  template: AdminQuestionnaireTemplate;
  onOpenChange: (open: boolean) => void;
  onDone: () => void;
}) {
  const [phone, setPhone] = useState(response.phone || "");
  const [wechat, setWechat] = useState(response.wechat || "");
  const [category, setCategory] = useState(response.intended_category || "");
  const [categoryOptions, setCategoryOptions] = useState<string[]>([]);

  useEffect(() => {
    getActivityCategories(template.activity_id)
      .then((data) => {
        if (data.success) setCategoryOptions(data.categories);
      })
      .catch((error) => toast.error(errorMessage(error, "获取活动类别失败")));
  }, [template.activity_id]);

  const submit = async () => {
    if (!phone.trim()) return toast.error("请输入手机号");
    if (!PHONE_PATTERN.test(phone.trim())) return toast.error("请输入正确的11位手机号码");
    if (!wechat.trim()) return toast.error("请输入微信号");
    if (!category) return toast.error("请选择意向类别");
    try {
      const result = await updateResponse(response.response_id, {
        phone: phone.trim(),
        wechat: wechat.trim(),
        intended_category: category,
      });
      if (result.success) {
        toast.success("修改成功");
        onOpenChange(false);
        onDone();
      } else {
        toast.error(result.message || "修改失败");
      }
    } catch (error) {
      toast.error(errorMessage(error, "修改失败"));
    }
  };

  return (
    <>
      <Field label="学号（只读）">
        <Input value={response.student_id} readOnly />
      </Field>
      <Field label="姓名（只读）">
        <Input value={response.student_name} readOnly />
      </Field>
      <Field label="手机号" required>
        <Input type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="请输入11位手机号" />
      </Field>
      <Field label="微信号" required>
        <Input value={wechat} onChange={(e) => setWechat(e.target.value)} placeholder="请输入微信号" />
      </Field>
      <Field label="意向学分类别" required>
        <Select value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="">请选择意向类别</option>
          {categoryOptions.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="提交时间（只读）">
        <Input value={response.submit_time} readOnly />
      </Field>
      <div className="flex gap-3 mt-2">
        <Button className="flex-1" onClick={submit}>
          保存
        </Button>
        <Button variant="secondary" className="flex-1" onClick={() => onOpenChange(false)}>
          取消
        </Button>
      </div>
    </>
  );
}

// ========== 创建/编辑问卷模板 ==========

function toDatetimeLocal(value: string): string {
  return value.replace(" ", "T").substring(0, 16);
}

function TemplateFormDialog({
  open,
  onOpenChange,
  activities,
  existing,
  onDone,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  activities: AdminActivity[];
  existing?: AdminQuestionnaireTemplate;
  onDone: () => void;
}) {
  const isEdit = existing !== undefined;
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title={isEdit ? "编辑问卷模板" : "创建活动问卷"} className="max-w-2xl">
        <TemplateForm
          key={existing?.questionnaire_id ?? "new"}
          activities={activities}
          existing={existing}
          onOpenChange={onOpenChange}
          onDone={onDone}
        />
      </DialogContent>
    </Dialog>
  );
}

function TemplateForm({
  activities,
  existing,
  onOpenChange,
  onDone,
}: {
  activities: AdminActivity[];
  existing?: AdminQuestionnaireTemplate;
  onOpenChange: (open: boolean) => void;
  onDone: () => void;
}) {
  const isEdit = existing !== undefined;
  const [activityId, setActivityId] = useState(existing?.activity_id ?? "");
  const [title, setTitle] = useState(existing?.title ?? "");
  const [startTime, setStartTime] = useState(existing ? toDatetimeLocal(existing.start_time) : "");
  const [endTime, setEndTime] = useState(existing ? toDatetimeLocal(existing.end_time) : "");
  const [maxParticipants, setMaxParticipants] = useState(String(existing?.max_participants ?? 0));
  const [questions, setQuestions] = useState<CustomQuestion[]>(() =>
    JSON.parse(JSON.stringify(existing?.custom_questions ?? [])),
  );
  const [submitting, setSubmitting] = useState(false);

  const activityName = useMemo(
    () => activities.find((item) => item.activity_id === existing?.activity_id)?.name ?? "未知活动",
    [activities, existing],
  );

  const submit = async () => {
    if (!isEdit && !activityId) return toast.error("请选择活动");
    if (!title.trim()) return toast.error("请输入问卷标题");
    if (!startTime || !endTime) return toast.error("请设置问卷时间");
    const questionError = validateQuestions(questions);
    if (questionError) return toast.error(questionError);

    setSubmitting(true);
    try {
      const payload = {
        title: title.trim(),
        start_time: startTime,
        end_time: endTime,
        max_participants: parseInt(maxParticipants, 10) || 0,
        custom_questions: questions,
      };
      const result =
        isEdit && existing
          ? await updateQuestionnaireTemplate(existing.questionnaire_id, payload)
          : await createQuestionnaireTemplate({ ...payload, activity_id: activityId });
      if (result.success) {
        toast.success(isEdit ? "更新成功" : "创建成功");
        onOpenChange(false);
        onDone();
      } else {
        toast.error(result.message || "保存失败");
      }
    } catch (error) {
      toast.error(errorMessage(error, "保存失败"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      {isEdit ? (
        <Field label="活动（只读）">
          <Input value={activityName} readOnly />
        </Field>
      ) : (
        <Field label="选择活动" required>
          <Select value={activityId} onChange={(e) => setActivityId(e.target.value)}>
            <option value="">请选择活动</option>
            {activities.map((activity) => (
              <option key={activity.activity_id} value={activity.activity_id}>
                {activity.name}
              </option>
            ))}
          </Select>
        </Field>
      )}
      <Field label="问卷标题" required>
        <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="例如：初级团校报名问卷" />
      </Field>
      <Field label="开始时间" required>
        <Input type="datetime-local" value={startTime} onChange={(e) => setStartTime(e.target.value)} />
      </Field>
      <Field label="结束时间" required>
        <Input type="datetime-local" value={endTime} onChange={(e) => setEndTime(e.target.value)} />
      </Field>
      <Field label="最大报名人数（0表示不限制）">
        <Input
          type="number"
          min={0}
          value={maxParticipants}
          onChange={(e) => setMaxParticipants(e.target.value)}
        />
      </Field>
      <div className="rounded-md bg-[#e3f2fd] px-3 py-2.5 mb-4 text-sm">
        <strong>固定题目：</strong>意向学分类别（单选，必填）
      </div>

      <div className="border-t-2 border-[#e0e0e0] pt-4">
        <QuestionBuilder questions={questions} onChange={setQuestions} />
      </div>

      <div className="flex gap-3 mt-5">
        <Button className="flex-1" onClick={submit} disabled={submitting}>
          {submitting ? "提交中..." : isEdit ? "保存" : "创建"}
        </Button>
        <Button variant="secondary" className="flex-1" onClick={() => onOpenChange(false)}>
          取消
        </Button>
      </div>
    </>
  );
}
