"""任务生命周期模块（架构深化 #1，见 #6 / #9）。

独占任务的状态机、权限规则与「活跃参与者」判定。对外暴露：

- 三段权限谓词：``is_creator`` / ``is_active_participant`` / ``can_manage``
  （外加指派权限 ``can_assign``）；
- ``available_actions(task, user)`` —— 此刻该用户可执行的动作集合；
- ``apply(action, task, user, *, payload)`` —— 执行一次状态转移。

状态机与权限判定为进程内纯领域逻辑，仅依赖任务字段 + 用户权限。``apply``
会在此之上产生副作用并写库（创建/审批认领申请、置负责人、记完成时间等），
使八个 HTTP 动作可退化为「解析入参 → 调 apply → 序列化」的薄调用方。
"""

from dataclasses import dataclass

from django.contrib.auth.models import User
from django.utils import timezone

from .models import Task, TaskClaimRequest


# ---- 权限谓词 -----------------------------------------------------------

def is_creator(task, user):
    """任务的创建者。"""
    return task.creator_id is not None and task.creator_id == user.pk


def is_active_participant(task, user):
    """活跃参与者：任务处于进行中（``in_progress``）时的负责人或协作者。

    供提交验收（complete）判定；附件子系统亦复用本谓词（ADR-0002）。
    """
    return task.status == "in_progress" and (
        task.assignee_id == user.pk
        or task.collaborators.filter(pk=user.pk).exists()
    )


def can_manage(user):
    """持任务管理权限者（社长组授予 ``tasks.manage_tasks``）。"""
    return user.has_perm("tasks.manage_tasks")


def can_assign(user):
    """持任务指派权限者（社长组授予 ``tasks.assign_task``）。"""
    return user.has_perm("tasks.assign_task")


# ---- 动作标识 -----------------------------------------------------------
# 与 tasks 视图的 @action 名一一对应，#12 可直接以此映射 HTTP 路由。
CLAIM = "claim"
APPROVE_CLAIM = "approve_claim"
REJECT_CLAIM = "reject_claim"
COMPLETE = "complete"
APPROVE_COMPLETION = "approve_completion"
REJECT_COMPLETION = "reject_completion"
CANCEL = "cancel"
ASSIGN = "assign"

# 稳定输出顺序：供前端按既定次序渲染按钮（顺序本身不是契约，仅为一致）。
_ACTION_ORDER = (
    CLAIM, APPROVE_CLAIM, REJECT_CLAIM,
    COMPLETE, APPROVE_COMPLETION, REJECT_COMPLETION,
    CANCEL, ASSIGN,
)


def available_actions(task, user):
    """此刻 ``user`` 可对 ``task`` 执行的动作（有序、唯一）。

    纯领域逻辑：仅依据任务字段 + 用户权限，不查认领申请、不触 HTTP。
    故「认领」类动作按「状态 + 角色」给出，至于此刻是否真有待审认领、
    是否已重复申请，留待 ``apply`` / HTTP 层在执行时校验。
    """
    if not user.is_authenticated:
        return ()
    actions = set()

    # 申请认领：待处理 / 认领审核中，且无负责人、且非创建者。
    if task.status in ("pending", "review") and not task.assignee_id and not is_creator(task, user):
        actions.add(CLAIM)
    # 审批认领：认领审核中，且为创建者或持管理权限。
    if task.status == "review" and (is_creator(task, user) or can_manage(user)):
        actions.add(APPROVE_CLAIM)
        actions.add(REJECT_CLAIM)
    # 提交验收：进行中，且为活跃参与者（负责人 / 协作者）或持管理权限。
    if task.status == "in_progress" and (is_active_participant(task, user) or can_manage(user)):
        actions.add(COMPLETE)
    # 通过 / 打回验收：待验收，且为创建者或持管理权限。
    if task.status == "reviewing" and (is_creator(task, user) or can_manage(user)):
        actions.add(APPROVE_COMPLETION)
        actions.add(REJECT_COMPLETION)
    # 取消：尚未终态，且为创建者或持管理权限。
    if task.status not in ("completed", "cancelled") and (is_creator(task, user) or can_manage(user)):
        actions.add(CANCEL)
    # 指派：持指派权限（与状态无关）。
    if can_assign(user):
        actions.add(ASSIGN)

    return tuple(action for action in _ACTION_ORDER if action in actions)


# ---- 转移执行 -----------------------------------------------------------

@dataclass(frozen=True)
class TransitionResult:
    """``apply`` 的返回：是否成功、所执行动作、转移后的任务、拒绝原因。"""

    ok: bool
    action: str
    task: Task
    reason: str | None = None


# 「状态 / 权限」闸口失败时的原因（载荷级校验另给具体原因）。
_UNAVAILABLE_REASON = {
    COMPLETE: "当前无法提交验收",
    APPROVE_COMPLETION: "当前无法通过验收",
    REJECT_COMPLETION: "当前无法打回验收",
    CANCEL: "当前无法取消任务",
    CLAIM: "当前无法申请认领",
    APPROVE_CLAIM: "当前无法审批认领",
    REJECT_CLAIM: "当前无法审批认领",
    ASSIGN: "无指派权限",
}


def apply(action, task, user, *, payload=None):
    """执行一次状态转移，返回 :class:`TransitionResult`。

    先以 :func:`available_actions` 把守「状态 + 权限」闸口，再做载荷级校验
    （打回理由、认领 id、指派 id、重复认领），最后落地副作用并写库。
    """
    payload = payload or {}

    if action not in available_actions(task, user):
        return TransitionResult(False, action, task, _UNAVAILABLE_REASON.get(action, "当前不可执行此操作"))

    if action == COMPLETE:
        task.status = "reviewing"
        task.reject_reason = ""
        task.save(update_fields=["status", "reject_reason", "updated_at"])
        return TransitionResult(True, action, task)

    if action == APPROVE_COMPLETION:
        task.status = "completed"
        task.completed_at = timezone.now()
        task.save(update_fields=["status", "completed_at", "updated_at"])
        return TransitionResult(True, action, task)

    if action == REJECT_COMPLETION:
        reason = str(payload.get("reason", "")).strip()
        if not reason:
            return TransitionResult(False, action, task, "请填写打回理由")
        task.status = "in_progress"
        task.reject_reason = reason
        task.save(update_fields=["status", "reject_reason", "updated_at"])
        return TransitionResult(True, action, task)

    if action == CANCEL:
        task.status = "cancelled"
        task.save(update_fields=["status", "updated_at"])
        return TransitionResult(True, action, task)

    if action == ASSIGN:
        assignee_id = payload.get("assignee_id")
        if assignee_id:
            try:
                assignee = User.objects.get(pk=assignee_id)
            except User.DoesNotExist:
                return TransitionResult(False, action, task, "用户不存在")
            task.assignee = assignee
            task.status = "in_progress"
        else:
            task.assignee = None
            task.status = "pending"
        task.save(update_fields=["assignee", "status", "updated_at"])
        return TransitionResult(True, action, task)

    if action == CLAIM:
        reason = str(payload.get("reason", "")).strip()
        _, created = TaskClaimRequest.objects.get_or_create(
            task=task, claimant=user, defaults={"reason": reason},
        )
        if not created:
            return TransitionResult(False, action, task, "你已经申请过认领此任务")
        # 首个认领申请把待处理任务流转到认领审核；审核中追加则状态不变。
        if task.status == "pending":
            task.status = "review"
            task.save(update_fields=["status", "updated_at"])
        return TransitionResult(True, action, task)

    if action == APPROVE_CLAIM:
        try:
            claim = TaskClaimRequest.objects.get(pk=payload.get("claim_id"), task=task, status="pending")
        except TaskClaimRequest.DoesNotExist:
            return TransitionResult(False, action, task, "认领请求不存在或已处理")
        claim.status = "approved"
        claim.reviewed_by = user
        claim.reviewed_at = timezone.now()
        claim.save(update_fields=["status", "reviewed_by", "reviewed_at"])
        task.assignee = claim.claimant
        task.status = "in_progress"
        task.save(update_fields=["assignee", "status", "updated_at"])
        return TransitionResult(True, action, task)

    if action == REJECT_CLAIM:
        try:
            claim = TaskClaimRequest.objects.get(pk=payload.get("claim_id"), task=task, status="pending")
        except TaskClaimRequest.DoesNotExist:
            return TransitionResult(False, action, task, "认领请求不存在或已处理")
        claim.status = "rejected"
        claim.reviewed_by = user
        claim.reviewed_at = timezone.now()
        claim.save(update_fields=["status", "reviewed_by", "reviewed_at"])
        # 已无其它待处理申请时，把任务从认领审核回退到待处理。
        if task.status == "review" and not TaskClaimRequest.objects.filter(task=task, status="pending").exists():
            task.status = "pending"
            task.save(update_fields=["status", "updated_at"])
        return TransitionResult(True, action, task)

    # 不可达：上方闸口已拦下所有不在 available_actions 中的动作，而命中的动作
    # 八种均在上方分支处理。保留此句作为派发完备性的断言，防新增动作时漏写分支。
    raise AssertionError(f"lifecycle.apply: 未处理的动作 {action!r}")
