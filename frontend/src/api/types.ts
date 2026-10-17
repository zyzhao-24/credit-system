/** API payload types mirroring the Flask backend responses. */

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user_type: "student" | "admin";
  role: string;
  department: string;
  name: string;
}

/** 登录第一步（密码）的响应：密码正确后进入 OTP 步骤而非直接发令牌。 */
export interface OtpRequiredResponse {
  success: boolean;
  otp_required: true;
  otp_ticket: string;
  message: string;
}

export type LoginStepOneResponse = TokenResponse | OtpRequiredResponse;

export function isOtpRequired(response: LoginStepOneResponse): response is OtpRequiredResponse {
  return (response as OtpRequiredResponse).otp_required === true;
}

export interface AuthUser {
  sub: string;
  user_type: "student" | "admin";
  role: string;
  department: string;
  name: string;
}

export interface CategoryStatus {
  credits: number;
  required: number;
  qualified: boolean;
}

export interface CreditActivityItem {
  activity_name: string;
  record_name: string;
  credits: number;
  categories: string[];
  assigned_category: string | null;
}

export interface CreditReport {
  success: boolean;
  student_id: string;
  student_name: string;
  total_credits: number;
  total_required: number;
  total_qualified: boolean;
  all_categories_qualified: boolean;
  final_qualified: boolean;
  category_status: Record<string, CategoryStatus>;
  activities: CreditActivityItem[];
}

export interface CategoryInfo {
  category_id: string;
  name: string;
  required_credits: number;
}

export interface ActivityListItem {
  activity_id: string;
  activity_name: string;
}

export interface StudentActivities {
  success: boolean;
  category_activities: Record<string, ActivityListItem[]>;
  no_category_activities: ActivityListItem[];
}

/** 学生报名信息（原注册问卷，已并入学生档案）。 */
export interface StudentProfile {
  student_id: string;
  name: string;
  phone: string;
  wechat: string;
  suggestion: string;
  updated_at: string;
}

export interface CustomQuestion {
  question_id: string;
  question_type: "description" | "single_choice" | "multiple_choice" | "text" | "textarea";
  question_text: string;
  required: boolean;
  options: string[];
  max_length: number;
  order: number;
}

export type CustomAnswers = Record<string, { answer: string | string[] }>;

export interface AvailableQuestionnaire {
  questionnaire_id: string;
  activity_id: string;
  title: string;
  activity_name: string;
  start_time: string;
  end_time: string;
  max_participants: number;
  response_count: number;
  is_registered: boolean;
  my_rank: number;
  is_waitlist: boolean;
  has_category_question: boolean;
  custom_questions: CustomQuestion[];
}

export interface MyRegistration {
  response_id: string;
  questionnaire_id: string;
  student_id: string;
  student_name: string;
  phone: string;
  wechat: string;
  intended_category: string;
  custom_answers: CustomAnswers;
  submit_time: string;
  status: "active" | "cancelled";
  rank: number;
  is_waitlist: boolean;
  is_selected: boolean;
  is_ended: boolean;
  questionnaire_title: string;
  activity_name: string;
  max_participants: number;
}

export interface AdminStudent {
  student_id: string;
  name: string;
}

export interface AdminCategory {
  name: string;
  required_credits: number;
}

export interface AdminAccount {
  admin_id: string;
  role: string;
  department: string;
  /** 是否已绑定 OTP（system 账号的 OTP 只能通过 manage.py 维护） */
  has_otp: boolean;
}

/** 创建/重置管理员 OTP 后一次性返回的绑定信息（仅本次响应可见）。 */
export interface AdminOtpBundle {
  otp_secret: string;
  otp_uri: string;
  otp_qr: string;
}

export interface AdminActivity {
  activity_id: string;
  name: string;
  categories: string[];
  records_count: number;
  department: string;
  created_by: string;
  allowed_editors: string[];
  has_questionnaire: boolean;
  questionnaire_start: string;
  questionnaire_end: string;
  max_participants: number;
  can_edit: boolean;
  current_participants?: number;
}

export interface AdminRecord {
  record_id: string;
  record_name: string;
  entries_count: number;
}

export interface AdminEntry {
  entry_id: number;
  student_id: string;
  student_name: string;
  credits: number;
  categories: string[];
  student_exists: boolean;
}

export interface AdminRecordDetail {
  record_id: string;
  record_name: string;
  activity_id: string;
  activity_name: string;
  activity_categories: string[];
  entries: AdminEntry[];
}

export interface ReportStats {
  qualified: number;
  unqualified: number;
  percentage: number;
}

export interface ReportStudent {
  student_id: string;
  student_name: string;
  total_credits: number;
  category_status: Record<string, CategoryStatus>;
  total_qualified: boolean;
  final_qualified: boolean;
}

export interface AdminReport {
  success: boolean;
  category_activities: Record<string, ActivityListItem[]>;
  no_category_activities: ActivityListItem[];
  category_stats: Record<string, ReportStats>;
  total_stats: ReportStats;
  final_stats: ReportStats;
  score_ranges: Record<string, number>;
  total_students: number;
  is_system_admin: boolean;
  students?: ReportStudent[];
}

export interface AllStudentCredits {
  student_id: string;
  student_name: string;
  total_credits: number;
  total_qualified: boolean;
  all_categories_qualified: boolean;
  final_qualified: boolean;
  category_status: Record<string, CategoryStatus>;
}

export interface AdminQuestionnaireTemplate {
  questionnaire_id: string;
  questionnaire_type: "activity_template";
  title: string;
  activity_name: string;
  activity_id: string;
  start_time: string;
  end_time: string;
  max_participants: number;
  response_count: number;
  status: string;
  created_time: string;
  is_ended: boolean;
  has_category_question: boolean;
  custom_questions: CustomQuestion[];
}

/** 管理端学生报名信息（与学生端档案同构）。 */
export type AdminStudentInfo = StudentProfile;

export type AdminQuestionnaire = AdminQuestionnaireTemplate;

export interface AdminResponse {
  response_id: string;
  questionnaire_id: string;
  student_id: string;
  student_name: string;
  phone: string;
  wechat: string;
  intended_category: string;
  custom_answers: CustomAnswers;
  submit_time: string;
  status: "active" | "cancelled";
  rank: number;
  is_waitlist: boolean;
  is_selected: boolean;
  is_ended: boolean;
}

export interface BatchImportResult {
  success: boolean;
  added: number;
  updated: number;
  ignored?: number;
  errors: string[];
  message?: string;
}
