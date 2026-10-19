import type { CustomAnswers, CustomQuestion, QuestionnaireBody } from "@/api/types";
import { Markdown, MarkdownInline } from "@/components/Markdown";
import { answerDisplayText } from "@/lib/letter";
import type { LetterFields } from "@/lib/letter";
import { cn } from "@/lib/utils";

interface QuestionDocumentProps {
  body: QuestionnaireBody;
  questions: CustomQuestion[];
  answers: CustomAnswers;
  /** 点击题目槽位（弹出侧栏作答） */
  onAnswer: (questionId: string) => void;
  /** 当前正在侧栏作答的题目 */
  activeQid?: string | null;
  /** 信息槽位的静态取值（姓名/学号/联系方式/活动/记录等） */
  fields?: LetterFields;
  /** 意向类别槽位：多类别记录时为文内单选；否则显示 fields.category 静态值 */
  categorySlot?: {
    options: string[];
    value: string;
    onChange: (value: string) => void;
  } | null;
}

/**
 * 学生填写视图：正文始终按 Markdown 渲染为连贯文档，
 * 题目槽位显示渲染后的作答（未作答显示可点击的空白），点击槽位弹出侧栏作答。
 */
export function QuestionDocument({
  body,
  questions,
  answers,
  onAnswer,
  activeQid,
  fields,
  categorySlot,
}: QuestionDocumentProps) {
  const questionMap = new Map(questions.map((question) => [question.question_id, question]));

  const renderField = (field: string) => {
    if (field === "category" && categorySlot) {
      return (
        <select
          value={categorySlot.value}
          onChange={(event) => categorySlot.onChange(event.target.value)}
          className="mx-1 h-8 rounded-md border-2 border-[#b0b0b0] bg-white px-1.5 text-sm focus:border-primary focus:outline-none"
        >
          {categorySlot.options.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      );
    }
    const value = fields?.[field as keyof LetterFields]?.trim();
    return (
      <span className="mx-1 inline-block border-b-2 border-[#b0b0b0] px-1 font-medium">
        {value || "＿＿＿＿"}
      </span>
    );
  };

  const renderQuestionSlot = (question: CustomQuestion) => {
    const display = answerDisplayText(question, answers);
    return (
      <button
        type="button"
        onClick={() => onAnswer(question.question_id)}
        title={`点击作答：${question.question_text}`}
        className={cn(
          "mx-0.5 inline max-w-full cursor-pointer rounded px-1 text-left align-baseline transition-colors",
          activeQid === question.question_id
            ? "bg-[#e3f2fd] outline outline-1 outline-primary"
            : "hover:bg-[#f0f7ff]",
          display ? "border-b-2 border-[#9ec9ef]" : "border-b-2 border-dashed border-[#bbb]",
        )}
      >
        {display ? (
          <MarkdownInline text={display} />
        ) : (
          <span className="text-[#999]">＿{question.question_text || "点击作答"}＿</span>
        )}
        {question.required ? <span className="text-danger">*</span> : null}
      </button>
    );
  };

  return (
    <div className="rounded-lg border border-[#e8e2d5] bg-[#fffef9] px-5 py-4">
      {body.map((paragraph, pIndex) => {
        // 纯文字段落：整段按 Markdown 渲染（列表/标题/公式块等可用）
        if (paragraph.every((part) => part.type === "text")) {
          const text = paragraph
            .map((part) => (part.type === "text" ? part.text : ""))
            .join("");
          return (
            <Markdown
              key={pIndex}
              text={text}
              className="letter-paragraph mb-3 text-[15px] leading-loose text-[#333] last:mb-0"
            />
          );
        }
        // 混排段落：文字片段按行内 Markdown 渲染，槽位保持嵌入文字流
        return (
          <p
            key={pIndex}
            className="mb-3 text-[15px] leading-loose text-[#333] last:mb-0"
            style={{ textIndent: "2em" }}
          >
            {paragraph.map((part, partIndex) => {
              if (part.type === "text") {
                return <MarkdownInline key={partIndex} text={part.text} />;
              }
              if (part.type === "field") {
                return <span key={partIndex}>{renderField(part.field)}</span>;
              }
              const question = questionMap.get(part.question_id);
              if (!question) return null;
              return <span key={partIndex}>{renderQuestionSlot(question)}</span>;
            })}
          </p>
        );
      })}
    </div>
  );
}
