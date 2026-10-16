import { ArrowDown, ArrowUp, Plus, X } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input, Textarea } from "@/components/ui/input";
import { newQuestion, QUESTION_TYPE_NAMES as TYPE_NAMES } from "@/lib/questions";
import type { CustomQuestion } from "@/api/types";

interface QuestionBuilderProps {
  questions: CustomQuestion[];
  onChange: (questions: CustomQuestion[]) => void;
}

/** 管理端自定义题目编辑器（创建/编辑问卷模板共用）。 */
export function QuestionBuilder({ questions, onChange }: QuestionBuilderProps) {
  const update = (index: number, patch: Partial<CustomQuestion>) => {
    onChange(questions.map((q, i) => (i === index ? { ...q, ...patch } : q)));
  };

  const move = (index: number, direction: -1 | 1) => {
    const target = index + direction;
    if (target < 0 || target >= questions.length) return;
    const next = [...questions];
    [next[index], next[target]] = [next[target], next[index]];
    onChange(next.map((q, i) => ({ ...q, order: i + 1 })));
  };

  const remove = (index: number) => {
    onChange(questions.filter((_, i) => i !== index).map((q, i) => ({ ...q, order: i + 1 })));
  };

  const updateOption = (qIndex: number, optIndex: number, value: string) => {
    const question = questions[qIndex];
    const options = question.options.map((opt, i) => (i === optIndex ? value : opt));
    update(qIndex, { options });
  };

  const addOption = (qIndex: number) => {
    const question = questions[qIndex];
    update(qIndex, { options: [...question.options, "新选项"] });
  };

  const removeOption = (qIndex: number, optIndex: number) => {
    const question = questions[qIndex];
    if (question.options.length <= 2) {
      toast.error("至少需要2个选项");
      return;
    }
    update(qIndex, { options: question.options.filter((_, i) => i !== optIndex) });
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold">自定义题目</h3>
        <div className="flex flex-wrap gap-1.5">
          {(Object.keys(TYPE_NAMES) as CustomQuestion["question_type"][]).map((type) => (
            <Button
              key={type}
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => onChange([...questions, newQuestion(type, questions.length + 1)])}
            >
              <Plus className="h-3.5 w-3.5" />
              {TYPE_NAMES[type].replace("题", "").replace("文字", "")}
            </Button>
          ))}
        </div>
      </div>

      <div className="max-h-[400px] overflow-y-auto pr-1">
        {questions.length === 0 ? (
          <div className="text-center py-5 text-[#999] text-sm">暂无自定义题目</div>
        ) : (
          questions.map((question, index) => (
            <div key={index} className="rounded-lg border-2 border-[#e0e0e0] bg-white p-4 mb-3">
              <div className="flex items-center justify-between mb-2.5">
                <strong className="text-primary text-sm">
                  题目 {index + 1} - {TYPE_NAMES[question.question_type]}
                </strong>
                <div className="flex gap-1.5">
                  {index > 0 ? (
                    <Button type="button" variant="secondary" size="sm" onClick={() => move(index, -1)}>
                      <ArrowUp className="h-3.5 w-3.5" />
                    </Button>
                  ) : null}
                  {index < questions.length - 1 ? (
                    <Button type="button" variant="secondary" size="sm" onClick={() => move(index, 1)}>
                      <ArrowDown className="h-3.5 w-3.5" />
                    </Button>
                  ) : null}
                  <Button type="button" variant="danger" size="sm" onClick={() => remove(index)}>
                    删除
                  </Button>
                </div>
              </div>

              <div className="mb-2.5">
                <label className="block text-sm mb-1">题目文本：</label>
                <Textarea
                  rows={2}
                  value={question.question_text}
                  onChange={(event) => update(index, { question_text: event.target.value })}
                />
              </div>

              {question.question_type !== "description" ? (
                <label className="flex items-center gap-2 cursor-pointer text-sm mb-2.5">
                  <Checkbox
                    checked={question.required}
                    onCheckedChange={(checked) => update(index, { required: checked === true })}
                  />
                  <span>必填</span>
                </label>
              ) : null}

              {question.question_type.includes("choice") ? (
                <div className="mb-2.5">
                  <label className="block text-sm mb-1">选项：</label>
                  {question.options.map((option, optIndex) => (
                    <div key={optIndex} className="flex gap-1.5 mb-1.5">
                      <Input
                        value={option}
                        onChange={(event) => updateOption(index, optIndex, event.target.value)}
                        className="flex-1"
                      />
                      <Button
                        type="button"
                        variant="danger"
                        size="icon"
                        className="h-10 w-10"
                        onClick={() => removeOption(index, optIndex)}
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    className="mt-1"
                    onClick={() => addOption(index)}
                  >
                    <Plus className="h-3.5 w-3.5" />
                    添加选项
                  </Button>
                </div>
              ) : null}

              {question.question_type === "text" || question.question_type === "textarea" ? (
                <div>
                  <label className="block text-sm mb-1">最大字符数：</label>
                  <Input
                    type="number"
                    min={1}
                    max={5000}
                    value={question.max_length}
                    onChange={(event) =>
                      update(index, { max_length: parseInt(event.target.value, 10) || 0 })
                    }
                    className="w-28"
                  />
                </div>
              ) : null}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
