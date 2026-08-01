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
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    avatar = models.ImageField(upload_to=avatar_upload_path, blank=True)
    nickname = models.CharField(max_length=50, blank=True)
    birthday = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True)
    bio = models.TextField(blank=True)

    # ---- 自助注册（#26）：身份元数据与验证门槛 ----
    # real_name 不公开（仅本人 / 审核员可见）；identity 是纯元数据，不影响权限。
    real_name = models.CharField("真实姓名", max_length=100, blank=True)
    identity = models.CharField("身份", max_length=10, choices=IDENTITY_CHOICES, blank=True)
    # 默认 True：历史账号 / 信息组分发账号 / admin 建号 / 懒创建 profile 都视为已信任（Tier-3），
    # 保持既有行为不变。**自助注册是唯一创建「未验证」profile 的路径**——register 视图显式置 False，
    # 并由测试钉死「注册后不能登录 / 不能写」。default=False 会迫使引入 post_save 信号（与 admin
    # ProfileInline 的 save_new 撞 OneToOne）或 data migration + 懒创建覆写，复杂度更高、安全收益为零。
    email_verified = models.BooleanField("邮箱已验证", default=True)
    identity_verified = models.BooleanField("身份已审核", default=True)
    verified_at = models.DateTimeField("审核时间", null=True, blank=True)
    verified_by = models.ForeignKey(
        User, verbose_name="审核人", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="verified_profiles",
    )

    def __str__(self):
        return f"{self.user.username}'s profile"


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
