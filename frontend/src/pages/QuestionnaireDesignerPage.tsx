import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { toast } from "sonner";
import { Plus, Trash2, X } from "lucide-react";
import { errorMessage } from "@/api/client";
import { useAuth } from "@/auth/auth-context";
import {
  createQuestionnaireTemplate,
  getActivityRecords,
  getAdminActivities,
  getAllQuestionnaires,
  updateQuestionnaireTemplate,
} from "@/api/service";
import type {
  AdminActivity,
  AdminQuestionnaireTemplate,
  AdminRecord,
  BodyField,
  CustomQuestion,
  QuestionnaireBody,
} from "@/api/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input, Select } from "@/components/ui/input";
import { BodyEditor, DND_NEW_FIELD, DND_NEW_TYPE } from "@/components/BodyEditor";
import type { BodyEditorHandle } from "@/components/BodyEditor";
import { PageHeader } from "@/components/PageHeader";
import { Field } from "@/components/common";
import {
  bodyOf,
  BUILDER_TYPES,
  FIELD_NAMES,
  isMultiline,
  newQuestion,
  QUESTION_TYPE_NAMES as TYPE_NAMES,
  TEXT_FORMAT_NAMES,
  validateQuestions,
} from "@/lib/questions";

function toDatetimeLocal(value: string): string {
  return value.replace(" ", "T").substring(0, 16);
}

/** 题型模块的图标，让左侧面板更直观 */
const TYPE_ICONS: Record<string, string> = {
  single_choice: "🔘",
  multiple_choice: "☑️",
  text: "✏️",
  number: "🔢",
  date: "📅",
  rating: "⭐",
};

/** 信息槽位的图标 */
const FIELD_ICONS: Record<BodyField, string> = {
  student_name: "👤",
  student_id: "🎓",
  phone: "📱",
  wechat: "💬",
  activity_name: "🎯",
  record_name: "📋",
  category: "🏷️",
};

const FIELD_ORDER: BodyField[] = [
  "student_name",
  "student_id",
  "phone",
  "wechat",
  "activity_name",
  "record_name",
  "category",
];

/**
 * 问卷设计器（独立页面）：正文是一篇可直接打字编辑的文档（支持 Markdown 与公式），
 * 信息槽位/题目作为芯片嵌入文字流中（左侧面板拖入或点击插入到光标处），
 * 点击题目芯片在右侧面板编辑属性，学生填写后即为连贯的文档。
 */
export function QuestionnaireDesignerPage() {
  const { questionnaireId } = useParams<{ questionnaireId: string }>();
  const navigate = useNavigate();
  const isEdit = Boolean(questionnaireId);
  const { user } = useAuth();
  // 独立问卷仅系统管理员可建；普通管理员只能绑定自己可编辑的活动
  const isSystemAdmin = user?.role === "system_admin";

  const [loading, setLoading] = useState(isEdit);
  const [notFound, setNotFound] = useState(false);
  const [activities, setActivities] = useState<AdminActivity[]>([]);
  const [existing, setExisting] = useState<AdminQuestionnaireTemplate | null>(null);

  // 元数据（activityId 为空即独立问卷，不再有单独的"问卷类型"）
  const [activityId, setActivityId] = useState("");
  const [records, setRecords] = useState<AdminRecord[]>([]);
  const [recordId, setRecordId] = useState("");
  const [title, setTitle] = useState("");
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");
  const [maxParticipants, setMaxParticipants] = useState("0");
  // 文档：题目定义 + 正文（可直接打字的 Markdown 文档，槽位以芯片嵌入）
  const [questions, setQuestions] = useState<CustomQuestion[]>([]);
  const [body, setBody] = useState<QuestionnaireBody>([]);
  const [selectedQid, setSelectedQid] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const editorRef = useRef<BodyEditorHandle>(null);

  const loadRecords = useCallback((targetActivityId: string) => {
    if (!targetActivityId) {
      setRecords([]);
      return;
    }
    getActivityRecords(targetActivityId)
      .then((data) => {
        if (data.success) setRecords(data.records);
      })
      .catch(() => undefined);
  }, []);

  const load = useCallback(() => {
    getAdminActivities()
      .then((data) => {
        if (data.success) setActivities(data.activities);
      })
      .catch(() => undefined);
    if (!questionnaireId) return;
    getAllQuestionnaires()
      .then((data) => {
        if (!data.success) {
          toast.error("加载问卷失败");
          return;
        }
        const template = data.questionnaires.find(
          (item) => item.questionnaire_id === questionnaireId,
        );
        if (!template) {
          setNotFound(true);
          return;
        }
        setExisting(template);
        setActivityId(template.activity_id);
        setRecordId(template.record_id ?? "");
        if (template.activity_id) loadRecords(template.activity_id);
        setTitle(template.title);
        setStartTime(toDatetimeLocal(template.start_time));
        setEndTime(toDatetimeLocal(template.end_time));
        setMaxParticipants(String(template.max_participants));
        const loadedQuestions: CustomQuestion[] = JSON.parse(
          JSON.stringify(template.custom_questions ?? []),
        );
        setQuestions(loadedQuestions.filter((q) => q.question_type !== "description"));
        setBody(bodyOf(template));
      })
      .catch((error) => toast.error(errorMessage(error, "加载问卷失败")))
      .finally(() => setLoading(false));
  }, [questionnaireId, loadRecords]);

  useEffect(load, [load]);

  const questionMap = useMemo(
    () => new Map(questions.map((question) => [question.question_id, question])),
    [questions],
  );

  // ========== 文档操作 ==========

  /** 新建一道题并把槽位插入编辑器（pos 缺省为光标处） */
  const addQuestionOfType = (type: CustomQuestion["question_type"], pos?: number) => {
    const question = { ...newQuestion(type, questions.length + 1), question_id: crypto.randomUUID() };
    setQuestions((prev) => [...prev, question]);
    editorRef.current?.insertQuestion(question.question_id, pos);
    setSelectedQid(question.question_id);
  };

  /** 新建问卷时的默认正文：整篇都可改，这只是一个起点 */
  const applyDefaultTemplate = (withRegistration: boolean) => {
    setBody((prev) => {
      if (prev.length > 0) return prev;
      return [
        withRegistration
          ? [
              { type: "field", field: "student_name" },
              { type: "text", text: "（学号：" },
              { type: "field", field: "student_id" },
              { type: "text", text: "）现向你报名" },
              { type: "field", field: "activity_name" },
              { type: "text", text: "的" },
              { type: "field", field: "record_name" },
              { type: "text", text: "，并且希望优先将活动学分归入" },
              { type: "field", field: "category" },
              { type: "text", text: "类别。" },
            ]
          : [
              { type: "field", field: "student_name" },
              { type: "text", text: "（学号：" },
              { type: "field", field: "student_id" },
              { type: "text", text: "）现提交本问卷。" },
            ],
      ];
    });
  };

  const removeQuestion = (questionId: string) => {
    setQuestions((prev) => prev.filter((question) => question.question_id !== questionId));
    setBody((prev) =>
      prev
        .map((paragraph) =>
          paragraph.filter(
            (part) => !(part.type === "question" && part.question_id === questionId),
          ),
        )
        .filter((paragraph) => paragraph.length > 0),
    );
    setSelectedQid((prev) => (prev === questionId ? null : prev));
  };

  const updateQuestion = (questionId: string, patch: Partial<CustomQuestion>) => {
    setQuestions((prev) =>
      prev.map((question) =>
        question.question_id === questionId ? { ...question, ...patch } : question,
      ),
    );
  };

  // ========== 保存 ==========

  const activityName = useMemo(
    () => activities.find((item) => item.activity_id === activityId)?.name ?? "",
    [activities, activityId],
  );
  const selectedRecord = useMemo(
    () => records.find((item) => item.record_id === recordId) ?? null,
    [records, recordId],
  );
  // 编辑已有模板时记录列表异步加载，绑定的记录可能还没进来
  const boundRecordName = selectedRecord?.record_name ?? existing?.record_name ?? "";
  const boundCategories = selectedRecord?.categories ?? existing?.record_categories ?? [];

  const save = async () => {
    if (!isEdit && activityId && !recordId) return toast.error("请选择绑定的记录");
    if (!title.trim()) return toast.error("请输入问卷标题");
    if (!startTime || !endTime) return toast.error("请设置问卷时间");
    const questionError = validateQuestions(questions);
    if (questionError) return toast.error(questionError);
    // 每道题必须放入正文恰好一次（后端同样强制）
    const placed = new Set(
      body.flatMap((paragraph) =>
        paragraph.filter((part) => part.type === "question").map((part) => part.question_id),
      ),
    );
    const missing = questions.find((question) => !placed.has(question.question_id));
    if (missing) return toast.error(`题目「${missing.question_text || "未命名"}」未放入正文`);

    setSubmitting(true);
    try {
      const payload = {
        title: title.trim(),
        start_time: startTime,
        end_time: endTime,
        max_participants: parseInt(maxParticipants, 10) || 0,
        record_id: activityId ? recordId : "",
        custom_questions: questions,
        body,
      };
      const result =
        isEdit && existing
          ? await updateQuestionnaireTemplate(existing.questionnaire_id, payload)
          : await createQuestionnaireTemplate({ ...payload, activity_id: activityId });
      if (result.success) {
        toast.success(
          isEdit
            ? `保存成功${"version" in result && result.version ? `，当前版本 v${result.version}` : ""}`
            : "创建成功",
        );
        navigate("/admin/questionnaires");
      } else {
        toast.error(result.message || "保存失败");
      }
    } catch (error) {
      toast.error(errorMessage(error, "保存失败"));
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-6">
        <PageHeader title="问卷设计器" homePath="/admin" backTo="/admin/questionnaires" />
        <p className="text-center text-[#999] py-10">加载中...</p>
      </div>
    );
  }
  if (notFound) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-6">
        <PageHeader title="问卷设计器" homePath="/admin" backTo="/admin/questionnaires" />
        <p className="text-center text-[#999] py-10">问卷不存在或已删除</p>
      </div>
    );
  }

  const selectedQuestion = selectedQid ? (questionMap.get(selectedQid) ?? null) : null;

  return (
    <div className="mx-auto max-w-7xl px-4 py-6">
      <PageHeader title="问卷设计器" homePath="/admin" backTo="/admin/questionnaires" />

      {/* 元数据栏 */}
      <Card className="mb-4 p-4">
        <div className="grid gap-x-4 gap-y-1 sm:grid-cols-2 lg:grid-cols-4">
          {isEdit ? (
            <Field label="活动">
              <Input value={activityName || "无（独立问卷）"} readOnly />
            </Field>
          ) : (
            <Field label={isSystemAdmin ? "活动（选「无」即独立问卷）" : "活动"} required>
              <Select
                value={activityId}
                onChange={(e) => {
                  setActivityId(e.target.value);
                  setRecordId("");
                  loadRecords(e.target.value);
                  if (!e.target.value) applyDefaultTemplate(false);
                }}
              >
                {isSystemAdmin ? <option value="">无（独立问卷）</option> : null}
                {!isSystemAdmin && !activityId ? <option value="">请选择活动</option> : null}
                {activities
                  .filter((activity) => isSystemAdmin || activity.can_edit)
                  .map((activity) => (
                    <option key={activity.activity_id} value={activity.activity_id}>
                      {activity.name}
                    </option>
                  ))}
              </Select>
            </Field>
          )}
          {activityId ? (
            <Field label="绑定记录" required>
              <Select
                value={recordId}
                onChange={(e) => {
                  setRecordId(e.target.value);
                  if (e.target.value) applyDefaultTemplate(true);
                }}
              >
                {!isEdit ? <option value="">请选择记录</option> : null}
                {!selectedRecord && recordId ? (
                  <option value={recordId}>{boundRecordName}（当前绑定）</option>
                ) : null}
                {records.map((record) => (
                  <option key={record.record_id} value={record.record_id}>
                    {record.record_name}
                    {record.categories.length > 0 ? `（${record.categories.join("、")}）` : ""}
                  </option>
                ))}
              </Select>
            </Field>
          ) : null}
          <Field label="问卷标题" required>
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="例如：初级团校报名问卷"
            />
          </Field>
          <Field label="开始时间" required>
            <Input
              type="datetime-local"
              value={startTime}
              onChange={(e) => setStartTime(e.target.value)}
            />
          </Field>
          <Field label="结束时间" required>
            <Input
              type="datetime-local"
              value={endTime}
              onChange={(e) => setEndTime(e.target.value)}
            />
          </Field>
          <Field label="最大报名人数（0 不限）">
            <Input
              type="number"
              min={0}
              value={maxParticipants}
              onChange={(e) => setMaxParticipants(e.target.value)}
            />
          </Field>
        </div>

        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 mt-1">
          {activityId && recordId ? (
            <p className="text-xs text-[#777]">
              {boundCategories.length >= 2
                ? `记录有多个类别（${boundCategories.join("、")}），将自动生成意向类别单选题；学生缺省作答时记为"无"`
                : boundCategories.length === 1
                  ? `记录只有一个类别，意向类别自动归入「${boundCategories[0]}」，无需提问`
                  : "该记录没有可行类别，不生成意向类别题"}
            </p>
          ) : null}
          {isEdit && existing ? (
            <Badge variant="info">当前版本 v{existing.version}</Badge>
          ) : null}
          <div className="ml-auto flex gap-2">
            <Button variant="secondary" onClick={() => navigate("/admin/questionnaires")}>
              取消
            </Button>
            <Button onClick={save} disabled={submitting}>
              {submitting ? "保存中..." : isEdit ? "保存修改" : "创建问卷"}
            </Button>
          </div>
        </div>
        {isEdit && existing ? (
          <p className="mt-2 text-xs text-[#999]">
            修改标题、正文、题目或绑定记录后保存，版本号将 +1；学生已提交的记录仍绑定提交时的问卷版本（v
            {existing.version} 之前的提交不受影响）。
          </p>
        ) : null}
      </Card>

      <div className="flex gap-4 items-start">
        {/* 题型模块面板 */}
        <Card className="w-44 shrink-0 p-3 sticky top-4">
          <h3 className="mb-2 text-sm font-semibold text-[#333]">信息字段</h3>
          <p className="mb-2 text-xs text-[#999]">自动填入的值，点击插入光标处，或拖入文中</p>
          <div className="flex flex-col gap-1.5 mb-3">
            {FIELD_ORDER.map((field) => (
              <button
                key={field}
                type="button"
                draggable
                onDragStart={(event) => {
                  event.dataTransfer.setData(DND_NEW_FIELD, field);
                  event.dataTransfer.effectAllowed = "copy";
                }}
                onClick={() => editorRef.current?.insertField(field)}
                className="flex cursor-grab items-center gap-2 rounded-md border-2 border-dashed border-[#a8d5b0] bg-[#f6fbf7] px-2.5 py-1.5 text-left text-sm transition-colors hover:border-[#4c9a5e] hover:bg-[#edf7ef] active:cursor-grabbing"
              >
                <span>{FIELD_ICONS[field]}</span>
                <span>{FIELD_NAMES[field]}</span>
                <Plus className="ml-auto h-3.5 w-3.5 text-[#aaa]" />
              </button>
            ))}
          </div>
          <h3 className="mb-2 text-sm font-semibold text-[#333]">题目字段</h3>
          <p className="mb-2 text-xs text-[#999]">点击插入光标处，或拖入文中任意位置</p>
          <div className="flex flex-col gap-1.5">
            {BUILDER_TYPES.map((type) => (
              <button
                key={type}
                type="button"
                draggable
                onDragStart={(event) => {
                  event.dataTransfer.setData(DND_NEW_TYPE, type);
                  event.dataTransfer.effectAllowed = "copy";
                }}
                onClick={() => addQuestionOfType(type)}
                className="flex cursor-grab items-center gap-2 rounded-md border-2 border-dashed border-[#c8c8c8] bg-[#fafafa] px-2.5 py-2 text-left text-sm transition-colors hover:border-primary hover:bg-[#f0f7ff] active:cursor-grabbing"
              >
                <span>{TYPE_ICONS[type]}</span>
                <span>{TYPE_NAMES[type]}</span>
                <Plus className="ml-auto h-3.5 w-3.5 text-[#aaa]" />
              </button>
            ))}
            <button
              type="button"
              onClick={() => editorRef.current?.insertParagraph()}
              className="flex items-center gap-2 rounded-md border-2 border-dashed border-[#d8c9a8] bg-[#fdfaf3] px-2.5 py-2 text-left text-sm transition-colors hover:border-[#c9a86a] hover:bg-[#faf3e3]"
            >
              <span>¶</span>
              <span>新段落</span>
              <Plus className="ml-auto h-3.5 w-3.5 text-[#aaa]" />
            </button>
          </div>
        </Card>

        {/* 文档画布：整篇直接打字编辑，支持 Markdown 与 $公式$ */}
        <div className="min-h-[420px] flex-1 rounded-lg border border-[#e8e2d5] bg-[#fffef9] p-5">
          {boundCategories.length >= 2 ? (
            <p className="mb-3 rounded-md bg-[#f4f9ff] px-3 py-2 text-xs text-[#555]">
              意向学分类别（自动生成）：{boundCategories.map((c) => `○ ${c}`).join("　")}
              <span className="ml-2 text-[#999]">缺省记为"无"</span>
            </p>
          ) : null}
          <BodyEditor
            ref={editorRef}
            body={body}
            questions={questions}
            selectedQid={selectedQid}
            onChange={setBody}
            onSelectQuestion={(qid) => setSelectedQid((prev) => (prev === qid ? null : qid))}
            onDropNewType={(type, pos) =>
              addQuestionOfType(type as CustomQuestion["question_type"], pos)
            }
          />
        </div>

        {/* 题目属性面板 */}
        <Card className="w-72 shrink-0 p-3 sticky top-4">
          {selectedQuestion ? (
            <QuestionPropertyPanel
              question={selectedQuestion}
              onUpdate={(patch) => updateQuestion(selectedQuestion.question_id, patch)}
              onRemove={() => removeQuestion(selectedQuestion.question_id)}
            />
          ) : (
            <div className="py-8 text-center text-sm text-[#999]">
              <p>点击正文中的题目槽位</p>
              <p className="mt-1 text-xs">在这里编辑题目内容与校验规则</p>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

/** 右侧题目属性面板：文本、必填、选项、校验规则等。 */
function QuestionPropertyPanel({
  question,
  onUpdate,
  onRemove,
}: {
  question: CustomQuestion;
  onUpdate: (patch: Partial<CustomQuestion>) => void;
  onRemove: () => void;
}) {
  const isChoice = question.question_type.includes("choice");
  const isText = question.question_type === "text" || question.question_type === "textarea";

  const updateOption = (optIndex: number, value: string) => {
    onUpdate({ options: question.options.map((opt, i) => (i === optIndex ? value : opt)) });
  };
  const addOption = () => onUpdate({ options: [...question.options, "新选项"] });
  const removeOption = (optIndex: number) => {
    if (question.options.length <= 2) {
      toast.error("至少需要2个选项");
      return;
    }
    onUpdate({ options: question.options.filter((_, i) => i !== optIndex) });
  };

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <strong className="text-sm text-primary">{TYPE_NAMES[question.question_type]}</strong>
        <Button type="button" variant="danger" size="icon" className="h-7 w-7" onClick={onRemove}>
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      </div>

      <div className="mb-2">
        <Input
          value={question.question_text}
          placeholder="题目名称（用于校验提示与导出列名）"
          onChange={(event) => onUpdate({ question_text: event.target.value })}
        />
      </div>

      <div className="mb-2 flex flex-col gap-1.5 text-sm">
        <label className="flex items-center gap-1.5 cursor-pointer">
          <Checkbox
            checked={question.required}
            onCheckedChange={(checked) => onUpdate({ required: checked === true })}
          />
          <span>必填</span>
        </label>
        {isChoice ? (
          <label className="flex items-center gap-1.5 cursor-pointer">
            <Checkbox
              checked={question.allow_other === true}
              onCheckedChange={(checked) => onUpdate({ allow_other: checked === true })}
            />
            <span>允许"其他"自定义项</span>
          </label>
        ) : null}
        {isText ? (
          <>
            <label className="flex items-center gap-1.5 cursor-pointer">
              <Checkbox
                checked={isMultiline(question)}
                onCheckedChange={(checked) => onUpdate({ multiline: checked === true })}
              />
              <span>多行作答</span>
            </label>
            <label className="flex items-center gap-1.5">
              <span className="text-[#666]">字数上限</span>
              <Input
                type="number"
                min={1}
                max={5000}
                value={question.max_length}
                onChange={(event) => onUpdate({ max_length: parseInt(event.target.value, 10) || 0 })}
                className="h-8 w-24"
              />
            </label>
            <label className="flex items-center gap-1.5">
              <span className="text-[#666]">格式校验</span>
              <Select
                value={question.format ?? "none"}
                onChange={(event) =>
                  onUpdate({ format: event.target.value as CustomQuestion["format"] })
                }
                className="h-8 w-32"
              >
                {Object.entries(TEXT_FORMAT_NAMES).map(([value, name]) => (
                  <option key={value} value={value}>
                    {name}
                  </option>
                ))}
              </Select>
            </label>
            {question.format === "regex" ? (
              <Input
                value={question.pattern ?? ""}
                placeholder="正则表达式，如 ^[A-Z]\d{5}$"
                onChange={(event) => onUpdate({ pattern: event.target.value })}
                className="h-8 font-mono text-xs"
              />
            ) : null}
          </>
        ) : null}
        {question.question_type === "number" ? (
          <div className="flex items-center gap-2">
            <label className="flex items-center gap-1.5">
              <span className="text-[#666]">最小</span>
              <Input
                type="number"
                value={question.min_value ?? ""}
                placeholder="不限"
                onChange={(event) =>
                  onUpdate({
                    min_value: event.target.value === "" ? null : Number(event.target.value),
                  })
                }
                className="h-8 w-20"
              />
            </label>
            <label className="flex items-center gap-1.5">
              <span className="text-[#666]">最大</span>
              <Input
                type="number"
                value={question.max_value ?? ""}
                placeholder="不限"
                onChange={(event) =>
                  onUpdate({
                    max_value: event.target.value === "" ? null : Number(event.target.value),
                  })
                }
                className="h-8 w-20"
              />
            </label>
          </div>
        ) : null}
        {question.question_type === "rating" ? (
          <label className="flex items-center gap-1.5">
            <span className="text-[#666]">评分上限</span>
            <Input
              type="number"
              min={2}
              max={10}
              value={question.max_rating}
              onChange={(event) => onUpdate({ max_rating: parseInt(event.target.value, 10) || 5 })}
              className="h-8 w-20"
            />
          </label>
        ) : null}
      </div>

      {isChoice ? (
        <div>
          {question.options.map((option, optIndex) => (
            <div key={optIndex} className="mb-1.5 flex gap-1.5">
              <Input
                value={option}
                onChange={(event) => updateOption(optIndex, event.target.value)}
                className="h-8 flex-1"
              />
              <Button
                type="button"
                variant="danger"
                size="icon"
                className="h-8 w-8"
                onClick={() => removeOption(optIndex)}
              >
                <X className="h-3.5 w-3.5" />
              </Button>
            </div>
          ))}
          <Button type="button" variant="secondary" size="sm" className="mt-0.5" onClick={addOption}>
            <Plus className="h-3.5 w-3.5" />
            添加选项
          </Button>
        </div>
      ) : null}
    </div>
  );
}
