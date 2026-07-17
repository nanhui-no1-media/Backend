import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Link from "@tiptap/extension-link";
import TaskList from "@tiptap/extension-task-list";
import TaskItem from "@tiptap/extension-task-item";
import { Table } from "@tiptap/extension-table";
import { TableRow } from "@tiptap/extension-table-row";
import { TableCell } from "@tiptap/extension-table-cell";
import { TableHeader } from "@tiptap/extension-table-header";
import TiptapImage from "@tiptap/extension-image";
import Placeholder from "@tiptap/extension-placeholder";
import { useRef, useState, type ReactNode } from "react";
import "./RichTextEditor.css";
// mammoth 经动态 import() 按需加载（见 importWord），并已 code-split 到独立 chunk。

interface Props {
  content: string;
  onChange?: (html: string) => void;
  /** 字数统计回调（正文文本长度）。 */
  onStats?: (chars: number) => void;
  placeholder?: string;
  editable?: boolean;
  /** 写作区最小高度（px）。 */
  minHeight?: number;
  /**
   * 图片上传：传入即启用「插入图片」按钮；返回上传后的图片 URL。
   * 同时供 Word 导入上传内嵌图片。与具体后端解耦，由调用方实现。
   */
  imageUpload?: (file: File) => Promise<string>;
  /** 启用「导入 Word」(.docx → HTML) 按钮。 */
  wordImport?: boolean;
}

/* 小图标（仅用于「动作」类按钮：图片 / 链接 / 导入 Word） */
const Icon = {
  image: (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="4" width="18" height="16" rx="2" /><circle cx="8.5" cy="9.5" r="1.5" /><path d="M21 16l-5-5L5 20" />
    </svg>
  ),
  link: (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10 13a5 5 0 0 0 7 0l2-2a5 5 0 0 0-7-7l-1 1" /><path d="M14 11a5 5 0 0 0-7 0l-2 2a5 5 0 0 0 7 7l1-1" />
    </svg>
  ),
  doc: (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" /><path d="M14 3v5h5" /><path d="M9 13h6M9 17h4" />
    </svg>
  ),
};

const Toolbar = ({
  editor,
  imageUpload,
  wordImport,
  importing,
  onInsertImage,
  onAddLink,
  onImportWord,
}: {
  editor: ReturnType<typeof useEditor>;
  imageUpload?: Props["imageUpload"];
  wordImport?: boolean;
  importing: boolean;
  onInsertImage: () => void;
  onAddLink: () => void;
  onImportWord: () => void;
}) => {
  if (!editor) return null;

  const btn = (label: ReactNode, action: () => void, active: boolean, title: string) => (
    <button
      type="button"
      className={`rte-btn${active ? " active" : ""}`}
      onClick={action}
      title={title}
      aria-label={title}
      aria-pressed={active}
    >
      {label}
    </button>
  );

  return (
    <div className="rte-toolbar">
      <div className="rte-group">
        {btn("H1", () => editor!.chain().focus().toggleHeading({ level: 1 }).run(), editor!.isActive("heading", { level: 1 }), "标题 1")}
        {btn("H2", () => editor!.chain().focus().toggleHeading({ level: 2 }).run(), editor!.isActive("heading", { level: 2 }), "标题 2")}
        {btn("H3", () => editor!.chain().focus().toggleHeading({ level: 3 }).run(), editor!.isActive("heading", { level: 3 }), "标题 3")}
      </div>
      <span className="rte-divider" />
      <div className="rte-group">
        {btn(<b>B</b>, () => editor!.chain().focus().toggleBold().run(), editor!.isActive("bold"), "加粗")}
        {btn(<i>I</i>, () => editor!.chain().focus().toggleItalic().run(), editor!.isActive("italic"), "斜体")}
        {btn(<s>S</s>, () => editor!.chain().focus().toggleStrike().run(), editor!.isActive("strike"), "删除线")}
        {btn("</>", () => editor!.chain().focus().toggleCodeBlock().run(), editor!.isActive("codeBlock"), "代码块")}
      </div>
      <span className="rte-divider" />
      <div className="rte-group">
        {btn("• 列表", () => editor!.chain().focus().toggleBulletList().run(), editor!.isActive("bulletList"), "无序列表")}
        {btn("1. 列表", () => editor!.chain().focus().toggleOrderedList().run(), editor!.isActive("orderedList"), "有序列表")}
        {btn("☑ 待办", () => editor!.chain().focus().toggleTaskList().run(), editor!.isActive("taskList"), "待办列表")}
      </div>
      <span className="rte-divider" />
      <div className="rte-group">
        {btn("“ 引用", () => editor!.chain().focus().toggleBlockquote().run(), editor!.isActive("blockquote"), "引用")}
        {btn("— 分割线", () => editor!.chain().focus().setHorizontalRule().run(), false, "分割线")}
      </div>

      {(imageUpload || wordImport) && <span className="rte-spacer" />}
      <div className="rte-group rte-actions">
        {imageUpload && (
          <button type="button" className="rte-action" onClick={onInsertImage} title="插入图片">{Icon.image} 图片</button>
        )}
        {imageUpload && (
          <button type="button" className="rte-action" onClick={onAddLink} title="插入链接">{Icon.link} 链接</button>
        )}
        {wordImport && (
          <button type="button" className="rte-action" onClick={onImportWord} disabled={importing} title="从 Word（.docx）文档导入">
            {Icon.doc} {importing ? "导入中…" : "导入 Word"}
          </button>
        )}
      </div>
    </div>
  );
};

export default function RichTextEditor({
  content,
  onChange,
  onStats,
  placeholder = "请输入内容...",
  editable = true,
  minHeight,
  imageUpload,
  wordImport,
}: Props) {
  const imageInput = useRef<HTMLInputElement>(null);
  const wordInput = useRef<HTMLInputElement>(null);
  const [importing, setImporting] = useState(false);
  const [err, setErr] = useState("");
  // 用 ref 持有最新回调，避免 useEditor 闭包过期
  const onChangeRef = useRef(onChange); onChangeRef.current = onChange;
  const onStatsRef = useRef(onStats); onStatsRef.current = onStats;

  const editor = useEditor({
    extensions: [
      StarterKit.configure({ heading: { levels: [1, 2, 3, 4, 5, 6] } }),
      Link.configure({
        autolink: true,
        HTMLAttributes: { target: "_blank", rel: "noopener noreferrer nofollow" },
      }),
      TaskList,
      TaskItem.configure({ nested: true }),
      Table.configure({ resizable: true }),
      TableRow,
      TableCell,
      TableHeader,
      TiptapImage.configure({ inline: true }),
      Placeholder.configure({ placeholder }),
    ],
    content,
    editable,
    onCreate: ({ editor }) => onStatsRef.current?.(editor.getText().length),
    onUpdate: ({ editor }) => {
      onChangeRef.current?.(editor.getHTML());
      onStatsRef.current?.(editor.getText().length);
    },
  });

  const insertImage = async (file: File | null) => {
    if (!file || !editor || !imageUpload) return;
    setErr("");
    try {
      const src = await imageUpload(file);
      editor.chain().focus().setImage({ src }).run();
    } catch (e: any) {
      setErr(e?.message || "图片上传失败");
    }
  };

  const addLink = () => {
    if (!editor) return;
    const href = window.prompt("输入链接地址（https://…）", "https://");
    if (href === null) return;
    if (href.trim() === "") {
      editor.chain().focus().extendMarkRange("link").unsetLink().run();
      return;
    }
    editor.chain().focus().extendMarkRange("link").setLink({ href: href.trim() }).run();
  };

  const importWord = async (file: File | null) => {
    if (!file || !editor) return;
    if (editor.getText().trim() && !window.confirm("导入将替换当前正文内容，是否继续？")) {
      return;
    }
    setImporting(true);
    setErr("");
    try {
      const arrayBuffer = await file.arrayBuffer();
      // 动态导入 mammoth：只在真正导入时加载，避免膨胀主包
      const mod: any = await import("mammoth");
      const mammoth: any = mod.default ?? mod;
      // Word 内嵌图片：上传到后端换 http URL（与 bleach 白名单 http(s) 协议匹配）
      const opts: any = imageUpload
        ? {
            convertImage: mammoth.images.imgElement(async (image: any) => {
              const buf: ArrayBuffer = await image.readAsArrayBuffer();
              const ext = (image.contentType || "image/png").split("/")[1] || "png";
              const f = new File([buf], `image.${ext}`, { type: image.contentType || "image/png" });
              const src = await imageUpload(f);
              return { src };
            }),
          }
        : undefined;
      const result = await mammoth.convertToHtml({ arrayBuffer }, opts);
      editor.chain().focus().setContent(result.value || "").run();
      onChangeRef.current?.(editor.getHTML());
      onStatsRef.current?.(editor.getText().length);
    } catch (e: any) {
      setErr(e?.message || "Word 导入失败，请确认是 .docx 格式");
    } finally {
      setImporting(false);
    }
  };

  if (!editable) {
    return (
      <div className="rte-readonly">
        {editor && <EditorContent editor={editor} />}
      </div>
    );
  }

  return (
    <div className="rte-wrapper" style={minHeight ? ({ ["--rte-min-height" as any]: `${minHeight}px` }) : undefined}>
      <Toolbar
        editor={editor}
        imageUpload={imageUpload}
        wordImport={wordImport}
        importing={importing}
        onInsertImage={() => imageInput.current?.click()}
        onAddLink={addLink}
        onImportWord={() => wordInput.current?.click()}
      />
      <EditorContent editor={editor} className="rte-content" />
      {err && <div className="rte-err">{err}</div>}
      <input
        ref={imageInput} type="file" accept="image/*" className="rte-file"
        onChange={(e) => { insertImage(e.target.files?.[0] ?? null); e.target.value = ""; }}
      />
      <input
        ref={wordInput} type="file" accept=".docx" className="rte-file"
        onChange={(e) => { importWord(e.target.files?.[0] ?? null); e.target.value = ""; }}
      />
    </div>
  );
}
