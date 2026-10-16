import { useEffect, useState } from "react";
import { toast } from "sonner";
import { errorMessage } from "@/api/client";
import { getAdminReport } from "@/api/service";
import type { AdminReport, ReportStudent } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ProgressBar } from "@/components/common";
import { QualifiedBadge } from "@/components/StatusBadge";

type SortKey = "student_id" | "student_name" | "total_credits" | "final_qualified";

/** 数据报表：活动列表、合格统计、分数段、学生列表（仅系统管理员）。 */
export function ReportSection({ isSystemAdmin }: { isSystemAdmin: boolean }) {
  const [report, setReport] = useState<AdminReport | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("student_id");

  useEffect(() => {
    getAdminReport()
      .then((data) => {
        if (data.success) setReport(data);
        else toast.error("加载报表失败");
      })
      .catch((error) => toast.error(errorMessage(error, "加载报表失败")));
  }, []);

  if (!report) {
    return <p className="text-center text-[#999] py-10">加载中...</p>;
  }

  const sortedStudents = sortReportStudents(report.students ?? [], sortKey);

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardTitle>活动列表（按类别）</CardTitle>
        <div className="grid grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-4">
          {Object.entries(report.category_activities).map(([category, items]) => (
            <div key={category} className="rounded-lg border border-[#e5e5e5] p-4">
              <h4 className="font-semibold text-primary mb-2">{category}</h4>
              <ul className="list-disc pl-5 text-sm leading-7 text-[#555]">
                {items.map((item) => (
                  <li key={item.activity_id}>{item.activity_name}</li>
                ))}
              </ul>
            </div>
          ))}
          {report.no_category_activities.length > 0 ? (
            <div className="rounded-lg border border-[#e5e5e5] p-4">
              <h4 className="font-semibold text-[#777] mb-2">无类别活动</h4>
              <ul className="list-disc pl-5 text-sm leading-7 text-[#555]">
                {report.no_category_activities.map((item) => (
                  <li key={item.activity_id}>{item.activity_name}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      </Card>

      <Card>
        <CardTitle>合格情况统计</CardTitle>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>项目</TableHead>
              <TableHead>合格人数</TableHead>
              <TableHead>未合格人数</TableHead>
              <TableHead>合格率</TableHead>
              <TableHead className="w-1/3">进度</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {Object.entries(report.category_stats).map(([category, stats]) => (
              <TableRow key={category}>
                <TableCell>{category}</TableCell>
                <TableCell>{stats.qualified}</TableCell>
                <TableCell>{stats.unqualified}</TableCell>
                <TableCell>{stats.percentage}%</TableCell>
                <TableCell>
                  <ProgressBar percentage={stats.percentage} />
                </TableCell>
              </TableRow>
            ))}
            <TableRow>
              <TableCell>
                <strong>总学分</strong>
              </TableCell>
              <TableCell>{report.total_stats.qualified}</TableCell>
              <TableCell>{report.total_stats.unqualified}</TableCell>
              <TableCell>{report.total_stats.percentage}%</TableCell>
              <TableCell>
                <ProgressBar percentage={report.total_stats.percentage} />
              </TableCell>
            </TableRow>
            <TableRow>
              <TableCell>
                <strong>最终合格</strong>
              </TableCell>
              <TableCell>{report.final_stats.qualified}</TableCell>
              <TableCell>{report.final_stats.unqualified}</TableCell>
              <TableCell>{report.final_stats.percentage}%</TableCell>
              <TableCell>
                <ProgressBar percentage={report.final_stats.percentage} />
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </Card>

      <Card>
        <CardTitle>分数段统计</CardTitle>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>分数段</TableHead>
              <TableHead>人数</TableHead>
              <TableHead>比例</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {Object.entries(report.score_ranges).map(([range, count]) => (
              <TableRow key={range}>
                <TableCell>{range}</TableCell>
                <TableCell>{count}</TableCell>
                <TableCell>
                  {report.total_students > 0
                    ? ((count / report.total_students) * 100).toFixed(1)
                    : 0}
                  %
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>

      {isSystemAdmin && report.students ? (
        <Card>
          <CardTitle>学生列表</CardTitle>
          <div className="mb-3 flex items-center gap-2 text-sm">
            <span>排序：</span>
            <Button size="sm" variant="secondary" onClick={() => setSortKey("student_id")}>
              按学号
            </Button>
            <Button size="sm" variant="secondary" onClick={() => setSortKey("student_name")}>
              按姓名
            </Button>
            <Button size="sm" variant="secondary" onClick={() => setSortKey("total_credits")}>
              按总学分
            </Button>
            <Button size="sm" variant="secondary" onClick={() => setSortKey("final_qualified")}>
              按合格状态
            </Button>
          </div>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>学号</TableHead>
                <TableHead>姓名</TableHead>
                <TableHead>总学分</TableHead>
                <TableHead>最终合格</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sortedStudents.map((student) => (
                <TableRow key={student.student_id}>
                  <TableCell>{student.student_id}</TableCell>
                  <TableCell>{student.student_name}</TableCell>
                  <TableCell>{student.total_credits}</TableCell>
                  <TableCell>
                    <QualifiedBadge qualified={student.final_qualified} mark />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      ) : null}
    </div>
  );
}

function sortReportStudents(students: ReportStudent[], key: SortKey): ReportStudent[] {
  return [...students].sort((a, b) => {
    if (key === "student_id" || key === "student_name") {
      return a[key].localeCompare(b[key]);
    }
    if (key === "total_credits") {
      return b.total_credits - a.total_credits;
    }
    return Number(b.final_qualified) - Number(a.final_qualified);
  });
}
