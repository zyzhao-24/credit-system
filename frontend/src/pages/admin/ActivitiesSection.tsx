import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { errorMessage } from "@/api/client";
import {
  batchAddEntries,
  batchDeleteEntries,
  batchUpdateEntries,
  createActivity,
  createEntry,
  createRecord,
  deleteActivity,
  deleteEntry,
  deleteRecord,
  getActivityRecords,
  getAdminActivities,
  getAdminCategories,
  getAdmins,
  getCheckedInMissing,
  getDepartments,
  getRecordDetail,
  updateActivity,
  updateEntry,
  updateRecord,
} from "@/api/service";
import type {
  AdminActivity,
  AdminCategory,
  AdminEntry,
  AdminRecord,
  AdminRecordDetail,
  CheckedInMissingStudent,
} from "@/api/types";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
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
import { CheckboxGroup } from "@/components/CheckboxGroup";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EmptyState, Field } from "@/components/common";

/** 活动管理标签页：紧凑可搜索的活动卡片 ⇄ 选中活动的记录列表，两级视图互相切换。 */
export function ActivitiesSection({ isSystemAdmin }: { isSystemAdmin: boolean }) {
  const [activities, setActivities] = useState<AdminActivity[]>([]);
  const [categories, setCategories] = useState<AdminCategory[]>([]);
  const [departments, setDepartments] = useState<string[]>([]);
  const [addOpen, setAddOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const load = useCallback(() => {
    getAdminActivities()
      .then((data) => {
        if (data.success) setActivities(data.activities);
      })
      .catch((error) => toast.error(errorMessage(error, "加载活动失败")));
    getAdminCategories()
      .then((data) => {
        if (data.success) setCategories(data.categories);
      })
      .catch(() => undefined);
    getDepartments()
      .then((data) => {
        if (data.success) setDepartments(data.departments);
      })
      .catch(() => undefined);
  }, []);

  useEffect(load, [load]);

  const keyword = search.trim().toLowerCase();
  const filtered = keyword
    ? activities.filter((activity) =>
        [activity.name, activity.department, ...activity.categories]
          .join(" ")
          .toLowerCase()
          .includes(keyword),
      )
    : activities;
  const selected = activities.find((a) => a.activity_id === selectedId) ?? null;

  // 记录列表视图（点击卡片进入，返回按钮切回卡片视图）
  if (selected) {
    return (
      <ActivityRecordsView
        activity={selected}
        categories={categories}
        departments={departments}
        isSystemAdmin={isSystemAdmin}
        onBack={() => setSelectedId(null)}
        onChanged={load}
      />
    );
  }

  return (
    <section>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <h2 className="text-xl font-semibold mr-auto">活动列表</h2>
        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="搜索活动名称 / 类别 / 部门"
          className="w-64"
        />
        <Button size="sm" onClick={() => setAddOpen(true)}>
          ➕ 创建活动
        </Button>
      </div>

      {activities.length === 0 ? (
        <EmptyState icon="🗂️" text="暂无活动" />
      ) : filtered.length === 0 ? (
        <EmptyState icon="🔍" text="没有匹配的活动" />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {filtered.map((activity) => (
            <ActivityCard
              key={activity.activity_id}
              activity={activity}
              onOpen={() => setSelectedId(activity.activity_id)}
            />
          ))}
        </div>
      )}

      <AddActivityDialog
        open={addOpen}
        onOpenChange={setAddOpen}
        departments={departments}
        onDone={load}
      />
    </section>
  );
}

/** 紧凑活动卡片：只展示摘要，点击进入记录列表视图。 */
function ActivityCard({ activity, onOpen }: { activity: AdminActivity; onOpen: () => void }) {
  return (
    <Card
      role="button"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onOpen();
        }
      }}
      className="cursor-pointer p-3 transition hover:border-primary/50 hover:shadow-[0_4px_16px_rgba(0,120,212,0.15)] border border-transparent"
    >
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-[15px] font-semibold leading-snug">{activity.name}</h3>
        {activity.can_edit ? null : (
          <span className="shrink-0 rounded bg-black/5 px-1.5 py-0.5 text-xs text-[#999]">只读</span>
        )}
      </div>
      {activity.categories.length > 0 ? (
        <div className="mt-1.5 flex flex-wrap gap-1">
          {activity.categories.map((category) => (
            <span key={category} className="rounded bg-primary/10 px-1.5 py-0.5 text-xs text-primary">
              {category}
            </span>
          ))}
        </div>
      ) : null}
      <p className="mt-2 text-xs text-[#777]">
        {activity.department || "未指定部门"} · 记录 {activity.records_count} 条
        {activity.has_questionnaire
          ? ` · 报名 ${activity.current_participants ?? 0}${
              activity.max_participants > 0 ? `/${activity.max_participants}` : ""
            } 人`
          : ""}
      </p>
    </Card>
  );
}

function AddActivityDialog({
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
  const [name, setName] = useState("");
  const [selectedDepartments, setSelectedDepartments] = useState<string[]>([]);

  const submit = async () => {
    if (!name.trim()) {
      toast.error("活动名称不能为空");
      return;
    }
    try {
      const result = await createActivity({
        name: name.trim(),
        department: selectedDepartments.join(", "),
      });
      if (result.success) {
        toast.success("创建成功，请在记录列表中为记录设置学分类别");
        onOpenChange(false);
        setName("");
        setSelectedDepartments([]);
        onDone();
      } else {
        toast.error(result.message || "创建失败");
      }
    } catch (error) {
      toast.error(errorMessage(error, "创建失败"));
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title="创建活动">
        <Field label="活动名称" required>
          <Input value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        <Field label="负责部门（可多选）">
          <CheckboxGroup
            options={departments}
            selected={selectedDepartments}
            onChange={setSelectedDepartments}
            idPrefix="add-act-dept"
          />
        </Field>
        <p className="text-xs text-[#888] leading-relaxed">
          学分类别在记录一级设置；活动类别由所属记录的类别自动汇总。
        </p>
        <div className="flex gap-3 mt-2">
          <Button className="flex-1" onClick={submit}>
            创建
          </Button>
          <Button variant="secondary" className="flex-1" onClick={() => onOpenChange(false)}>
            取消
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

/** 记录列表视图：单个活动的记录管理，所有活动级操作按钮集中在这里。 */
function ActivityRecordsView({
  activity,
  categories,
  departments,
  isSystemAdmin,
  onBack,
  onChanged,
}: {
  activity: AdminActivity;
  categories: AdminCategory[];
  departments: string[];
  isSystemAdmin: boolean;
  onBack: () => void;
  onChanged: () => void;
}) {
  const [records, setRecords] = useState<AdminRecord[] | null>(null);
  const [recordSearch, setRecordSearch] = useState("");
  const [addRecordOpen, setAddRecordOpen] = useState(false);
  const [permissionOpen, setPermissionOpen] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const [editTarget, setEditTarget] = useState<AdminRecord | null>(null);
  const [deleteRecordTarget, setDeleteRecordTarget] = useState<AdminRecord | null>(null);
  const [detailRecordId, setDetailRecordId] = useState<string | null>(null);

  const loadRecords = useCallback(() => {
    getActivityRecords(activity.activity_id)
      .then((data) => {
        if (data.success) setRecords(data.records);
      })
      .catch((error) => toast.error(errorMessage(error, "加载记录失败")));
  }, [activity.activity_id]);

  useEffect(loadRecords, [loadRecords]);

  const keyword = recordSearch.trim().toLowerCase();
  const filteredRecords =
    records && keyword
      ? records.filter((record) => record.record_name.toLowerCase().includes(keyword))
      : records;

  return (
    <section>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Button size="sm" variant="secondary" onClick={onBack}>
          ← 返回活动列表
        </Button>
        <h2 className="text-xl font-semibold">{activity.name}</h2>
        <div className="ml-auto flex flex-wrap gap-2">
          {activity.can_edit ? (
            <>
              <Button size="sm" onClick={() => setAddRecordOpen(true)}>
                添加记录
              </Button>
              <Button size="sm" variant="danger" onClick={() => setDeleteConfirm(true)}>
                删除活动
              </Button>
            </>
          ) : (
            <span className="self-center text-sm text-[#999]">无编辑权限</span>
          )}
          {isSystemAdmin ? (
            <Button size="sm" variant="secondary" onClick={() => setPermissionOpen(true)}>
              权限管理
            </Button>
          ) : null}
        </div>
      </div>

      <Card className="mb-3 flex flex-wrap gap-x-5 gap-y-1 p-3 text-sm text-[#555]">
        <span>
          <strong>活动类别（记录类别并集）：</strong>
          {activity.categories.join(", ") || "-"}
        </span>
        {activity.department ? (
          <span>
            <strong>负责部门：</strong>
            {activity.department}
          </span>
        ) : null}
        {activity.has_questionnaire ? (
          <span>
            <strong>问卷报名：</strong>
            {activity.current_participants ?? 0}
            {activity.max_participants > 0 ? `/${activity.max_participants}` : ""} 人
          </span>
        ) : null}
      </Card>

      <div className="mb-2 flex items-center justify-between gap-2">
        <h4 className="font-medium">记录列表</h4>
        <Input
          value={recordSearch}
          onChange={(e) => setRecordSearch(e.target.value)}
          placeholder="搜索记录名称"
          className="w-56"
        />
      </div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>记录名称</TableHead>
            <TableHead>学分类别</TableHead>
            <TableHead>条目数</TableHead>
            <TableHead>操作</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {filteredRecords && filteredRecords.length > 0 ? (
            filteredRecords.map((record) => (
              <TableRow key={record.record_id}>
                <TableCell>{record.record_name}</TableCell>
                <TableCell>
                  <div className="flex flex-wrap gap-1">
                    {record.categories.map((category) => (
                      <span
                        key={category}
                        className="rounded bg-primary/10 px-1.5 py-0.5 text-xs text-primary"
                      >
                        {category}
                      </span>
                    ))}
                  </div>
                </TableCell>
                <TableCell>{record.entries_count}</TableCell>
                <TableCell>
                  <div className="flex flex-wrap gap-2">
                    <Button size="sm" variant="secondary" onClick={() => setDetailRecordId(record.record_id)}>
                      查看详情
                    </Button>
                    {activity.can_edit ? (
                      <>
                        <Button size="sm" variant="secondary" onClick={() => setEditTarget(record)}>
                          编辑
                        </Button>
                        <Button size="sm" variant="danger" onClick={() => setDeleteRecordTarget(record)}>
                          删除
                        </Button>
                      </>
                    ) : null}
                  </div>
                </TableCell>
              </TableRow>
            ))
          ) : (
            <TableRow>
              <TableCell colSpan={4} className="text-center text-[#666]">
                {records && records.length > 0 ? "没有匹配的记录" : "暂无记录"}
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>

      <AddRecordDialog
        open={addRecordOpen}
        onOpenChange={setAddRecordOpen}
        activityId={activity.activity_id}
        categories={categories}
        onDone={(recordId) => {
          loadRecords();
          onChanged();
          setDetailRecordId(recordId);
        }}
      />
      <EditRecordDialog
        target={editTarget}
        onOpenChange={(open) => !open && setEditTarget(null)}
        categories={categories}
        onDone={() => {
          loadRecords();
          onChanged();
        }}
      />
      <PermissionDialog
        open={permissionOpen}
        onOpenChange={setPermissionOpen}
        activity={activity}
        departments={departments}
        onDone={onChanged}
      />
      <ConfirmDialog
        open={deleteConfirm}
        onOpenChange={setDeleteConfirm}
        message="确定删除该活动？"
        onConfirm={async () => {
          try {
            const result = await deleteActivity(activity.activity_id);
            if (result.success) {
              onChanged();
              onBack();
            } else toast.error(result.message || "删除失败");
          } catch (error) {
            toast.error(errorMessage(error, "删除失败"));
          }
        }}
      />
      <ConfirmDialog
        open={deleteRecordTarget !== null}
        onOpenChange={(open) => !open && setDeleteRecordTarget(null)}
        message="确定删除该记录？所有学分条目也将被删除。"
        onConfirm={async () => {
          if (!deleteRecordTarget) return;
          try {
            const result = await deleteRecord(deleteRecordTarget.record_id);
            if (result.success) {
              loadRecords();
              onChanged();
            } else {
              toast.error(result.message || "删除失败");
            }
          } catch (error) {
            toast.error(errorMessage(error, "删除失败"));
          }
        }}
      />
      {detailRecordId ? (
        <RecordDetailDialog
          recordId={detailRecordId}
          canEdit={activity.can_edit}
          onClose={() => {
            setDetailRecordId(null);
            loadRecords();
          }}
        />
      ) : null}
    </section>
  );
}

function AddRecordDialog({
  open,
  onOpenChange,
  activityId,
  categories,
  onDone,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  activityId: string;
  categories: AdminCategory[];
  onDone: (recordId: string) => void;
}) {
  const [name, setName] = useState("");
  const [selected, setSelected] = useState<string[]>([]);

  const submit = async () => {
    if (!name.trim()) {
      toast.error("记录名称不能为空");
      return;
    }
    if (selected.length === 0) {
      toast.error("请至少选择一个类别");
      return;
    }
    try {
      const result = await createRecord({
        activity_id: activityId,
        record_name: name.trim(),
        categories: selected,
      });
      if (result.success && result.record_id) {
        onOpenChange(false);
        setName("");
        setSelected([]);
        onDone(result.record_id);
      } else {
        toast.error(result.message || "添加失败");
      }
    } catch (error) {
      toast.error(errorMessage(error, "添加失败"));
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title="添加记录">
        <Field label="记录名称" required>
          <Input value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        <Field label="学分类别（可多选，记录内条目的可选范围）" required>
          <CheckboxGroup
            options={categories.map((c) => c.name)}
            selected={selected}
            onChange={setSelected}
            idPrefix="add-record-cat"
          />
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

function EditRecordDialog({
  target,
  onOpenChange,
  categories,
  onDone,
}: {
  target: AdminRecord | null;
  onOpenChange: (open: boolean) => void;
  categories: AdminCategory[];
  onDone: () => void;
}) {
  return (
    <Dialog open={target !== null} onOpenChange={onOpenChange}>
      <DialogContent title="编辑记录">
        {target ? (
          <EditRecordForm
            key={target.record_id}
            target={target}
            categories={categories}
            onOpenChange={onOpenChange}
            onDone={onDone}
          />
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

function EditRecordForm({
  target,
  categories,
  onOpenChange,
  onDone,
}: {
  target: AdminRecord;
  categories: AdminCategory[];
  onOpenChange: (open: boolean) => void;
  onDone: () => void;
}) {
  const [name, setName] = useState(target.record_name);
  const [selected, setSelected] = useState<string[]>(() => target.categories);

  const submit = async () => {
    if (!name.trim()) {
      toast.error("记录名称不能为空");
      return;
    }
    if (selected.length === 0) {
      toast.error("请至少选择一个类别");
      return;
    }
    try {
      const result = await updateRecord({
        record_id: target.record_id,
        record_name: name.trim(),
        categories: selected,
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
      <Field label="记录名称" required>
        <Input value={name} onChange={(e) => setName(e.target.value)} />
      </Field>
      <Field label="学分类别（可多选）" required>
        <CheckboxGroup
          options={categories.map((c) => c.name)}
          selected={selected}
          onChange={setSelected}
          idPrefix="edit-record-cat"
        />
      </Field>
      <p className="text-xs text-[#888] leading-relaxed">
        缩减类别时，若仍有条目使用被移除的类别，需要先调整这些条目。
      </p>
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

function PermissionDialog({
  open,
  onOpenChange,
  activity,
  departments,
  onDone,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  activity: AdminActivity;
  departments: string[];
  onDone: () => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title="活动权限管理">
        <PermissionForm
          key={activity.activity_id}
          activity={activity}
          departments={departments}
          onOpenChange={onOpenChange}
          onDone={onDone}
        />
      </DialogContent>
    </Dialog>
  );
}

function PermissionForm({
  activity,
  departments,
  onOpenChange,
  onDone,
}: {
  activity: AdminActivity;
  departments: string[];
  onOpenChange: (open: boolean) => void;
  onDone: () => void;
}) {
  const [selectedDepartments, setSelectedDepartments] = useState<string[]>(() =>
    activity.department ? activity.department.split(", ").filter(Boolean) : [],
  );
  const [adminOptions, setAdminOptions] = useState<{ id: string; label: string }[]>([]);
  const [selectedAdmins, setSelectedAdmins] = useState<string[]>(() => activity.allowed_editors ?? []);

  useEffect(() => {
    getAdmins()
      .then((data) => {
        if (data.success) {
          setAdminOptions(
            data.admins
              .filter((admin) => admin.role !== "system_admin")
              .map((admin) => ({
                id: admin.admin_id,
                label: admin.department ? `${admin.admin_id} (${admin.department})` : admin.admin_id,
              })),
          );
        }
      })
      .catch((error) => toast.error(errorMessage(error, "加载管理员失败")));
  }, []);

  const submit = async () => {
    try {
      const result = await updateActivity({
        activity_id: activity.activity_id,
        department: selectedDepartments.join(", "),
        allowed_editors: selectedAdmins,
      });
      if (result.success) {
        toast.success("权限设置成功");
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
      <Field label="活动名称">
        <Input value={activity.name} readOnly />
      </Field>
      <Field label="负责部门（可多选）">
        <CheckboxGroup
          options={departments}
          selected={selectedDepartments}
          onChange={setSelectedDepartments}
          idPrefix="perm-dept"
        />
      </Field>
      <Field label="允许编辑的管理员（可多选）">
        <div className="flex flex-col gap-2 rounded-md border border-[#e0e0e0] p-3 max-h-56 overflow-y-auto">
          {adminOptions.length === 0 ? (
            <p className="text-sm text-[#999]">暂无普通管理员</p>
          ) : (
            adminOptions.map((option) => (
              <label key={option.id} className="flex items-center gap-2 cursor-pointer text-sm">
                <Checkbox
                  checked={selectedAdmins.includes(option.id)}
                  onCheckedChange={(checked) =>
                    setSelectedAdmins(
                      checked === true
                        ? [...selectedAdmins, option.id]
                        : selectedAdmins.filter((id) => id !== option.id),
                    )
                  }
                />
                <span>{option.label}</span>
              </label>
            ))
          )}
        </div>
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

// ========== 记录详情与条目管理 ==========

function RecordDetailDialog({
  recordId,
  canEdit,
  onClose,
}: {
  recordId: string;
  canEdit: boolean;
  onClose: () => void;
}) {
  const [record, setRecord] = useState<AdminRecordDetail | null>(null);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [addEntryOpen, setAddEntryOpen] = useState(false);
  const [entryPrefill, setEntryPrefill] = useState<CheckedInMissingStudent | null>(null);
  const [batchAddOpen, setBatchAddOpen] = useState(false);
  const [batchUpdateOpen, setBatchUpdateOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<AdminEntry | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<AdminEntry | null>(null);
  const [batchDeleteConfirm, setBatchDeleteConfirm] = useState(false);
  // 已签到未录入的批量录入对话框
  const [batchCheckinOpen, setBatchCheckinOpen] = useState(false);
  // 已签到但本记录还没有学分条目的学生（是否录入由人工决定）
  const [checkinMissing, setCheckinMissing] = useState<CheckedInMissingStudent[]>([]);

  const load = useCallback(() => {
    getRecordDetail(recordId)
      .then((data) => {
        if (data.success) {
          setRecord(data.record);
          setSelectedIds([]);
        }
      })
      .catch((error) => toast.error(errorMessage(error, "加载条目失败")));
    if (canEdit) {
      getCheckedInMissing(recordId)
        .then((data) => {
          if (data.success) setCheckinMissing(data.students);
        })
        .catch(() => undefined);
    }
  }, [recordId, canEdit]);

  useEffect(load, [load]);

  const toggleAll = (checked: boolean) => {
    if (!record) return;
    // 批量接口按学号操作，与 legacy 行为一致
    setSelectedIds(checked ? Array.from(new Set(record.entries.map((entry) => entry.student_id))) : []);
  };

  const toggleOne = (studentId: string, checked: boolean) => {
    setSelectedIds((prev) =>
      checked ? [...new Set([...prev, studentId])] : prev.filter((id) => id !== studentId),
    );
  };

  return (
    <>
      <Dialog open onOpenChange={(open) => !open && onClose()}>
        <DialogContent
          title={record ? `${record.activity_name} - ${record.record_name}` : "记录详情"}
          className="max-w-4xl"
        >
          {canEdit ? (
            <div className="mb-4 flex flex-wrap gap-2">
              <Button size="sm" onClick={() => setAddEntryOpen(true)}>
                ➕ 添加条目
              </Button>
              <Button size="sm" onClick={() => setBatchAddOpen(true)}>
                批量添加条目
              </Button>
              <Button size="sm" variant="secondary" onClick={() => setBatchUpdateOpen(true)}>
                批量修改选中
              </Button>
              <Button size="sm" variant="danger" onClick={() => setBatchDeleteConfirm(true)}>
                批量删除选中
              </Button>
            </div>
          ) : null}

          {canEdit && checkinMissing.length > 0 ? (
            <div className="mb-4 rounded-md border border-[#ffe0b2] bg-[#fffaf0] p-3">
              <div className="mb-2 flex items-center gap-3">
                <p className="text-sm font-medium text-[#8a5a00]">
                  已签到未录入（{checkinMissing.length} 人）— 是否录入由人工决定
                </p>
                <Button
                  size="sm"
                  className="ml-auto"
                  onClick={() => setBatchCheckinOpen(true)}
                >
                  批量录入
                </Button>
              </div>
              <div className="max-h-40 overflow-y-auto">
                {checkinMissing.map((student) => (
                  <div
                    key={student.student_id}
                    className="flex items-center gap-3 py-1 text-sm"
                  >
                    <span className="font-mono">{student.student_id}</span>
                    <span>{student.student_name}</span>
                    {student.intended_category ? (
                      <span className="text-[#777]">意向：{student.intended_category}</span>
                    ) : null}
                    <span className="text-xs text-[#999]">{student.checked_in_at}</span>
                    <Button
                      size="sm"
                      variant="secondary"
                      className="ml-auto"
                      onClick={() => {
                        setEntryPrefill(student);
                        setAddEntryOpen(true);
                      }}
                    >
                      录入
                    </Button>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {record ? (
            <Table>
              <TableHeader>
                <TableRow>
                  {canEdit ? (
                    <TableHead className="w-10">
                      <Checkbox
                        checked={
                          record.entries.length > 0 &&
                          selectedIds.length === new Set(record.entries.map((e) => e.student_id)).size
                        }
                        onCheckedChange={(checked) => toggleAll(checked === true)}
                      />
                    </TableHead>
                  ) : null}
                  <TableHead>学号</TableHead>
                  <TableHead>姓名</TableHead>
                  <TableHead>学分</TableHead>
                  <TableHead>类别</TableHead>
                  {canEdit ? <TableHead>操作</TableHead> : null}
                </TableRow>
              </TableHeader>
              <TableBody>
                {record.entries.map((entry) => (
                  <TableRow key={entry.entry_id}>
                    {canEdit ? (
                      <TableCell>
                        <Checkbox
                          checked={selectedIds.includes(entry.student_id)}
                          onCheckedChange={(checked) => toggleOne(entry.student_id, checked === true)}
                        />
                      </TableCell>
                    ) : null}
                    <TableCell>{entry.student_id}</TableCell>
                    <TableCell>
                      {entry.student_name}
                      {!entry.student_exists ? (
                        <span className="text-[#ff8c00]">（学生不存在）</span>
                      ) : null}
                    </TableCell>
                    <TableCell>{entry.credits}</TableCell>
                    <TableCell>{entry.categories.join(", ")}</TableCell>
                    {canEdit ? (
                      <TableCell>
                        <div className="flex gap-2">
                          <Button size="sm" variant="secondary" onClick={() => setEditTarget(entry)}>
                            编辑
                          </Button>
                          <Button size="sm" variant="danger" onClick={() => setDeleteTarget(entry)}>
                            删除
                          </Button>
                        </div>
                      </TableCell>
                    ) : null}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="text-center text-[#999] py-6">加载中...</p>
          )}

          <div className="mt-4 border-t border-black/10 pt-4">
            <Button variant="secondary" onClick={onClose}>
              关闭
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {record ? (
        <>
          <AddEntryDialog
            key={entryPrefill?.student_id ?? "blank"}
            open={addEntryOpen}
            onOpenChange={(open) => {
              setAddEntryOpen(open);
              if (!open) setEntryPrefill(null);
            }}
            recordId={recordId}
            categories={record.categories}
            prefill={entryPrefill}
            onDone={load}
          />
          <BatchAddEntriesDialog
            open={batchAddOpen}
            onOpenChange={setBatchAddOpen}
            recordId={recordId}
            activityCategories={record.categories}
            onDone={load}
          />
          {batchCheckinOpen ? (
            <BatchCheckinEntriesDialog
              recordId={recordId}
              categories={record.categories}
              students={checkinMissing}
              onClose={() => setBatchCheckinOpen(false)}
              onDone={() => {
                setBatchCheckinOpen(false);
                load();
              }}
            />
          ) : null}
          <BatchUpdateDialog
            open={batchUpdateOpen}
            onOpenChange={setBatchUpdateOpen}
            recordId={recordId}
            activityCategories={record.categories}
            selectedIds={selectedIds}
            onDone={load}
          />
          <EditEntryDialog
            target={editTarget}
            onOpenChange={(open) => !open && setEditTarget(null)}
            recordId={recordId}
            activityCategories={record.categories}
            onDone={load}
          />
          <ConfirmDialog
            open={deleteTarget !== null}
            onOpenChange={(open) => !open && setDeleteTarget(null)}
            message="确定删除该条目？"
            onConfirm={async () => {
              if (!deleteTarget) return;
              try {
                const result = await deleteEntry({
                  record_id: recordId,
                  entry_id: deleteTarget.entry_id,
                });
                if (result.success) load();
                else toast.error(result.message || "删除失败");
              } catch (error) {
                toast.error(errorMessage(error, "删除失败"));
              }
            }}
          />
          <ConfirmDialog
            open={batchDeleteConfirm}
            onOpenChange={setBatchDeleteConfirm}
            message={`确定删除选中的 ${selectedIds.length} 个条目？`}
            onConfirm={async () => {
              if (selectedIds.length === 0) {
                toast.error("请选择要删除的条目");
                return;
              }
              try {
                const result = await batchDeleteEntries({
                  record_id: recordId,
                  student_ids: selectedIds,
                });
                if (result.success) load();
                else toast.error(result.message || "删除失败");
              } catch (error) {
                toast.error(errorMessage(error, "删除失败"));
              }
            }}
          />
        </>
      ) : null}
    </>
  );
}

function AddEntryDialog({
  open,
  onOpenChange,
  recordId,
  categories,
  prefill,
  onDone,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  recordId: string;
  categories: string[];
  /** 从"已签到未录入"面板一键带入的学生信息（学分仍由人工填写） */
  prefill?: CheckedInMissingStudent | null;
  onDone: () => void;
}) {
  // 预填值经 key 重挂载注入（父组件以 prefill 学号为 key），此处只作初始值
  const [studentId, setStudentId] = useState(prefill?.student_id ?? "");
  const [credits, setCredits] = useState("");
  const [selected, setSelected] = useState<string[]>(
    prefill?.intended_category && categories.includes(prefill.intended_category)
      ? [prefill.intended_category]
      : [],
  );

  const submit = async () => {
    try {
      const result = await createEntry({
        record_id: recordId,
        student_id: studentId.trim(),
        credits: parseFloat(credits) || 0,
        categories: selected,
      });
      if (result.success) {
        toast.success("添加成功");
        setStudentId("");
        setCredits("");
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
      <DialogContent title="添加学分条目">
        <Field label="学号" required>
          <Input value={studentId} onChange={(e) => setStudentId(e.target.value)} />
        </Field>
        <Field label="学分" required>
          <Input type="number" step="0.1" value={credits} onChange={(e) => setCredits(e.target.value)} />
        </Field>
        <Field label="类别（可多选，限记录类别）" required>
          <CheckboxGroup
            options={categories}
            selected={selected}
            onChange={setSelected}
            idPrefix="add-entry-cat"
          />
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

/** 已签到未录入学生的批量录入：默认全选学生与全部类别（意向类别仅供参考），均可修改。 */
function BatchCheckinEntriesDialog({
  recordId,
  categories,
  students,
  onClose,
  onDone,
}: {
  recordId: string;
  categories: string[];
  students: CheckedInMissingStudent[];
  onClose: () => void;
  onDone: () => void;
}) {
  const [selectedIds, setSelectedIds] = useState<string[]>(() =>
    students.map((student) => student.student_id),
  );
  const [credits, setCredits] = useState("0");
  const [selectedCats, setSelectedCats] = useState<string[]>(() => categories);
  const [submitting, setSubmitting] = useState(false);

  const toggleOne = (studentId: string, checked: boolean) => {
    setSelectedIds((prev) =>
      checked ? [...prev, studentId] : prev.filter((id) => id !== studentId),
    );
  };

  const submit = async () => {
    if (selectedIds.length === 0) {
      toast.error("请选择要录入的学生");
      return;
    }
    if (selectedCats.length === 0) {
      toast.error("请至少选择一个类别");
      return;
    }
    setSubmitting(true);
    try {
      const result = await batchAddEntries({
        record_id: recordId,
        entries_text: selectedIds.join("\n"),
        categories: selectedCats,
        default_credits: parseFloat(credits) || 0,
      });
      if (result.success) {
        let message = `批量录入成功！新增: ${result.added}，更新: ${result.updated}`;
        if (result.errors.length > 0) message += `；错误: ${result.errors.join("；")}`;
        toast.success(message);
        onDone();
      } else {
        toast.error(result.message || "录入失败");
      }
    } catch (error) {
      toast.error(errorMessage(error, "录入失败"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent title={`批量录入已签到学生（${selectedIds.length}/${students.length} 人）`}>
        <div className="mb-3 max-h-48 overflow-y-auto rounded-md border border-[#e5e5e5] p-2">
          <label className="flex items-center gap-2 px-1 py-1 text-sm font-medium">
            <Checkbox
              checked={selectedIds.length === students.length}
              onCheckedChange={(checked) =>
                setSelectedIds(checked === true ? students.map((s) => s.student_id) : [])
              }
            />
            全选
          </label>
          {students.map((student) => (
            <label
              key={student.student_id}
              className="flex items-center gap-2 px-1 py-1 text-sm"
            >
              <Checkbox
                checked={selectedIds.includes(student.student_id)}
                onCheckedChange={(checked) => toggleOne(student.student_id, checked === true)}
              />
              <span className="font-mono">{student.student_id}</span>
              <span>{student.student_name}</span>
              {student.intended_category ? (
                <span className="text-xs text-[#999]">意向：{student.intended_category}</span>
              ) : null}
            </label>
          ))}
        </div>
        <Field label="学分" required>
          <Input
            type="number"
            step="0.1"
            value={credits}
            onChange={(e) => setCredits(e.target.value)}
            className="max-w-[200px]"
          />
        </Field>
        <Field label="类别（默认全选，可修改；意向类别仅供参考）" required>
          <CheckboxGroup
            options={categories}
            selected={selectedCats}
            onChange={setSelectedCats}
            idPrefix="batch-checkin-cat"
          />
        </Field>
        <div className="flex gap-3 mt-2">
          <Button className="flex-1" onClick={submit} disabled={submitting}>
            {submitting ? "录入中..." : "批量录入"}
          </Button>
          <Button variant="secondary" className="flex-1" onClick={onClose}>
            取消
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function BatchAddEntriesDialog({
  open,
  onOpenChange,
  recordId,
  activityCategories,
  onDone,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  recordId: string;
  activityCategories: string[];
  onDone: () => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title="批量添加条目">
        <BatchAddEntriesForm
          recordId={recordId}
          activityCategories={activityCategories}
          onOpenChange={onOpenChange}
          onDone={onDone}
        />
      </DialogContent>
    </Dialog>
  );
}

function BatchAddEntriesForm({
  recordId,
  activityCategories,
  onOpenChange,
  onDone,
}: {
  recordId: string;
  activityCategories: string[];
  onOpenChange: (open: boolean) => void;
  onDone: () => void;
}) {
  const [defaultCredits, setDefaultCredits] = useState("0");
  const [selected, setSelected] = useState<string[]>(() => activityCategories);
  const [text, setText] = useState("");

  const submit = async () => {
    if (selected.length === 0) {
      toast.error("请至少选择一个类别");
      return;
    }
    try {
      const result = await batchAddEntries({
        record_id: recordId,
        entries_text: text,
        categories: selected,
        default_credits: parseFloat(defaultCredits) || 0,
      });
      if (result.success) {
        let message = `批量操作成功！新增: ${result.added}，更新: ${result.updated}`;
        if ((result.ignored ?? 0) > 0) message += `，忽略: ${result.ignored}（姓名无匹配）`;
        if (result.errors.length > 0) message += `；错误: ${result.errors.join("；")}`;
        toast.success(message);
        onOpenChange(false);
        onDone();
      } else {
        toast.error(result.message || "操作失败");
      }
    } catch (error) {
      toast.error(errorMessage(error, "操作失败"));
    }
  };

  return (
    <>
      <p className="text-sm">格式：姓名或学号 或 姓名或学号,学分（每行一个条目）</p>
      <p className="text-xs text-[#616161] mt-1 mb-3 leading-relaxed">
        • 纯数字视为学号，无论学生是否存在都保留
        <br />• 非数字视为姓名，匹配系统中的学生，无匹配则忽略
        <br />• 多个同名学生都会被匹配
        <br />• 如果不带学分，使用下方默认学分
      </p>
      <Field label="默认学分">
        <Input
          type="number"
          step="0.1"
          value={defaultCredits}
          onChange={(e) => setDefaultCredits(e.target.value)}
          className="max-w-[200px]"
        />
      </Field>
      <Field label="类别选择（可多选）" required>
        <CheckboxGroup
          options={activityCategories}
          selected={selected}
          onChange={setSelected}
          idPrefix="batch-entry-cat"
        />
      </Field>
      <Field label="条目数据">
        <Textarea
          rows={8}
          value={text}
          onChange={(event) => setText(event.target.value)}
          placeholder={"2021001,2\n张三,3\n李四\n王五"}
        />
      </Field>
      <div className="flex gap-3 mt-2">
        <Button className="flex-1" onClick={submit}>
          添加
        </Button>
        <Button variant="secondary" className="flex-1" onClick={() => onOpenChange(false)}>
          取消
        </Button>
      </div>
    </>
  );
}

function BatchUpdateDialog({
  open,
  onOpenChange,
  recordId,
  activityCategories,
  selectedIds,
  onDone,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  recordId: string;
  activityCategories: string[];
  selectedIds: string[];
  onDone: () => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title="批量修改条目">
        <BatchUpdateForm
          recordId={recordId}
          activityCategories={activityCategories}
          selectedIds={selectedIds}
          onOpenChange={onOpenChange}
          onDone={onDone}
        />
      </DialogContent>
    </Dialog>
  );
}

function BatchUpdateForm({
  recordId,
  activityCategories,
  selectedIds,
  onOpenChange,
  onDone,
}: {
  recordId: string;
  activityCategories: string[];
  selectedIds: string[];
  onOpenChange: (open: boolean) => void;
  onDone: () => void;
}) {
  const [credits, setCredits] = useState("");
  const [selected, setSelected] = useState<string[]>([]);

  const submit = async () => {
    const newCredits = credits ? parseFloat(credits) : null;
    const newCategories = selected.length > 0 ? selected : null;
    if (newCredits === null && newCategories === null) {
      toast.error("请至少修改学分或类别");
      return;
    }
    if (selectedIds.length === 0) {
      toast.error("请选择要修改的条目");
      return;
    }
    try {
      const result = await batchUpdateEntries({
        record_id: recordId,
        student_ids: selectedIds,
        credits: newCredits,
        categories: newCategories,
      });
      if (result.success) {
        toast.success(`批量修改成功！修改了 ${result.updated ?? 0} 个条目`);
        onOpenChange(false);
        onDone();
      } else {
        toast.error(result.message || "修改失败");
      }
    } catch (error) {
      toast.error(errorMessage(error, "修改失败"));
    }
  };

  return (
    <>
      <Field label="新学分（留空则不修改）">
        <Input
          type="number"
          step="0.1"
          value={credits}
          onChange={(e) => setCredits(e.target.value)}
          placeholder="留空不修改"
        />
      </Field>
      <Field label="新类别（不选则不修改）">
        <CheckboxGroup
          options={activityCategories}
          selected={selected}
          onChange={setSelected}
          idPrefix="batch-update-cat"
        />
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

function EditEntryDialog({
  target,
  onOpenChange,
  recordId,
  activityCategories,
  onDone,
}: {
  target: AdminEntry | null;
  onOpenChange: (open: boolean) => void;
  recordId: string;
  activityCategories: string[];
  onDone: () => void;
}) {
  return (
    <Dialog open={target !== null} onOpenChange={onOpenChange}>
      <DialogContent title="编辑条目">
        {target ? (
          <EditEntryForm
            target={target}
            recordId={recordId}
            activityCategories={activityCategories}
            onOpenChange={onOpenChange}
            onDone={onDone}
          />
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

function EditEntryForm({
  target,
  recordId,
  activityCategories,
  onOpenChange,
  onDone,
}: {
  target: AdminEntry;
  recordId: string;
  activityCategories: string[];
  onOpenChange: (open: boolean) => void;
  onDone: () => void;
}) {
  const [credits, setCredits] = useState(() => String(target.credits));
  const [selected, setSelected] = useState<string[]>(() => target.categories);

  const submit = async () => {
    if (selected.length === 0) {
      toast.error("请至少选择一个类别");
      return;
    }
    try {
      const result = await updateEntry({
        record_id: recordId,
        entry_id: target.entry_id,
        credits: parseFloat(credits) || 0,
        categories: selected,
      });
      if (result.success) {
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
      <Field label="学分" required>
        <Input type="number" step="0.1" value={credits} onChange={(e) => setCredits(e.target.value)} />
      </Field>
      <Field label="类别（可多选）" required>
        <CheckboxGroup
          options={activityCategories}
          selected={selected}
          onChange={setSelected}
          idPrefix="edit-entry-cat"
        />
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
