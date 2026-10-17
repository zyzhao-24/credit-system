import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { FileDown, Search } from "lucide-react";
import { errorMessage } from "@/api/client";
import { getAdminReport, queryStudent } from "@/api/service";
import { printCreditReport } from "@/lib/printReport";
import type { AdminReport, CreditReport, ReportStudent } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
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

/** 数据报表：活动列表、合格统计、分数段、学生列表（可搜索并点开学分详情）。 */
export function ReportSection({ isSystemAdmin }: { isSystemAdmin: boolean }) {
  const [report, setReport] = useState<AdminReport | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("student_id");
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);

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

  const keyword = search.trim().toLowerCase();
  const students = sortReportStudents(report.students ?? [], sortKey).filter(
    (student) =>
      !keyword ||
      student.student_id.toLowerCase().includes(keyword) ||
      student.student_name.toLowerCase().includes(keyword),
  );

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
          <div className="mb-3 flex flex-wrap items-center gap-2 text-sm">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-[#999]" />
              <Input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="搜索学号或姓名"
                className="pl-8 w-56"
              />
            </div>
            <span className="ml-2">排序：</span>
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
              {students.map((student) => (
                <TableRow
                  key={student.student_id}
                  className="cursor-pointer hover:bg-[#f5f9fd]"
                  onClick={() => setSelectedId(student.student_id)}
                >
                  <TableCell>{student.student_id}</TableCell>
                  <TableCell>{student.student_name}</TableCell>
                  <TableCell>{student.total_credits}</TableCell>
                  <TableCell>
                    <QualifiedBadge qualified={student.final_qualified} mark />
                  </TableCell>
                </TableRow>
              ))}
              {students.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-[#999]">
                    没有匹配的学生
                  </TableCell>
                </TableRow>
              ) : null}
            </TableBody>
          </Table>
          <p className="mt-2 text-xs text-[#999]">点击学生行可查看学分详情并导出 PDF</p>
        </Card>
      ) : null}

      <StudentCreditDialog
        studentId={selectedId}
        onOpenChange={(open) => {
          if (!open) setSelectedId(null);
        }}
      />
    </div>
  );
}

/** 点击学生行后打开的学分详情对话框（含 PDF 导出）。 */
function StudentCreditDialog({
  studentId,
  onOpenChange,
}: {
  studentId: string | null;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={studentId !== null} onOpenChange={onOpenChange}>
      <DialogContent title="学生学分详情" className="max-w-3xl">
        {studentId ? <StudentCreditView key={studentId} studentId={studentId} /> : null}
      </DialogContent>
    </Dialog>
  );
}

function StudentCreditView({ studentId }: { studentId: string }) {
  const [result, setResult] = useState<CreditReport | null>(null);
  const [failed, setFailed] = useState(false);

  const load = useCallback(() => {
    queryStudent(studentId)
      .then((data) => {
        if (data.success) setResult(data);
        else {
          toast.error(data.message || "未找到该学生");
          setFailed(true);
        }
      })
      .catch((error) => {
        toast.error(errorMessage(error, "查询失败"));
        setFailed(true);
      });
  }, [studentId]);

  useEffect(load, [load]);

  if (failed) {
    return <p className="text-center text-[#999] py-6">加载失败</p>;
  }
  if (!result) {
    return <p className="text-center text-[#999] py-6">加载中...</p>;
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-end">
        <Button variant="secondary" size="sm" onClick={() => printCreditReport(result, "admin")}>
          <FileDown className="h-4 w-4" />
          导出PDF
        </Button>
      </div>

      <Card>
        <CardTitle>学生信息</CardTitle>
        <p className="text-sm leading-7">
          <strong>学号：</strong>
          {result.student_id}
        </p>
        <p className="text-sm leading-7">
          <strong>姓名：</strong>
          {result.student_name}
        </p>
      </Card>

      <Card>
        <CardTitle>总学分情况</CardTitle>
        <div className="text-sm leading-7">
          <p>
            <strong>已获得学分：</strong>
            {result.total_credits}
          </p>
          <p>
            <strong>合格学分：</strong>
            {result.total_required}
          </p>
          <p className="flex items-center gap-2">
            <strong>总学分状态：</strong>
            <QualifiedBadge qualified={result.total_qualified} />
          </p>
          <p className="flex items-center gap-2">
            <strong>所有类别状态：</strong>
            <QualifiedBadge qualified={result.all_categories_qualified} />
          </p>
          <p className="mt-2.5 flex items-center gap-2 border-t-2 border-[#ddd] pt-2.5">
            <strong>最终合格情况：</strong>
            <span className="text-base">
              <QualifiedBadge qualified={result.final_qualified} mark />
            </span>
          </p>
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
            {Object.entries(result.category_status).map(([category, status]) => (
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
            {result.activities.map((activity, index) => (
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
