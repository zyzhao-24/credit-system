import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { errorMessage } from "@/api/client";
import {
  cancelQuestionnaire,
  getActivityCategories,
  getAvailableQuestionnaires,
  getMyRegistrations,
  getRegistrationQuestionnaire,
  submitQuestionnaire,
  updateQuestionnaireResponse,
} from "@/api/service";
import type {
  AvailableQuestionnaire,
  CustomAnswers,
  MyRegistration,
} from "@/api/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/common";
import { QuestionRenderer } from "@/components/QuestionRenderer";
import { RegistrationBadge } from "@/components/StatusBadge";
import { cn } from "@/lib/utils";

interface FillState {
  questionnaire: AvailableQuestionnaire;
  /** 编辑已有报名时为原报名记录 */
  existing?: MyRegistration;
}

/** 学生活动报名页：可报名问卷 + 我的报名。 */
export function ActivityRegistrationPage() {
  const navigate = useNavigate();
  const [available, setAvailable] = useState<AvailableQuestionnaire[]>([]);
  const [registrations, setRegistrations] = useState<MyRegistration[]>([]);
  const [fill, setFill] = useState<FillState | null>(null);
  const [cancelTarget, setCancelTarget] = useState<MyRegistration | null>(null);

  const loadData = useCallback(() => {
    getAvailableQuestionnaires()
      .then((data) => {
        if (data.success) setAvailable(data.questionnaires);
        else toast.error(data.message || "加载可报名问卷失败");
      })
      .catch((error) => toast.error(errorMessage(error, "加载失败")));
    getMyRegistrations()
      .then((data) => {
        if (data.success) setRegistrations(data.registrations);
      })
      .catch((error) => toast.error(errorMessage(error, "加载失败")));
  }, []);

  useEffect(loadData, [loadData]);

  const openFill = async (questionnaire: AvailableQuestionnaire, existing?: MyRegistration) => {
    if (!existing) {
      try {
        const registration = await getRegistrationQuestionnaire();
        if (
          registration.success &&
          (!registration.questionnaire.phone || !registration.questionnaire.wechat)
        ) {
          toast.warning("请先完善注册问卷中的手机号和微信号");
          navigate("/student/questionnaire");
          return;
        }
      } catch (error) {
        toast.error(errorMessage(error, "检查注册问卷失败"));
        return;
      }
    }
    setFill({ questionnaire, existing });
  };

  const openEdit = (registration: MyRegistration) => {
    const questionnaire = available.find(
      (item) => item.questionnaire_id === registration.questionnaire_id,
    );
    if (!questionnaire) {
      toast.error("问卷不存在或已截止，无法修改");
      return;
    }
    openFill(questionnaire, registration);
  };

  const confirmCancel = async () => {
    if (!cancelTarget) return;
    try {
      const result = await cancelQuestionnaire(cancelTarget.response_id);
      if (result.success) {
        toast.success("取消成功");
        loadData();
      } else {
        toast.error(result.message || "取消失败");
      }
    } catch (error) {
      toast.error(errorMessage(error, "取消失败"));
    }
  };

  return (
    <div className="mx-auto max-w-4xl px-4 py-6">
      <PageHeader
        title="活动报名"
        homePath="/student"
        extra={
          <Button variant="secondary" size="sm" onClick={() => navigate("/student")}>
            返回首页
          </Button>
        }
      />

      <Tabs defaultValue="available">
        <TabsList>
          <TabsTrigger value="available">可报名问卷</TabsTrigger>
          <TabsTrigger value="mine">我的报名</TabsTrigger>
        </TabsList>

        <TabsContent value="available">
          {available.length === 0 ? (
            <EmptyState icon="📋" text="暂无可报名的问卷" />
          ) : (
            available.map((questionnaire) => (
              <AvailableCard
                key={questionnaire.questionnaire_id}
                questionnaire={questionnaire}
                onRegister={() => openFill(questionnaire)}
              />
            ))
          )}
        </TabsContent>

        <TabsContent value="mine">
          {registrations.length === 0 ? (
            <EmptyState icon="📝" text="您还没有报名任何活动" />
          ) : (
            registrations.map((registration) => (
              <RegistrationCard
                key={registration.response_id}
                registration={registration}
                onEdit={() => openEdit(registration)}
                onCancel={() => setCancelTarget(registration)}
              />
            ))
          )}
        </TabsContent>
      </Tabs>

      {fill ? (
        <FillDialog
          state={fill}
          onClose={() => setFill(null)}
          onSubmitted={() => {
            setFill(null);
            loadData();
          }}
        />
      ) : null}

      <ConfirmDialog
        open={cancelTarget !== null}
        onOpenChange={(open) => {
          if (!open) setCancelTarget(null);
        }}
        message="确定要取消报名吗？"
        onConfirm={confirmCancel}
      />
    </div>
  );
}

function AvailableCard({
  questionnaire,
  onRegister,
}: {
  questionnaire: AvailableQuestionnaire;
  onRegister: () => void;
}) {
  const maxText = questionnaire.max_participants > 0 ? questionnaire.max_participants : "不限";
  const isFull =
    questionnaire.max_participants > 0 && questionnaire.response_count >= questionnaire.max_participants;

  return (
    <Card className="mb-5">
      <div className="flex items-start justify-between mb-3">
        <h3 className="text-lg font-semibold text-[#1976d2]">📋 {questionnaire.title}</h3>
        {questionnaire.is_registered ? (
          questionnaire.is_waitlist ? (
            <Badge variant="waitlist">候补</Badge>
          ) : (
            <Badge variant="qualified">已报名</Badge>
          )
        ) : isFull ? (
          <Badge variant="waitlist">可候补</Badge>
        ) : null}
      </div>
      <div className="text-sm leading-7 text-[#666]">
        <div>
          <strong>活动：</strong>
          {questionnaire.activity_name}
        </div>
        <div>
          <strong>时间：</strong>
          {questionnaire.start_time} ~ {questionnaire.end_time}
        </div>
        <div>
          <strong>人数：</strong>已报名 {questionnaire.response_count}/{maxText}
        </div>
        {isFull && !questionnaire.is_registered ? (
          <div className="text-[#ff9800]">
            <strong>提示：</strong>名额已满，报名后将进入候补名单
          </div>
        ) : null}
      </div>
      <div className="mt-4">
        {questionnaire.is_registered ? (
          <Button disabled className="w-full">
            已报名
          </Button>
        ) : (
          <Button className="w-full" onClick={onRegister}>
            {isFull ? "候补报名" : "立即报名"}
          </Button>
        )}
      </div>
    </Card>
  );
}

function RegistrationCard({
  registration,
  onEdit,
  onCancel,
}: {
  registration: MyRegistration;
  onEdit: () => void;
  onCancel: () => void;
}) {
  const active = registration.status === "active";
  return (
    <Card className="mb-5">
      <div className="flex items-start justify-between mb-3">
        <h3 className="text-lg font-semibold text-[#1976d2]">📋 {registration.questionnaire_title}</h3>
        <RegistrationBadge
          status={registration.status}
          isEnded={registration.is_ended}
          isSelected={registration.is_selected}
          isWaitlist={registration.is_waitlist}
        />
      </div>
      <div className="text-sm leading-7 text-[#666]">
        <div>
          <strong>活动：</strong>
          {registration.activity_name}
        </div>
        {active && registration.rank > 0 ? (
          <div>
            <strong>{registration.max_participants > 0 ? "排名：" : "报名顺序："}</strong>
            {registration.max_participants > 0
              ? `${registration.rank}/${registration.max_participants}${registration.is_waitlist ? " (候补)" : ""}`
              : `第${registration.rank}位`}
          </div>
        ) : null}
        {registration.intended_category ? (
          <div>
            <strong>意向类别：</strong>
            {registration.intended_category}
          </div>
        ) : null}
        <div>
          <strong>提交时间：</strong>
          {registration.submit_time}
        </div>
      </div>

      {registration.is_ended && active ? (
        registration.is_selected ? (
          <div className="mt-3 rounded-md border-l-4 border-success bg-[#e8f5e9] px-3 py-2.5 text-sm">
            <strong>恭喜！</strong>您已成功入选此活动
          </div>
        ) : (
          <div className="mt-3 rounded-md border-l-4 border-[#f44336] bg-[#ffebee] px-3 py-2.5 text-sm">
            <strong>很遗憾，</strong>您未能入选此活动
          </div>
        )
      ) : null}

      {active && !registration.is_ended ? (
        <div className="mt-4 flex gap-3">
          <Button variant="secondary" className="flex-1" onClick={onEdit}>
            修改
          </Button>
          <Button variant="danger" className="flex-1" onClick={onCancel}>
            取消报名
          </Button>
        </div>
      ) : null}
    </Card>
  );
}

function FillDialog({
  state,
  onClose,
  onSubmitted,
}: {
  state: FillState;
  onClose: () => void;
  onSubmitted: () => void;
}) {
  const { questionnaire, existing } = state;
  const [categories, setCategories] = useState<string[] | null>(null);
  const [category, setCategory] = useState(existing?.intended_category ?? "");
  const [answers, setAnswers] = useState<CustomAnswers>(existing?.custom_answers ?? {});
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    getActivityCategories(questionnaire.activity_id)
      .then((data) => {
        if (data.success) {
          if (data.categories.length === 0) {
            toast.error("该活动没有设置学分类别，请联系管理员");
            onClose();
            return;
          }
          setCategories(data.categories);
        } else {
          toast.error(data.message || "获取活动类别失败");
          onClose();
        }
      })
      .catch((error) => {
        toast.error(errorMessage(error, "获取活动类别失败"));
        onClose();
      });
  }, [questionnaire.activity_id, onClose]);

  const submit = async () => {
    if (questionnaire.has_category_question && !category) {
      toast.error("请选择意向学分类别");
      return;
    }
    for (const question of questionnaire.custom_questions ?? []) {
      if (question.question_type === "description") continue;
      const answer = answers[question.question_id]?.answer;
      const empty =
        answer === undefined ||
        (typeof answer === "string" && !answer.trim()) ||
        (Array.isArray(answer) && answer.length === 0);
      if (question.required && empty) {
        toast.error(`请回答：${question.question_text}`);
        return;
      }
    }

    setSubmitting(true);
    try {
      const payload = {
        questionnaire_id: questionnaire.questionnaire_id,
        intended_category: category,
        custom_answers: answers,
      };
      const result = existing
        ? await updateQuestionnaireResponse(existing.response_id, payload)
        : await submitQuestionnaire(payload);
      if (result.success) {
        toast.success(existing ? "修改成功！" : "报名成功！");
        onSubmitted();
      } else {
        toast.error(result.message || (existing ? "修改失败" : "报名失败"));
      }
    } catch (error) {
      toast.error(errorMessage(error, existing ? "修改失败" : "报名失败"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        title={existing ? `修改报名 - ${questionnaire.title}` : questionnaire.title}
        className="max-w-xl"
      >
        <div className="rounded-md bg-[#e3f2fd] px-3 py-3 mb-5 text-sm">
          <strong>提示：</strong>手机号和微信号将自动从注册问卷中获取
        </div>

        {questionnaire.has_category_question ? (
          <div className="mb-2">
            <p className="mb-2.5 font-medium">
              1. 意向学分类别 <span className="text-danger">*</span>
            </p>
            {categories === null ? (
              <p className="text-sm text-[#999]">加载类别中...</p>
            ) : (
              <div className="flex flex-col gap-2">
                {categories.map((name) => (
                  <label
                    key={name}
                    className={cn(
                      "flex items-center gap-2.5 rounded-md border-2 px-3 py-2.5 cursor-pointer transition-colors",
                      category === name
                        ? "border-primary bg-[#e3f2fd]"
                        : "border-[#e0e0e0] hover:border-primary hover:bg-[#f5f9ff]",
                    )}
                  >
                    <input
                      type="radio"
                      name="intendedCategory"
                      value={name}
                      checked={category === name}
                      onChange={() => setCategory(name)}
                      className="h-4.5 w-4.5 accent-primary"
                    />
                    <span>{name}</span>
                  </label>
                ))}
              </div>
            )}
          </div>
        ) : null}

        <QuestionRenderer
          questions={questionnaire.custom_questions ?? []}
          answers={answers}
          onChange={setAnswers}
        />

        <div className="flex gap-3 mt-6">
          <Button className="flex-1" onClick={submit} disabled={submitting || categories === null}>
            {submitting ? "提交中..." : "提交"}
          </Button>
          <Button variant="secondary" className="flex-1" onClick={onClose}>
            取消
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
