import { Checkbox } from "@/components/ui/checkbox";
import { Input, Textarea } from "@/components/ui/input";
import type { CustomAnswers, CustomQuestion } from "@/api/types";
import { cn } from "@/lib/utils";

interface QuestionRendererProps {
  questions: CustomQuestion[];
  answers: CustomAnswers;
  onChange: (answers: CustomAnswers) => void;
  /** 题号起始值（意向类别固定为第 1 题时为 2） */
  startIndex?: number;
}

const optionClass =
  "flex items-center gap-2.5 rounded-md border-2 border-[#e0e0e0] px-3 py-2.5 cursor-pointer transition-colors hover:border-primary hover:bg-[#f5f9ff] has-checked:border-primary has-checked:bg-[#e3f2fd]";

/** 学生填写问卷时的自定义题目渲染器。 */
export function QuestionRenderer({ questions, answers, onChange, startIndex = 2 }: QuestionRendererProps) {
  const setAnswer = (questionId: string, answer: string | string[]) => {
    onChange({ ...answers, [questionId]: { answer } });
  };

  return (
    <>
      {questions.map((question, index) => {
        const number = index + startIndex;
        const requiredMark = question.required ? <span className="text-danger">*</span> : null;
        const current = answers[question.question_id]?.answer;

        if (question.question_type === "description") {
          return (
            <div
              key={question.question_id || index}
              className="mt-5 rounded-md border-l-4 border-primary bg-[#f5f5f5] px-3 py-3 whitespace-pre-wrap leading-relaxed text-sm"
            >
              {question.question_text}
            </div>
          );
        }

        return (
          <div key={question.question_id || index} className="mt-5">
            <p className="mb-2.5 font-medium">
              {number}. {question.question_text} {requiredMark}
            </p>

            {question.question_type === "single_choice" ? (
              <div className="flex flex-col gap-2">
                {question.options.map((option) => (
                  <label key={option} className={cn(optionClass)}>
                    <input
                      type="radio"
                      name={`question_${question.question_id}`}
                      value={option}
                      checked={current === option}
                      onChange={() => setAnswer(question.question_id, option)}
                      className="h-4.5 w-4.5 accent-primary"
                    />
                    <span>{option}</span>
                  </label>
                ))}
              </div>
            ) : null}

            {question.question_type === "multiple_choice" ? (
              <div className="flex flex-col gap-2">
                {question.options.map((option) => {
                  const selected = Array.isArray(current) ? current : [];
                  const checked = selected.includes(option);
                  return (
                    <label key={option} className={cn(optionClass)}>
                      <Checkbox
                        checked={checked}
                        onCheckedChange={(state) => {
                          const next =
                            state === true
                              ? [...selected, option]
                              : selected.filter((item) => item !== option);
                          setAnswer(question.question_id, next);
                        }}
                      />
                      <span>{option}</span>
                    </label>
                  );
                })}
              </div>
            ) : null}

            {question.question_type === "text" ? (
              <Input
                value={typeof current === "string" ? current : ""}
                maxLength={question.max_length || 200}
                placeholder="请输入答案"
                onChange={(event) => setAnswer(question.question_id, event.target.value)}
              />
            ) : null}

            {question.question_type === "textarea" ? (
              <Textarea
                rows={4}
                value={typeof current === "string" ? current : ""}
                maxLength={question.max_length || 500}
                placeholder="请输入答案"
                onChange={(event) => setAnswer(question.question_id, event.target.value)}
              />
            ) : null}
          </div>
        );
      })}
    </>
  );
}
