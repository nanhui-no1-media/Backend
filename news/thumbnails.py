"""新闻封面缩略图：上传时生成小图（列表 / 卡片用，省流量）。

- 宽 ≤ 800px（列表最大显示约 600px，留 @2x 余量），保持原比例不裁剪
- EXIF 方向转正（手机拍照）；透明底合成白底；统一输出 JPEG
- 解码失败返回 None：调用方回退原图，不阻断上传
"""
from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image, ImageOps

THUMB_MAX_WIDTH = 800
_THUMB_QUALITY = 82


def make_cover_thumbnail(uploaded_file) -> ContentFile | None:
    """从封面文件生成缩略图；任何解码 / 处理失败都返回 None。"""
    try:
        uploaded_file.seek(0)
        img = Image.open(uploaded_file)
        img = ImageOps.exif_transpose(img)
        if img.width > THUMB_MAX_WIDTH:
            height = round(img.height * THUMB_MAX_WIDTH / img.width)
            img = img.resize((THUMB_MAX_WIDTH, height), Image.Resampling.LANCZOS)
        # 透明底 → 白底（JPEG 不支持透明）
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGBA")
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[-1])
            img = bg
        elif img.mode != "RGB":
            img = img.convert("RGB")
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=_THUMB_QUALITY, optimize=True)
        return ContentFile(buf.getvalue())
    except Exception:
        return None
