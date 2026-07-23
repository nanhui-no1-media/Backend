"""集中一处上传校验（原 tasks / proposals 各有一份逐行重复的实现，T3 将删除）。

校验规则：
- 文件大小不超过 50MB；
- 禁止上传可执行 / 脚本类扩展名；
- 按 content-type 把文件分类为 图片 / 视频 / 文档 / 压缩包 / 其他。
"""
import os

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

FORBIDDEN_EXTENSIONS = frozenset({
    ".exe", ".bat", ".cmd", ".sh", ".php", ".asp", ".jsp",
    ".py", ".rb", ".pl", ".cgi", ".com", ".scr", ".pif", ".msi",
})

_DOCUMENT_CONTENT_TYPES = frozenset({
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "text/plain",
})

_ARCHIVE_CONTENT_TYPES = frozenset({
    "application/zip",
    "application/x-rar-compressed",
    "application/x-7z-compressed",
    "application/gzip",
})


def classify_file_type(content_type):
    """按 content-type 推断 file_type（与原 tasks/proposals 逻辑一致）。"""
    ct = content_type or ""
    if ct.startswith("image/"):
        return "image"
    if ct.startswith("video/"):
        return "video"
    if ct in _DOCUMENT_CONTENT_TYPES:
        return "document"
    if ct in _ARCHIVE_CONTENT_TYPES:
        return "archive"
    return "other"


def upload_error(file):
    """返回上传文件的错误消息（若合法则返回 None）。"""
    if file.size > MAX_FILE_SIZE:
        return "文件大小不能超过 50MB"
    ext = os.path.splitext(file.name)[1].lower()
    if ext in FORBIDDEN_EXTENSIONS:
        return "禁止上传此类型的文件"
    return None
