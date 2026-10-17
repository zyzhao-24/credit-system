import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { errorMessage } from "@/api/client";
import {
  confirmAdminOtpReset,
  createAdmin,
  createCategory,
  createDepartment,
  deleteAdmin,
  deleteCategory,
  deleteDepartment,
  getAdminCategories,
  getAdmins,
  getDepartments,
  getTotalCredits,
  resetAdminOtp,
  saveTotalCredits,
  updateAdmin,
} from "@/api/service";
import { useAuth } from "@/auth/auth-context";
import type { AdminAccount, AdminCategory, AdminOtpBundle, OtpBindChallenge } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
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
import { OtpBundleDialog } from "@/components/OtpBundleDialog";
import { Field } from "@/components/common";

/** 系统设置标签页（仅系统管理员）：类别、总学分、部门、管理员账号。
 *  邮件服务配置已移至本机专用维护页 /local/system，不在此出现。 */
export function SettingsSection() {
  const { user } = useAuth();

  return (
    <div className="flex flex-col gap-8">
      <CategoriesBlock />
      <TotalCreditsBlock />
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

const SYSTEM_ADMIN_ID = "system";

function AdminsBlock({ currentAdminId }: { currentAdminId: string }) {
  const [admins, setAdmins] = useState<AdminAccount[]>([]);
  const [departments, setDepartments] = useState<string[]>([]);
  const [addOpen, setAddOpen] = useState(false);
  const [passwordTarget, setPasswordTarget] = useState<AdminAccount | null>(null);
  const [departmentTarget, setDepartmentTarget] = useState<AdminAccount | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<AdminAccount | null>(null);
  const [resetOtpTarget, setResetOtpTarget] = useState<AdminAccount | null>(null);
  const [otpBundle, setOtpBundle] = useState<AdminOtpBundle | null>(null);
  const [resetChallenge, setResetChallenge] = useState<OtpBindChallenge | null>(null);

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
              <TableHead>动态验证码</TableHead>
              <TableHead>操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {admins.map((admin) => {
              const isSelf = admin.admin_id === currentAdminId;
              const isSystem = admin.role === "system_admin";
              const isBuiltin = admin.admin_id === SYSTEM_ADMIN_ID;
              return (
                <TableRow key={admin.admin_id}>
                  <TableCell>{admin.admin_id}</TableCell>
                  <TableCell>{isSystem ? "系统管理员" : "管理员"}</TableCell>
                  <TableCell>{admin.department || "-"}</TableCell>
                  <TableCell>
                    {admin.has_otp ? (
                      <span className="text-success">已绑定</span>
                    ) : (
                      <span className="text-danger">未绑定</span>
                    )}
                  </TableCell>
                  <TableCell>
                    {isBuiltin ? (
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => {
                          window.location.href = "/local/system";
                        }}
                      >
                        前往本机维护页
                      </Button>
                    ) : (
                      <div className="flex flex-wrap gap-2">
                        <Button size="sm" variant="secondary" onClick={() => setPasswordTarget(admin)}>
                          修改密码
                        </Button>
                        {!isSelf ? (
                          <Button size="sm" variant="secondary" onClick={() => setDepartmentTarget(admin)}>
                            修改部门
                          </Button>
                        ) : null}
                        <Button size="sm" variant="secondary" onClick={() => setResetOtpTarget(admin)}>
                          重置 OTP
                        </Button>
                        {!isSystem ? (
                          <Button size="sm" variant="danger" onClick={() => setDeleteTarget(admin)}>
                            删除
                          </Button>
                        ) : null}
                      </div>
                    )}
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
        onCreated={(bundle) => {
          load();
          if (bundle) setOtpBundle(bundle);
        }}
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
        open={resetOtpTarget !== null}
        onOpenChange={(open) => !open && setResetOtpTarget(null)}
        message={`确定重置管理员"${resetOtpTarget?.admin_id ?? ""}"的动态验证码？将生成新的绑定二维码，二次确认生效前旧验证码保持不变。`}
        onConfirm={async () => {
          if (!resetOtpTarget) return;
          try {
            const result = await resetAdminOtp(resetOtpTarget.admin_id);
            if (result.success && result.ticket && result.otp_secret && result.otp_uri && result.otp_qr) {
              setResetChallenge({
                ticket: result.ticket,
                otp_secret: result.otp_secret,
                otp_uri: result.otp_uri,
                otp_qr: result.otp_qr,
              });
            } else if (!result.success) {
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
      <OtpBundleDialog bundle={otpBundle} onOpenChange={(open) => !open && setOtpBundle(null)} />
      <OtpBundleDialog
        bundle={resetChallenge}
        title="重置管理员 OTP"
        onOpenChange={(open) => {
          if (!open) setResetChallenge(null);
        }}
        activation={{
          type: "confirm",
          onConfirm: async () => {
            if (!resetChallenge) return false;
            try {
              const result = await confirmAdminOtpReset(resetChallenge.ticket);
              if (result.success) {
                toast.success(result.message || "动态验证码已生效");
                load();
                return true;
              }
              toast.error(result.message || "确认失败");
              return false;
            } catch (error) {
              toast.error(errorMessage(error, "确认失败"));
              return false;
            }
          },
        }}
      />
    </section>
  );
}

function AddAdminDialog({
  open,
  onOpenChange,
  departments,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  departments: string[];
  onCreated: (bundle: AdminOtpBundle | null) => void;
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
        const bundle =
          result.otp_secret && result.otp_uri && result.otp_qr
            ? { otp_secret: result.otp_secret, otp_uri: result.otp_uri, otp_qr: result.otp_qr }
            : null;
        onOpenChange(false);
        setAdminId("");
        setPassword("admin123");
        setDepartment("");
        // 创建即绑定 OTP：随后弹出一次性二维码对话框
        onCreated(bundle);
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
