import os
import uuid

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.contrib.auth.models import User


def avatar_upload_path(instance, filename):
    ext = os.path.splitext(filename)[1]
    return f"avatars/user_{instance.user_id}{ext}"


# 私有文件存储：身份证明落 PRIVATE_MEDIA_ROOT（与公开 MEDIA_ROOT 隔离），
# 绝不经 config/urls.py 的 static(MEDIA_URL) 公开服务；由带鉴权的下载视图提供（#31）。
# 用 callable 而非实例：migration 序列化函数引用、运行期按 settings 解析路径，避免绝对路径入库。
def private_media_storage():
    return FileSystemStorage(location=settings.PRIVATE_MEDIA_ROOT)


def identity_proof_upload_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    return f"identity_proofs/user_{instance.user_id}_{uuid.uuid4().hex}{ext}"


class Profile(models.Model):
    GENDER_CHOICES = [
        ("M", "男"),
        ("F", "女"),
        ("O", "其他"),
    ]
    IDENTITY_CHOICES = [
        ("student", "在校生"),
        ("external", "外校生"),
        ("graduate", "毕业生"),
        ("parent", "家长"),
        ("teacher", "教师"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    avatar = models.ImageField(upload_to=avatar_upload_path, blank=True)
    nickname = models.CharField(max_length=50, blank=True)
    birthday = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True)
    bio = models.TextField(blank=True)

    # 可选资料（ADR-0006 决策 3）：real_name 不公开（仅本人 / 审核员可见），在提交身份证明
    # 时收集；identity 是纯元数据，不影响权限。验证态不在 Profile 上——见 Verification。
    real_name = models.CharField("真实姓名", max_length=100, blank=True)
    identity = models.CharField("身份", max_length=10, choices=IDENTITY_CHOICES, blank=True)

    def __str__(self):
        return f"{self.user.username}'s profile"


class Verification(models.Model):
    """验证通道当前状态（ADR-0006）：每 (user, channel) 一行，in-place 更新。

    账号「已验证」⇔ 任一通道 ``status=approved``（见 :func:`is_verified`）。通道是一等公民：
    邮箱、人工审批是通道；加通道 = 加 choices + 实现该通道流程，核心判定（任一 approved）不动。

    - ``identifier`` 是通道主体：邮箱=待验地址（验证前住此、不进 ``User.email``）；人工=空。
    - 审计走 ``IdentityProof``（人工通道证据，永久留底）；本表不留尝试历史。
    """

    CHANNEL_EMAIL = "email"
    CHANNEL_MANUAL = "manual"
    CHANNELS = [
        (CHANNEL_EMAIL, "邮箱"),
        (CHANNEL_MANUAL, "人工审批"),
    ]

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUSES = [
        (STATUS_PENDING, "待验证"),
        (STATUS_APPROVED, "已通过"),
        (STATUS_REJECTED, "已驳回"),
    ]

    user = models.ForeignKey(
        User, verbose_name="用户", on_delete=models.CASCADE, related_name="verifications"
    )
    channel = models.CharField("通道", max_length=20, choices=CHANNELS)
    status = models.CharField("状态", max_length=10, choices=STATUSES, default=STATUS_PENDING)
    identifier = models.CharField("通道标识", max_length=254, blank=True, default="")
    verified_at = models.DateTimeField("通过时间", null=True, blank=True)
    verified_by = models.ForeignKey(
        User, verbose_name="审核人", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="verifications_reviewed",
    )

    class Meta:
        verbose_name = "验证通道"
        verbose_name_plural = "验证通道"
        constraints = [
            models.UniqueConstraint(fields=["user", "channel"], name="unique_user_channel"),
        ]
        indexes = [models.Index(fields=["user", "status"])]
        ordering = ["user", "channel"]

    def __str__(self):
        return f"{self.user.username} · {self.get_channel_display()} · {self.get_status_display()}"


def is_verified(user):
    """账号「已验证」单一计算源（ADR-0006）：任一验证通道 approved 即真。

    驱动 写操作门禁 / 徽章 / 邮箱登录前提 / 密码重置前提 / 验证面板。无 Verification 行 ⇒
    未验证（访客）——不再有「无 profile 视为已审核」后备（ADR-0006 决策 7）。

    纯计算：不含超级用户逃生舱（那是访问控制轴，由 ``IsVerified`` 门禁承担，ADR-0005 决策 9）。
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    return user.verifications.filter(status=Verification.STATUS_APPROVED).exists()


class IdentityProof(models.Model):
    """身份证明材料（学生证照片等）——审计留底，永久保存（审核通过后也不删）。

    与「附件」子系统隔离：附件绑定单一父级并随父级回收（ADR 0002）；身份证明无父级、
    供事后追溯。文件存 PRIVATE_MEDIA_ROOT 私有存储，仅本人或持 can_review_identity 者可读。
    """

    user = models.ForeignKey(
        User, verbose_name="用户", on_delete=models.CASCADE, related_name="identity_proofs"
    )
    file = models.ImageField(
        "证明材料", upload_to=identity_proof_upload_path, storage=private_media_storage
    )
    uploaded_at = models.DateTimeField("上传时间", auto_now_add=True)

    class Meta:
        verbose_name = "身份证明"
        verbose_name_plural = "身份证明"
        ordering = ["-uploaded_at"]
        permissions = [
            ("can_review_identity", "可以审核身份证明材料"),
        ]

    def __str__(self):
        return f"{self.user.username} 的身份证明 ({self.uploaded_at:%Y-%m-%d})"


class UserSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="login_sessions")
    session_key = models.CharField(max_length=40, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")
    device_type = models.CharField(max_length=16, default="Unknown")
    device_name = models.CharField(max_length=128, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    is_current = models.BooleanField(default=True)

    class Meta:
        indexes = [models.Index(fields=["user", "is_current"])]
        ordering = ["-created_at"]

    def __str__(self):
        state = "current" if self.is_current else "old"
        return f"{self.user.username} @ {self.session_key[:8]} ({state})"
