/**
 * 把常见视频平台的「视频页 URL」转成可嵌入的 iframe player src。
 * 服务端清洗器另以 iframe src 域名白名单兜底（见 news/serializers.py），故此处仅做转换、不做安全。
 * 不识别的链接返回 null（调用方提示「不支持的视频链接」）。
 */
export function parseVideoEmbed(
  url: string,
): { src: string; provider: "bilibili" | "youtube" | "qq" | "youku" } | null {
  const u = (url || "").trim();
  if (!u) return null;

  // B站：bilibili.com/video/BVxxxxxxxxxx
  const bv = u.match(/bilibili\.com\/video\/(BV[0-9A-Za-z]{10})/);
  if (bv) return { src: `https://player.bilibili.com/player.html?bvid=${bv[1]}`, provider: "bilibili" };

  // YouTube：watch?v= / embed/ / shorts/ / youtu.be/
  const yt = u.match(/(?:youtube\.com\/(?:watch\?v=|embed\/|shorts\/)|youtu\.be\/)([\w-]{11})/);
  if (yt) return { src: `https://www.youtube.com/embed/${yt[1]}`, provider: "youtube" };

  // 腾讯视频：x/cover/<cover>/<vid>.html 或 x/page/<vid>.html
  const qq = u.match(/v\.qq\.com\/x\/(?:cover\/[\w]+\/([\w]+)|page\/([\w]+))\.html/);
  if (qq) {
    const vid = qq[1] || qq[2];
    return { src: `https://v.qq.com/iframe/player.html?vid=${vid}&tiny=0&auto=0`, provider: "qq" };
  }

  // 优酷：v_show/id_<id>.html
  const yk = u.match(/youku\.com\/v_show\/id_([\w=]+)\.html/);
  if (yk) return { src: `https://player.youku.com/embed/${yk[1]}`, provider: "youku" };

  return null;
}
