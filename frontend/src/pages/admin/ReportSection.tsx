import { useEffect, useState } from "react";
import { toast } from "sonner";
import { errorMessage } from "@/api/client";
import { getAdminReport } from "@/api/service";
import type { AdminReport } from "@/api/types";
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

/** 数据报表：活动列表、合格统计、分数段。学生学分列表在“合格情况”标签页。 */
export function ReportSection() {
  const [report, setReport] = useState<AdminReport | null>(null);

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
    </div>
  );
}
