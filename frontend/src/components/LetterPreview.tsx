import { Markdown } from "@/components/Markdown";

/** 全文渲染：正文段落按 Markdown 渲染（含公式），组合后即为连贯的文档。 */
export function LetterPreview({ paragraphs }: { paragraphs: string[] }) {
  return (
    <div className="rounded-lg border border-[#e8dcc8] bg-[#fffdf7] px-5 py-4 shadow-sm">
      {paragraphs.map((paragraph, index) => (
        <Markdown
          key={index}
          text={paragraph}
          className="mb-2.5 leading-relaxed text-[15px] text-[#333] last:mb-0 letter-paragraph"
        />
      ))}
    </div>
  );
}
