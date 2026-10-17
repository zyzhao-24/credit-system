import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { FileDown } from "lucide-react";
import { downloadFile, errorMessage } from "@/api/client";
import {
  batchImportStudents,
  changeStudentPasswordByAdmin,
  createStudent,
  deleteStudent,
  getAdminStudents,
  resetStudentOtp,
  updateAdminStudentInfo,
} from "@/api/service";
import type { AdminStudent } from "@/api/types";
import { Button } from "@/components/ui/button";
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
import { Field } from "@/components/common";

const PHONE_PATTERN = /^1[3-9]\d{9}$/;

/** 学生管理标签页：学生列表（含联系方式，普通管理员只读且不见联系方式）。 */
export function StudentsSection({ canEdit }: { canEdit: boolean }) {
  const [students, setStudents] = useState<AdminStudent[]>([]);
  const [search, setSearch] = useState("");
  const [addOpen, setAddOpen] = useState(false);
  const [batchOpen, setBatchOpen] = useState(false);
  const [detailTarget, setDetailTarget] = useState<AdminStudent | null>(null);
  const [passwordTarget, setPasswordTarget] = useState<AdminStudent | null>(null);
  const [resetOtpTarget, setResetOtpTarget] = useState<AdminStudent | null>(null);
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
          student.name.toLowerCase().includes(query) ||
          (student.phone ?? "").includes(query) ||
          (student.wechat ?? "").toLowerCase().includes(query),
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
            variant="success"
            onClick={() => downloadFile("/api/admin/students/info/export", "学生报名信息.xlsx")}
          >
            <FileDown className="h-4 w-4" />
            导出报名信息
          </Button>
        </div>
      ) : null}
      <Input
        value={search}
        onChange={(event) => setSearch(event.target.value)}
        placeholder={
          canEdit ? "搜索学号、姓名、手机号、微信号..." : "搜索学号或姓名..."
        }
        className="max-w-xs mb-3"
      />
      <div className="rounded-xl bg-white shadow-[0_2px_8px_rgba(0,0,0,0.05)] overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>学号</TableHead>
              <TableHead>姓名</TableHead>
              {canEdit ? <TableHead>手机号</TableHead> : null}
              {canEdit ? <TableHead>微信号</TableHead> : null}
              {canEdit ? <TableHead>OTP</TableHead> : null}
              {canEdit ? <TableHead>操作</TableHead> : null}
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.map((student) => (
              <TableRow key={student.student_id}>
                <TableCell>{student.student_id}</TableCell>
                <TableCell>{student.name}</TableCell>
                {canEdit ? <TableCell>{student.phone || "-"}</TableCell> : null}
                {canEdit ? <TableCell>{student.wechat || "-"}</TableCell> : null}
                {canEdit ? (
                  <TableCell>
                    {student.has_otp ? (
                      <span className="text-success">已绑定</span>
                    ) : (
                      <span className="text-danger">未绑定</span>
                    )}
                  </TableCell>
                ) : null}
                {canEdit ? (
                  <TableCell>
                    <div className="flex flex-wrap gap-2">
                      <Button size="sm" variant="secondary" onClick={() => setDetailTarget(student)}>
                        详情
                      </Button>
                      <Button size="sm" variant="secondary" onClick={() => setPasswordTarget(student)}>
                        重设密码
                      </Button>
                      <Button size="sm" variant="secondary" onClick={() => setResetOtpTarget(student)}>
                        重置 OTP
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
      </div>

      <AddStudentDialog open={addOpen} onOpenChange={setAddOpen} onDone={load} />
      <BatchStudentDialog open={batchOpen} onOpenChange={setBatchOpen} onDone={load} />
      <StudentDetailDialog
        target={detailTarget}
        onOpenChange={(open) => !open && setDetailTarget(null)}
        onDone={load}
      />
      <ChangeStudentPasswordDialog
        target={passwordTarget}
        onOpenChange={(open) => !open && setPasswordTarget(null)}
      />
      <ConfirmDialog
        open={resetOtpTarget !== null}
        onOpenChange={(open) => !open && setResetOtpTarget(null)}
        message={`确定重置学生"${resetOtpTarget?.name ?? ""}"的动态验证码？该学生的 OTP 将立即变为未绑定状态，其下次登录时会自动通过学号邮箱重新绑定。`}
        onConfirm={async () => {
          if (!resetOtpTarget) return;
          try {
            const result = await resetStudentOtp(resetOtpTarget.student_id);
            if (result.success) {
              toast.success(result.message || "已重置为未绑定状态");
              load();
            } else {
              toast.error(result.message || "重置失败");
            }
          } catch (error) {
            toast.error(errorMessage(error, "重置失败"));
          }
        }}
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

/** 完整报名信息弹窗：查看并可编辑手机号/微信号/建议。 */
function StudentDetailDialog({
  target,
  onOpenChange,
  onDone,
}: {
  target: AdminStudent | null;
  onOpenChange: (open: boolean) => void;
  onDone: () => void;
}) {
  return (
    <Dialog open={target !== null} onOpenChange={onOpenChange}>
      <DialogContent title="学生详情">
        {target ? (
          <StudentDetailForm
            key={target.student_id}
            target={target}
            onOpenChange={onOpenChange}
            onDone={onDone}
          />
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

function StudentDetailForm({
  target,
  onOpenChange,
  onDone,
}: {
  target: AdminStudent;
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
      <Field label="学号">
        <Input value={target.student_id} readOnly />
      </Field>
      <Field label="姓名">
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
      {target.updated_at ? (
        <Field label="最近更新">
          <Input value={target.updated_at} readOnly />
        </Field>
      ) : null}
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

function ChangeStudentPasswordDialog({
  target,
  onOpenChange,
}: {
  target: AdminStudent | null;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={target !== null} onOpenChange={onOpenChange}>
      <DialogContent title="重设学生密码">
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
