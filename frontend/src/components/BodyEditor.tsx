import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
} from "react";
import { Annotation, EditorState, Prec, StateEffect, type Range } from "@codemirror/state";
import {
  Decoration,
  EditorView,
  WidgetType,
  keymap,
  placeholder as cmPlaceholder,
  type DecorationSet,
  type ViewUpdate,
  ViewPlugin,
} from "@codemirror/view";
import { defaultKeymap, history, historyKeymap } from "@codemirror/commands";
import { defaultHighlightStyle, syntaxHighlighting, syntaxTree } from "@codemirror/language";
import { markdown } from "@codemirror/lang-markdown";
import type { SyntaxNode } from "@lezer/common";
import katex from "katex";
import type { BodyField, BodyPart, CustomQuestion, QuestionnaireBody } from "@/api/types";
import { FIELD_NAMES, QUESTION_TYPE_NAMES } from "@/lib/questions";

/** 与设计器共用的拖拽 MIME 类型 */
export const DND_NEW_TYPE = "application/x-question-type";
export const DND_NEW_FIELD = "application/x-body-field";
export const DND_MOVE_QID = "application/x-question-id";

/** 每个芯片在文档中占用一个私用区字符，身份即字符，天然支持撤销/移动 */
interface ChipDesc {
  kind: "field" | "question";
  key: string;
}

/** 程序性修改（插入/移动/删除芯片、外部重建）绕过题目芯片保护 */
const Programmatic = Annotation.define<boolean>();
const refreshChips = StateEffect.define<null>();

export interface BodyEditorHandle {
  /** 在光标处（或指定位置）插入信息槽位 */
  insertField: (field: BodyField, pos?: number) => void;
  /** 在光标处（或指定位置）插入题目槽位；已在文中时移动到目标位置 */
  insertQuestion: (questionId: string, pos?: number) => void;
  /** 在光标处开启新段落 */
  insertParagraph: () => void;
  focus: () => void;
}

interface BodyEditorProps {
  body: QuestionnaireBody;
  questions: CustomQuestion[];
  selectedQid: string | null;
  onChange: (body: QuestionnaireBody) => void;
  onSelectQuestion: (questionId: string) => void;
  /** 从题型面板拖入新题型（由父组件创建题目后回调 handle.insertQuestion） */
  onDropNewType: (type: string, pos: number) => void;
}

/** 编辑器内部上下文：通过 ref 暴露给 CodeMirror 扩展，避免闭包过期 */
interface EditorCtx {
  chips: Map<string, ChipDesc>;
  questions: CustomQuestion[];
  selectedQid: string | null;
  onChange: (body: QuestionnaireBody) => void;
  onSelectQuestion: (questionId: string) => void;
  onDropNewType: (type: string, pos: number) => void;
  insertField: (field: BodyField, pos?: number) => void;
  insertQuestion: (questionId: string, pos?: number) => void;
}

function isChipCode(char: string): boolean {
  const code = char.codePointAt(0) ?? 0;
  return code >= 0xe000 && code <= 0xf8ff;
}

/** 把编辑器文档解析回正文模型：空行分段，芯片字符还原为槽位 */
function parseDoc(doc: string, chips: Map<string, ChipDesc>): QuestionnaireBody {
  const paragraphs: BodyPart[][] = [];
  let current: BodyPart[] = [];
  let textBuf = "";

  const flushText = () => {
    const chunks = textBuf.split(/\n{2,}/);
    textBuf = "";
    chunks.forEach((chunk, index) => {
      if (index > 0) {
        if (current.length > 0) paragraphs.push(current);
        current = [];
      }
      const text = chunk.replace(/^\n+|\n+$/g, "");
      if (text.trim()) current.push({ type: "text", text });
    });
  };

  for (const char of doc) {
    const desc = isChipCode(char) ? chips.get(char) : undefined;
    if (desc) {
      flushText();
      current.push(
        desc.kind === "field"
          ? { type: "field", field: desc.key as BodyField }
          : { type: "question", question_id: desc.key },
      );
    } else {
      textBuf += char;
    }
  }
  flushText();
  if (current.length > 0) paragraphs.push(current);
  return paragraphs;
}

/** 把正文模型展开为编辑器文档文本，并为每个槽位分配芯片字符 */
function buildDoc(body: QuestionnaireBody, chips: Map<string, ChipDesc>, nextCode: () => string): string {
  const lines: string[] = [];
  for (const paragraph of body) {
    let line = "";
    for (const part of paragraph) {
      if (part.type === "text") {
        line += part.text;
      } else {
        const code = nextCode();
        chips.set(
          code,
          part.type === "field"
            ? { kind: "field", key: part.field }
            : { kind: "question", key: part.question_id },
        );
        line += code;
      }
    }
    lines.push(line);
  }
  return lines.join("\n\n");
}

class ChipWidget extends WidgetType {
  constructor(
    readonly code: string,
    readonly desc: ChipDesc,
    readonly label: string,
    readonly typeName: string | null,
    readonly selected: boolean,
    readonly removable: boolean,
    readonly ctx: () => EditorCtx,
  ) {
    super();
  }

  override eq(other: ChipWidget): boolean {
    return (
      other.code === this.code &&
      other.label === this.label &&
      other.selected === this.selected &&
      other.removable === this.removable
    );
  }

  override toDOM(view: EditorView): HTMLElement {
    const span = document.createElement("span");
    span.className =
      `body-chip ${this.desc.kind === "field" ? "body-chip-field" : "body-chip-question"}` +
      (this.selected ? " body-chip-selected" : "");
    if (this.desc.kind === "question") {
      span.title = "点击编辑题目属性；拖到其他位置可移动；删除请在右侧面板操作";
      span.draggable = true;
      span.addEventListener("dragstart", (event) => {
        event.dataTransfer?.setData(DND_MOVE_QID, this.desc.key);
        if (event.dataTransfer) event.dataTransfer.effectAllowed = "move";
      });
      span.addEventListener("click", (event) => {
        event.preventDefault();
        this.ctx().onSelectQuestion(this.desc.key);
      });
    }
    if (this.typeName) {
      const type = document.createElement("span");
      type.className = "body-chip-type";
      type.textContent = this.typeName;
      span.appendChild(type);
    }
    const label = document.createElement("span");
    label.textContent = this.label;
    span.appendChild(label);
    if (this.desc.kind === "question" && this.removable) {
      const required = document.createElement("span");
      required.textContent = "*";
      required.style.color = "#d13438";
      span.appendChild(required);
    }
    if (this.desc.kind === "field") {
      const close = document.createElement("button");
      close.type = "button";
      close.className = "body-chip-close";
      close.title = "移除此槽位";
      close.textContent = "×";
      close.addEventListener("mousedown", (event) => {
        event.preventDefault();
        const doc = view.state.doc.toString();
        const at = doc.indexOf(this.code);
        if (at >= 0) {
          view.dispatch({
            changes: { from: at, to: at + 1 },
            annotations: Programmatic.of(true),
          });
        }
      });
      span.appendChild(close);
    }
    return span;
  }

  override ignoreEvent(): boolean {
    return false;
  }
}

function questionLabel(question: CustomQuestion | undefined): string {
  return question?.question_text || "（未命名）";
}

/** 隐藏语法节点首尾的直接子标记节点（**、`、~~ 等） */
function hideChildMarks(node: SyntaxNode, markName: string, out: Range<Decoration>[]): void {
  const cursor = node.cursor();
  if (!cursor.firstChild()) return;
  do {
    if (cursor.name === markName) {
      out.push(Decoration.replace({}).range(cursor.from, cursor.to));
    }
  } while (cursor.nextSibling());
}

/** 公式实时渲染：KaTeX 替换 $...$ / $$...$$ 源码 */
class MathWidget extends WidgetType {
  constructor(
    readonly tex: string,
    readonly display: boolean,
  ) {
    super();
  }

  override eq(other: MathWidget): boolean {
    return other.tex === this.tex && other.display === this.display;
  }

  override toDOM(): HTMLElement {
    const span = document.createElement("span");
    span.className = this.display ? "cm-math cm-math-display" : "cm-math";
    try {
      span.innerHTML = katex.renderToString(this.tex, {
        displayMode: this.display,
        throwOnError: false,
      });
    } catch {
      span.textContent = this.tex;
    }
    return span;
  }

  override ignoreEvent(): boolean {
    return false;
  }
}

/**
 * 问卷正文编辑器：整篇文字直接打字编辑（Markdown 源码），
 * 信息槽位与题目作为芯片嵌入文字流，点击题目芯片编辑属性。
 */
export const BodyEditor = forwardRef<BodyEditorHandle, BodyEditorProps>(function BodyEditor(
  { body, questions, selectedQid, onChange, onSelectQuestion, onDropNewType },
  ref,
) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewRef = useRef<EditorView | null>(null);
  const counterRef = useRef(0xe000);
  const lastEmitted = useRef<QuestionnaireBody>(body);
  const ctxRef = useRef<EditorCtx>({
    chips: new Map(),
    questions,
    selectedQid,
    onChange,
    onSelectQuestion,
    onDropNewType,
    insertField: () => undefined,
    insertQuestion: () => undefined,
  });

  const allocCode = () => String.fromCodePoint(counterRef.current++);

  const insertChip = (desc: ChipDesc, pos?: number) => {
    const view = viewRef.current;
    if (!view) return;
    const chips = ctxRef.current.chips;
    if (desc.kind === "question") {
      // 同一题目只能出现一次：已在文中则视为移动
      const doc = view.state.doc.toString();
      for (const [code, existing] of chips) {
        if (existing.kind === "question" && existing.key === desc.key) {
          const at = doc.indexOf(code);
          if (at >= 0) {
            view.dispatch({
              changes: { from: at, to: at + 1 },
              annotations: Programmatic.of(true),
            });
          }
          chips.delete(code);
        }
      }
    }
    const code = allocCode();
    chips.set(code, desc);
    const at = pos ?? view.state.selection.main.head;
    view.dispatch({
      changes: { from: at, insert: code },
      selection: { anchor: at + 1 },
      annotations: Programmatic.of(true),
    });
    view.focus();
  };

  ctxRef.current.questions = questions;
  ctxRef.current.selectedQid = selectedQid;
  ctxRef.current.onChange = onChange;
  ctxRef.current.onSelectQuestion = onSelectQuestion;
  ctxRef.current.onDropNewType = onDropNewType;
  ctxRef.current.insertField = (field, pos) => insertChip({ kind: "field", key: field }, pos);
  ctxRef.current.insertQuestion = (questionId, pos) =>
    insertChip({ kind: "question", key: questionId }, pos);

  useImperativeHandle(ref, () => ({
    insertField: (field, pos) => ctxRef.current.insertField(field, pos),
    insertQuestion: (questionId, pos) => ctxRef.current.insertQuestion(questionId, pos),
    insertParagraph: () => {
      const view = viewRef.current;
      if (!view) return;
      const at = view.state.selection.main.head;
      view.dispatch({
        changes: { from: at, insert: "\n\n" },
        selection: { anchor: at + 2 },
        annotations: Programmatic.of(true),
      });
      view.focus();
    },
    focus: () => viewRef.current?.focus(),
  }));

  // 挂载编辑器（仅一次）
  useEffect(() => {
    const ctx = ctxRef.current;
    ctx.chips.clear();
    const initialDoc = buildDoc(lastEmitted.current, ctx.chips, allocCode);

    const computeDecorations = (state: EditorState): DecorationSet => {
      const context = ctxRef.current;
      const text = state.doc.toString();
      const questionMap = new Map(
        context.questions.map((question) => [question.question_id, question]),
      );
      const widgets: Range<Decoration>[] = [];
      for (let index = 0; index < text.length; index++) {
        const code = text[index];
        const desc = context.chips.get(code);
        if (!desc) continue;
        const question = desc.kind === "question" ? questionMap.get(desc.key) : undefined;
        widgets.push(
          Decoration.replace({
            widget: new ChipWidget(
              code,
              desc,
              desc.kind === "field" ? FIELD_NAMES[desc.key as BodyField] : questionLabel(question),
              desc.kind === "question"
                ? (QUESTION_TYPE_NAMES[question?.question_type ?? "text"] ?? null)
                : null,
              desc.kind === "question" && context.selectedQid === desc.key,
              question?.required === true,
              () => ctxRef.current,
            ),
          }).range(index, index + 1),
        );
      }

      // ===== Markdown 实时渲染：光标不在其上时隐藏标记、公式替换为渲染结果 =====
      const selection = state.selection.main;
      const intersectsSelection = (from: number, to: number) =>
        selection.from <= to && selection.to >= from;

      // 先收集公式范围，语法装饰跳过公式内部
      const mathRanges: { from: number; to: number; tex: string; display: boolean; block: boolean }[] = [];
      const mathRe = /\$\$([\s\S]+?)\$\$|\$([^$\n]+?)\$/g;
      let match: RegExpExecArray | null;
      while ((match = mathRe.exec(text)) !== null) {
        const from = match.index;
        const to = from + match[0].length;
        if (intersectsSelection(from, to)) continue;
        let hasChip = false;
        for (let index = from; index < to; index++) {
          if (isChipCode(text[index])) {
            hasChip = true;
            break;
          }
        }
        if (hasChip) continue;
        const tex = match[1] ?? match[2] ?? "";
        let display = match[1] !== undefined;
        let block = false;
        let rangeFrom = from;
        let rangeTo = to;
        if (display && to - from > 2 && state.doc.lineAt(from).number !== state.doc.lineAt(to).number) {
          // 跨行块公式：独占整行时才折叠为块级渲染
          const startLine = state.doc.lineAt(from);
          const endLine = state.doc.lineAt(to);
          if (!text.slice(startLine.from, from).trim() && !text.slice(to, endLine.to).trim()) {
            block = true;
            rangeFrom = startLine.from;
            rangeTo = endLine.to;
          } else {
            display = false;
          }
        }
        mathRanges.push({ from: rangeFrom, to: rangeTo, tex, display, block });
      }

      const inMath = (from: number, to: number) =>
        mathRanges.some((range) => from >= range.from && to <= range.to);

      syntaxTree(state).iterate({
        enter: (node) => {
          const { name, from, to } = node;
          if (inMath(from, to)) return false;
          if (name.startsWith("ATXHeading")) {
            const level = name.replace("ATXHeading", "");
            widgets.push(Decoration.line({ class: `cm-md-h${level}` }).range(from));
            if (!intersectsSelection(from, to)) {
              const mark = node.node.getChild("HeaderMark");
              if (mark) {
                widgets.push(Decoration.replace({}).range(mark.from, Math.min(mark.to + 1, to)));
              }
            }
          } else if (name === "StrongEmphasis" || name === "Emphasis") {
            widgets.push(
              Decoration.mark({ class: name === "Emphasis" ? "cm-md-em" : "cm-md-strong" }).range(
                from,
                to,
              ),
            );
            if (!intersectsSelection(from, to)) hideChildMarks(node.node, "EmphasisMark", widgets);
          } else if (name === "Strikethrough") {
            widgets.push(Decoration.mark({ class: "cm-md-strike" }).range(from, to));
            if (!intersectsSelection(from, to))
              hideChildMarks(node.node, "StrikethroughMark", widgets);
          } else if (name === "InlineCode") {
            widgets.push(Decoration.mark({ class: "cm-md-code" }).range(from, to));
            if (!intersectsSelection(from, to)) hideChildMarks(node.node, "CodeMark", widgets);
          }
          return undefined;
        },
      });

      for (const range of mathRanges) {
        widgets.push(
          Decoration.replace({
            widget: new MathWidget(range.tex, range.display),
            block: range.block,
          }).range(range.from, range.to),
        );
      }
      // 兼容 "#标题"（# 后无空格）：语法树不识别，用正则补上行样式（标记保持可见）
      const headingRe = /^(#{1,6})(?=[^\s#])/gm;
      let headingMatch: RegExpExecArray | null;
      while ((headingMatch = headingRe.exec(text)) !== null) {
        const line = state.doc.lineAt(headingMatch.index);
        widgets.push(
          Decoration.line({ class: `cm-md-h${headingMatch[1].length}` }).range(line.from),
        );
      }
      return Decoration.set(widgets, true);
    };

    const chipDecorations = ViewPlugin.fromClass(
      class {
        decorations: DecorationSet;
        constructor(view: EditorView) {
          this.decorations = computeDecorations(view.state);
        }
        update(update: ViewUpdate) {
          if (
            update.docChanged ||
            update.selectionSet ||
            update.transactions.some((tr) => tr.effects.some((effect) => effect.is(refreshChips)))
          ) {
            this.decorations = computeDecorations(update.state);
          }
        }
      },
      { decorations: (value) => value.decorations },
    );

    // 题目芯片不可通过退格/覆盖输入删除（删除题目请走属性面板）
    const protectQuestions = EditorState.transactionFilter.of((tr) => {
      if (!tr.docChanged || tr.annotation(Programmatic)) return tr;
      if (!(tr.isUserEvent("delete") || tr.isUserEvent("input"))) return tr;
      const context = ctxRef.current;
      const validQids = new Set(context.questions.map((question) => question.question_id));
      const startDoc = tr.startState.doc.toString();
      let blocked = false;
      tr.changes.iterChanges((fromA, toA) => {
        if (blocked) return;
        for (let index = fromA; index < toA; index++) {
          const desc = context.chips.get(startDoc[index]);
          if (desc?.kind === "question" && validQids.has(desc.key)) {
            blocked = true;
            break;
          }
        }
      });
      return blocked ? [] : tr;
    });

    const state = EditorState.create({
      doc: initialDoc,
      extensions: [
        Prec.highest(protectQuestions),
        history(),
        keymap.of([...defaultKeymap, ...historyKeymap]),
        markdown({ addKeymap: false }),
        syntaxHighlighting(defaultHighlightStyle),
        chipDecorations,
        EditorView.lineWrapping,
        cmPlaceholder(
          "在这里直接书写正文（支持 Markdown 与 $公式$），从左侧拖入信息字段和题目…",
        ),
        EditorView.clipboardInputFilter.of((text) => text.replace(/[-]/g, "")),
        EditorView.updateListener.of((update) => {
          if (!update.docChanged) return;
          const context = ctxRef.current;
          const parsed = parseDoc(update.state.doc.toString(), context.chips);
          lastEmitted.current = parsed;
          context.onChange(parsed);
        }),
        EditorView.domEventHandlers({
          dragover: (event) => {
            event.preventDefault();
          },
          drop: (event, view) => {
            event.preventDefault();
            const pos =
              view.posAtCoords({ x: event.clientX, y: event.clientY }) ?? view.state.doc.length;
            const data = event.dataTransfer;
            if (!data) return;
            const newType = data.getData(DND_NEW_TYPE);
            if (newType) {
              ctxRef.current.onDropNewType(newType, pos);
              return;
            }
            const newField = data.getData(DND_NEW_FIELD);
            if (newField) {
              ctxRef.current.insertField(newField as BodyField, pos);
              return;
            }
            const qid = data.getData(DND_MOVE_QID);
            if (qid) ctxRef.current.insertQuestion(qid, pos);
          },
        }),
      ],
    });

    const view = new EditorView({ state, parent: containerRef.current! });
    viewRef.current = view;
    return () => {
      view.destroy();
      viewRef.current = null;
    };
     
  }, []);

  // 外部结构性修改（默认模板、删除题目）→ 重建文档；编辑器自身产生的变更跳过
  useEffect(() => {
    const view = viewRef.current;
    if (!view || body === lastEmitted.current) return;
    const chips = ctxRef.current.chips;
    chips.clear();
    const text = buildDoc(body, chips, allocCode);
    lastEmitted.current = body;
    view.dispatch({
      changes: { from: 0, to: view.state.doc.length, insert: text },
      annotations: Programmatic.of(true),
    });
     
  }, [body]);

  // 题目内容/选中状态变化 → 仅刷新芯片标签
  useEffect(() => {
    viewRef.current?.dispatch({ effects: refreshChips.of(null) });
  }, [questions, selectedQid]);

  return <div ref={containerRef} className="body-editor" />;
});
