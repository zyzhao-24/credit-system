import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { FileDown } from "lucide-react";
import QRCode from "react-qr-code";
import { downloadFile, errorMessage } from "@/api/client";
import {
  cancelCheckin,
  closeCheckin,
  confirmCheckin,
  deleteQuestionnaireTemplate,
  deleteResponse,
  generateCheckinCode,
  getAllQuestionnaires,
  getQuestionnaireResponses,
  openCheckin,
  setResponseAbsent,
  updateResponse,
} from "@/api/service";
import type { AdminQuestionnaireTemplate, AdminResponse } from "@/api/types";
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
import { LetterPreview } from "@/components/LetterPreview";
import { Markdown, MarkdownInline } from "@/components/Markdown";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState, Field } from "@/components/common";
import { CheckinBadge, RegistrationBadge } from "@/components/StatusBadge";
import { composeLetter } from "@/lib/letter";

const PHONE_PATTERN = /^1[3-9]\d{9}$/;

/** 问卷管理页（系统管理员）：紧凑可搜索的模板卡片 ⇄ 选中模板的填写记录视图。 */
export function QuestionnaireAdminPage() {
  const navigate = useNavigate();
  const [templates, setTemplates] = useState<AdminQuestionnaireTemplate[]>([]);
  const [actSearch, setActSearch] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const load = useCallback(() => {
    getAllQuestionnaires()
      .then((data) => {
        if (data.success) {
          setTemplates(data.questionnaires);
        } else {
          toast.error("加载失败");
        }
      })
      .catch((error) => toast.error(errorMessage(error, "加载失败")));
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
  const selected = templates.find((t) => t.questionnaire_id === selectedId) ?? null;

  // 填写记录视图（点击卡片进入，返回按钮切回卡片视图）
  if (selected) {
    return (
      <div className="mx-auto max-w-[1500px] px-4 py-6">
        <PageHeader title="问卷管理" homePath="/admin" backTo="/admin" />
        <TemplateDetailView
          template={selected}
          onBack={() => setSelectedId(null)}
          onChanged={() => setReloadKey((key) => key + 1)}
        />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-6">
      <PageHeader title="问卷管理" homePath="/admin" backTo="/admin" />

      <section>
        <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
          <h2 className="text-xl font-semibold mr-auto">问卷模板</h2>
          <Input
            value={actSearch}
            onChange={(event) => setActSearch(event.target.value)}
            placeholder="搜索问卷标题、活动名称..."
            className="w-64"
          />
          <Button size="sm" onClick={() => navigate("/admin/questionnaires/design")}>
            ➕ 创建问卷
          </Button>
        </div>

        {templates.length === 0 ? (
          <EmptyState icon="📋" text="暂无问卷" />
        ) : filteredTemplates.length === 0 ? (
          <EmptyState icon="🔍" text="没有符合条件的问卷" />
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {filteredTemplates.map((template) => (
              <TemplateCard
                key={template.questionnaire_id}
                template={template}
                onOpen={() => setSelectedId(template.questionnaire_id)}
              />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function templateBadge(template: AdminQuestionnaireTemplate) {
  if (template.is_ended) return <Badge variant="ended">已截止</Badge>;
  if (template.status === "active") return <Badge variant="qualified">进行中</Badge>;
  return <Badge variant="unqualified">已关闭</Badge>;
}

/** 紧凑模板卡片：摘要 + 状态，点击进入填写记录视图。 */
function TemplateCard({
  template,
  onOpen,
}: {
  template: AdminQuestionnaireTemplate;
  onOpen: () => void;
}) {
  const isFull =
    template.max_participants > 0 && template.response_count >= template.max_participants;
  return (
    <Card
      role="button"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onOpen();
        }
      }}
      className="cursor-pointer p-3 transition border border-transparent hover:border-primary/50 hover:shadow-[0_4px_16px_rgba(0,120,212,0.15)]"
    >
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-[15px] font-semibold leading-snug">{template.title}</h3>
        {templateBadge(template)}
      </div>
      <div className="mt-1.5 flex flex-wrap gap-1">
        {template.questionnaire_type === "standalone" ? (
          <span className="rounded bg-[#6b5ce7]/10 px-1.5 py-0.5 text-xs text-[#6b5ce7]">
            独立问卷
          </span>
        ) : (
          <span className="rounded bg-primary/10 px-1.5 py-0.5 text-xs text-primary">
            {template.activity_name}
          </span>
        )}
        {template.record_name ? (
          <span className="rounded bg-[#2e7d32]/10 px-1.5 py-0.5 text-xs text-[#2e7d32]">
            记录：{template.record_name}
          </span>
        ) : null}
      </div>
      <p className="mt-2 text-xs text-[#777]">
        {template.start_time} ~ {template.end_time}
        <br />
        已收集 {template.response_count} 份
        {template.max_participants > 0 ? ` / 限 ${template.max_participants} 人` : ""}
        {isFull ? "（已满）" : ""} · 题目 {template.custom_questions.length} 道 · v
        {template.version}
      </p>
    </Card>
  );
}

/** 填写记录视图：单个问卷的记录管理，所有操作按钮集中在这里。 */
function TemplateDetailView({
  template,
  onBack,
  onChanged,
}: {
  template: AdminQuestionnaireTemplate;
  onBack: () => void;
  onChanged: () => void;
}) {
  const navigate = useNavigate();
  const [responses, setResponses] = useState<AdminResponse[] | null>(null);
  const [responseSearch, setResponseSearch] = useState("");
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const [detailTarget, setDetailTarget] = useState<AdminResponse | null>(null);
  const [editTarget, setEditTarget] = useState<AdminResponse | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<AdminResponse | null>(null);
  const [checkinBusy, setCheckinBusy] = useState(false);
  // 逐人签到二维码弹窗的目标（签到码仅管理端可见，现场出示给本人扫）
  const [qrTarget, setQrTarget] = useState<AdminResponse | null>(null);

  const loadResponses = useCallback(() => {
    getQuestionnaireResponses(template.questionnaire_id)
      .then((data) => {
        if (data.success) setResponses(data.responses);
        else toast.error(data.message || "加载填写记录失败");
      })
      .catch((error) => toast.error(errorMessage(error, "加载填写记录失败")));
  }, [template.questionnaire_id]);

  useEffect(loadResponses, [loadResponses]);

  const toggleCheckin = async () => {
    setCheckinBusy(true);
    try {
      const result = template.checkin_open
        ? await closeCheckin(template.questionnaire_id)
        : await openCheckin(template.questionnaire_id);
      if (result.success) {
        toast.success(result.message || "操作成功");
        onChanged();
      } else {
        toast.error(result.message || "操作失败");
      }
    } catch (error) {
      toast.error(errorMessage(error, "操作失败"));
    } finally {
      setCheckinBusy(false);
    }
  };

  const markAbsent = async (response: AdminResponse, absent: boolean) => {
    try {
      const result = await setResponseAbsent(response.response_id, absent);
      if (result.success) {
        toast.success(result.message || "操作成功");
        loadResponses();
      } else {
        toast.error(result.message || "操作失败");
      }
    } catch (error) {
      toast.error(errorMessage(error, "操作失败"));
    }
  };

  const confirmResponseCheckin = async (response: AdminResponse) => {
    try {
      const result = await confirmCheckin(response.response_id);
      if (result.success) {
        toast.success(result.message || "已确认");
        loadResponses();
      } else {
        toast.error(result.message || "确认失败");
      }
    } catch (error) {
      toast.error(errorMessage(error, "确认失败"));
    }
  };

  const cancelResponseCheckin = async (response: AdminResponse) => {
    try {
      const result = await cancelCheckin(response.response_id);
      if (result.success) {
        toast.success(result.message || "已取消签到");
        loadResponses();
      } else {
        toast.error(result.message || "操作失败");
      }
    } catch (error) {
      toast.error(errorMessage(error, "操作失败"));
    }
  };

  const generateCodeFor = async (response: AdminResponse) => {
    try {
      const result = await generateCheckinCode(response.response_id);
      if (result.success) {
        toast.success(`${response.student_name} 的签到码：${result.checkin_code}`);
        loadResponses();
      } else {
        toast.error(result.message || "生成失败");
      }
    } catch (error) {
      toast.error(errorMessage(error, "生成失败"));
    }
  };

  const keyword = responseSearch.trim().toLowerCase();
  const filteredResponses =
    responses && keyword
      ? responses.filter((response) =>
          [response.student_id, response.student_name, response.phone, response.wechat]
            .join(" ")
            .toLowerCase()
            .includes(keyword),
        )
      : responses;

  const maxText = template.max_participants > 0 ? template.max_participants : "不限";
  const waitlistCount =
    template.max_participants > 0
      ? Math.max(0, template.response_count - template.max_participants)
      : 0;
  const isFull =
    template.max_participants > 0 && template.response_count >= template.max_participants;

  return (
    <section>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Button size="sm" variant="secondary" onClick={onBack}>
          ← 返回问卷列表
        </Button>
        <h2 className="text-xl font-semibold">{template.title}</h2>
        {templateBadge(template)}
        <div className="ml-auto flex flex-wrap gap-2">
          <Button
            size="sm"
            variant="secondary"
            onClick={() => navigate(`/admin/questionnaires/design/${template.questionnaire_id}`)}
          >
            编辑模板
          </Button>
          <Button
            size="sm"
            variant="success"
            onClick={() =>
              downloadFile(
                `/api/admin/questionnaire/responses/${template.questionnaire_id}/export`,
                `${template.title}_填写记录.xlsx`,
              )
            }
          >
            <FileDown className="h-4 w-4" />
            导出记录
          </Button>
          <Button size="sm" variant="danger" onClick={() => setDeleteConfirm(true)}>
            删除问卷
          </Button>
        </div>
      </div>

      <Card className="mb-3 flex flex-wrap gap-x-5 gap-y-1 p-3 text-sm text-[#555]">
        <span>
          <strong>{template.questionnaire_type === "standalone" ? "类型" : "活动"}：</strong>
          {template.questionnaire_type === "standalone"
            ? "独立问卷"
            : template.activity_name || "未知活动"}
        </span>
        {template.record_name ? (
          <span>
            <strong>绑定记录：</strong>
            {template.record_name}
            {template.record_categories.length > 0
              ? `（${template.record_categories.join("、")}）`
              : ""}
          </span>
        ) : null}
        <span>
          <strong>时间：</strong>
          {template.start_time} ~ {template.end_time}
        </span>
        <span>
          <strong>人数限制：</strong>
          {maxText}
        </span>
        <span>
          <strong>已报名：</strong>
          {template.response_count}
          {isFull ? <span className="text-[#ff9800]">（已满，候补{waitlistCount}人）</span> : null}
        </span>
        <span>
          <strong>当前版本：</strong>v{template.version}
        </span>
      </Card>

      {/* 现场签到：每位报名者独立的一次性签到码，在下方"签到码"列展示 */}
      <Card className="mb-3 p-3">
        <div className="flex flex-wrap items-center gap-3">
          <strong className="text-sm">现场签到</strong>
          {template.checkin_open ? (
            <>
              <Badge variant="qualified">签到中</Badge>
              <Button size="sm" variant="danger" disabled={checkinBusy} onClick={toggleCheckin}>
                关闭签到
              </Button>
            </>
          ) : (
            <>
              <span className="text-sm text-[#777]">未开启</span>
              <Button size="sm" disabled={checkinBusy} onClick={toggleCheckin}>
                开启签到
              </Button>
            </>
          )}
          <span className="text-xs text-[#999]">
            开启后为名额内报名者自动生成独立的 6 位一次性签到码（见"签到码"列）；候补默认不生成，
            需要时在"签到码"列逐人点「生成」。签到与正常报名一致，即时生效
          </span>
        </div>
      </Card>

      <div className="mb-2 flex items-center justify-between gap-2">
        <h4 className="font-medium">填写记录</h4>
        <Input
          value={responseSearch}
          onChange={(e) => setResponseSearch(e.target.value)}
          placeholder="搜索学号 / 姓名 / 联系方式"
          className="w-56"
        />
      </div>

      {responses === null ? (
        <p className="text-center text-[#999] py-5">加载中...</p>
      ) : (
        // 列较多时保持自然宽度，超出部分横向滚动（Table 自带 overflow-x-auto）
        <Table className="min-w-[1200px] [&_td]:whitespace-nowrap [&_th]:whitespace-nowrap">
          <TableHeader>
            <TableRow>
              <TableHead className="text-center w-16">排名</TableHead>
              <TableHead>学号</TableHead>
              <TableHead>姓名</TableHead>
              <TableHead>手机号</TableHead>
              <TableHead>微信号</TableHead>
              {template.questionnaire_type !== "standalone" ? (
                <TableHead>意向类别</TableHead>
              ) : null}
              <TableHead>提交时间</TableHead>
              <TableHead className="text-center w-16">版本</TableHead>
              <TableHead className="text-center">状态</TableHead>
              <TableHead className="text-center">签到</TableHead>
              {template.checkin_open ? (
                <TableHead className="text-center">签到码</TableHead>
              ) : null}
              <TableHead className="text-center">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredResponses && filteredResponses.length > 0 ? (
              filteredResponses.map((response) => (
                <TableRow key={response.response_id}>
                  <TableCell className="text-center">
                    {response.rank > 0 ? response.rank : "-"}
                  </TableCell>
                  <TableCell>{response.student_id}</TableCell>
                  <TableCell>{response.student_name}</TableCell>
                  <TableCell>{response.phone || "-"}</TableCell>
                  <TableCell>{response.wechat || "-"}</TableCell>
                  {template.questionnaire_type !== "standalone" ? (
                    <TableCell>{response.intended_category || "-"}</TableCell>
                  ) : null}
                  <TableCell>{response.submit_time}</TableCell>
                  <TableCell className="text-center">
                    {response.template_version ? (
                      <span title="提交时的问卷版本">v{response.template_version}</span>
                    ) : (
                      "-"
                    )}
                  </TableCell>
                  <TableCell className="text-center">
                    <RegistrationBadge
                      status={response.status}
                      isEnded={response.is_ended}
                      isSelected={response.is_selected}
                      isWaitlist={response.is_waitlist}
                    />
                  </TableCell>
                  <TableCell className="text-center">
                    <CheckinBadge
                      state={response.checkin_state}
                      checkedInAt={response.checked_in_at}
                    />
                  </TableCell>
                  {template.checkin_open ? (
                    <TableCell className="text-center">
                      {response.checkin_code ? (
                        <span className="inline-flex items-center gap-1">
                          <span className="font-mono font-bold tracking-[0.2em]">
                            {response.checkin_code}
                          </span>
                          <button
                            type="button"
                            className="text-[#999] hover:text-primary"
                            title="出示该学生的签到二维码"
                            onClick={() => setQrTarget(response)}
                          >
                            ▣
                          </button>
                        </span>
                      ) : response.status === "active" && !response.checked_in_at ? (
                        <Button
                          size="sm"
                          variant="secondary"
                          title="为该学生手动生成一次性签到码（候补默认不分配）"
                          onClick={() => generateCodeFor(response)}
                        >
                          生成
                        </Button>
                      ) : (
                        <span className="text-muted-foreground text-xs">-</span>
                      )}
                    </TableCell>
                  ) : null}
                  <TableCell className="text-center">
                    <div className="flex justify-center gap-1.5">
                      <Button size="sm" variant="secondary" onClick={() => setDetailTarget(response)}>
                        详情
                      </Button>
                      <Button size="sm" variant="secondary" onClick={() => setEditTarget(response)}>
                        编辑
                      </Button>
                      {response.status === "active" && response.checkin_state === "pending" ? (
                        <Button
                          size="sm"
                          variant="success"
                          title="确认该候补学生的签到"
                          onClick={() => confirmResponseCheckin(response)}
                        >
                          确认签到
                        </Button>
                      ) : null}
                      {response.status === "active" && response.checkin_state === "none" ? (
                        <Button
                          size="sm"
                          variant="success"
                          title="管理员现场确认，直接标记该学生已签到（无需签到码）"
                          onClick={() => confirmResponseCheckin(response)}
                        >
                          标记签到
                        </Button>
                      ) : null}
                      {response.status === "active" && response.checked_in_at ? (
                        <Button
                          size="sm"
                          variant="secondary"
                          title="取消后该学生恢复为未签到，可重新签到；之后才能标记缺席"
                          onClick={() => cancelResponseCheckin(response)}
                        >
                          取消签到
                        </Button>
                      ) : null}
                      {response.status === "active" && !response.absent && !response.checked_in_at ? (
                        <Button
                          size="sm"
                          variant="secondary"
                          title="标记缺席后不再占用名额，候补按顺序自动转正"
                          onClick={() => markAbsent(response, true)}
                        >
                          缺席
                        </Button>
                      ) : null}
                      {response.status === "active" && response.absent ? (
                        <Button
                          size="sm"
                          variant="secondary"
                          title="取消缺席标记，恢复占名额"
                          onClick={() => markAbsent(response, false)}
                        >
                          恢复
                        </Button>
                      ) : null}
                      <Button size="sm" variant="danger" onClick={() => setDeleteTarget(response)}>
                        删除
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell
                  colSpan={template.questionnaire_type !== "standalone" ? 10 : 9}
                  className="text-center text-[#666]"
                >
                  {responses.length > 0 ? "没有匹配的记录" : "暂无填写记录"}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      )}

      <ConfirmDialog
        open={deleteConfirm}
        onOpenChange={setDeleteConfirm}
        message="确定要删除这个问卷模板吗？删除后学生将无法填写此问卷。"
        onConfirm={async () => {
          try {
            const result = await deleteQuestionnaireTemplate(template.questionnaire_id);
            if (result.success) {
              toast.success("删除成功");
              onChanged();
              onBack();
            } else {
              toast.error(result.message || "删除失败");
            }
          } catch (error) {
            toast.error(errorMessage(error, "删除失败"));
          }
        }}
      />
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
      {/* 逐人签到二维码：现场出示给该学生扫，链接自动带入其一次性签到码 */}
      <Dialog open={qrTarget !== null} onOpenChange={(open) => !open && setQrTarget(null)}>
        {qrTarget ? (
          <DialogContent
            title={`签到二维码 - ${qrTarget.student_name}（${qrTarget.student_id}）`}
            className="max-w-xs"
          >
            <div className="flex flex-col items-center gap-3 py-2">
              <div className="rounded-md border border-[#e0e0e0] bg-white p-3">
                <QRCode
                  value={`${window.location.origin}/student/activities?checkin=${qrTarget.questionnaire_id}&code=${qrTarget.checkin_code}`}
                  size={200}
                />
              </div>
              <span className="font-mono text-2xl font-bold tracking-[0.3em] text-primary">
                {qrTarget.checkin_code}
              </span>
              <p className="text-center text-xs text-[#999]">
                请仅出示给本人扫码；该码签到成功后立即作废
              </p>
            </div>
          </DialogContent>
        ) : null}
      </Dialog>
    </section>
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
  // 历史提交按提交时的问卷快照展示，模板后续修改不影响旧答案对应的题目
  const questions =
    response?.template_snapshot?.custom_questions ?? template.custom_questions ?? [];
  const snapshotTitle = response?.template_snapshot?.title;

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
                <RegistrationBadge
                  status={response.status}
                  isEnded={response.is_ended}
                  isSelected={response.is_selected}
                  isWaitlist={response.is_waitlist}
                />
              </div>
              <div>
                <strong>问卷版本：</strong>
                {response.template_version ? `v${response.template_version}` : "-"}
                {response.template_version && response.template_version !== template.version
                  ? `（当前模板 v${template.version}）`
                  : ""}
              </div>
            </div>

            {questions.length > 0 ? (
              <div className="border-t-2 border-[#e0e0e0] pt-5">
                <h3 className="font-semibold mb-3">自定义题目答案</h3>
                {snapshotTitle && snapshotTitle !== template.title ? (
                  <p className="mb-3 text-xs text-[#999]">
                    提交时问卷标题为「{snapshotTitle}」（按提交时的问卷版本展示）
                  </p>
                ) : null}
                {questions
                  .filter((question) => question.question_type !== "description")
                  .map((question, index) => {
                    const answer = response.custom_answers?.[question.question_id]?.answer;
                    return (
                      <div key={question.question_id || index} className="mb-4 rounded-lg bg-[#f5f5f5] p-4">
                        <div className="font-medium text-[#1976d2] mb-2">
                          {index + 1}. {question.question_text}
                        </div>
                        <div className="rounded bg-white p-2.5 text-sm">
                          {answer === undefined || answer === "" || (Array.isArray(answer) && answer.length === 0) ? (
                            <span className="text-[#999]">未填写</span>
                          ) : Array.isArray(answer) ? (
                            <MarkdownInline text={answer.join("、")} />
                          ) : (
                            <Markdown text={answer} />
                          )}
                        </div>
                      </div>
                    );
                  })}
              </div>
            ) : null}

            <div className="border-t-2 border-[#e0e0e0] pt-4 mb-4">
              <LetterPreview
                paragraphs={composeLetter(
                  {
                    student_name: response.student_name,
                    student_id: response.student_id,
                    phone: response.phone,
                    wechat: response.wechat,
                    activity_name:
                      template.questionnaire_type === "standalone" ? "" : template.activity_name,
                    record_name:
                      response.template_snapshot?.record_name ?? template.record_name ?? "",
                    category: response.intended_category,
                  },
                  questions,
                  response.custom_answers ?? {},
                  response.template_snapshot?.body ?? template.body,
                )}
              />
            </div>

            <div className="flex gap-3 mt-2">
              <Button variant="secondary" className="flex-1" onClick={() => onOpenChange(false)}>
                关闭
              </Button>
            </div>
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
  // 意向类别选项来自绑定记录的可行类别（多类别时允许"无"）
  const categoryOptions =
    template.record_categories.length >= 2
      ? ["无", ...template.record_categories]
      : template.record_categories;

  const submit = async () => {
    if (!phone.trim()) return toast.error("请输入手机号");
    if (!PHONE_PATTERN.test(phone.trim())) return toast.error("请输入正确的11位手机号码");
    if (!wechat.trim()) return toast.error("请输入微信号");
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
      {template.record_categories.length > 0 ? (
        <Field label="意向学分类别">
          <Select value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="">请选择意向类别</option>
            {categoryOptions.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </Select>
        </Field>
      ) : null}
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
