import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { FileDown, FileSpreadsheet, Search } from "lucide-react";
import { downloadFile, errorMessage } from "@/api/client";
import { getAllStudentsCredits, queryStudent } from "@/api/service";
import { printCreditReport } from "@/lib/printReport";
import type { AllStudentCredits, CreditReport } from "@/api/types";
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
import { QualifiedBadge } from "@/components/StatusBadge";

type SortKey = "student_id" | "student_name" | "total_credits" | "final_qualified";

/** 合格情况（仅系统管理员）：Excel 导出 + 学生学分列表（搜索/排序/点开详情）。 */
export function QualificationSection() {
  const [students, setStudents] = useState<AllStudentCredits[]>([]);
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("student_id");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    getAllStudentsCredits()
      .then((data) => {
        if (data.success) setStudents(data.students);
      })
      .catch((error) => toast.error(errorMessage(error, "加载失败")));
  }, []);

  const keyword = search.trim().toLowerCase();
  const filtered = sortStudents(students, sortKey).filter(
    (student) =>
      !keyword ||
      student.student_id.toLowerCase().includes(keyword) ||
      student.student_name.toLowerCase().includes(keyword),
  );

  return (
    <section>
      <h2 className="text-xl font-semibold mb-3">合格情况</h2>
      <div className="mb-6">
        <Button
          variant="success"
          onClick={() => downloadFile("/api/admin/export", "学生学分统计.xlsx")}
        >
          <FileSpreadsheet className="h-4 w-4" />
          导出Excel
        </Button>
      </div>

      <Card className="p-0 overflow-hidden">
        <div className="p-5 pb-0">
          <CardTitle>学生学分列表</CardTitle>
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
        </div>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>学号</TableHead>
              <TableHead>姓名</TableHead>
              <TableHead>总学分</TableHead>
              <TableHead>总学分合格</TableHead>
              <TableHead>类别全合格</TableHead>
              <TableHead>最终合格</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.map((student) => (
              <TableRow
                key={student.student_id}
                className="cursor-pointer hover:bg-[#f5f9fd]"
                onClick={() => setSelectedId(student.student_id)}
              >
                <TableCell>{student.student_id}</TableCell>
                <TableCell>{student.student_name}</TableCell>
                <TableCell>{student.total_credits}</TableCell>
                <TableCell>
                  <QualifiedBadge qualified={student.total_qualified} />
                </TableCell>
                <TableCell>
                  <QualifiedBadge qualified={student.all_categories_qualified} />
                </TableCell>
                <TableCell>
                  <QualifiedBadge qualified={student.final_qualified} mark />
                </TableCell>
              </TableRow>
            ))}
            {filtered.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center text-[#999]">
                  没有匹配的学生
                </TableCell>
              </TableRow>
            ) : null}
          </TableBody>
        </Table>
        <p className="px-5 py-2 text-xs text-[#999]">点击学生行可查看学分详情并导出 PDF</p>
      </Card>

      <StudentCreditDialog
        studentId={selectedId}
        onOpenChange={(open) => {
          if (!open) setSelectedId(null);
        }}
      />
    </section>
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

function sortStudents(students: AllStudentCredits[], key: SortKey): AllStudentCredits[] {
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
