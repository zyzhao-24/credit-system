import { useEffect, useRef } from "react";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import type { CustomQuestion } from "@/api/types";
import { Markdown, MarkdownInline } from "@/components/Markdown";
import { isMultiline, OTHER_PREFIX } from "@/lib/questions";
import { cn } from "@/lib/utils";

/** 自适应高度的文本框：有最小宽度，随内容纵向生长 */
function AutosizeTextarea({
  value,
  placeholder,
  maxLength,
  rows,
  autoFocus,
  onChange,
}: {
  value: string;
  placeholder?: string;
  maxLength?: number;
  rows?: number;
  autoFocus?: boolean;
  onChange: (value: string) => void;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [value]);

  return (
    <textarea
      ref={ref}
      value={value}
      rows={rows ?? 2}
      maxLength={maxLength}
      placeholder={placeholder}
      autoFocus={autoFocus}
      onChange={(event) => onChange(event.target.value)}
      className="w-full min-w-[260px] resize-none overflow-hidden rounded-md border-2 border-[#c8c8c8] bg-white px-2.5 py-1.5 text-sm leading-relaxed focus:border-primary focus:outline-none"
    />
  );
}

const FORMAT_PLACEHOLDERS: Record<string, string> = {
  phone: "手机号",
  email: "邮箱",
  idcard: "身份证号",
};

/**
 * 作答侧栏内容：显示题目（Markdown 渲染），下方是对应的作答控件。
 * 文本题是带最小宽度的自适应文本框，支持 Markdown 与公式。
 */
export function AnswerPanel({
  question,
  answer,
  onChange,
}: {
  question: CustomQuestion;
  answer: string | string[] | undefined;
  onChange: (answer: string | string[]) => void;
}) {
  const type = question.question_type;
  const stringValue = typeof answer === "string" ? answer : "";
  const setString = (value: string) => onChange(value);

  return (
    <div>
      <div className="mb-3 text-[15px] leading-relaxed text-[#333]">
        <Markdown text={question.question_text || "（未命名题目）"} />
        {question.required ? <span className="ml-1 text-danger text-sm">* 必填</span> : null}
      </div>

      {type === "text" || type === "textarea" ? (
        <>
          <AutosizeTextarea
            value={stringValue}
            maxLength={question.max_length || 500}
            rows={isMultiline(question) ? 5 : 2}
            autoFocus
            placeholder={
              FORMAT_PLACEHOLDERS[question.format ?? "none"] ??
              "支持 Markdown 与 $公式$"
            }
            onChange={setString}
          />
          {isMultiline(question) || !question.format || question.format === "none" ? (
            <p className="mt-1 text-xs text-[#999]">支持 Markdown 与 $公式$，提交后在文中渲染</p>
          ) : null}
        </>
      ) : null}

      {type === "number" ? (
        <Input
          type="number"
          autoFocus
          value={stringValue}
          min={question.min_value ?? undefined}
          max={question.max_value ?? undefined}
          onChange={(event) => setString(event.target.value)}
          className="min-w-[260px]"
        />
      ) : null}

      {type === "date" ? (
        <Input
          type="date"
          value={stringValue}
          onChange={(event) => setString(event.target.value)}
          className="min-w-[260px]"
        />
      ) : null}

      {type === "single_choice" ? (
        <SingleChoice question={question} value={stringValue} onChange={setString} />
      ) : null}

      {type === "multiple_choice" ? (
        <MultipleChoice
          question={question}
          value={Array.isArray(answer) ? answer : []}
          onChange={onChange}
        />
      ) : null}

      {type === "rating" ? (
        <Rating question={question} value={stringValue} onChange={setString} />
      ) : null}
    </div>
  );
}

function SingleChoice({
  question,
  value,
  onChange,
}: {
  question: CustomQuestion;
  value: string;
  onChange: (value: string) => void;
}) {
  const otherSelected = value.startsWith(OTHER_PREFIX);
  return (
    <div className="flex flex-col gap-2">
      {question.options.map((option) => (
        <label key={option} className="flex cursor-pointer items-baseline gap-2 text-sm">
          <input
            type="radio"
            className="accent-[#0078d4]"
            checked={!otherSelected && value === option}
            onChange={() => onChange(option)}
          />
          <MarkdownInline text={option} />
        </label>
      ))}
      {question.allow_other ? (
        <label className="flex cursor-pointer items-baseline gap-2 text-sm">
          <input
            type="radio"
            className="accent-[#0078d4]"
            checked={otherSelected}
            onChange={() => onChange(OTHER_PREFIX)}
          />
          <span className="shrink-0">其他</span>
          {otherSelected ? (
            <input
              value={value.slice(OTHER_PREFIX.length)}
              placeholder="请填写"
              autoFocus
              onChange={(event) => onChange(OTHER_PREFIX + event.target.value)}
              className="min-w-[160px] flex-1 rounded-md border-2 border-[#c8c8c8] bg-white px-2 py-1 text-sm focus:border-primary focus:outline-none"
            />
          ) : null}
        </label>
      ) : null}
    </div>
  );
}

function MultipleChoice({
  question,
  value,
  onChange,
}: {
  question: CustomQuestion;
  value: string[];
  onChange: (answer: string | string[]) => void;
}) {
  const otherEntry = value.find((item) => item.startsWith(OTHER_PREFIX));
  const toggle = (option: string, checked: boolean) => {
    onChange(checked ? [...value, option] : value.filter((item) => item !== option));
  };
  return (
    <div className="flex flex-col gap-2">
      {question.options.map((option) => (
        <label key={option} className="flex cursor-pointer items-baseline gap-2 text-sm">
          <Checkbox
            checked={value.includes(option)}
            onCheckedChange={(state) => toggle(option, state === true)}
          />
          <MarkdownInline text={option} />
        </label>
      ))}
      {question.allow_other ? (
        <label className="flex cursor-pointer items-baseline gap-2 text-sm">
          <Checkbox
            checked={otherEntry !== undefined}
            onCheckedChange={(state) => {
              const withoutOther = value.filter((item) => !item.startsWith(OTHER_PREFIX));
              onChange(state === true ? [...withoutOther, OTHER_PREFIX] : withoutOther);
            }}
          />
          <span className="shrink-0">其他</span>
          {otherEntry !== undefined ? (
            <input
              value={otherEntry.slice(OTHER_PREFIX.length)}
              placeholder="请填写"
              onClick={(event) => event.preventDefault()}
              onChange={(event) =>
                onChange([
                  ...value.filter((item) => !item.startsWith(OTHER_PREFIX)),
                  OTHER_PREFIX + event.target.value,
                ])
              }
              className="min-w-[160px] flex-1 rounded-md border-2 border-[#c8c8c8] bg-white px-2 py-1 text-sm focus:border-primary focus:outline-none"
            />
          ) : null}
        </label>
      ) : null}
    </div>
  );
}

function Rating({
  question,
  value,
  onChange,
}: {
  question: CustomQuestion;
  value: string;
  onChange: (value: string) => void;
}) {
  const score = parseInt(value, 10) || 0;
  return (
    <span className="inline-flex items-center gap-1">
      {Array.from({ length: question.max_rating || 5 }, (_, star) => star + 1).map((score_value) => (
        <button
          key={score_value}
          type="button"
          aria-label={`${score_value} 分`}
          onClick={() => onChange(String(score_value))}
          className={cn(
            "text-2xl leading-none transition-colors cursor-pointer",
            score >= score_value ? "text-[#ffb900]" : "text-[#d0d0d0] hover:text-[#ffd76e]",
          )}
        >
          ★
        </button>
      ))}
    </span>
  );
}
