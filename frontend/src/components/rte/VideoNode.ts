import { Node, mergeAttributes } from "@tiptap/core";

type VideoAttrs = {
  kind: "file" | "embed";
  src: string;
  provider: "bilibili" | "youtube" | "qq" | "youku" | null;
};

declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    video: {
      /** 在光标处插入一个视频节点（本地上传 file / 外链嵌入 embed）。 */
      insertVideo: (attrs: VideoAttrs) => ReturnType;
    };
  }
}

/**
 * 视频原子节点：
 * - file → 渲染 <video src controls preload="metadata">（本地上传）
 * - embed → 渲染 <iframe src frameborder allow>（外链嵌入，16:9 由 CSS 给）
 * renderHTML 手控输出（不经 HTMLAttributes 自动渲染），故内部 kind/provider 不会漏成 HTML 属性。
 */
export const Video = Node.create({
  name: "video",
  group: "block",
  atom: true,

  addAttributes() {
    return {
      kind: { default: "file" },
      src: { default: "" },
      provider: { default: null },
    };
  },

  parseHTML() {
    return [
      {
        tag: "video",
        getAttrs: (el) => ({ kind: "file", src: (el as HTMLElement).getAttribute("src") || "" }),
      },
      {
        tag: "iframe",
        getAttrs: (el) => ({ kind: "embed", src: (el as HTMLElement).getAttribute("src") || "" }),
      },
    ];
  },

  renderHTML({ node }) {
    const src = String(node.attrs.src ?? "");
    if (node.attrs.kind === "embed") {
      return [
        "iframe",
        mergeAttributes({
          src,
          frameborder: "0",
          allow: "autoplay; fullscreen; picture-in-picture",
        }),
      ];
    }
    return ["video", mergeAttributes({ src, controls: "controls", preload: "metadata" })];
  },

  addCommands() {
    return {
      insertVideo:
        (attrs) =>
        ({ commands }) =>
          commands.insertContent({ type: "video", attrs }),
    };
  },
});
