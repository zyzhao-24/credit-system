import { api } from "./client";
import type {
  AdminAccount,
  AdminActivity,
  AdminCategory,
  AdminOtpBundle,
  AdminQuestionnaire,
  AdminRecord,
  AdminRecordDetail,
  AdminReport,
  AdminResponse,
  AdminStudent,
  AllStudentCredits,
  AvailableQuestionnaire,
  BatchImportResult,
  CategoryInfo,
  CheckedInMissingStudent,
  CreditReport,
  CustomAnswers,
  CustomQuestion,
  FeedbackAdjustment,
  FeedbackItem,
  FeedbackMatch,
  FeedbackActivityOption,
  FeedbackType,
  LoginStepOneResponse,
  MyRegistration,
  OtpBindChallenge,
  QuestionnaireBody,
  StudentActivities,
  StudentProfile,
  TokenResponse,
} from "./types";

interface BasicResponse {
  success: boolean;
  message?: string;
  [key: string]: unknown;
}

// ========== 认证 ==========

export async function loginWithToken(
  username: string,
  passwordDigest: string,
  userType: "student" | "admin",
): Promise<LoginStepOneResponse> {
  const body = new URLSearchParams({
    grant_type: "password",
    username,
    password: passwordDigest,
    user_type: userType,
  });
  const { data } = await api.post<LoginStepOneResponse>("/api/auth/token", body, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  return data;
}

/** 登录第二步：用 otp_ticket + 6位动态验证码换取正式访问令牌。 */
export async function verifyOtpCode(otpTicket: string, otpCode: string): Promise<TokenResponse> {
  const { data } = await api.post<TokenResponse>("/api/auth/token/verify", {
    otp_ticket: otpTicket,
    otp_code: otpCode,
  });
  return data;
}

export async function logoutRemote(): Promise<void> {
  await api.post("/api/auth/logout");
}

/** 注册第一步：向学号邮箱发送6位验证码。 */
export async function sendRegistrationCode(
  studentId: string,
  name: string,
): Promise<BasicResponse> {
  const { data } = await api.post<BasicResponse>("/api/student/register/send_code", {
    student_id: studentId,
    name,
  });
  return data;
}

export async function registerStudent(payload: {
  name: string;
  student_id: string;
  phone: string;
  wechat: string;
  password: string;
  suggestion: string;
  email_code: string;
}): Promise<BasicResponse & { otp_bind?: OtpBindChallenge }> {
  const { data } = await api.post<BasicResponse & { otp_bind?: OtpBindChallenge }>(
    "/api/student/register",
    payload,
  );
  return data;
}

/** 确认待生效的 OTP 绑定：验证码证明已扫码后才写入。 */
export async function confirmOtpBind(ticket: string, otpCode: string): Promise<BasicResponse> {
  const { data } = await api.post<BasicResponse>("/api/auth/otp/bind/confirm", {
    ticket,
    otp_code: otpCode,
  });
  return data;
}

/** 忘记密码第一步：向学号邮箱发送验证码。 */
export async function sendForgotPasswordCode(studentId: string): Promise<BasicResponse> {
  const { data } = await api.post<BasicResponse>("/api/student/forgot_password/send_code", {
    student_id: studentId,
  });
  return data;
}

/** 忘记密码第二步：邮箱验证码 + 自设新密码，成功后可选择重绑 OTP。 */
export async function forgotPassword(
  studentId: string,
  newPassword: string,
  emailCode: string,
): Promise<BasicResponse & { otp_bind?: OtpBindChallenge }> {
  const { data } = await api.post<BasicResponse & { otp_bind?: OtpBindChallenge }>(
    "/api/student/forgot_password",
    { student_id: studentId, new_password: newPassword, email_code: emailCode },
  );
  return data;
}

// ========== 学生端 ==========

export async function getMyCredits(): Promise<CreditReport> {
  const { data } = await api.get<CreditReport>("/api/student/my_credits");
  return data;
}

export async function changeStudentPassword(
  oldPasswordDigest: string,
  newPassword: string,
): Promise<BasicResponse> {
  const { data } = await api.post<BasicResponse>("/api/student/change_password", {
    old_password_hash: oldPasswordDigest,
    new_password: newPassword,
  });
  return data;
}

export async function getStudentActivities(): Promise<StudentActivities> {
  const { data } = await api.get<StudentActivities>("/api/student/activities");
  return data;
}

export async function getStudentCategories(): Promise<{ success: boolean; categories: CategoryInfo[] }> {
  const { data } = await api.get<{ success: boolean; categories: CategoryInfo[] }>(
    "/api/student/categories",
  );
  return data;
}

export async function getStudentProfile(): Promise<{
  success: boolean;
  profile: StudentProfile;
}> {
  const { data } = await api.get("/api/student/profile");
  return data;
}

export async function updateStudentProfile(payload: {
  phone: string;
  wechat: string;
  suggestion: string;
}): Promise<BasicResponse> {
  const { data } = await api.put<BasicResponse>("/api/student/profile", payload);
  return data;
}

export async function getActivityCategories(
  activityId: string,
): Promise<{ success: boolean; categories: string[]; message?: string }> {
  const { data } = await api.get(`/api/student/activity/${activityId}/categories`);
  return data;
}

// ========== 学生问卷报名 ==========

export async function getAvailableQuestionnaires(): Promise<{
  success: boolean;
  questionnaires: AvailableQuestionnaire[];
  message?: string;
}> {
  const { data } = await api.get("/api/student/questionnaires/available");
  return data;
}

export async function getMyRegistrations(): Promise<{
  success: boolean;
  registrations: MyRegistration[];
}> {
  const { data } = await api.get("/api/student/questionnaires/my_registrations");
  return data;
}

export async function submitQuestionnaire(payload: {
  questionnaire_id: string;
  intended_category: string;
  custom_answers: CustomAnswers;
}): Promise<BasicResponse> {
  const { data } = await api.post<BasicResponse>("/api/student/questionnaire/submit", payload);
  return data;
}

export async function updateQuestionnaireResponse(
  responseId: string,
  payload: { questionnaire_id: string; intended_category: string; custom_answers: CustomAnswers },
): Promise<BasicResponse> {
  const { data } = await api.put<BasicResponse>(
    `/api/student/questionnaire/update/${responseId}`,
    payload,
  );
  return data;
}

export async function cancelQuestionnaire(responseId: string): Promise<BasicResponse> {
  const { data } = await api.post<BasicResponse>(`/api/student/questionnaire/cancel/${responseId}`);
  return data;
}

/** 学生现场签到（签到码来自管理员展示/扫码链接） */
export async function checkinQuestionnaire(
  questionnaireId: string,
  code: string,
): Promise<BasicResponse & { checkin_state?: "valid" | "pending" | null }> {
  const { data } = await api.post<BasicResponse & { checkin_state?: "valid" | "pending" | null }>(
    `/api/student/questionnaire/${questionnaireId}/checkin`,
    { code },
  );
  return data;
}

// ========== 管理端：学生 ==========

export async function getAdminStudents(): Promise<{
  success: boolean;
  students: AdminStudent[];
  can_edit: boolean;
}> {
  const { data } = await api.get("/api/admin/students");
  return data;
}

export async function createStudent(payload: {
  student_id: string;
  name: string;
  password: string;
}): Promise<BasicResponse> {
  const { data } = await api.post<BasicResponse>("/api/admin/students", payload);
  return data;
}

export async function deleteStudent(studentId: string): Promise<BasicResponse> {
  const { data } = await api.delete<BasicResponse>("/api/admin/students", {
    data: { student_id: studentId },
  });
  return data;
}

export async function batchImportStudents(csvData: string): Promise<BatchImportResult> {
  const { data } = await api.post<BatchImportResult>("/api/admin/students/batch", {
    csv_data: csvData,
  });
  return data;
}

export async function changeStudentPasswordByAdmin(
  studentId: string,
  newPassword: string,
): Promise<BasicResponse> {
  const { data } = await api.post<BasicResponse>("/api/admin/change_student_password", {
    student_id: studentId,
    new_password: newPassword,
  });
  return data;
}

// ========== 管理端：学生报名信息 ==========

export async function updateAdminStudentInfo(payload: {
  student_id: string;
  phone: string;
  wechat: string;
  suggestion: string;
}): Promise<BasicResponse> {
  const { data } = await api.put<BasicResponse>("/api/admin/students/info", payload);
  return data;
}

/** 重置学生的 OTP：仅置为未绑定状态，学生下次登录时自动经邮箱重新绑定。 */
export async function resetStudentOtp(studentId: string): Promise<BasicResponse> {
  const { data } = await api.post<BasicResponse>("/api/admin/students/reset_otp", {
    student_id: studentId,
  });
  return data;
}

/** 学生主动重置 OTP：返回待生效的绑定二维码，验证码确认后才写入。 */
export async function beginStudentOtpReset(): Promise<
  BasicResponse & { otp_bind?: OtpBindChallenge }
> {
  const { data } = await api.post<BasicResponse & { otp_bind?: OtpBindChallenge }>(
    "/api/student/otp/reset",
  );
  return data;
}

// ========== 管理端：系统设置 ==========

export async function getAdminCategories(): Promise<{
  success: boolean;
  categories: AdminCategory[];
}> {
  const { data } = await api.get("/api/admin/categories");
  return data;
}

export async function createCategory(payload: {
  name: string;
  required_credits: number;
}): Promise<BasicResponse> {
  const { data } = await api.post<BasicResponse>("/api/admin/categories", payload);
  return data;
}

/** 快速修改类别的合格学分。 */
export async function updateCategory(payload: {
  name: string;
  required_credits: number;
}): Promise<BasicResponse> {
  const { data } = await api.put<BasicResponse>("/api/admin/categories", payload);
  return data;
}

export async function deleteCategory(name: string): Promise<BasicResponse> {
  const { data } = await api.delete<BasicResponse>("/api/admin/categories", { data: { name } });
  return data;
}

export async function getTotalCredits(): Promise<{
  success: boolean;
  total_required_credits: number;
}> {
  const { data } = await api.get("/api/admin/total_credits");
  return data;
}

export async function saveTotalCredits(totalRequiredCredits: number): Promise<BasicResponse> {
  const { data } = await api.post<BasicResponse>("/api/admin/total_credits", {
    total_required_credits: totalRequiredCredits,
  });
  return data;
}

export async function getDepartments(): Promise<{ success: boolean; departments: string[] }> {
  const { data } = await api.get("/api/admin/departments");
  return data;
}

export async function createDepartment(department: string): Promise<BasicResponse> {
  const { data } = await api.post<BasicResponse>("/api/admin/departments", { department });
  return data;
}

export async function deleteDepartment(department: string): Promise<BasicResponse> {
  const { data } = await api.delete<BasicResponse>("/api/admin/departments", { data: { department } });
  return data;
}

export async function getAdmins(): Promise<{ success: boolean; admins: AdminAccount[] }> {
  const { data } = await api.get("/api/admin/admins");
  return data;
}

export async function createAdmin(payload: {
  admin_id: string;
  password: string;
  role: string;
  department: string;
}): Promise<BasicResponse & Partial<AdminOtpBundle>> {
  const { data } = await api.post<BasicResponse & Partial<AdminOtpBundle>>(
    "/api/admin/admins",
    payload,
  );
  return data;
}

/** 重置普通管理员的 OTP 第一步：返回待生效的二维码/密钥（仅本次响应可见）。 */
export async function resetAdminOtp(
  adminId: string,
): Promise<BasicResponse & Partial<OtpBindChallenge>> {
  const { data } = await api.post<BasicResponse & Partial<OtpBindChallenge>>(
    "/api/admin/admins/reset_otp",
    { admin_id: adminId },
  );
  return data;
}

/** 重置普通管理员的 OTP 第二步：系统管理员二次确认后候选密钥才生效。 */
export async function confirmAdminOtpReset(ticket: string): Promise<BasicResponse> {
  const { data } = await api.post<BasicResponse>("/api/admin/admins/reset_otp/confirm", { ticket });
  return data;
}

export async function updateAdmin(payload: {
  admin_id: string;
  password?: string;
  department?: string;
}): Promise<BasicResponse> {
  const { data } = await api.put<BasicResponse>("/api/admin/admins", payload);
  return data;
}

export async function deleteAdmin(adminId: string): Promise<BasicResponse> {
  const { data } = await api.delete<BasicResponse>("/api/admin/admins", { data: { admin_id: adminId } });
  return data;
}

// ========== 管理端：活动/记录/条目 ==========

export async function getAdminActivities(): Promise<{
  success: boolean;
  activities: AdminActivity[];
}> {
  const { data } = await api.get("/api/admin/activities");
  return data;
}

export async function createActivity(payload: {
  name: string;
  department: string;
}): Promise<BasicResponse> {
  const { data } = await api.post<BasicResponse>("/api/admin/activities", payload);
  return data;
}

export async function updateActivity(payload: {
  activity_id: string;
  department?: string;
  allowed_editors?: string[];
}): Promise<BasicResponse> {
  const { data } = await api.put<BasicResponse>("/api/admin/activities", payload);
  return data;
}

export async function deleteActivity(activityId: string): Promise<BasicResponse> {
  const { data } = await api.delete<BasicResponse>("/api/admin/activities", {
    data: { activity_id: activityId },
  });
  return data;
}

export async function getActivityRecords(
  activityId: string,
): Promise<{ success: boolean; records: AdminRecord[] }> {
  const { data } = await api.get(`/api/admin/activities/${activityId}/records`);
  return data;
}

export async function createRecord(payload: {
  activity_id: string;
  record_name: string;
  categories: string[];
}): Promise<BasicResponse & { record_id?: string }> {
  const { data } = await api.post<BasicResponse & { record_id?: string }>(
    "/api/admin/records",
    payload,
  );
  return data;
}

/** 编辑记录：名称与可行类别均可改；缩减类别时若仍有条目使用被移除的类别会被拒绝。 */
export async function updateRecord(payload: {
  record_id: string;
  record_name?: string;
  categories?: string[];
}): Promise<BasicResponse> {
  const { data } = await api.put<BasicResponse>("/api/admin/records", payload);
  return data;
}

export async function deleteRecord(recordId: string): Promise<BasicResponse> {
  const { data } = await api.delete<BasicResponse>("/api/admin/records", {
    data: { record_id: recordId },
  });
  return data;
}

export async function getRecordDetail(
  recordId: string,
): Promise<{ success: boolean; record: AdminRecordDetail }> {
  const { data } = await api.get(`/api/admin/records/${recordId}`);
  return data;
}

export async function createEntry(payload: {
  record_id: string;
  student_id: string;
  credits: number;
  categories: string[];
}): Promise<BasicResponse> {
  const { data } = await api.post<BasicResponse>("/api/admin/entries", payload);
  return data;
}

export async function updateEntry(payload: {
  record_id: string;
  entry_id?: number;
  student_id?: string;
  credits?: number;
  categories?: string[];
}): Promise<BasicResponse> {
  const { data } = await api.put<BasicResponse>("/api/admin/entries", payload);
  return data;
}

export async function deleteEntry(payload: {
  record_id: string;
  entry_id?: number;
  student_id?: string;
}): Promise<BasicResponse> {
  const { data } = await api.delete<BasicResponse>("/api/admin/entries", { data: payload });
  return data;
}

export async function batchAddEntries(payload: {
  record_id: string;
  entries_text: string;
  categories: string[];
  default_credits: number;
}): Promise<BatchImportResult> {
  const { data } = await api.post<BatchImportResult>("/api/admin/entries/batch", payload);
  return data;
}

export async function batchUpdateEntries(payload: {
  record_id: string;
  student_ids: string[];
  credits: number | null;
  categories: string[] | null;
}): Promise<BasicResponse & { updated?: number }> {
  const { data } = await api.post("/api/admin/entries/batch_update", payload);
  return data;
}

export async function batchDeleteEntries(payload: {
  record_id: string;
  student_ids: string[];
}): Promise<BasicResponse> {
  const { data } = await api.post<BasicResponse>("/api/admin/entries/batch_delete", payload);
  return data;
}

// ========== 管理端：查询、报表 ==========

export async function queryStudent(query: string): Promise<CreditReport & { message?: string }> {
  const { data } = await api.post("/api/query/student", { query });
  return data;
}

export async function getAdminReport(): Promise<AdminReport> {
  const { data } = await api.get<AdminReport>("/api/admin/report");
  return data;
}

export async function getAllStudentsCredits(): Promise<{
  success: boolean;
  students: AllStudentCredits[];
}> {
  const { data } = await api.get("/api/admin/all_students_credits");
  return data;
}

// ========== 管理端：问卷 ==========

export async function getAllQuestionnaires(): Promise<{
  success: boolean;
  questionnaires: AdminQuestionnaire[];
  total: number;
}> {
  const { data } = await api.get("/api/admin/questionnaires/all");
  return data;
}

export async function createQuestionnaireTemplate(payload: {
  activity_id: string;
  record_id: string;
  title: string;
  start_time: string;
  end_time: string;
  max_participants: number;
  custom_questions: CustomQuestion[];
  body?: QuestionnaireBody;
}): Promise<BasicResponse & { questionnaire_id?: string }> {
  const { data } = await api.post<BasicResponse & { questionnaire_id?: string }>(
    "/api/admin/questionnaire/create_template",
    payload,
  );
  return data;
}

export async function updateQuestionnaireTemplate(
  questionnaireId: string,
  payload: {
    title: string;
    start_time: string;
    end_time: string;
    max_participants: number;
    record_id?: string;
    custom_questions: CustomQuestion[];
    body?: QuestionnaireBody;
  },
): Promise<BasicResponse & { version?: number }> {
  const { data } = await api.put<BasicResponse & { version?: number }>(
    `/api/admin/questionnaire/template/${questionnaireId}`,
    payload,
  );
  return data;
}

export async function deleteQuestionnaireTemplate(questionnaireId: string): Promise<BasicResponse> {
  const { data } = await api.delete<BasicResponse>(
    `/api/admin/questionnaire/template/${questionnaireId}`,
  );
  return data;
}

export async function getQuestionnaireResponses(
  questionnaireId: string,
): Promise<{ success: boolean; responses: AdminResponse[]; message?: string }> {
  const { data } = await api.get(`/api/admin/questionnaire/responses/${questionnaireId}`);
  return data;
}

export async function updateResponse(
  responseId: string,
  payload: { phone: string; wechat: string; intended_category: string },
): Promise<BasicResponse> {
  const { data } = await api.put<BasicResponse>(
    `/api/admin/questionnaire/response/${responseId}`,
    payload,
  );
  return data;
}

export async function deleteResponse(responseId: string): Promise<BasicResponse> {
  const { data } = await api.delete<BasicResponse>(`/api/admin/questionnaire/response/${responseId}`);
  return data;
}

// ========== 管理端：现场签到 ==========

export async function openCheckin(questionnaireId: string): Promise<BasicResponse> {
  const { data } = await api.post<BasicResponse>(
    `/api/admin/questionnaire/${questionnaireId}/checkin/open`,
  );
  return data;
}

export async function closeCheckin(questionnaireId: string): Promise<BasicResponse> {
  const { data } = await api.post<BasicResponse>(
    `/api/admin/questionnaire/${questionnaireId}/checkin/close`,
  );
  return data;
}

export async function confirmCheckin(responseId: string): Promise<BasicResponse> {
  const { data } = await api.post<BasicResponse>(
    `/api/admin/questionnaire/response/${responseId}/checkin/confirm`,
  );
  return data;
}

/** 为单个报名者手动生成一次性签到码（候补默认不分配，由管理员逐人生成） */
export async function generateCheckinCode(
  responseId: string,
): Promise<BasicResponse & { checkin_code?: string }> {
  const { data } = await api.post<BasicResponse & { checkin_code?: string }>(
    `/api/admin/questionnaire/response/${responseId}/checkin/code`,
  );
  return data;
}

/** 取消学生的签到（签到开启时会补发新的一次性码，学生可重新签到） */
export async function cancelCheckin(responseId: string): Promise<BasicResponse> {
  const { data } = await api.post<BasicResponse>(
    `/api/admin/questionnaire/response/${responseId}/checkin/cancel`,
  );
  return data;
}

export async function setResponseAbsent(
  responseId: string,
  absent: boolean,
): Promise<BasicResponse> {
  const { data } = await api.post<BasicResponse>(
    `/api/admin/questionnaire/response/${responseId}/absent`,
    { absent },
  );
  return data;
}

/** 已签到（有效）但该记录下还没有条目的学生 */
export async function getCheckedInMissing(
  recordId: string,
): Promise<{ success: boolean; students: CheckedInMissingStudent[] }> {
  const { data } = await api.get(`/api/admin/records/${recordId}/checked_in_missing`);
  return data;
}

// ========== 反馈（BUG / 活动漏录） ==========

export async function submitFeedback(payload: {
  type: FeedbackType;
  content?: string;
  activity_name?: string;
  record_name?: string;
  credits?: number;
  categories?: string[];
  evidence?: string;
}): Promise<BasicResponse> {
  const { data } = await api.post<BasicResponse>("/api/student/feedback", payload);
  return data;
}

/** 修改自己待处理的 BUG 反馈 */
export async function editFeedback(
  feedbackId: string,
  content: string,
): Promise<BasicResponse> {
  const { data } = await api.put<BasicResponse>(`/api/student/feedback/${feedbackId}`, {
    content,
  });
  return data;
}

/** 漏录填写时的活动重合提示（朴素字符匹配） */
export async function matchFeedbackActivities(
  activityName: string,
): Promise<{ success: boolean; matches: FeedbackMatch[] }> {
  const { data } = await api.post("/api/student/feedback/match", {
    activity_name: activityName,
  });
  return data;
}

export async function getMyFeedback(): Promise<{
  success: boolean;
  feedbacks: FeedbackItem[];
  missing_open: boolean;
}> {
  const { data } = await api.get("/api/student/feedback");
  return data;
}

/** 漏录申请的选项数据：全部活动及各自记录的可行类别 */
export async function getFeedbackActivityOptions(): Promise<{
  success: boolean;
  activities: FeedbackActivityOption[];
}> {
  const { data } = await api.get("/api/student/feedback/activities");
  return data;
}

export async function getAdminFeedback(): Promise<{
  success: boolean;
  feedbacks: FeedbackItem[];
  missing_open: boolean;
}> {
  const { data } = await api.get("/api/admin/feedback");
  return data;
}

/** 开启/关闭集中活动反馈（开启期间学生才能提交活动漏录申请） */
export async function setMissingFeedbackOpen(
  open: boolean,
): Promise<BasicResponse & { missing_open?: boolean }> {
  const { data } = await api.post<BasicResponse & { missing_open?: boolean }>(
    "/api/admin/feedback/missing_open",
    { open },
  );
  return data;
}

/** 处理反馈：reply=回复BUG并结案；record=核定并记录；reject=拒绝；reopen=重新打开 */
export async function handleFeedback(
  feedbackId: string,
  payload: {
    action: "reply" | "record" | "reject" | "reopen";
    reply?: string;
    adjustment?: FeedbackAdjustment;
  },
): Promise<BasicResponse> {
  const { data } = await api.post<BasicResponse>(
    `/api/admin/feedback/${feedbackId}/handle`,
    payload,
  );
  return data;
}
