# 招生与加入 API

`recruitment` 模块承载「加入社团」落地页：本年度**招生公告**（单例）、**自我介绍问卷**（`kind=join` 的问卷单例，SurveyJS Schema）与报名作答。公告与问卷对公众可读、报名对公众可提交；编辑与报名结果读取复用门户管理员权限 `about.manage_aboutpage`。

> 全局约定（认证 / 错误 / 分页 / CSRF）见 [API 总览](README.md)。相关设计记录：[ADR-0009：门户重构（加入问卷 = 嵌入式 SurveyJS）](../adr/0009-portal-review-about-tutorials.md)、[ADR-0014：问卷与问卷结果从活动表拆出](../adr/0014-questionnaire-independent.md)

## 概念与约定

- 四条路径挂载于 `/recruitment/`（`recruitment/urls.py`）：`/recruitment/` 落地页、`/recruitment/notice/` 招生公告、`/recruitment/schema/` 自我介绍问卷 Schema、`/recruitment/responses/` 报名作答。
- **招生公告是单例**（`RecruitmentNotice`）：无需建记录，读写均指向唯一一行（`get_solo()`）。**自我介绍问卷**是 `Questionnaire` 中 `kind=join` 的单例（模型住在 `activities`，见 [activities.md](activities.md)）；加入页只是作答入口，编辑走问卷后台 / 本模块的 Schema 端点。
- 编辑权限复用门户管理员：公告与 Schema 的写入端点、报名结果读取，均需 `about.manage_aboutpage`（`CanEditAbout` / `IsAboutEditor`）；落地页与公告 / Schema 的读取公开。
- 报名规则：**已登录一人一份；未登录访客按设备标识一份**。访客请求须带 `X-Device-Id` 头（门户生成的标准 UUID，写入 localStorage；见 [ADR-0014](../adr/0014-questionnaire-independent.md)）；缺失或格式非法一律视为未提供。
- 「立即加入」须先勾选公告确认（`notice_acknowledged` 必须为 `true`），否则提交被拒。
- 未登录提交不记名（落 `device_id`）；已登录提交记 `user`。设备标识可被清 localStorage / 换浏览器绕过——这是 Web 侧的去重上限，不是硬件标识（ADR-0014）。
- 作答键名与 SurveyJS 元素 `name` 一一对应（如 `grade`、`intro`），`answers` 按原样 JSON 落库。

## 端点一览

| 方法 | 路径 | 认证 | 权限 | 说明 |
|---|---|---|---|---|
| GET | `/recruitment/` | 公开 | — | 加入落地页：公告 + 问卷 Schema + 是否已提交 |
| GET | `/recruitment/notice/` | 公开 | — | 读取招生公告 |
| PUT / PATCH | `/recruitment/notice/` | 登录 | `about.manage_aboutpage` | 更新招生公告 |
| GET | `/recruitment/schema/` | 公开 | — | 读取自我介绍问卷 Schema |
| PUT / PATCH | `/recruitment/schema/` | 登录 | `about.manage_aboutpage` | 更新自我介绍问卷 Schema |
| GET | `/recruitment/responses/` | 登录 | `about.manage_aboutpage` | 报名作答列表 |
| POST | `/recruitment/responses/` | 公开 | — | 提交报名作答 |

## 端点详情

### 加入落地页

`GET /recruitment/`

**认证**：公开；**权限**：—

一次返回公告、问卷 Schema 与当前请求者是否已提交。

**响应 `200 OK`**

```json
{
  "notice": {
    "content": "<p>2026 学年招新开始，欢迎高一新同学报名。</p>",
    "updated_at": "2026-09-01T02:00:00Z"
  },
  "schema": {
    "title": "自我介绍问卷",
    "pages": [
      {
        "name": "page1",
        "elements": [
          { "type": "radiogroup", "name": "grade", "title": "年级", "isRequired": true, "choices": ["高一", "高二", "高三"] },
          { "type": "checkbox", "name": "skills", "title": "擅长方向（可多选）", "choices": ["摄影", "剪辑", "平面设计", "撰稿"] },
          { "type": "dropdown", "name": "source", "title": "你如何得知本社团？", "choices": ["同学介绍", "海报", "其他"] },
          { "type": "text", "name": "other_source", "title": "其他来源", "visibleIf": "{source} = '其他'" },
          { "type": "comment", "name": "intro", "title": "自我介绍", "isRequired": true }
        ]
      }
    ],
    "triggers": [
      { "type": "skip", "expression": "{grade} = '高三'", "gotoName": "intro" }
    ]
  },
  "already_responded": false
}
```

- `schema` 是问卷当前保存的 SurveyJS JSON（上例为默认 Schema；元素、选项与跳题可由管理员在编辑器中改写）。
- `already_responded`：已登录按用户查；访客按 `X-Device-Id` 查；两者都没有时恒为 `false`。

### 读取招生公告

`GET /recruitment/notice/`

**认证**：公开；**权限**：—

**响应 `200 OK`**

```json
{ "content": "<p>2026 学年招新开始，欢迎高一新同学报名。</p>", "updated_at": "2026-09-01T02:00:00Z" }
```

`content` 为消毒后的 HTML（`common.rich_text.sanitize_html`），前台以富文本渲染。

### 更新招生公告

`PUT /recruitment/notice/` · `PATCH /recruitment/notice/`

**认证**：登录；**权限**：`about.manage_aboutpage`

**请求体**：`content`（string）— 公告 HTML；写入前做 HTML 消毒，缺省不改动原值。

```json
{ "content": "<p>报名截止 9 月 30 日，请抓紧时间。</p>" }
```

**响应 `200 OK`**：与读取公告同形（`content` + `updated_at`）。

**错误**：403 未登录或未持 `about.manage_aboutpage`。

### 读取自我介绍问卷 Schema

`GET /recruitment/schema/`

**认证**：公开；**权限**：—

**响应 `200 OK`**

```json
{
  "schema": {
    "title": "自我介绍问卷",
    "pages": [
      { "name": "page1", "elements": [ { "type": "radiogroup", "name": "grade", "title": "年级", "choices": ["高一", "高二", "高三"] } ] }
    ],
    "triggers": [ { "type": "skip", "expression": "{grade} = '高三'", "gotoName": "intro" } ]
  },
  "updated_at": "2026-09-10T06:00:00Z"
}
```

`schema` 即 `Questionnaire.get_join()` 的 JSON 字段；尚未初始化时返回默认 Schema（含 `grade` / `skills` / `source` / `other_source` / `intro` 五个元素与一条跳题 trigger）。

### 更新自我介绍问卷 Schema

`PUT /recruitment/schema/` · `PATCH /recruitment/schema/`

**认证**：登录；**权限**：`about.manage_aboutpage`

**请求体**：`schema`（object）— 完整 SurveyJS Schema。

```json
{ "schema": { "title": "自我介绍问卷", "pages": [ { "name": "p1", "elements": [ { "type": "text", "name": "intro", "title": "自我介绍", "isRequired": true } ] } ] } }
```

**响应 `200 OK`**：与读取 Schema 同形（`schema` + `updated_at`）。

**错误**

| 状态码 | 场景 |
|---|---|
| 400 | `{"schema": ["问卷 Schema 须为 JSON 对象"]}`（非对象）或 `{"schema": ["Schema 须包含 pages"]}`（缺 `pages`） |
| 403 | 未登录或未持 `about.manage_aboutpage` |

### 报名作答列表

`GET /recruitment/responses/`

**认证**：登录；**权限**：`about.manage_aboutpage`

**查询参数**

| 名称 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `page` | integer | 否 | 页码（全局分页，每页 20） |

**响应 `200 OK`**

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 12,
      "answers": {
        "grade": "高一",
        "skills": ["摄影"],
        "source": "同学介绍",
        "intro": "我是一年级（3）班的小李，想加入摄像组。"
      },
      "submitted_at": "2026-09-18T03:20:00Z"
    }
  ]
}
```

只返回作答本身（`answers` 的键名即问卷元素 `name`），不回传作答者身份或设备标识。

**错误**：403 未登录或未持 `about.manage_aboutpage`。

### 提交报名

`POST /recruitment/responses/`

**认证**：公开；**权限**：—

**请求头**：`X-Device-Id` — 访客必带（标准 UUID 格式，非法值视同缺失）；已登录可省略。

**请求体**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `answers` | object | 是 | 问卷作答（键为元素 `name`）；空对象 / 非对象被拒 |
| `notice_acknowledged` | boolean | 是 | 公告确认，须为 `true`；write_only，不落库、不回显 |

```json
{
  "answers": {
    "grade": "高一",
    "skills": ["摄影"],
    "source": "同学介绍",
    "intro": "我是一年级（3）班的小李，想加入摄像组。"
  },
  "notice_acknowledged": true
}
```

**响应 `201 Created`**

```json
{ "ok": true, "id": 12, "message": "报名已提交，我们会尽快与你联系。" }
```

`id` 为报名记录（`QuestionnaireResponse`）主键。

**错误**

| 状态码 | 场景 |
|---|---|
| 400 | 未勾选公告确认：`{"notice_acknowledged": ["请先勾选「我已阅读并知晓公告内容」"]}`；字段缺失时为 DRF 必填报错 |
| 400 | `answers` 缺失、为空对象或非对象：`{"answers": ["请填写问卷后再提交"]}` |
| 400 | 访客缺少或格式非法的 `X-Device-Id`：`{"detail": "缺少设备标识"}` |
| 400 | 重复提交：`{"detail": "你已经提交过了"}`（已登录一人一份；访客按 `X-Device-Id` 一设备一份） |
