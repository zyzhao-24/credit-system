import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";

const remarkPlugins = [remarkGfm, remarkMath];
const rehypePlugins = [rehypeKatex];

/** 兼容中文写作习惯：行首 # 后不加空格也视为标题（CommonMark 原本要求 # 后必须有空格） */
function normalizeMarkdown(text: string): string {
  return text.replace(/^(#{1,6})(?=[^\s#])/gm, "$1 ");
}

/** 块级 Markdown 渲染（段落、列表、公式块等），用于正文段落与全文渲染。 */
export function Markdown({ text, className }: { text: string; className?: string }) {
  return (
    <div className={className ? `md-content ${className}` : "md-content"}>
      <ReactMarkdown remarkPlugins={remarkPlugins} rehypePlugins={rehypePlugins}>
        {normalizeMarkdown(text)}
      </ReactMarkdown>
    </div>
  );
}

/** 行内 Markdown 渲染（不包 <p>），用于选项标签、答案等嵌入文字流的内容。 */
export function MarkdownInline({ text }: { text: string }) {
  return (
    <span className="md-inline">
      <ReactMarkdown
        remarkPlugins={remarkPlugins}
        rehypePlugins={rehypePlugins}
        components={{ p: ({ children }) => <>{children}</> }}
      >
        {normalizeMarkdown(text)}
      </ReactMarkdown>
    </span>
  );
}
