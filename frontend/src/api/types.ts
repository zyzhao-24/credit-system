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
  question_type:
    | "description"
    | "single_choice"
    | "multiple_choice"
    | "text"
    | "textarea"
    | "number"
    | "date"
    | "rating";
  question_text: string;
  required: boolean;
  options: string[];
  max_length: number;
  /** 文本题是否多行作答（简答）；旧数据 textarea 类型等同多行 */
  multiline?: boolean;
  /** 评分题的满分（2-10），其余题型为 0 */
  max_rating: number;
  /** 选择题是否允许"其他"自定义填写项（答案以"其他："前缀存储） */
  allow_other?: boolean;
  /** 文本题格式校验：none/phone/email/idcard/regex */
  format?: "none" | "phone" | "email" | "idcard" | "regex";
  /** format=regex 时的自定义正则表达式 */
  pattern?: string;
  /** 数字题的取值范围（null 表示不限） */
  min_value?: number | null;
  max_value?: number | null;
  order: number;
}

export type CustomAnswers = Record<string, { answer: string | string[] }>;

/**
 * 正文文档：段落数组，每段是文本片段、题目槽位与信息槽位的有序混排。
 * 整篇文字均可自定义，个人信息（姓名/学号/联系方式）与题目嵌入文中，
 * 填写后即为连贯的文档。
 */
export type BodyField =
  | "student_name"
  | "student_id"
  | "phone"
  | "wechat"
  | "activity_name"
  | "record_name"
  | "category";

export type BodyPart =
  | { type: "text"; text: string }
  | { type: "question"; question_id: string }
  | { type: "field"; field: BodyField };

export type QuestionnaireBody = BodyPart[][];

/** 提交时保存的问卷快照：模板后续修改不影响历史提交的解读 */
export interface TemplateSnapshot {
  title: string;
  /** 提交时模板的版本号（旧快照可能没有） */
  version?: number;
  /** 提交时绑定的记录及其可行类别（旧快照可能没有） */
  record_id?: string;
  record_name?: string;
  record_categories?: string[];
  has_category_question: boolean;
  custom_questions: CustomQuestion[];
  /** 正文文档（旧快照没有时按题目顺序合成） */
  body?: QuestionnaireBody;
}

export interface AvailableQuestionnaire {
  questionnaire_id: string;
  activity_id: string;
  title: string;
  activity_name: string;
  /** 绑定的记录及其可行类别（未绑定/独立问卷为空） */
  record_id?: string;
  record_name?: string;
  record_categories?: string[];
  start_time: string;
  end_time: string;
  max_participants: number;
  response_count: number;
  is_registered: boolean;
  my_rank: number;
  is_waitlist: boolean;
  has_category_question: boolean;
  custom_questions: CustomQuestion[];
  /** 正文文档：题目嵌入文字流 */
  body?: QuestionnaireBody;
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
  /** 签到是否开启（管理员在问卷详情页开关） */
  checkin_open: boolean;
  checked_in_at: string;
  /** absent 缺席 / none 未签到 / pending 候补待确认 / valid 已签到 */
  checkin_state: "absent" | "none" | "pending" | "valid";
  absent: boolean;
}

export interface AdminStudent {
  student_id: string;
  name: string;
  /** 以下字段仅系统管理员可见（联系方式、报名详情与 OTP 状态） */
  phone?: string;
  wechat?: string;
  suggestion?: string;
  updated_at?: string;
  has_otp?: boolean;
}

export interface AdminCategory {
  name: string;
  required_credits: number;
}

export interface AdminAccount {
  admin_id: string;
  role: string;
  department: string;
  /** 是否已绑定 OTP（system 账号的 OTP 只能通过本机维护台 :5002 维护） */
  has_otp: boolean;
}

/** 创建/重置 OTP 后一次性返回的绑定信息（仅本次响应可见）。 */
export interface AdminOtpBundle {
  otp_secret: string;
  otp_uri: string;
  otp_qr: string;
}

/** 待生效的 OTP 绑定：二维码 + 票据，验证/确认后候选密钥才写入。 */
export interface OtpBindChallenge extends AdminOtpBundle {
  ticket: string;
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
  categories: string[];
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
  /** 记录的可行类别（条目类别必须从中选择） */
  categories: string[];
  /** 活动类别（全部记录类别的并集，仅展示用） */
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
  /** activity_template=活动报名问卷；standalone=独立问卷（不绑定活动，activity_id 为空） */
  questionnaire_type: "activity_template" | "standalone";
  title: string;
  activity_name: string;
  activity_id: string;
  /** 绑定的记录及其可行类别；意向类别题由多类别记录自动生成 */
  record_id: string;
  record_name: string;
  record_categories: string[];
  start_time: string;
  end_time: string;
  max_participants: number;
  response_count: number;
  status: string;
  created_time: string;
  is_ended: boolean;
  has_category_question: boolean;
  custom_questions: CustomQuestion[];
  /** 正文文档：题目嵌入文字流 */
  body?: QuestionnaireBody;
  /** 模板版本号：题目或标题每次修改时 +1 */
  version: number;
  /** 现场签到会话开关（每位报名者的一次性签到码在填写记录中展示） */
  checkin_open: boolean;
}

/** 已签到（有效）但记录下还没有条目的学生 */
export interface CheckedInMissingStudent {
  student_id: string;
  student_name: string;
  intended_category: string;
  checked_in_at: string;
}

/** 反馈类型：bug=BUG 反馈（每人一条待处理，可修改）；missing=活动漏录 */
export type FeedbackType = "bug" | "missing";

/** 与已有活动的朴素字符匹配结果（仅作人工参考） */
export interface FeedbackMatch {
  activity_id: string;
  name: string;
  rate: number;
}

/** 管理员核定漏录申请后的合理值 */
export interface FeedbackAdjustment {
  activity_name: string;
  record_name: string;
  credits: number;
  categories: string[];
}

/** 漏录申请的选项数据：活动及其记录的可行类别 */
export interface FeedbackActivityOption {
  activity_id: string;
  name: string;
  records: {
    record_id: string;
    record_name: string;
    categories: string[];
  }[];
}

export interface FeedbackItem {
  feedback_id: string;
  student_id: string;
  student_name: string;
  type: FeedbackType;
  type_text: string;
  content: string;
  status: "pending" | "resolved";
  /** ""=未结案 / recorded=核定并记录 / rejected=已拒绝 */
  outcome: "" | "recorded" | "rejected";
  outcome_text: string;
  reply: string;
  handled_by: string;
  created_at: string;
  handled_at: string;
  /** 以下为漏录申请的结构化字段（bug 类型为空） */
  activity_name: string;
  record_name: string;
  credits: number;
  categories: string[];
  evidence: string;
  match_hint: FeedbackMatch[];
  adjustment: FeedbackAdjustment | null;
}

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
  /** 提交时的问卷快照；旧数据可能没有，回退到当前模板 */
  template_snapshot?: TemplateSnapshot | null;
  /** 提交时模板的版本号（旧数据为 null） */
  template_version?: number | null;
  submit_time: string;
  status: "active" | "cancelled";
  rank: number;
  is_waitlist: boolean;
  is_selected: boolean;
  is_ended: boolean;
  checked_in_at: string;
  checkin_confirmed: boolean;
  /** absent 缺席 / none 未签到 / pending 候补待确认 / valid 已签到 */
  checkin_state: "absent" | "none" | "pending" | "valid";
  absent: boolean;
  /** 该报名的一次性签到码（签到开启且未签到时非空，仅管理端可见） */
  checkin_code: string;
}

export interface BatchImportResult {
  success: boolean;
  added: number;
  updated: number;
  ignored?: number;
  errors: string[];
  message?: string;
}
