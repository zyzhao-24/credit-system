import { useEffect, useState } from "react";
import { toast } from "sonner";
import { errorMessage } from "@/api/client";
import { getStudentProfile, updateStudentProfile } from "@/api/service";
import type { StudentProfile } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { Input, Textarea } from "@/components/ui/input";
import { PageHeader } from "@/components/PageHeader";
import { Field } from "@/components/common";

const PHONE_PATTERN = /^1[3-9]\d{9}$/;

/** 学生报名信息：查看和更新手机号、微信号、建议（数据直接存放在学生档案上）。 */
export function StudentProfilePage() {
  const [profile, setProfile] = useState<StudentProfile | null>(null);
  const [phone, setPhone] = useState("");
  const [wechat, setWechat] = useState("");
  const [suggestion, setSuggestion] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const load = () => {
    getStudentProfile()
      .then((data) => {
        if (data.success) {
          setProfile(data.profile);
          setPhone(data.profile.phone || "");
          setWechat(data.profile.wechat || "");
          setSuggestion(data.profile.suggestion || "");
        } else {
          toast.error("加载失败");
        }
      })
      .catch((error) => toast.error(errorMessage(error, "加载失败")));
  };

  useEffect(load, []);

  const save = async () => {
    const trimmedPhone = phone.trim();
    if (trimmedPhone && !PHONE_PATTERN.test(trimmedPhone)) {
      toast.error("请输入正确的11位手机号码");
      return;
    }
    setSubmitting(true);
    try {
      const result = await updateStudentProfile({
        phone: trimmedPhone,
        wechat: wechat.trim(),
        suggestion: suggestion.trim(),
      });
      if (result.success) {
        toast.success("保存成功！");
        load();
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
    <div className="mx-auto max-w-3xl px-4 py-6">
      <PageHeader title="报名信息" homePath="/student" />

      <Card>
        <CardTitle>基本信息</CardTitle>
        {profile ? (
          <>
            <Field label="学号">
              <Input value={profile.student_id} readOnly />
            </Field>
            <Field label="姓名">
              <Input value={profile.name} readOnly />
            </Field>
            <Field label="手机号" required>
              <Input
                type="tel"
                value={phone}
                onChange={(event) => setPhone(event.target.value)}
                placeholder="请输入11位手机号"
                inputMode="numeric"
              />
              <small className="text-[#666]">用于活动报名，请务必填写</small>
            </Field>
            <Field label="微信号" required>
              <Input
                value={wechat}
                onChange={(event) => setWechat(event.target.value)}
                placeholder="请输入微信号"
              />
              <small className="text-[#666]">用于活动报名，请务必填写</small>
            </Field>
            <Field label="建议">
              <Textarea
                rows={4}
                value={suggestion}
                onChange={(event) => setSuggestion(event.target.value)}
                placeholder="对团校活动的建议（选填）"
              />
            </Field>
            {profile.updated_at ? (
              <Field label="最近更新">
                <Input value={profile.updated_at} readOnly />
              </Field>
            ) : null}
            <Button className="w-full" onClick={save} disabled={submitting}>
              {submitting ? "保存中..." : "保存"}
            </Button>
          </>
        ) : (
          <p className="text-[#999] py-6 text-center">加载中...</p>
        )}
      </Card>
    </div>
  );
}
