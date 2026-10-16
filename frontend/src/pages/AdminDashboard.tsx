import { Link } from "react-router";
import { ClipboardList } from "lucide-react";
import { useAuth } from "@/auth/auth-context";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageHeader } from "@/components/PageHeader";
import { ActivitiesSection } from "./admin/ActivitiesSection";
import { ExportSection } from "./admin/ExportSection";
import { QuerySection } from "./admin/QuerySection";
import { ReportSection } from "./admin/ReportSection";
import { SettingsSection } from "./admin/SettingsSection";

/**
 * 管理员控制台。系统管理员显示全部五个标签；普通管理员显示
 * 学生列表（只读）、活动管理和数据报表（仅总体统计），与 legacy 一致。
 */
export function AdminDashboard() {
  const { user } = useAuth();
  const isSystemAdmin = user?.role === "system_admin";

  return (
    <div className="mx-auto max-w-6xl px-4 py-6">
      <PageHeader title="管理员控制台" homePath="/admin" />

      <Tabs defaultValue={isSystemAdmin ? "settings" : "students"}>
        <TabsList>
          {isSystemAdmin ? <TabsTrigger value="settings">系统设置</TabsTrigger> : null}
          {!isSystemAdmin ? <TabsTrigger value="students">学生列表</TabsTrigger> : null}
          <TabsTrigger value="activities">活动管理</TabsTrigger>
          {isSystemAdmin ? <TabsTrigger value="query">学分查询</TabsTrigger> : null}
          <TabsTrigger value="report">数据报表</TabsTrigger>
          {isSystemAdmin ? <TabsTrigger value="export">数据导出</TabsTrigger> : null}
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

        {isSystemAdmin ? (
          <TabsContent value="settings">
            <SettingsSection />
          </TabsContent>
        ) : null}

        {!isSystemAdmin ? (
          <TabsContent value="students">
            <SettingsSection readOnlyStudentsOnly />
          </TabsContent>
        ) : null}

        <TabsContent value="activities">
          <ActivitiesSection isSystemAdmin={isSystemAdmin} />
        </TabsContent>

        {isSystemAdmin ? (
          <TabsContent value="query">
            <QuerySection />
          </TabsContent>
        ) : null}

        <TabsContent value="report">
          <ReportSection isSystemAdmin={isSystemAdmin} />
        </TabsContent>

        {isSystemAdmin ? (
          <TabsContent value="export">
            <ExportSection />
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
