import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { errorMessage } from "@/api/client";
import {
  createAdmin,
  createCategory,
  createDepartment,
  deleteAdmin,
  deleteCategory,
  deleteDepartment,
  getAdminCategories,
  getAdmins,
  getDepartments,
  getEmailConfig,
  getTotalCredits,
  saveEmailConfig,
  saveTotalCredits,
  sendTestEmail,
  updateAdmin,
} from "@/api/service";
import { useAuth } from "@/auth/auth-context";
import type { AdminAccount, AdminCategory, EmailConfig } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Input, Select } from "@/components/ui/input";
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

/** 系统设置标签页（仅系统管理员）：类别、总学分、邮箱、部门、管理员账号。 */
export function SettingsSection() {
  const { user } = useAuth();

  return (
    <div className="flex flex-col gap-8">
      <CategoriesBlock />
      <TotalCreditsBlock />
      <EmailConfigBlock />
      <DepartmentsBlock />
      <AdminsBlock currentAdminId={user?.sub ?? ""} />
    </div>
  );
}

// ========== 类别管理 ==========

function CategoriesBlock() {
  const [categories, setCategories] = useState<AdminCategory[]>([]);
  const [addOpen, setAddOpen] = useState(false);
  const [name, setName] = useState("");
  const [credits, setCredits] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);

  const load = useCallback(() => {
    getAdminCategories()
      .then((data) => {
        if (data.success) setCategories(data.categories);
      })
      .catch((error) => toast.error(errorMessage(error, "加载类别失败")));
  }, []);

  useEffect(load, [load]);

  const submit = async () => {
    try {
      const result = await createCategory({
        name: name.trim(),
        required_credits: parseFloat(credits) || 0,
      });
      if (result.success) {
        setAddOpen(false);
        setName("");
        setCredits("");
        load();
      } else {
        toast.error(result.message || "添加失败");
      }
    } catch (error) {
      toast.error(errorMessage(error, "添加失败"));
    }
  };

  return (
    <section>
      <h2 className="text-xl font-semibold mb-3">类别管理</h2>
      <div className="mb-3">
        <Button size="sm" onClick={() => setAddOpen(true)}>
          ➕ 添加类别
        </Button>
      </div>
      <Card className="p-0 overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>类别名称</TableHead>
              <TableHead>合格学分</TableHead>
              <TableHead>操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {categories.map((category) => (
              <TableRow key={category.name}>
                <TableCell>{category.name}</TableCell>
                <TableCell>{category.required_credits}</TableCell>
                <TableCell>
                  <Button size="sm" variant="danger" onClick={() => setDeleteTarget(category.name)}>
                    删除
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>

      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent title="添加类别">
          <Field label="类别名称" required>
            <Input value={name} onChange={(e) => setName(e.target.value)} />
          </Field>
          <Field label="合格学分" required>
            <Input type="number" value={credits} onChange={(e) => setCredits(e.target.value)} />
          </Field>
          <div className="flex gap-3 mt-2">
            <Button className="flex-1" onClick={submit}>
              添加
            </Button>
            <Button variant="secondary" className="flex-1" onClick={() => setAddOpen(false)}>
              取消
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
        message="确定删除该类别？"
        onConfirm={async () => {
          if (!deleteTarget) return;
          try {
            const result = await deleteCategory(deleteTarget);
            if (result.success) {
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

// ========== 总学分设置 ==========

function TotalCreditsBlock() {
  const [value, setValue] = useState("");

  useEffect(() => {
    getTotalCredits()
      .then((data) => {
        if (data.success) setValue(String(data.total_required_credits));
      })
      .catch((error) => toast.error(errorMessage(error, "加载总学分失败")));
  }, []);

  const save = async () => {
    try {
      const result = await saveTotalCredits(parseFloat(value) || 0);
      if (result.success) toast.success("保存成功");
      else toast.error(result.message || "保存失败");
    } catch (error) {
      toast.error(errorMessage(error, "保存失败"));
    }
  };

  return (
    <section>
      <h2 className="text-xl font-semibold mb-3">总学分设置</h2>
      <div className="flex items-end gap-3">
        <Field label="合格所需总学分">
          <Input
            type="number"
            value={value}
            onChange={(event) => setValue(event.target.value)}
            className="max-w-[200px]"
          />
        </Field>
        <Button className="mb-4" onClick={save}>
          保存
        </Button>
      </div>
    </section>
  );
}

// ========== 邮箱配置 ==========

function EmailConfigBlock() {
  const [config, setConfig] = useState<EmailConfig | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [suffix, setSuffix] = useState("");
  const [showSavedPassword, setShowSavedPassword] = useState(false);
  const [testOpen, setTestOpen] = useState(false);

  useEffect(() => {
    getEmailConfig()
      .then((data) => {
        if (data.success) {
          setConfig(data.email_config);
          setEmail(data.email_config.service_email || "");
          setSuffix(data.email_config.student_email_suffix || "");
        }
      })
      .catch((error) => toast.error(errorMessage(error, "加载邮箱配置失败")));
  }, []);

  const save = async () => {
    const trimmedEmail = email.trim();
    const trimmedSuffix = suffix.trim();
    if (trimmedEmail && !trimmedEmail.includes("@")) {
      toast.error("请输入有效的服务邮箱地址");
      return;
    }
    if (trimmedSuffix && !trimmedSuffix.startsWith("@")) {
      toast.error("学生邮箱后缀应以@开头，如：@example.com");
      return;
    }
    try {
      const result = await saveEmailConfig({
        service_email: trimmedEmail,
        service_email_password: password,
        student_email_suffix: trimmedSuffix,
      });
      if (result.success) {
        toast.success("邮箱配置保存成功");
        if (password) {
          setConfig((prev) =>
            prev ? { ...prev, has_password: true, service_email_password: password } : prev,
          );
        }
        setPassword("");
      } else {
        toast.error(result.message || "保存失败");
      }
    } catch (error) {
      toast.error(errorMessage(error, "保存失败"));
    }
  };

  const savedPassword = config?.service_email_password ?? "";

  return (
    <section>
      <h2 className="text-xl font-semibold mb-3">邮箱配置</h2>
      <Card>
        <Field label="服务邮箱">
          <Input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="用于发送密码重置邮件"
          />
        </Field>
        {config?.has_password ? (
          <Field label="当前已保存的密码/授权码">
            <div className="flex gap-2">
              <Input
                type={showSavedPassword ? "text" : "password"}
                value={savedPassword}
                readOnly
                className="flex-1 bg-[#f5f5f5]"
              />
              <Button
                type="button"
                variant="secondary"
                onClick={() => setShowSavedPassword((v) => !v)}
              >
                {showSavedPassword ? "隐藏" : "显示"}
              </Button>
            </div>
          </Field>
        ) : null}
        <Field label="服务邮箱密码/授权码">
          <Input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder={
              config?.has_password ? "输入新值以更改，留空保持不变" : "邮箱密码或SMTP授权码"
            }
          />
        </Field>
        <Field label="学生邮箱后缀">
          <Input
            value={suffix}
            onChange={(event) => setSuffix(event.target.value)}
            placeholder="如：@example.com"
          />
        </Field>
        <div className="flex gap-3 items-center">
          <Button onClick={save}>保存邮箱配置</Button>
          <Button variant="secondary" onClick={() => setTestOpen(true)}>
            测试邮箱配置
          </Button>
        </div>
        <p className="text-sm text-[#666] mt-2">💡 提示：QQ邮箱需使用授权码，163邮箱需开启SMTP服务</p>
        <p className="text-sm text-danger mt-1">⚠️ 注意：Outlook个人邮箱已禁用SMTP，建议使用QQ或163邮箱</p>
      </Card>
      <TestEmailDialog open={testOpen} onOpenChange={setTestOpen} />
    </section>
  );
}

function TestEmailDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [address, setAddress] = useState("");
  const [debug, setDebug] = useState(false);
  const [debugInfo, setDebugInfo] = useState<string[]>([]);
  const [sending, setSending] = useState(false);

  const send = async () => {
    const trimmed = address.trim();
    if (!trimmed) return toast.error("请输入测试邮箱地址");
    if (!trimmed.includes("@")) return toast.error("请输入有效的邮箱地址");
    setSending(true);
    setDebugInfo([]);
    try {
      const result = await sendTestEmail(trimmed, debug);
      if (debug && result.debug_info) {
        setDebugInfo(result.debug_info);
      }
      if (result.success) {
        toast.success(result.message || "发送成功");
        if (!debug) onOpenChange(false);
      } else {
        toast.error(result.message || "测试失败");
      }
    } catch (error) {
      toast.error(errorMessage(error, "测试失败"));
    } finally {
      setSending(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title="测试邮箱配置">
        <p className="text-sm text-[#666] -mt-2 mb-4">发送测试邮件以验证邮箱配置是否正确</p>
        <Field label="测试邮箱地址" required>
          <Input
            type="email"
            value={address}
            onChange={(event) => setAddress(event.target.value)}
            placeholder="输入接收测试邮件的邮箱"
          />
        </Field>
        <label className="flex items-center gap-2 cursor-pointer text-sm mb-4">
          <Checkbox checked={debug} onCheckedChange={(checked) => setDebug(checked === true)} />
          <span>显示调试信息</span>
        </label>
        <div className="flex gap-3">
          <Button className="flex-1" onClick={send} disabled={sending}>
            {sending ? "发送中..." : "发送测试邮件"}
          </Button>
          <Button variant="secondary" className="flex-1" onClick={() => onOpenChange(false)}>
            取消
          </Button>
        </div>
        {debugInfo.length > 0 ? (
          <div className="mt-5 max-h-[300px] overflow-y-auto rounded-md bg-[#f5f5f5] p-3 font-mono text-xs">
            {debugInfo.map((line, index) => (
              <div key={index}>{line}</div>
            ))}
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

// ========== 部门管理 ==========

function DepartmentsBlock() {
  const [departments, setDepartments] = useState<string[]>([]);
  const [addOpen, setAddOpen] = useState(false);
  const [name, setName] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);

  const load = useCallback(() => {
    getDepartments()
      .then((data) => {
        if (data.success) setDepartments(data.departments);
      })
      .catch((error) => toast.error(errorMessage(error, "加载部门失败")));
  }, []);

  useEffect(load, [load]);

  const submit = async () => {
    if (!name.trim()) {
      toast.error("请输入部门名称");
      return;
    }
    try {
      const result = await createDepartment(name.trim());
      if (result.success) {
        setAddOpen(false);
        setName("");
        load();
      } else {
        toast.error(result.message || "添加失败");
      }
    } catch (error) {
      toast.error(errorMessage(error, "添加失败"));
    }
  };

  return (
    <section>
      <h2 className="text-xl font-semibold mb-3">部门管理</h2>
      <div className="mb-3">
        <Button size="sm" onClick={() => setAddOpen(true)}>
          ➕ 添加部门
        </Button>
      </div>
      <Card className="p-0 overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>部门名称</TableHead>
              <TableHead>操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {departments.map((department) => (
              <TableRow key={department}>
                <TableCell>{department}</TableCell>
                <TableCell>
                  <Button size="sm" variant="danger" onClick={() => setDeleteTarget(department)}>
                    删除
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>

      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent title="添加部门">
          <Field label="部门名称" required>
            <Input value={name} onChange={(e) => setName(e.target.value)} />
          </Field>
          <div className="flex gap-3 mt-2">
            <Button className="flex-1" onClick={submit}>
              添加
            </Button>
            <Button variant="secondary" className="flex-1" onClick={() => setAddOpen(false)}>
              取消
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
        message={`确定删除部门"${deleteTarget ?? ""}"？`}
        onConfirm={async () => {
          if (!deleteTarget) return;
          try {
            const result = await deleteDepartment(deleteTarget);
            if (result.success) load();
            else toast.error(result.message || "删除失败");
          } catch (error) {
            toast.error(errorMessage(error, "删除失败"));
          }
        }}
      />
    </section>
  );
}

// ========== 管理员账号管理 ==========

function AdminsBlock({ currentAdminId }: { currentAdminId: string }) {
  const [admins, setAdmins] = useState<AdminAccount[]>([]);
  const [departments, setDepartments] = useState<string[]>([]);
  const [addOpen, setAddOpen] = useState(false);
  const [passwordTarget, setPasswordTarget] = useState<AdminAccount | null>(null);
  const [departmentTarget, setDepartmentTarget] = useState<AdminAccount | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<AdminAccount | null>(null);

  const load = useCallback(() => {
    getAdmins()
      .then((data) => {
        if (data.success) setAdmins(data.admins);
      })
      .catch((error) => toast.error(errorMessage(error, "加载管理员失败")));
    getDepartments()
      .then((data) => {
        if (data.success) setDepartments(data.departments);
      })
      .catch(() => undefined);
  }, []);

  useEffect(load, [load]);

  return (
    <section>
      <h2 className="text-xl font-semibold mb-3">管理员账号管理</h2>
      <div className="mb-3">
        <Button size="sm" onClick={() => setAddOpen(true)}>
          ➕ 添加管理员
        </Button>
      </div>
      <Card className="p-0 overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>账号</TableHead>
              <TableHead>角色</TableHead>
              <TableHead>部门</TableHead>
              <TableHead>操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {admins.map((admin) => {
              const isSelf = admin.admin_id === currentAdminId;
              const isSystem = admin.role === "system_admin";
              return (
                <TableRow key={admin.admin_id}>
                  <TableCell>{admin.admin_id}</TableCell>
                  <TableCell>{isSystem ? "系统管理员" : "管理员"}</TableCell>
                  <TableCell>{admin.department || "-"}</TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-2">
                      <Button size="sm" variant="secondary" onClick={() => setPasswordTarget(admin)}>
                        修改密码
                      </Button>
                      {!isSelf ? (
                        <Button size="sm" variant="secondary" onClick={() => setDepartmentTarget(admin)}>
                          修改部门
                        </Button>
                      ) : null}
                      {!isSystem ? (
                        <Button size="sm" variant="danger" onClick={() => setDeleteTarget(admin)}>
                          删除
                        </Button>
                      ) : null}
                    </div>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </Card>

      <AddAdminDialog
        open={addOpen}
        onOpenChange={setAddOpen}
        departments={departments}
        onDone={load}
      />
      <AdminPasswordDialog
        target={passwordTarget}
        onOpenChange={(open) => !open && setPasswordTarget(null)}
      />
      <AdminDepartmentDialog
        target={departmentTarget}
        onOpenChange={(open) => !open && setDepartmentTarget(null)}
        departments={departments}
      />
      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
        message={`确定删除管理员"${deleteTarget?.admin_id ?? ""}"？`}
        onConfirm={async () => {
          if (!deleteTarget) return;
          try {
            const result = await deleteAdmin(deleteTarget.admin_id);
            if (result.success) load();
            else toast.error(result.message || "删除失败");
          } catch (error) {
            toast.error(errorMessage(error, "删除失败"));
          }
        }}
      />
    </section>
  );
}

function AddAdminDialog({
  open,
  onOpenChange,
  departments,
  onDone,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  departments: string[];
  onDone: () => void;
}) {
  const [adminId, setAdminId] = useState("");
  const [password, setPassword] = useState("admin123");
  const [department, setDepartment] = useState("");

  const submit = async () => {
    if (!adminId.trim()) {
      toast.error("请输入账号");
      return;
    }
    try {
      const result = await createAdmin({
        admin_id: adminId.trim(),
        password,
        role: "admin",
        department,
      });
      if (result.success) {
        onOpenChange(false);
        setAdminId("");
        setPassword("admin123");
        setDepartment("");
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
      <DialogContent title="添加管理员">
        <Field label="账号" required>
          <Input value={adminId} onChange={(e) => setAdminId(e.target.value)} />
        </Field>
        <Field label="密码">
          <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </Field>
        <Field label="部门">
          <Select value={department} onChange={(e) => setDepartment(e.target.value)}>
            <option value="">无</option>
            {departments.map((dept) => (
              <option key={dept} value={dept}>
                {dept}
              </option>
            ))}
          </Select>
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

function AdminPasswordDialog({
  target,
  onOpenChange,
}: {
  target: AdminAccount | null;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={target !== null} onOpenChange={onOpenChange}>
      <DialogContent title="修改管理员密码">
        {target ? <AdminPasswordForm target={target} onOpenChange={onOpenChange} /> : null}
      </DialogContent>
    </Dialog>
  );
}

function AdminPasswordForm({
  target,
  onOpenChange,
}: {
  target: AdminAccount;
  onOpenChange: (open: boolean) => void;
}) {
  const [password, setPassword] = useState("");

  const submit = async () => {
    if (!password) {
      toast.error("请输入新密码");
      return;
    }
    try {
      const result = await updateAdmin({ admin_id: target.admin_id, password });
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
      <Field label="账号">
        <Input value={target.admin_id} readOnly />
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

function AdminDepartmentDialog({
  target,
  onOpenChange,
  departments,
}: {
  target: AdminAccount | null;
  onOpenChange: (open: boolean) => void;
  departments: string[];
}) {
  return (
    <Dialog open={target !== null} onOpenChange={onOpenChange}>
      <DialogContent title="修改管理员部门">
        {target ? (
          <AdminDepartmentForm
            target={target}
            onOpenChange={onOpenChange}
            departments={departments}
          />
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

function AdminDepartmentForm({
  target,
  onOpenChange,
  departments,
}: {
  target: AdminAccount;
  onOpenChange: (open: boolean) => void;
  departments: string[];
}) {
  const [department, setDepartment] = useState(target.department || "");

  const submit = async () => {
    try {
      const result = await updateAdmin({ admin_id: target.admin_id, department });
      if (result.success) {
        toast.success("部门修改成功");
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
      <Field label="账号">
        <Input value={target.admin_id} readOnly />
      </Field>
      <Field label="所属部门">
        <Select value={department} onChange={(e) => setDepartment(e.target.value)}>
          <option value="">无</option>
          {departments.map((dept) => (
            <option key={dept} value={dept}>
              {dept}
            </option>
          ))}
        </Select>
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
