import { useEffect, useState } from "react";
import { toast } from "sonner";
import { FileSpreadsheet } from "lucide-react";
import { downloadFile, errorMessage } from "@/api/client";
import { getAllStudentsCredits } from "@/api/service";
import type { AllStudentCredits } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
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

/** 数据导出（仅系统管理员）：Excel 导出 + 全员学分概览。 */
export function ExportSection() {
  const [students, setStudents] = useState<AllStudentCredits[]>([]);
  const [search, setSearch] = useState("");

  useEffect(() => {
    getAllStudentsCredits()
      .then((data) => {
        if (data.success) setStudents(data.students);
      })
      .catch((error) => toast.error(errorMessage(error, "加载失败")));
  }, []);

  const query = search.trim().toLowerCase();
  const filtered = query
    ? students.filter(
        (student) =>
          student.student_id.toLowerCase().includes(query) ||
          student.student_name.toLowerCase().includes(query),
      )
    : students;

  return (
    <section>
      <h2 className="text-xl font-semibold mb-3">数据导出</h2>
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
          <CardTitle>所有学生学分概览</CardTitle>
          <Input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="搜索学号或姓名..."
            className="max-w-xs mb-3"
          />
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
              <TableRow key={student.student_id}>
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
          </TableBody>
        </Table>
      </Card>
    </section>
  );
}
