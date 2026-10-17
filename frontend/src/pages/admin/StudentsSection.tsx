import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { ChevronDown, ChevronRight, FileDown } from "lucide-react";
import { downloadFile, errorMessage } from "@/api/client";
import {
  batchImportStudents,
  changeStudentPasswordByAdmin,
  createStudent,
  deleteStudent,
  getAdminStudentInfos,
  getAdminStudents,
  updateAdminStudentInfo,
} from "@/api/service";
import type { AdminStudent, AdminStudentInfo } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Input, Textarea } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EmptyState, Field } from "@/components/common";

const PHONE_PATTERN = /^1[3-9]\d{9}$/;

/** 学生管理标签页：学生列表（普通管理员只读）+ 报名信息（仅系统管理员）。 */
export function StudentsSection({ canEdit }: { canEdit: boolean }) {
  return (
    <div className="flex flex-col gap-8">
      <StudentsBlock canEdit={canEdit} />
      {canEdit ? <StudentInfosBlock /> : null}
    </div>
  );
}

// ========== 学生列表 ==========

function StudentsBlock({ canEdit }: { canEdit: boolean }) {
  const [students, setStudents] = useState<AdminStudent[]>([]);
  const [search, setSearch] = useState("");
  const [addOpen, setAddOpen] = useState(false);
  const [batchOpen, setBatchOpen] = useState(false);
  const [passwordTarget, setPasswordTarget] = useState<AdminStudent | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<AdminStudent | null>(null);

  const load = useCallback(() => {
    getAdminStudents()
      .then((data) => {
        if (data.success) setStudents(data.students);
      })
      .catch((error) => toast.error(errorMessage(error, "加载学生失败")));
  }, []);

  useEffect(load, [load]);

  const query = search.trim().toLowerCase();
  const filtered = query
    ? students.filter(
        (student) =>
          student.student_id.toLowerCase().includes(query) ||
          student.name.toLowerCase().includes(query),
      )
    : students;

  return (
    <section>
      <h2 className="text-xl font-semibold mb-3">学生管理</h2>
      {canEdit ? (
        <div className="flex flex-wrap gap-2 mb-3">
          <Button size="sm" onClick={() => setAddOpen(true)}>
            ➕ 添加学生
          </Button>
          <Button size="sm" variant="secondary" onClick={() => setBatchOpen(true)}>
            📋 批量导入
          </Button>
          <Button
            size="sm"
            variant="secondary"
            onClick={() => downloadFile("/api/admin/students/export_csv", "学生名单.csv")}
          >
            📥 导出CSV
          </Button>
        </div>
      ) : null}
      <Input
        value={search}
        onChange={(event) => setSearch(event.target.value)}
        placeholder="搜索学号或姓名..."
        className="max-w-xs mb-3"
      />
      <Card className="p-0 overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>学号</TableHead>
              <TableHead>姓名</TableHead>
              {canEdit ? <TableHead>操作</TableHead> : null}
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.map((student) => (
              <TableRow key={student.student_id}>
                <TableCell>{student.student_id}</TableCell>
                <TableCell>{student.name}</TableCell>
                {canEdit ? (
                  <TableCell>
                    <div className="flex gap-2">
                      <Button size="sm" variant="secondary" onClick={() => setPasswordTarget(student)}>
                        修改密码
                      </Button>
                      <Button size="sm" variant="danger" onClick={() => setDeleteTarget(student)}>
                        删除
                      </Button>
                    </div>
                  </TableCell>
                ) : null}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>

      <AddStudentDialog open={addOpen} onOpenChange={setAddOpen} onDone={load} />
      <BatchStudentDialog open={batchOpen} onOpenChange={setBatchOpen} onDone={load} />
      <ChangeStudentPasswordDialog
        target={passwordTarget}
        onOpenChange={(open) => !open && setPasswordTarget(null)}
      />
      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
        message="确定删除该学生？学生的学分记录将被保留。"
        onConfirm={async () => {
          if (!deleteTarget) return;
          try {
            const result = await deleteStudent(deleteTarget.student_id);
            if (result.success) {
              toast.success(result.message || "已删除");
              load();
            } else {
              toast.error(result.message || "删除失败");
            }
          } catch (error) {
            toast.error(errorMessage(error, "删除失败"));
          }
        }}
      />
    </section>
  );
}

function AddStudentDialog({
  open,
  onOpenChange,
  onDone,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onDone: () => void;
}) {
  const [studentId, setStudentId] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("123456");

  const submit = async () => {
    try {
      const result = await createStudent({ student_id: studentId.trim(), name: name.trim(), password });
      if (result.success) {
        toast.success(result.message || "添加成功");
        onOpenChange(false);
        setStudentId("");
        setName("");
        setPassword("123456");
        onDone();
      } else {
        toast.error(result.message || "添加失败");
      }
    } catch (error) {
      toast.error(errorMessage(error, "添加失败"));
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title="添加学生">
        <Field label="学号" required>
          <Input value={studentId} onChange={(e) => setStudentId(e.target.value)} />
        </Field>
        <Field label="姓名" required>
          <Input value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        <Field label="密码（默认123456）">
          <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </Field>
        <div className="flex gap-3 mt-2">
          <Button className="flex-1" onClick={submit}>
            添加
          </Button>
          <Button variant="secondary" className="flex-1" onClick={() => onOpenChange(false)}>
            取消
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function BatchStudentDialog({
  open,
  onOpenChange,
  onDone,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onDone: () => void;
}) {
  const [csvData, setCsvData] = useState("");

  const submit = async () => {
    try {
      const result = await batchImportStudents(csvData);
      if (result.success) {
        toast.success(
          `导入成功！新增: ${result.added}, 更新: ${result.updated}${
            result.errors.length > 0 ? `；错误: ${result.errors.join(", ")}` : ""
          }`,
        );
        onOpenChange(false);
        setCsvData("");
        onDone();
      } else {
        toast.error(result.message || "导入失败");
      }
    } catch (error) {
      toast.error(errorMessage(error, "导入失败"));
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title="批量导入学生">
        <p className="text-sm">格式：学号,姓名,密码（每行一个学生，无表头）</p>
        <p className="text-xs text-[#616161] mt-1 mb-3 leading-relaxed">
          • 学号只能包含数字（可含前导零）
          <br />• 密码可省略，默认为 123456
          <br />• 已有学生只有填写第三列密码才会更新密码
        </p>
        <Field label="学生数据">
          <Textarea
            rows={10}
            value={csvData}
            onChange={(event) => setCsvData(event.target.value)}
            placeholder={"学号,姓名,密码\n2021001,张三,123456\n2021002,李四,123456"}
          />
        </Field>
        <div className="flex gap-3 mt-2">
          <Button className="flex-1" onClick={submit}>
            导入
          </Button>
          <Button variant="secondary" className="flex-1" onClick={() => onOpenChange(false)}>
            取消
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function ChangeStudentPasswordDialog({
  target,
  onOpenChange,
}: {
  target: AdminStudent | null;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={target !== null} onOpenChange={onOpenChange}>
      <DialogContent title="修改学生密码">
        {target ? (
          <ChangeStudentPasswordForm target={target} onOpenChange={onOpenChange} />
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

function ChangeStudentPasswordForm({
  target,
  onOpenChange,
}: {
  target: AdminStudent;
  onOpenChange: (open: boolean) => void;
}) {
  const [password, setPassword] = useState("");

  const submit = async () => {
    if (!password) {
      toast.error("请输入新密码");
      return;
    }
    try {
      const result = await changeStudentPasswordByAdmin(target.student_id, password);
      if (result.success) {
        toast.success("密码修改成功");
        onOpenChange(false);
      } else {
        toast.error(result.message || "修改失败");
      }
    } catch (error) {
      toast.error(errorMessage(error, "修改失败"));
    }
  };

  return (
    <>
      <Field label="学号">
        <Input value={target.student_id} readOnly />
      </Field>
      <Field label="新密码" required>
        <Input value={password} onChange={(e) => setPassword(e.target.value)} />
      </Field>
      <div className="flex gap-3 mt-2">
        <Button className="flex-1" onClick={submit}>
          修改
        </Button>
        <Button variant="secondary" className="flex-1" onClick={() => onOpenChange(false)}>
          取消
        </Button>
      </div>
    </>
  );
}

// ========== 报名信息（学生档案的一部分） ==========

function StudentInfosBlock() {
  const [infos, setInfos] = useState<AdminStudentInfo[]>([]);
  const [expanded, setExpanded] = useState(false);
  const [search, setSearch] = useState("");
  const [editTarget, setEditTarget] = useState<AdminStudentInfo | null>(null);

  const load = useCallback(() => {
    getAdminStudentInfos()
      .then((data) => {
        if (data.success) {
          setInfos(data.students);
        } else {
          toast.error("加载失败");
        }
      })
      .catch((error) => toast.error(errorMessage(error, "加载报名信息失败")));
  }, []);

  useEffect(load, [load]);

  const query = search.trim().toLowerCase();
  const filtered = query
    ? infos.filter(
        (info) =>
          info.student_id.toLowerCase().includes(query) ||
          info.name.toLowerCase().includes(query) ||
          (info.phone ?? "").includes(query) ||
          (info.wechat ?? "").toLowerCase().includes(query),
      )
    : infos;

  return (
    <section>
      <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
        <button
          className="flex items-center gap-1 text-xl font-semibold cursor-pointer"
          onClick={() => setExpanded((prev) => !prev)}
        >
          {expanded ? <ChevronDown className="h-5 w-5" /> : <ChevronRight className="h-5 w-5" />}
          报名信息
        </button>
        <div className="flex gap-2">
          <Input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="搜索学号、姓名、手机号..."
            className="w-64"
          />
          <Button
            variant="success"
            size="sm"
            onClick={() =>
              downloadFile("/api/admin/students/info/export", "学生报名信息.csv")
            }
          >
            <FileDown className="h-4 w-4" />
            导出CSV
          </Button>
        </div>
      </div>

      {expanded ? (
        <>
          <div className="mb-4 rounded-lg border-l-4 border-primary bg-[#e3f2fd] px-3 py-3 text-sm">
            <strong>统计：</strong>总数：{infos.length}
            {filtered.length !== infos.length ? (
              <span className="ml-5">筛选结果：{filtered.length}</span>
            ) : null}
          </div>
          {filtered.length === 0 ? (
            <EmptyState
              icon="📝"
              text={infos.length === 0 ? "暂无学生" : "没有符合条件的学生"}
            />
          ) : (
            filtered.map((item) => (
              <StudentInfoCard
                key={item.student_id}
                item={item}
                onEdit={() => setEditTarget(item)}
              />
            ))
          )}
        </>
      ) : (
        <div className="rounded-lg border-l-4 border-primary bg-[#e3f2fd] px-3 py-3 text-sm">
          <strong>统计：</strong>总数：{infos.length}
        </div>
      )}

      <EditStudentInfoDialog
        target={editTarget}
        onOpenChange={(open) => !open && setEditTarget(null)}
        onDone={load}
      />
    </section>
  );
}

function StudentInfoCard({
  item,
  onEdit,
}: {
  item: AdminStudentInfo;
  onEdit: () => void;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <Card className="mb-4">
      <button className="w-full text-left cursor-pointer" onClick={() => setExpanded((prev) => !prev)}>
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-[#1976d2] flex items-center gap-1">
            {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
            {item.student_id} - {item.name}
          </h3>
          <span className="text-sm text-[#666]">{item.updated_at || "未填写"}</span>
        </div>
      </button>
      {expanded ? (
        <div className="mt-4 border-t-2 border-[#e0e0e0] pt-4">
          <div className="grid grid-cols-2 gap-4 mb-4 text-sm">
            <div>
              <strong>手机号：</strong>
              {item.phone || "-"}
            </div>
            <div>
              <strong>微信号：</strong>
              {item.wechat || "-"}
            </div>
          </div>
          <div className="mb-4 text-sm">
            <strong>建议：</strong>
            <div className="mt-1 rounded-md bg-[#f5f5f5] p-2.5 whitespace-pre-wrap break-words">
              {item.suggestion || "无"}
            </div>
          </div>
          <div className="flex gap-2">
            <Button size="sm" variant="secondary" onClick={onEdit}>
              编辑
            </Button>
          </div>
        </div>
      ) : null}
    </Card>
  );
}

function EditStudentInfoDialog({
  target,
  onOpenChange,
  onDone,
}: {
  target: AdminStudentInfo | null;
  onOpenChange: (open: boolean) => void;
  onDone: () => void;
}) {
  return (
    <Dialog open={target !== null} onOpenChange={onOpenChange}>
      <DialogContent title="编辑报名信息">
        {target ? (
          <EditStudentInfoForm target={target} onOpenChange={onOpenChange} onDone={onDone} />
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

function EditStudentInfoForm({
  target,
  onOpenChange,
  onDone,
}: {
  target: AdminStudentInfo;
  onOpenChange: (open: boolean) => void;
  onDone: () => void;
}) {
  const [phone, setPhone] = useState(target.phone || "");
  const [wechat, setWechat] = useState(target.wechat || "");
  const [suggestion, setSuggestion] = useState(target.suggestion || "");

  const submit = async () => {
    if (phone.trim() && !PHONE_PATTERN.test(phone.trim())) {
      toast.error("请输入正确的11位手机号码");
      return;
    }
    try {
      const result = await updateAdminStudentInfo({
        student_id: target.student_id,
        phone: phone.trim(),
        wechat: wechat.trim(),
        suggestion: suggestion.trim(),
      });
      if (result.success) {
        toast.success("保存成功");
        onOpenChange(false);
        onDone();
      } else {
        toast.error(result.message || "保存失败");
      }
    } catch (error) {
      toast.error(errorMessage(error, "保存失败"));
    }
  };

  return (
    <>
      <Field label="学号（只读）">
        <Input value={target.student_id} readOnly />
      </Field>
      <Field label="姓名（只读）">
        <Input value={target.name} readOnly />
      </Field>
      <Field label="手机号">
        <Input type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} />
      </Field>
      <Field label="微信号">
        <Input value={wechat} onChange={(e) => setWechat(e.target.value)} />
      </Field>
      <Field label="建议">
        <Textarea rows={3} value={suggestion} onChange={(e) => setSuggestion(e.target.value)} />
      </Field>
      <div className="flex gap-3 mt-2">
        <Button className="flex-1" onClick={submit}>
          保存
        </Button>
        <Button variant="secondary" className="flex-1" onClick={() => onOpenChange(false)}>
          取消
        </Button>
      </div>
    </>
  );
}
