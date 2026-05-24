import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import TaskList from "@tiptap/extension-task-list";
import TaskItem from "@tiptap/extension-task-item";
import { Table } from "@tiptap/extension-table";
import { TableRow } from "@tiptap/extension-table-row";
import { TableCell } from "@tiptap/extension-table-cell";
import { TableHeader } from "@tiptap/extension-table-header";
import TiptapImage from "@tiptap/extension-image";
import Placeholder from "@tiptap/extension-placeholder";
import "./RichTextEditor.css";

interface Props {
  content: string;
  onChange?: (html: string) => void;
  placeholder?: string;
  editable?: boolean;
}

const Toolbar = ({ editor }: { editor: ReturnType<typeof useEditor> }) => {
  if (!editor) return null;

  const btn = (label: string, action: () => void, active?: boolean) => (
    <button
      type="button"
      className={`rte-btn${active ? " active" : ""}`}
      onClick={action}
      title={label}
    >
      {label}
    </button>
  );

  return (
    <div className="rte-toolbar">
      <div className="rte-group">
        {btn("H1", () => editor.chain().focus().toggleHeading({ level: 1 }).run(), editor.isActive("heading", { level: 1 }))}
        {btn("H2", () => editor.chain().focus().toggleHeading({ level: 2 }).run(), editor.isActive("heading", { level: 2 }))}
        {btn("H3", () => editor.chain().focus().toggleHeading({ level: 3 }).run(), editor.isActive("heading", { level: 3 }))}
      </div>
      <div className="rte-divider" />
      <div className="rte-group">
        {btn("B", () => editor.chain().focus().toggleBold().run(), editor.isActive("bold"))}
        {btn("I", () => editor.chain().focus().toggleItalic().run(), editor.isActive("italic"))}
        {btn("S", () => editor.chain().focus().toggleStrike().run(), editor.isActive("strike"))}
        {btn("</>", () => editor.chain().focus().toggleCodeBlock().run(), editor.isActive("codeBlock"))}
      </div>
      <div className="rte-divider" />
      <div className="rte-group">
        {btn("UL", () => editor.chain().focus().toggleBulletList().run(), editor.isActive("bulletList"))}
        {btn("OL", () => editor.chain().focus().toggleOrderedList().run(), editor.isActive("orderedList"))}
        {btn("TODO", () => editor.chain().focus().toggleTaskList().run(), editor.isActive("taskList"))}
      </div>
      <div className="rte-divider" />
      <div className="rte-group">
        {btn("引用", () => editor.chain().focus().toggleBlockquote().run(), editor.isActive("blockquote"))}
        {btn("分割线", () => editor.chain().focus().setHorizontalRule().run())}
      </div>
    </div>
  );
};

export default function RichTextEditor({ content, onChange, placeholder = "请输入内容...", editable = true }: Props) {
  const editor = useEditor({
    extensions: [
      StarterKit.configure({ heading: { levels: [1, 2, 3] } }),
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
    onUpdate: ({ editor }) => {
      onChange?.(editor.getHTML());
    },
  });

  if (!editable) {
    return (
      <div className="rte-readonly">
        {editor && <EditorContent editor={editor} />}
      </div>
    );
  }

  return (
    <div className="rte-wrapper">
      <Toolbar editor={editor} />
      <EditorContent editor={editor} className="rte-content" />
    </div>
  );
}
