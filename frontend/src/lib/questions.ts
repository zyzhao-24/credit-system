import type { CustomQuestion } from "@/api/types";

export const QUESTION_TYPE_NAMES: Record<CustomQuestion["question_type"], string> = {
  description: "说明文字",
  single_choice: "单选题",
  multiple_choice: "多选题",
  text: "填空题",
  textarea: "简答题",
};

export function newQuestion(type: CustomQuestion["question_type"], order: number): CustomQuestion {
  return {
    question_id: "",
    question_type: type,
    question_text: "",
    required: false,
    options: type.includes("choice") ? ["选项1", "选项2"] : [],
    max_length: type === "text" ? 200 : type === "textarea" ? 500 : 0,
    order,
  };
}

/** 校验规则与 legacy 一致：题目文本必填，选择题至少两个选项。 */
export function validateQuestions(questions: CustomQuestion[]): string | null {
  for (let i = 0; i < questions.length; i++) {
    const question = questions[i];
    if (!question.question_text.trim()) {
      return `题目${i + 1}的文本不能为空`;
    }
    if (question.question_type.includes("choice") && question.options.length < 2) {
      return `题目${i + 1}至少需要2个选项`;
    }
  }
  return null;
}
