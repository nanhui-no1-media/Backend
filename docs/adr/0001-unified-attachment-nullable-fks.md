# 统一附件模型：每父级一个可空 FK（而非 GenericForeignKey）

任务和申报各自有一份几乎相同的附件模型（`tasks.Attachment`、`proposals.ProposalAttachment`），字段与校验逻辑逐行重复。决定合并为**一张 `Attachment` 表**，对每种父级保留一个**可空外键**（`task`、`proposal`，`on_delete=CASCADE`），并约束“恰好填一个父级”。

保留真外键是为了让**删除父级时 CASCADE 自动连带删除附件行**，再由一个 `post_delete` 信号同步删除磁盘文件——“自动回收不再被引用的附件”就此缩成一处信号、无需定时任务。

## 被否的方案

- **GenericForeignKey（`content_type` + `object_id`）**：最通用的“一个模型挂任意父级”做法，但 GFK 不参与 CASCADE——删父级后附件行不会消失，只会变成 `object_id` 指向已删对象的僵尸行。这让“回收”从“删文件”退化成“扫全表找悬空引用”，与自动回收目标相悖。
- **保留两张表、只抽共享代码**：能消除重复，但不是字面意义上的“一个附件系统”，且 GC 信号要在两处模型上分别挂。
