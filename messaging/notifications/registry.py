"""源与通道的注册表（进程内单例）。

源与通道都是代码级注册：新增一种 = 写一个类 + ``@register_*``。
数据库只存「用户订阅」（NotificationSubscription）与「投递记录」（NotificationDelivery）。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Event:
    """源内的事件类型（Phase 1 用于展示与校验；订阅粒度为源级）。"""

    key: str
    name: str


class NotificationSource:
    """通知源基类。子类声明 key / name / description / events / default_channels。"""

    key: str = ""
    name: str = ""
    description: str = ""
    events: tuple = ()
    default_channels: tuple = ("site",)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Source {self.key}>"


class BaseChannel:
    """投递通道基类。"""

    key: str = ""
    name: str = ""
    description: str = ""

    def is_available(self, user) -> bool:
        """该用户当前是否可用此通道（如邮箱已验证）。"""
        return True

    def deliver(self, delivery) -> None:
        """投递一条 NotificationDelivery；失败请抛异常（worker 记录并重试）。"""
        raise NotImplementedError

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Channel {self.key}>"


_SOURCES: dict[str, NotificationSource] = {}
_CHANNELS: dict[str, BaseChannel] = {}


def register_source(cls):
    """类装饰器：注册通知源（类或实例均可）。"""
    inst = cls() if isinstance(cls, type) else cls
    if not inst.key:
        raise ValueError("NotificationSource 必须有非空 key")
    _SOURCES[inst.key] = inst
    return cls


def register_channel(cls):
    """类装饰器：注册投递通道（类或实例均可）。"""
    inst = cls() if isinstance(cls, type) else cls
    if not inst.key:
        raise ValueError("BaseChannel 必须有非空 key")
    _CHANNELS[inst.key] = inst
    return cls


def get_source(key: str):
    return _SOURCES.get(key)


def get_channel(key: str):
    return _CHANNELS.get(key)


def all_sources() -> list:
    return sorted(_SOURCES.values(), key=lambda s: s.key)


def all_channels() -> list:
    return sorted(_CHANNELS.values(), key=lambda c: c.key)
