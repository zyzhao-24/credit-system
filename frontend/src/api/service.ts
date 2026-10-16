import { api } from "./client";
import type {
  AdminAccount,
  AdminActivity,
  AdminCategory,
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
  CreditReport,
  CustomAnswers,
  CustomQuestion,
  EmailConfig,
  MyRegistration,
  RegistrationQuestionnaire,
  StudentActivities,
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
): Promise<TokenResponse> {
  const body = new URLSearchParams({
    grant_type: "password",
    username,
    password: passwordDigest,
    user_type: userType,
  });
  const { data } = await api.post<TokenResponse>("/api/auth/token", body, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  return data;
}

export async function logoutRemote(): Promise<void> {
  await api.post("/api/auth/logout");
}

export async function registerStudent(payload: {
  name: string;
  student_id: string;
  phone: string;
  wechat: string;
  password: string;
  suggestion: string;
}): Promise<BasicResponse> {
  const { data } = await api.post<BasicResponse>("/api/student/register", payload);
  return data;
}

export async function forgotPassword(studentId: string): Promise<BasicResponse> {
  const { data } = await api.post<BasicResponse>("/api/student/forgot_password", {
    student_id: studentId,
  });
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

export async function getRegistrationQuestionnaire(): Promise<{
  success: boolean;
  questionnaire: RegistrationQuestionnaire;
}> {
  const { data } = await api.get("/api/student/registration_questionnaire");
  return data;
}

export async function updateRegistrationQuestionnaire(payload: {
  phone: string;
  wechat: string;
  suggestion: string;
}): Promise<BasicResponse> {
  const { data } = await api.put<BasicResponse>("/api/student/registration_questionnaire", payload);
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

export async function getEmailConfig(): Promise<{ success: boolean; email_config: EmailConfig }> {
  const { data } = await api.get("/api/admin/email_config");
  return data;
}

export async function saveEmailConfig(payload: {
  service_email: string;
  service_email_password: string;
  student_email_suffix: string;
}): Promise<BasicResponse> {
  const { data } = await api.post<BasicResponse>("/api/admin/email_config", payload);
  return data;
}

export async function sendTestEmail(
  testEmail: string,
  debug: boolean,
): Promise<BasicResponse & { debug_info?: string[] }> {
  const { data } = await api.post("/api/admin/test_email", { test_email: testEmail, debug });
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
}): Promise<BasicResponse> {
  const { data } = await api.post<BasicResponse>("/api/admin/admins", payload);
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
  categories: string[];
  department: string;
}): Promise<BasicResponse> {
  const { data } = await api.post<BasicResponse>("/api/admin/activities", payload);
  return data;
}

export async function updateActivity(payload: {
  activity_id: string;
  categories?: string[];
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
}): Promise<BasicResponse & { record_id?: string }> {
  const { data } = await api.post<BasicResponse & { record_id?: string }>(
    "/api/admin/records",
    payload,
  );
  return data;
}

export async function renameRecord(payload: {
  record_id: string;
  record_name: string;
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

export async function updateQuestionnaire(payload: {
  questionnaire_id: string;
  phone: string;
  wechat: string;
  suggestion?: string;
  status?: string;
}): Promise<BasicResponse> {
  const { data } = await api.put<BasicResponse>("/api/admin/questionnaire/update", payload);
  return data;
}

export async function deleteQuestionnaire(questionnaireId: string): Promise<BasicResponse> {
  const { data } = await api.delete<BasicResponse>(`/api/admin/questionnaire/${questionnaireId}`);
  return data;
}

export async function createQuestionnaireTemplate(payload: {
  activity_id: string;
  title: string;
  start_time: string;
  end_time: string;
  max_participants: number;
  custom_questions: CustomQuestion[];
}): Promise<BasicResponse> {
  const { data } = await api.post<BasicResponse>(
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
    custom_questions: CustomQuestion[];
  },
): Promise<BasicResponse> {
  const { data } = await api.put<BasicResponse>(
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
