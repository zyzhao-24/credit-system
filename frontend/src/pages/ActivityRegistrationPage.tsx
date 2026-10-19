import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { toast } from "sonner";
import QrScanner from "qr-scanner";
import { errorMessage } from "@/api/client";
import { useAuth } from "@/auth/auth-context";
import {
  cancelQuestionnaire,
  checkinQuestionnaire,
  getAvailableQuestionnaires,
  getMyRegistrations,
  getStudentProfile,
  submitQuestionnaire,
  updateQuestionnaireResponse,
} from "@/api/service";
import type {
  AvailableQuestionnaire,
  CustomAnswers,
  MyRegistration,
  StudentProfile,
} from "@/api/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AnswerPanel } from "@/components/AnswerPanel";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/common";
import { QuestionDocument } from "@/components/QuestionDocument";
import { CheckinBadge, RegistrationBadge } from "@/components/StatusBadge";
import { bodyOf, validateAnswers } from "@/lib/questions";

interface FillState {
  questionnaire: AvailableQuestionnaire;
  /** 编辑已有报名时为原报名记录 */
  existing?: MyRegistration;
}

/** 签到对话框目标：扫码链接可预填签到码 */
interface CheckinState {
  registration: MyRegistration;
  code: string;
}

/** 学生活动报名页：可报名问卷 + 我的报名。 */
export function ActivityRegistrationPage() {
  const navigate = useNavigate();
  const [available, setAvailable] = useState<AvailableQuestionnaire[]>([]);
  const [registrations, setRegistrations] = useState<MyRegistration[]>([]);
  const [fill, setFill] = useState<FillState | null>(null);
  const [cancelTarget, setCancelTarget] = useState<MyRegistration | null>(null);
  const [checkin, setCheckin] = useState<CheckinState | null>(null);
  const [tab, setTab] = useState("available");
  const [searchParams, setSearchParams] = useSearchParams();
  // 扫码链接只处理一次，处理后清掉地址栏参数
  const scanHandled = useRef(false);

  // 扫码签到链接：?checkin=<问卷ID>&code=<签到码>，自动打开对应报名的签到框
  // （在数据加载回调中处理，URL 参数视为一次性外部输入）
  const handleScanParams = useCallback(
    (regs: MyRegistration[]) => {
      if (scanHandled.current) return;
      const qid = searchParams.get("checkin");
      if (!qid) return;
      scanHandled.current = true;
      const code = searchParams.get("code") ?? "";
      setSearchParams({}, { replace: true });
      const registration = regs.find(
        (item) => item.questionnaire_id === qid && item.status === "active",
      );
      if (!registration) {
        toast.error("没有找到对应的报名记录");
        return;
      }
      setTab("mine");
      if (!registration.checkin_open) {
        toast.warning("该活动的签到尚未开启");
        return;
      }
      if (registration.checkin_state !== "none") {
        toast.info("您已签到，无需重复操作");
        return;
      }
      setCheckin({ registration, code });
    },
    [searchParams, setSearchParams],
  );

  const loadData = useCallback(() => {
    getAvailableQuestionnaires()
      .then((data) => {
        if (data.success) setAvailable(data.questionnaires);
        else toast.error(data.message || "加载可报名问卷失败");
      })
      .catch((error) => toast.error(errorMessage(error, "加载失败")));
    getMyRegistrations()
      .then((data) => {
        if (data.success) {
          setRegistrations(data.registrations);
          handleScanParams(data.registrations);
        }
      })
      .catch((error) => toast.error(errorMessage(error, "加载失败")));
  }, [handleScanParams]);

  useEffect(loadData, [loadData]);

  const openFill = async (questionnaire: AvailableQuestionnaire, existing?: MyRegistration) => {
    if (!existing) {
      try {
        const profile = await getStudentProfile();
        if (profile.success && (!profile.profile.phone || !profile.profile.wechat)) {
          toast.warning("请先完善报名信息中的手机号和微信号");
          navigate("/student/profile");
          return;
        }
      } catch (error) {
        toast.error(errorMessage(error, "检查报名信息失败"));
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
      <PageHeader title="活动报名" homePath="/student" backTo="/student" />

      <Tabs value={tab} onValueChange={setTab}>
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
                onCheckin={() => setCheckin({ registration, code: "" })}
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

      {checkin ? (
        <CheckinDialog
          state={checkin}
          onClose={() => setCheckin(null)}
          onDone={() => {
            setCheckin(null);
            loadData();
          }}
        />
      ) : null}
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
            <Badge variant="qualified">成功</Badge>
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
            报名成功
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
  onCheckin,
}: {
  registration: MyRegistration;
  onEdit: () => void;
  onCancel: () => void;
  onCheckin: () => void;
}) {
  const active = registration.status === "active";
  const canCheckin = active && registration.checkin_open && registration.checkin_state === "none";
  return (
    <Card className="mb-5">
      <div className="flex items-start justify-between mb-3">
        <h3 className="text-lg font-semibold text-[#1976d2]">📋 {registration.questionnaire_title}</h3>
        <div className="flex items-center gap-1.5">
          {active ? (
            <CheckinBadge
              state={registration.checkin_state}
              checkedInAt={registration.checked_in_at}
            />
          ) : null}
          <RegistrationBadge
            status={registration.status}
            isEnded={registration.is_ended}
            isSelected={registration.is_selected}
            isWaitlist={registration.is_waitlist}
          />
        </div>
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
            <strong>恭喜！</strong>报名成功
          </div>
        ) : (
          <div className="mt-3 rounded-md border-l-4 border-[#f44336] bg-[#ffebee] px-3 py-2.5 text-sm">
            <strong>很遗憾，</strong>报名失败
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

      {canCheckin ? (
        <div className="mt-4">
          <Button variant="success" className="w-full" onClick={onCheckin}>
            ✓ 签到
          </Button>
        </div>
      ) : null}
      {active && registration.checkin_state === "pending" ? (
        <p className="mt-3 text-xs text-[#ff9800]">签到已记录，待管理员确认后生效</p>
      ) : null}
    </Card>
  );
}

/** 签到对话框：输入本人一次性签到码，或调起摄像头扫管理员出示的二维码。 */
function CheckinDialog({
  state,
  onClose,
  onDone,
}: {
  state: CheckinState;
  onClose: () => void;
  onDone: () => void;
}) {
  const [code, setCode] = useState(state.code);
  const [submitting, setSubmitting] = useState(false);
  const [scanning, setScanning] = useState(false);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  // 扫描回调可能连续触发，只取第一次成功识别
  const scannedRef = useRef(false);

  const submit = useCallback(
    async (codeOverride?: string) => {
      const trimmed = (codeOverride ?? code).trim();
      if (!/^\d{6}$/.test(trimmed)) {
        toast.error("请输入 6 位数字签到码");
        return;
      }
      setSubmitting(true);
      try {
        const result = await checkinQuestionnaire(
          state.registration.questionnaire_id,
          trimmed,
        );
        if (result.success) {
          toast.success(result.message || "签到成功");
          onDone();
        } else {
          toast.error(result.message || "签到失败");
        }
      } catch (error) {
        toast.error(errorMessage(error, "签到失败"));
      } finally {
        setSubmitting(false);
      }
    },
    [code, state.registration.questionnaire_id, onDone],
  );

  // 摄像头扫码：识别签到二维码链接（或纯 6 位码文本）后自动提交
  useEffect(() => {
    if (!scanning) return;
    const video = videoRef.current;
    if (!video) return;
    const scanner = new QrScanner(
      video,
      (result) => {
        if (scannedRef.current) return;
        const text = result.data.trim();
        let scanned = "";
        if (/^\d{6}$/.test(text)) {
          scanned = text;
        } else {
          try {
            const url = new URL(text);
            const qid = url.searchParams.get("checkin");
            const codeParam = url.searchParams.get("code") ?? "";
            if (qid && qid !== state.registration.questionnaire_id) {
              toast.error("该二维码属于其他活动");
              return;
            }
            if (/^\d{6}$/.test(codeParam)) scanned = codeParam;
          } catch {
            // 非 URL 文本，忽略
          }
        }
        if (!scanned) {
          toast.error("无法识别的二维码");
          return;
        }
        scannedRef.current = true;
        setScanning(false);
        setCode(scanned);
        submit(scanned);
      },
      { returnDetailedScanResult: true, highlightScanRegion: true },
    );
    scanner.start().catch(() => {
      toast.error("无法打开摄像头，请检查浏览器权限后重试");
      setScanning(false);
    });
    return () => {
      scanner.stop();
      scanner.destroy();
    };
  }, [scanning, state.registration.questionnaire_id, submit]);

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent title={`签到 - ${state.registration.questionnaire_title}`} className="max-w-sm">
        <p className="mb-4 text-sm text-[#666]">
          请输入您的 6 位签到码（活动现场向管理员获取，每人一码），或扫管理员出示的二维码
        </p>
        {scanning ? (
          <div className="mb-4 overflow-hidden rounded-md bg-black">
            <video ref={videoRef} className="h-56 w-full object-cover" muted playsInline />
          </div>
        ) : (
          <Input
            value={code}
            onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
            placeholder="6 位签到码"
            inputMode="numeric"
            autoFocus
            className="mb-4 text-center font-mono text-xl tracking-[0.4em]"
            onKeyDown={(event) => {
              if (event.key === "Enter") submit();
            }}
          />
        )}
        <div className="flex gap-3">
          {scanning ? (
            <Button variant="secondary" className="flex-1" onClick={() => setScanning(false)}>
              停止扫码
            </Button>
          ) : (
            <>
              <Button className="flex-1" onClick={() => submit()} disabled={submitting}>
                {submitting ? "签到中..." : "确认签到"}
              </Button>
              <Button variant="secondary" className="flex-1" onClick={() => setScanning(true)}>
                📷 扫码
              </Button>
            </>
          )}
          <Button variant="secondary" className="flex-1" onClick={onClose}>
            取消
          </Button>
        </div>
      </DialogContent>
    </Dialog>
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
  const { user } = useAuth();
  // 意向类别由绑定记录的类别决定：多类别→文内单选槽位（缺省为"无"）；单一类别→静态值
  const recordCategories = questionnaire.record_categories ?? [];
  const showCategorySlot = recordCategories.length >= 2;
  const [category, setCategory] = useState(existing?.intended_category ?? "");
  const [answers, setAnswers] = useState<CustomAnswers>(existing?.custom_answers ?? {});
  const [profile, setProfile] = useState<StudentProfile | null>(null);
  // 正在侧栏作答的题目
  const [answerQid, setAnswerQid] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    getStudentProfile()
      .then((data) => {
        if (data.success) setProfile(data.profile);
      })
      .catch(() => undefined);
  }, []);

  const submit = async () => {
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
    const answerError = validateAnswers(questionnaire.custom_questions ?? [], answers);
    if (answerError) {
      toast.error(answerError);
      return;
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

  const effectiveCategory = showCategorySlot
    ? category || "无"
    : recordCategories.length === 1
      ? recordCategories[0]
      : "";
  // 正文信息槽位的取值：个人档案 + 问卷绑定信息
  const letterFields = {
    student_name: user?.name ?? "",
    student_id: user?.sub ?? "",
    phone: profile?.phone ?? "",
    wechat: profile?.wechat ?? "",
    activity_name: questionnaire.activity_id ? questionnaire.activity_name : "",
    record_name: questionnaire.record_name ?? "",
    category: effectiveCategory,
  };

  const answerQuestion = answerQid
    ? (questionnaire.custom_questions ?? []).find((q) => q.question_id === answerQid) ?? null
    : null;

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        title={existing ? `修改报名 - ${questionnaire.title}` : questionnaire.title}
        className={answerQuestion ? "max-w-4xl" : "max-w-xl"}
      >
        <div className="rounded-md bg-[#e3f2fd] px-3 py-3 mb-5 text-sm">
          <strong>提示：</strong>个人信息已自动填入文中；点击文中的题目槽位，在右侧作答（支持 Markdown 与公式）
        </div>

        <div className="flex gap-5 items-start">
          <div className="min-w-0 flex-1">
            <QuestionDocument
              body={bodyOf(questionnaire)}
              questions={questionnaire.custom_questions ?? []}
              answers={answers}
              onAnswer={(qid) => setAnswerQid((prev) => (prev === qid ? null : qid))}
              activeQid={answerQid}
              fields={letterFields}
              categorySlot={
                showCategorySlot
                  ? {
                      options: ["无", ...recordCategories],
                      value: category || "无",
                      onChange: setCategory,
                    }
                  : null
              }
            />
          </div>

          {answerQuestion ? (
            <div className="w-72 shrink-0 rounded-md border border-[#e8e2d5] bg-[#fdfcf8] p-3">
              <div className="mb-2 flex items-center justify-between">
                <strong className="text-sm text-[#555]">作答</strong>
                <button
                  type="button"
                  onClick={() => setAnswerQid(null)}
                  className="text-[#999] hover:text-[#333]"
                  title="收起"
                >
                  ✕
                </button>
              </div>
              <AnswerPanel
                question={answerQuestion}
                answer={answers[answerQuestion.question_id]?.answer}
                onChange={(answer) =>
                  setAnswers((prev) => ({
                    ...prev,
                    [answerQuestion.question_id]: { answer },
                  }))
                }
              />
            </div>
          ) : null}
        </div>

        <div className="flex gap-3 mt-6">
          <Button className="flex-1" onClick={submit} disabled={submitting}>
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
