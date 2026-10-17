import { Link } from "react-router";
import { ClipboardList } from "lucide-react";
import { useAuth } from "@/auth/auth-context";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageHeader } from "@/components/PageHeader";
import { ActivitiesSection } from "./admin/ActivitiesSection";
import { QualificationSection } from "./admin/QualificationSection";
import { ReportSection } from "./admin/ReportSection";
import { SettingsSection } from "./admin/SettingsSection";
import { StudentsSection } from "./admin/StudentsSection";

/**
 * 管理员控制台。系统管理员显示全部标签；普通管理员显示
 * 学生管理（只读学生列表，无注册问卷）、活动管理和数据报表（仅总体统计），与 legacy 一致。
 * 学分查询/导出在“合格情况”标签页；注册问卷管理并入“学生管理”。
 */
export function AdminDashboard() {
  const { user } = useAuth();
  const isSystemAdmin = user?.role === "system_admin";

  return (
    <div className="mx-auto max-w-6xl px-4 py-6">
      <PageHeader title="管理员控制台" homePath="/admin" />

      <Tabs defaultValue="students">
        <TabsList>
          <TabsTrigger value="students">学生管理</TabsTrigger>
          {isSystemAdmin ? <TabsTrigger value="settings">系统设置</TabsTrigger> : null}
          <TabsTrigger value="activities">活动管理</TabsTrigger>
          <TabsTrigger value="report">数据报表</TabsTrigger>
          {isSystemAdmin ? <TabsTrigger value="qualification">合格情况</TabsTrigger> : null}
          {isSystemAdmin ? (
            <TabsTrigger value="__questionnaires" asChild>
              <Link to="/admin/questionnaires" className="text-primary">
                <span className="inline-flex items-center gap-1">
                  <ClipboardList className="h-4 w-4" />
                  问卷管理
                </span>
              </Link>
            </TabsTrigger>
          ) : null}
        </TabsList>

        <TabsContent value="students">
          <StudentsSection canEdit={isSystemAdmin} />
        </TabsContent>

        {isSystemAdmin ? (
          <TabsContent value="settings">
            <SettingsSection />
          </TabsContent>
        ) : null}

        <TabsContent value="activities">
          <ActivitiesSection isSystemAdmin={isSystemAdmin} />
        </TabsContent>

        <TabsContent value="report">
          <ReportSection />
        </TabsContent>

        {isSystemAdmin ? (
          <TabsContent value="qualification">
            <QualificationSection />
          </TabsContent>
        ) : null}
      </Tabs>

      {!isSystemAdmin ? (
        <p className="mt-6 text-center text-sm text-[#999]">
          普通管理员可查看学生列表、管理活动和查看总体统计；其余功能仅系统管理员可用。
        </p>
      ) : null}
    </div>
  );
}
