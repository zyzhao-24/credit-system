import type { BodyField, CustomAnswers, CustomQuestion, QuestionnaireBody } from "@/api/types";
import { bodyOf, OTHER_PREFIX } from "@/lib/questions";

/** 信息槽位的取值：姓名/学号/联系方式/活动/记录/意向类别 */
export type LetterFields = Partial<Record<BodyField, string>>;

const BLANK = "＿＿＿＿";

function answerToText(question: CustomQuestion, value: string | string[]): string {
  if (Array.isArray(value)) {
    return value
      .map((item) => (item.startsWith(OTHER_PREFIX) ? item.slice(OTHER_PREFIX.length) : item))
      .join("、");
  }
  if (question.question_type === "rating") {
    return `${value} 分`;
  }
  if (value.startsWith(OTHER_PREFIX)) {
    return value.slice(OTHER_PREFIX.length);
  }
  return value;
}

/** 某道题当前作答的展示文本（Markdown 源码，渲染后嵌入文中）；未作答返回 null */
export function answerDisplayText(question: CustomQuestion, answers: CustomAnswers): string | null {
  const value = answers[question.question_id]?.answer;
  const empty =
    value === undefined ||
    (typeof value === "string" && !value.trim()) ||
    (Array.isArray(value) && value.length === 0);
  return empty ? null : answerToText(question, value);
}

/**
 * 把正文文档组合成连贯的段落：整篇文字都是设计者自定义的，
 * 题目槽位替换为作答、信息槽位替换为实际取值（未作答/无取值显示为空缺）。
 */
export function composeLetter(
  fields: LetterFields,
  questions: CustomQuestion[],
  answers: CustomAnswers,
  body?: QuestionnaireBody,
): string[] {
  const questionMap = new Map(questions.map((question) => [question.question_id, question]));
  const resolvedBody = body ?? bodyOf({ custom_questions: questions });
  const paragraphs: string[] = [];
  for (const paragraph of resolvedBody) {
    const text = paragraph
      .map((part) => {
        if (part.type === "text") return part.text;
        if (part.type === "field") return fields[part.field]?.trim() || BLANK;
        const question = questionMap.get(part.question_id);
        if (!question) return "";
        return answerDisplayText(question, answers) ?? BLANK;
      })
      .join("")
      .trim();
    if (text) paragraphs.push(text);
  }
  return paragraphs;
}

/** 设计器里的示例答案：让全文渲染在保存前即可读。 */
export function sampleAnswers(questions: CustomQuestion[]): CustomAnswers {
  const answers: CustomAnswers = {};
  for (const question of questions) {
    switch (question.question_type) {
      case "single_choice":
        answers[question.question_id] = { answer: question.options[0] ?? "选项" };
        break;
      case "multiple_choice":
        answers[question.question_id] = { answer: question.options.slice(0, 2) };
        break;
      case "text":
      case "textarea":
        answers[question.question_id] = { answer: "示例回答内容" };
        break;
      case "number":
        answers[question.question_id] = { answer: String(question.min_value ?? 1) };
        break;
      case "date":
        answers[question.question_id] = { answer: "2026-01-01" };
        break;
      case "rating":
        answers[question.question_id] = { answer: String(Math.min(question.max_rating || 5, 4)) };
        break;
      default:
        break;
    }
  }
  return answers;
}
