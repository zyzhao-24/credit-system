import type { CreditReport } from "@/api/types";

type PrintVariant = "student" | "admin";

const PALETTES: Record<
  PrintVariant,
  { border: string; light: string; lighter: string; text: string }
> = {
  student: { border: "#64B5F6", light: "#E3F2FD", lighter: "#BBDEFB", text: "#1565C0" },
  admin: { border: "#EF5350", light: "#FFEBEE", lighter: "#FFCDD2", text: "#C62828" },
};

function escapeHtml(value: unknown): string {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function badge(qualified: boolean, mark = true): string {
  const cls = qualified ? "status-qualified" : "status-unqualified";
  const text = qualified ? `${mark ? "✓ " : ""}已合格` : `${mark ? "✗ " : ""}未合格`;
  return `<span class="status-badge ${cls}">${text}</span>`;
}

function buildPrintHtml(data: CreditReport, variant: PrintVariant): string {
  void variant;
  const now = new Date().toLocaleString("zh-CN");
  const categoryRows = Object.entries(data.category_status ?? {})
    .map(
      ([name, status]) => `<tr>
        <td>${escapeHtml(name)}</td>
        <td>${status.credits}</td>
        <td>${status.required}</td>
        <td>${badge(status.qualified)}</td>
      </tr>`,
    )
    .join("");
  const activityRows = (data.activities ?? [])
    .map(
      (activity) => `<tr>
        <td>${escapeHtml(activity.activity_name)}</td>
        <td>${escapeHtml(activity.record_name)}</td>
        <td>${activity.credits}</td>
        <td>${escapeHtml((activity.categories ?? []).join(", "))}</td>
        <td>${escapeHtml(activity.assigned_category || "-")}</td>
      </tr>`,
    )
    .join("");

  return `
    <div class="print-title">团校积分系统 - 学分报告</div>
    <div class="print-info">
      <strong>学号：</strong>${escapeHtml(data.student_id)} &nbsp;&nbsp;&nbsp;
      <strong>姓名：</strong>${escapeHtml(data.student_name)} &nbsp;&nbsp;&nbsp;
      <strong>导出时间：</strong>${escapeHtml(now)}
    </div>
    <div class="info-card">
      <h3>总学分情况</h3>
      <p><strong>已获得学分：</strong>${data.total_credits ?? 0}</p>
      <p><strong>合格学分：</strong>${data.total_required ?? 0}</p>
      <p><strong>总学分状态：</strong>${badge(Boolean(data.total_qualified))}</p>
      <p><strong>所有类别状态：</strong>${badge(Boolean(data.all_categories_qualified))}</p>
    </div>
    <div class="info-card">
      <h3>各类别学分情况</h3>
      <table>
        <thead><tr><th>类别名称</th><th>已获学分</th><th>合格学分</th><th>状态</th></tr></thead>
        <tbody>${categoryRows}</tbody>
      </table>
    </div>
    <div class="info-card">
      <h3>参与活动详情</h3>
      <table>
        <thead><tr><th>活动名称</th><th>记录名称</th><th>学分</th><th>可选类别</th><th>计入类别</th></tr></thead>
        <tbody>${activityRows}</tbody>
      </table>
    </div>
    <div class="info-card" style="text-align: center; font-size: 18px; font-weight: bold;">
      最终合格状态：${badge(Boolean(data.final_qualified))}
    </div>
  `;
}

function buildPrintStyle(variant: PrintVariant): string {
  const palette = PALETTES[variant];
  return `
    .print-title {
      text-align: center; font-size: 20px; font-weight: bold;
      margin-bottom: 12px; border-bottom: 2px solid ${palette.text};
      padding-bottom: 6px; color: ${palette.text};
    }
    .print-info {
      margin-bottom: 10px; padding: 8px; border: 1px solid ${palette.border};
      border-radius: 4px; background: ${palette.light} !important;
    }
    .print-area .info-card {
      margin-bottom: 10px; padding: 8px; border: 1px solid ${palette.border};
      border-radius: 4px; background: ${palette.lighter} !important;
      page-break-inside: avoid;
    }
    .print-area .info-card h3 { margin: 0 0 6px 0; font-size: 15px; color: ${palette.text}; }
    .print-area .info-card p { margin: 3px 0; font-size: 13px; }
    .print-area .status-badge {
      display: inline-block; padding: 2px 8px; font-size: 12px; border-radius: 3px;
    }
    .print-area .status-qualified { background: #d4edda !important; color: #155724 !important; }
    .print-area .status-unqualified { background: #f8d7da !important; color: #721c24 !important; }
    .print-area table {
      width: 100%; border-collapse: collapse; margin: 6px 0;
      font-size: 12px; border: 1px solid ${palette.border};
    }
    .print-area th, .print-area td {
      border: 1px solid ${palette.lighter}; padding: 5px 6px; text-align: left;
    }
    .print-area th { font-weight: bold; background: ${palette.light} !important; color: ${palette.text}; }
  `;
}

/** 通过浏览器打印对话框导出学分报告（用户可另存为 PDF）。 */
export function printCreditReport(data: CreditReport, variant: PrintVariant): void {
  const style = document.createElement("style");
  style.textContent = buildPrintStyle(variant);
  document.head.appendChild(style);

  const printArea = document.createElement("div");
  printArea.className = "print-area";
  printArea.innerHTML = buildPrintHtml(data, variant);
  document.body.appendChild(printArea);

  window.print();

  window.setTimeout(() => {
    document.body.removeChild(printArea);
    document.head.removeChild(style);
  }, 100);
}
