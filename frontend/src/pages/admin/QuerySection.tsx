import { useState } from "react";
import { toast } from "sonner";
import { FileDown } from "lucide-react";
import { errorMessage } from "@/api/client";
import { queryStudent } from "@/api/service";
import { printCreditReport } from "@/lib/printReport";
import type { CreditReport } from "@/api/types";
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
import { Field } from "@/components/common";
import { QualifiedBadge } from "@/components/StatusBadge";

/** 学分查询（仅系统管理员）。 */
export function QuerySection() {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<CreditReport | null>(null);
  const [searching, setSearching] = useState(false);

  const search = async () => {
    setSearching(true);
    try {
      const data = await queryStudent(query.trim());
      if (data.success) {
        setResult(data);
      } else {
        toast.error(data.message || "未找到该学生");
        setResult(null);
      }
    } catch (error) {
      toast.error(errorMessage(error, "查询失败"));
      setResult(null);
    } finally {
      setSearching(false);
    }
  };

  return (
    <section>
      <h2 className="text-xl font-semibold mb-3">学生学分查询</h2>
      <div className="flex items-end gap-2 max-w-xl mb-6">
        <div className="flex-1">
          <Field label="输入学号或姓名">
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="学号或姓名"
              onKeyDown={(event) => {
                if (event.key === "Enter") search();
              }}
            />
          </Field>
        </div>
        <Button className="mb-4" onClick={search} disabled={searching}>
          {searching ? "查询中..." : "查询"}
        </Button>
        {result ? (
          <Button className="mb-4" variant="secondary" onClick={() => printCreditReport(result, "admin")}>
            <FileDown className="h-4 w-4" />
            导出PDF
          </Button>
        ) : null}
      </div>

      {result ? (
        <div className="flex flex-col gap-4">
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
      ) : null}
    </section>
  );
}
