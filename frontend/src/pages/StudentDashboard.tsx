import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router";
import { toast } from "sonner";
import { ClipboardList, FileDown, FileText } from "lucide-react";
import { errorMessage } from "@/api/client";
import { changeStudentPassword, getMyCredits, getStudentActivities } from "@/api/service";
import { sha256Hex } from "@/lib/sha256";
import { printCreditReport } from "@/lib/printReport";
import { useAuth } from "@/auth/auth-context";
import type { CreditReport, StudentActivities } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { PageHeader } from "@/components/PageHeader";
import { Field } from "@/components/common";
import { QualifiedBadge } from "@/components/StatusBadge";

/** 学生主页：我的学分、活动列表、修改密码、导出 PDF。 */
export function StudentDashboard() {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const [credits, setCredits] = useState<CreditReport | null>(null);
  const [activities, setActivities] = useState<StudentActivities | null>(null);

  useEffect(() => {
    getMyCredits()
      .then((data) => {
        if (data.success) setCredits(data);
        else toast.error("加载失败");
      })
      .catch((error) => toast.error(errorMessage(error, "加载失败")));
  }, []);

  const loadActivities = useCallback(() => {
    getStudentActivities()
      .then((data) => {
        if (data.success) setActivities(data);
      })
      .catch((error) => toast.error(errorMessage(error, "加载失败")));
  }, []);

  return (
    <div className="mx-auto max-w-6xl px-4 py-6">
      <PageHeader
        title="我的学分"
        homePath="/student"
        extra={
          <Button
            size="sm"
            onClick={() => (credits ? printCreditReport(credits, "student") : toast.error("数据尚未加载完成"))}
          >
            <FileDown className="h-4 w-4" />
            导出PDF
          </Button>
        }
      />

      <Tabs defaultValue="credits">
        <TabsList>
          <TabsTrigger value="credits">我的学分</TabsTrigger>
          <TabsTrigger value="activities" onClick={loadActivities}>
            活动列表
          </TabsTrigger>
          <TabsTrigger value="password">修改密码</TabsTrigger>
          <TabsTrigger value="__questionnaire" asChild>
            <Link to="/student/profile" className="text-success">
              <span className="inline-flex items-center gap-1">
                <FileText className="h-4 w-4" />
                报名信息
              </span>
            </Link>
          </TabsTrigger>
          <TabsTrigger value="__registration" asChild>
            <Link to="/student/activities" className="text-[#e65100]">
              <span className="inline-flex items-center gap-1">
                <ClipboardList className="h-4 w-4" />
                活动报名
              </span>
            </Link>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="credits">
          {credits ? <CreditsView data={credits} /> : <p className="text-[#999] py-10 text-center">加载中...</p>}
        </TabsContent>

        <TabsContent value="activities">
          <ActivitiesView data={activities} />
        </TabsContent>

        <TabsContent value="password">
          <ChangePasswordCard
            onChanged={async () => {
              await logout();
              navigate("/login");
            }}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function CreditsView({ data }: { data: CreditReport }) {
  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardTitle>基本信息</CardTitle>
        <p className="text-sm leading-7">
          <strong>学号：</strong>
          {data.student_id}
        </p>
        <p className="text-sm leading-7">
          <strong>姓名：</strong>
          {data.student_name}
        </p>
      </Card>

      <Card>
        <CardTitle>总学分情况</CardTitle>
        <div className="text-sm leading-7">
          <p>
            <strong>已获得学分：</strong>
            {data.total_credits}
          </p>
          <p>
            <strong>合格学分：</strong>
            {data.total_required}
          </p>
          <p className="flex items-center gap-2">
            <strong>总学分状态：</strong>
            <QualifiedBadge qualified={data.total_qualified} />
          </p>
          <p className="flex items-center gap-2">
            <strong>所有类别状态：</strong>
            <QualifiedBadge qualified={data.all_categories_qualified} />
          </p>
          <p className="mt-2.5 flex items-center gap-2 border-t-2 border-[#ddd] pt-2.5">
            <strong>最终合格情况：</strong>
            <span className="text-base">
              <QualifiedBadge qualified={data.final_qualified} mark />
            </span>
          </p>
          {!data.final_qualified ? (
            <p className="mt-2 text-sm text-[#666]">
              <em>提示：需要总学分达标且所有类别都合格才能最终合格</em>
            </p>
          ) : null}
        </div>
      </Card>

      <Card>
        <CardTitle>各类别学分情况</CardTitle>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>类别</TableHead>
              <TableHead>已获得学分</TableHead>
              <TableHead>合格学分</TableHead>
              <TableHead>状态</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {Object.entries(data.category_status).map(([category, status]) => (
              <TableRow key={category}>
                <TableCell>{category}</TableCell>
                <TableCell>{status.credits}</TableCell>
                <TableCell>{status.required}</TableCell>
                <TableCell>
                  <QualifiedBadge qualified={status.qualified} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>

      <Card>
        <CardTitle>活动参与记录</CardTitle>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>活动名称</TableHead>
              <TableHead>记录名称</TableHead>
              <TableHead>学分</TableHead>
              <TableHead>可选类别</TableHead>
              <TableHead>计入类别</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.activities.map((activity, index) => (
              <TableRow key={index}>
                <TableCell>{activity.activity_name}</TableCell>
                <TableCell>{activity.record_name}</TableCell>
                <TableCell>{activity.credits}</TableCell>
                <TableCell>{activity.categories.join(", ")}</TableCell>
                <TableCell>{activity.assigned_category || "-"}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>
    </div>
  );
}

function ActivitiesView({ data }: { data: StudentActivities | null }) {
  if (!data) {
    return <p className="text-[#999] py-10 text-center">加载中...</p>;
  }
  return (
    <Card>
      <CardTitle>活动列表（按类别）</CardTitle>
      <div className="grid grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-4">
        {Object.entries(data.category_activities).map(([category, items]) => (
          <div key={category} className="rounded-lg border border-[#e5e5e5] p-4">
            <h4 className="font-semibold text-primary mb-2">{category}</h4>
            <ul className="list-disc pl-5 text-sm leading-7 text-[#555]">
              {items.map((item) => (
                <li key={item.activity_id}>{item.activity_name}</li>
              ))}
            </ul>
          </div>
        ))}
        {data.no_category_activities.length > 0 ? (
          <div className="rounded-lg border border-[#e5e5e5] p-4">
            <h4 className="font-semibold text-[#777] mb-2">无类别活动</h4>
            <ul className="list-disc pl-5 text-sm leading-7 text-[#555]">
              {data.no_category_activities.map((item) => (
                <li key={item.activity_id}>{item.activity_name}</li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </Card>
  );
}

function ChangePasswordCard({ onChanged }: { onChanged: () => Promise<void> }) {
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const submit = async () => {
    if (!oldPassword || !newPassword || !confirmPassword) {
      toast.error("请填写所有字段");
      return;
    }
    if (newPassword !== confirmPassword) {
      toast.error("两次输入的新密码不一致");
      return;
    }
    if (newPassword.length < 6) {
      toast.error("新密码至少需要6位字符");
      return;
    }
    setSubmitting(true);
    try {
      const oldDigest = await sha256Hex(oldPassword);
      const result = await changeStudentPassword(oldDigest, newPassword);
      if (result.success) {
        toast.success("密码修改成功，请重新登录");
        await onChanged();
      } else {
        toast.error(result.message || "修改失败");
      }
    } catch (error) {
      toast.error(errorMessage(error, "修改失败"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card className="max-w-md">
      <CardTitle>修改密码</CardTitle>
      <Field label="原密码">
        <Input
          type="password"
          value={oldPassword}
          onChange={(event) => setOldPassword(event.target.value)}
          autoComplete="current-password"
        />
      </Field>
      <Field label="新密码">
        <Input
          type="password"
          value={newPassword}
          onChange={(event) => setNewPassword(event.target.value)}
          autoComplete="new-password"
        />
      </Field>
      <Field label="确认新密码">
        <Input
          type="password"
          value={confirmPassword}
          onChange={(event) => setConfirmPassword(event.target.value)}
          autoComplete="new-password"
        />
      </Field>
      <Button onClick={submit} disabled={submitting}>
        {submitting ? "提交中..." : "修改密码"}
      </Button>
    </Card>
  );
}
