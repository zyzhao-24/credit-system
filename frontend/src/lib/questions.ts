import type { BodyField, CustomQuestion, QuestionnaireBody } from "@/api/types";

/** 正文可嵌入的信息槽位（与后端 BODY_FIELDS 一致） */
export const FIELD_NAMES: Record<BodyField, string> = {
  student_name: "姓名",
  student_id: "学号",
  phone: "手机号",
  wechat: "微信号",
  activity_name: "活动名称",
  record_name: "记录名称",
  category: "意向类别",
};

/**
 * 题型清单：文本题（填空/简答合并，用"多行作答"区分）、数字、日期、评分等。
 * 旧数据里的 textarea 类型等同 text + multiline；description 只存在于旧数据，
 * 新模板用文字段落代替说明块。
 */
export const QUESTION_TYPE_NAMES: Record<CustomQuestion["question_type"], string> = {
  description: "说明文字",
  single_choice: "单选题",
  multiple_choice: "多选题",
  text: "文本题",
  textarea: "文本题",
  number: "数字题",
  date: "日期题",
  rating: "评分题",
};

/** 设计器可插入正文的题型（说明文字由正文文本段落承担，不再是题目） */
export const BUILDER_TYPES: CustomQuestion["question_type"][] = [
  "single_choice",
  "multiple_choice",
  "text",
  "number",
  "date",
  "rating",
];

/** 为没有正文的旧模板合成文档：说明文字变文本段，其余题目各占一段（与后端一致） */
export function synthesizeBody(questions: CustomQuestion[]): QuestionnaireBody {
  const body: QuestionnaireBody = [];
  for (const question of questions) {
    if (question.question_type === "description") {
      if (question.question_text.trim()) {
        body.push([{ type: "text", text: question.question_text.trim() }]);
      }
    } else {
      body.push([{ type: "question", question_id: question.question_id }]);
    }
  }
  return body;
}

/** 取问卷的正文文档，缺失时按题目顺序合成 */
export function bodyOf(source: {
  body?: QuestionnaireBody | null;
  custom_questions: CustomQuestion[];
}): QuestionnaireBody {
  return source.body ?? synthesizeBody(source.custom_questions);
}

/** 文本题格式校验选项（与后端 TEXT_FORMATS 一致） */
export const TEXT_FORMAT_NAMES: Record<NonNullable<CustomQuestion["format"]>, string> = {
  none: "无校验",
  phone: "手机号",
  email: "邮箱",
  idcard: "身份证号",
  regex: "自定义正则",
};

export const OTHER_PREFIX = "其他：";

/** 与后端 _FORMAT_PATTERNS 一致的文本格式校验 */
const FORMAT_PATTERNS: Record<string, { pattern: RegExp; message: string }> = {
  phone: { pattern: /^1[3-9]\d{9}$/, message: "手机号格式不正确" },
  email: { pattern: /^[\w.+-]+@[\w-]+(\.[\w-]+)+$/, message: "邮箱格式不正确" },
  idcard: { pattern: /^\d{17}[\dXx]$/, message: "身份证号格式不正确" },
};

function choiceValueOk(question: CustomQuestion, value: string | string[]): boolean {
  if (typeof value !== "string") return false;
  if (question.options.includes(value)) return true;
  return (
    question.allow_other === true && value.startsWith(OTHER_PREFIX) && value.length > OTHER_PREFIX.length
  );
}

/**
 * 提交前的客户端答案预校验（与后端 validate_answers 一致，后端仍会强制校验）。
 * 返回错误消息或 null。
 */
export function validateAnswers(
  questions: CustomQuestion[],
  answers: Record<string, { answer: string | string[] } | undefined>,
): string | null {
  for (const question of questions) {
    const type = question.question_type;
    if (type === "description") continue;
    const value = answers[question.question_id]?.answer;
    const empty =
      value === undefined ||
      (typeof value === "string" && !value.trim()) ||
      (Array.isArray(value) && value.length === 0);
    const label = question.question_text;
    if (empty) {
      if (question.required) return `请回答：${label}`;
      continue;
    }
    if (type === "single_choice") {
      if (!choiceValueOk(question, value)) return `「${label}」的答案不在选项中`;
    } else if (type === "multiple_choice") {
      if (!Array.isArray(value) || value.some((item) => !choiceValueOk(question, item))) {
        return `「${label}」的答案不在选项中`;
      }
    } else if (type === "number") {
      const number = Number(value);
      if (Number.isNaN(number)) return `「${label}」需要填写数字`;
      if (question.min_value != null && number < question.min_value) {
        return `「${label}」不能小于 ${question.min_value}`;
      }
      if (question.max_value != null && number > question.max_value) {
        return `「${label}」不能大于 ${question.max_value}`;
      }
    } else if (type === "date") {
      if (!/^\d{4}-\d{2}-\d{2}$/.test(String(value))) return `「${label}」需要填写日期`;
    } else if (type === "rating") {
      const score = parseInt(String(value), 10);
      if (!Number.isInteger(score) || score < 1 || score > (question.max_rating || 5)) {
        return `「${label}」的评分超出范围`;
      }
    } else if (type === "text" || type === "textarea") {
      const text = String(value);
      const maxLength = question.max_length || 500;
      if (text.length > maxLength) return `「${label}」超过最大字符数 ${maxLength}`;
      const format = question.format ?? "none";
      if (format in FORMAT_PATTERNS) {
        const { pattern, message } = FORMAT_PATTERNS[format];
        if (!pattern.test(text.trim())) return `「${label}」${message}`;
      } else if (format === "regex" && question.pattern) {
        try {
          if (!new RegExp(question.pattern).test(text.trim())) {
            return `「${label}」格式不符合要求`;
          }
        } catch {
          // 模板保存时已校验过正则有效性
        }
      }
    }
  }
  return null;
}

export function isMultiline(question: CustomQuestion): boolean {
  return question.question_type === "textarea" || question.multiline === true;
}

export function newQuestion(type: CustomQuestion["question_type"], order: number): CustomQuestion {
  return {
    question_id: "",
    question_type: type === "textarea" ? "text" : type,
    question_text: "",
    required: false,
    options: type.includes("choice") ? ["选项1", "选项2"] : [],
    max_length: type === "text" || type === "textarea" ? 500 : 0,
    multiline: false,
    max_rating: type === "rating" ? 5 : 0,
    allow_other: false,
    format: "none",
    pattern: "",
    min_value: null,
    max_value: null,
    order,
  };
}

/** 校验规则与后端 normalize_custom_questions 一致。 */
export function validateQuestions(questions: CustomQuestion[]): string | null {
  for (let i = 0; i < questions.length; i++) {
    const question = questions[i];
    if (!question.question_text.trim()) {
      return `题目${i + 1}的文本不能为空`;
    }
    if (question.question_type.includes("choice")) {
      const options = question.options.map((option) => option.trim()).filter(Boolean);
      if (options.length < 2) {
        return `题目${i + 1}至少需要2个选项`;
      }
      if (new Set(options).size !== options.length) {
        return `题目${i + 1}的选项重复`;
      }
    }
    if (
      question.question_type === "rating" &&
      (!Number.isInteger(question.max_rating) || question.max_rating < 2 || question.max_rating > 10)
    ) {
      return `题目${i + 1}的评分上限需为 2-10 的整数`;
    }
    if (question.question_type === "number") {
      const minValue = question.min_value ?? null;
      const maxValue = question.max_value ?? null;
      if (minValue !== null && maxValue !== null && minValue > maxValue) {
        return `题目${i + 1}的最小值不能大于最大值`;
      }
    }
    if (question.question_type === "text" || question.question_type === "textarea") {
      if (question.format === "regex") {
        if (!question.pattern?.trim()) {
          return `题目${i + 1}选择自定义正则时必须填写表达式`;
        }
        try {
          new RegExp(question.pattern);
        } catch {
          return `题目${i + 1}的正则表达式无效`;
        }
      }
    }
  }
  return null;
}
