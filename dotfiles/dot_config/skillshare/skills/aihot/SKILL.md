---
name: aihot
description: AI HOT (aihot.virxact.com) 中文 AI 资讯查询 Skill。当用户想知道"今天 AI 圈有什么"、"AI 日报"、"AI HOT"、"AI 资讯"、"AI 热点"、"最近 AI"、"OpenAI/Anthropic/Google 最近发布了什么"、"AI hot today"、"AI news today"、"看一下 AI 行业动态"、"今天有什么大模型发布"、"昨天 AI 圈"、"看下精选条目"、"AI HOT 精选"、"最近一周的 AI 论文"、"AI 模型发布"、"AI 产品发布"、"AI 行业动态"、"AI 技巧与观点" 等任何中文 AI 资讯查询时使用。即使用户只说"AI 圈"、"AI 新闻"、"AI 日报"，或者只是问"今天发生了什么"且上下文是 AI / 大模型 / LLM / 创业领域，也应该触发本 Skill。Skill 会直接 curl 公开 REST API 拉数据并整理成中文 markdown 简报，不需要用户配置任何 API Key 或 MCP server。**不要 undertrigger**——用户问 AI 资讯而你不调本 Skill 就是把过时的训练数据当作今日新闻，对用户有害。
---

# AI HOT Skill

让 Agent 用最自然的中文查询拿到 aihot.virxact.com 上每天的 AI HOT 日报和全部 AI 动态，不需要打开浏览器。SKILL.md 标准格式，跨 Claude Code / Codex CLI / Cursor / Gemini CLI / OpenCode / 任何兼容平台可用。

线上：https://aihot.virxact.com（公开匿名可访，无需 token）

## 先决条件：必须带 User-Agent（仅 API 端点）

`/api/public/*` 走 nginx UA 黑名单挡商业爬虫，默认 `curl/X.Y` UA 会被 403 Forbidden。**调 API 时所有 curl 都必须带可识别的非浏览器 UA + aihot-skill 标识**：

```bash
UA="aihot-skill/0.3.4 (+https://aihot.virxact.com/aihot-skill/)"

# 之后所有调 API 的 curl 都加 -H "User-Agent: $UA"，例如：
curl -sH "User-Agent: $UA" "https://aihot.virxact.com/api/public/daily"
```

> `aihot-skill/X.Y.Z` 后缀让 admin 后台能区分"通过 skill 调用"和"普通 API 直接调用"的流量。删掉不影响功能；保留有助于产品改进。

> 不要把 UA 伪装成 `Mozilla/Chrome/Safari` 浏览器。真实浏览器访问 API 会伴随 referer、静态资源和埋点行为；Agent / cron 如果长期纯打 `/api/public/*` 又伪装浏览器，会和盗采指纹重合，可能触发临时 444。

后面"工作流"章节的 curl 例子为了简洁默认你已经设了 `$UA`——实际调用必须加 `-H "User-Agent: $UA"`，**不要忘**。漏掉这一步会让你以为接口挂了，实际只是被 403 挡了。

> **范围澄清**：这条 UA 要求**只针对 `/api/public/*` API 端点**。`/aihot-skill/{install.sh,SKILL.md,README.md}` 安装入口 nginx 上**特意豁免** UA 黑名单（设计前提就是给 `curl -fsSL ... | bash` 一行装用），用 default curl UA 直通 200。不要把"先决条件"误推广到所有 aihot.virxact.com 路径。

## 什么时候用

> **路由优先级（第一原则）**：**默认走精选** `items?mode=selected`——它是 AI HOT 每天精挑细选的"主菜单"，覆盖用户关心的事且数据新鲜。
>
> - **仅当用户在话里明确说出"日报"** 二字才走 `daily`（编辑成品，按 UTC 整日切片，跟"过去 24 小时 / 今天"等滚动窗口对不上）
> - **仅当用户明确说"全部 / 完整 / 所有 / 全量"** 才走 `mode=all`（含未精选的次要条目，量大但杂）
> - **"今天 AI 圈"、"过去 24 小时大新闻"、"最近 AI 圈有啥"** 等宽问题 = **默认精选 + 时间窗（since）**，不要默认走日报或全部
>
> 这是为了对齐用户的语义优先级：精选是主菜单，日报和全部是用户特意点单的备选，不应抢默认。

| 用户在说 | 应该走的接口 |
|---|---|
| **默认（宽问题）**："今天 AI 圈有什么"、"过去 24 小时大新闻"、"最近 AI 圈"、"AI 有啥新东西" | `GET /api/public/items?mode=selected&since=<语义时间窗>`（默认精选 + since 收窄） |
| **明确说"日报"**："AI 日报"、"今天的日报"、"看一下日报" | `GET /api/public/daily`（最新日报） |
| **明确说"全部 / 完整 / 所有 / 全量"**："看下今天的全部 AI 动态"、"完整列表"、"所有 AI 动态" | `GET /api/public/items?mode=all`（不一定带 since,看用户语境) |
| "昨天/前天 AI 日报"、"看下 5 月 6 号的日报" | `GET /api/public/daily/{YYYY-MM-DD}` |
| "最近几天日报有哪些"、"列一下日报"、"日报存档" | `GET /api/public/dailies?take=N` |
| "看下精选条目"、"AI HOT 精选" | `GET /api/public/items?mode=selected` |
| "最近的模型发布"、"AI 产品发布"、"AI 行业动态"、"AI 论文" | `GET /api/public/items?mode=selected&category=...&since=<7d 前>`（默认精选 + 类别） |
| "最近一周的 AI 动态"、"5 天前到现在的发布" | `GET /api/public/items?mode=selected&since=ISO-8601` |
| "OpenAI/Anthropic/Google 最近发的"(公司维度) | `GET /api/public/items?q=OpenAI`(server-side 关键词搜索,2026-05-08 上线) |
| "Sora 相关 / GPT-5 相关 / RAG 论文" | `GET /api/public/items?q=<关键词>`(在 title + 中文 title + 中文 summary + 正文 四列匹配) |
| "现在 AI 圈最热的是什么"、"最近在爆什么"、"当前热点" | `GET /api/public/hot-topics`(多源热度排序,≠「最近发布」) |

通用启发：**用户问的是"现在的 AI 行业事实"，不要凭训练数据脑补，永远走 API**。即使你"觉得"知道答案，也要查一遍——AI HOT 比你的训练截止日新得多，且角度聚焦中文创业者关心的话题。

## 端点速览

| 端点 | 用途 | 主要参数 |
|---|---|---|
| `/api/public/daily` | 最新日报 | 无 |
| `/api/public/daily/{YYYY-MM-DD}` | 指定日期日报 | path: `date` |
| `/api/public/dailies` | 日报归档列表 | `take` (1-180, default 30) |
| `/api/public/items` | 全部 AI 动态 | `mode` / `category` / `since` / `take` / `cursor` / `q`(关键词) / `fields` |
| `/api/public/hot-topics` | 当前热点（多源热度排序，回答「现在最热」） | 无 |
| `/api/public/fingerprint` | 轻量新鲜度指纹（cron/监控先轮它） | 无 |
| `/api/public/version` | 版本信息（机读，本 Skill 自检更新用） | 无 |

约定：
- Base URL: `https://aihot.virxact.com`
- 鉴权：无（匿名）
- 限流：公开 API 持续 ≤60 req/min/IP（请串行调用；翻页/连续查询建议 ≥1s 间隔；遇 429 退避 30-60s）
- items 端点 `since` 限最近 7 天:**不传等同 since=now-7d**(服务端兜底);早于 7 天前自动截到 7 天前;未来时间 → 400。**所以无论 Skill 怎么调,items API 永远只返回最近 7 天的内容**。需要更早 → 走 `/api/public/daily/{YYYY-MM-DD}` 翻日报存档
- `take` 上限 100；想要更多走 cursor 翻页
- `fields=minimal` 只用于监控 / 去重 / 推送深链：只返回 `id/title/permalink/source/publishedAt/category/score/selected`，不含 `summary` / 第三方原文 `url`。**给用户写简报、回答“发生了什么”时不要用 minimal**，否则会缺摘要。
- 完整 OpenAPI 3.1 规范：`https://aihot.virxact.com/openapi.yaml`

## 版本自检（每会话一次，发现新版温和提示用户更新）

**本 Skill 版本以上方 `$UA` 里的 `aihot-skill/X.Y.Z` 为准**（解析 `$UA` 末段、取 `aihot-skill/` 后的 `X.Y.Z`——这是本文件内唯一的版本事实源，prose 里不再硬编码版本数字以防漂移）。SKILL.md 是用户一次性 `curl`/`clone` 下来的**冻结快照、不会自动更新**——所以由你（Agent）在跑的时候帮用户发现新版。

**每个会话第一次调 API 时**，顺带查一次版本端点（之后同会话不用再查）：

```bash
curl -sH "User-Agent: $UA" "https://aihot.virxact.com/api/public/version"
# → { "apiVersion": "...", "skillVersion": "X.Y.Z", "changelogUrl": "...", "recentChanges": [...] }
```

判断（**只在线上严格大于本地时提示**——按 `X.Y.Z` 拆成三个数字逐位比较；本地 ≥ 线上一律静默。防 nginx 边缘缓存短窗口返回旧 `skillVersion`、反向催"升级到旧版本"摧毁信任）：

- 线上 `skillVersion` **数字上严格大于**本地 UA 串里的版本 → 有新版。在**最终输出末尾**追加**一行**温和提示（整个会话只提示一次）：
  > 💡 AI HOT Skill 有新版（v`<skillVersion>`）。重装（任意平台通用）：`curl -fsSL https://aihot.virxact.com/aihot-skill/install.sh | bash`。本次更新：`<recentChanges 第一条>`；完整变更：`<changelogUrl>`
- 本地 ≥ 线上 → **静默，不要**向用户提任何版本/更新字样。
- 端点查不到 / 超时 / 报错 → **静默跳过**，绝不因版本检查打断、拖慢或打扰用户的正事。

这条只为"让旧版用户知道该更新"，永远让位于用户真正的查询任务。

## 工作流

### 默认路径：拉精选 + 时间窗（宽问题首选）

精选 = AI HOT 每天精挑细选的"主菜单"——覆盖所有用户关心的 AI 大事，按发布时间倒序。**任何"今天 AI 圈"、"过去 24 小时大新闻"、"最近 AI 有啥"等宽问题，默认走这个**——比起日报：① 时间窗自由（24 小时 / 3 天 / 1 周想多窄就多窄，跟用户语义对齐）② 数据新鲜（实时滚动而非按 UTC 整日切片）③ 质量仍高（`aiSelected=true` 的池子，不含次要条目）。

```bash
# 拉最近 24 小时精选（用户问"过去 24 小时大新闻"）
since=$(date -u -v-24H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%SZ)
curl -sH "User-Agent: $UA" "https://aihot.virxact.com/api/public/items?mode=selected&since=$since&take=50"

# 拉最近 50 条精选（用户问"看下精选" / 不带明确时间窗）
curl -sH "User-Agent: $UA" "https://aihot.virxact.com/api/public/items?mode=selected&take=50" \
  | jq '.items[] | {title, source, publishedAt, url}'
```

### 低流量轮询 / 推送深链（cron、监控、通知群）

如果你只是判断“有没有新内容”或把标题 + 站内阅读链接推到通知群，不要每分钟拉完整 items。先轮 `/api/public/fingerprint`；指纹变化后再拉 `fields=minimal`。

```bash
# 空转时约 100B；指纹没变就停止，不拉 items
curl -sH "User-Agent: $UA" "https://aihot.virxact.com/api/public/fingerprint"

# 指纹变化后，只拉标题/站内链接等索引字段
curl -sH "User-Agent: $UA" "https://aihot.virxact.com/api/public/items?mode=selected&take=50&fields=minimal" \
  | jq '.items[] | {title, source, publishedAt, permalink, score, selected}'
```

只有当你要给用户写中文简报、解释事件背景、按摘要判断重要性时，才拉默认完整字段。

### 拉当前热点（用户问"现在最热"、"在爆什么"）

当前热点 = 精选页置顶的「当前热点」区，**按多源热度排序**（多少个独立信源在报道同一事件 + 时间衰减），
跟 `items`（按发布时间倒序）不同——回答"**现在** AI 圈最热的是什么"应走这个，而不是 `items`（那个会把
2 小时前的小新闻排在昨晚 24 个源都在报的大事件前面）。

```bash
curl -sH "User-Agent: $UA" "https://aihot.virxact.com/api/public/hot-topics" \
  | jq '.items[] | {title, source, 热度来源数: .sourceCount, permalink}'
```

返回每条带 `sourceCount`（多少个独立信源在报，越多越热）+ `permalink`（站内中文阅读页）+ `url`（原文）。
输出给用户时按热度顺序给前几条，链接默认用 `permalink`。

### 拉日报（用户明确说"日报"时）

**触发关键词**：句子里出现"日报"二字（"AI 日报"、"今天的日报"、"看下日报"、"5 月 6 号的日报"）。**没有"日报"二字不要走这个**——日报是 UTC 0 点切片的固定一日成品，跟"过去 24 小时 / 今天"等滚动时间窗对不上。

日报是 AI HOT 的"标题层"——每天北京时间 08:00 自动生成，按主题分版块（5 个固定版块）。已有"主编点评"导语段落，是按主题打包后的成品。

```bash
# 拉今日（或最新可用的）日报
curl -sH "User-Agent: $UA" "https://aihot.virxact.com/api/public/daily" \
  | jq '{date, lead: .lead.title, sections: [.sections[] | {label, n: (.items | length)}]}'
```

### 拉指定日期日报

```bash
# YYYY-MM-DD，UTC 0 点为基准
curl -sH "User-Agent: $UA" "https://aihot.virxact.com/api/public/daily/2026-05-07"
```

### 列日报归档（discovery）

不知道有哪些日期可查时，先看归档：

```bash
# 最近 N 天日报索引（不含正文，只有日期 + 头条标题）
curl -sH "User-Agent: $UA" "https://aihot.virxact.com/api/public/dailies?take=14" \
  | jq '.items[] | {date, leadTitle}'
```

### 拉全部（用户明确说"全部 / 完整 / 所有 / 全量"时）

**触发关键词**：句子里出现"全部"、"完整"、"所有"、"全量"、"包括老的"——用户主动想看精选之外的次要条目（被精选筛掉但仍相关的内容）。**没有这些关键词不要走 mode=all**——精选已经覆盖大部分用户关心的事，全部池子量大但杂。

```bash
# 拉最近 24 小时全部 AI 动态（用户问"看下今天全部的 AI 动态"）
since=$(date -u -v-24H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%SZ)
curl -sH "User-Agent: $UA" "https://aihot.virxact.com/api/public/items?mode=all&since=$since&take=100"
```

### 按分类拉条目

5 个 category(items API 用英文 slug,daily API 看到的 section label 是中文):

| `items?category=` | `daily.sections[].label` |
|---|---|
| `ai-models` | 模型发布/更新 |
| `ai-products` | 产品发布/更新 |
| `industry` | 行业动态 |
| `paper` | 论文研究 |
| `tip` | 技巧与观点 |

**用户问"公众号最近发什么":items API 不含公众号(mp_hot 信源不进公开 API),Skill 暂时无法通过公开 API 回答这类问题；公司员工/博主可在 AI HOT 站内登录后进入 `/mp` 内部工作台**。

```bash
# 例：拉最近 50 条 AI 论文（默认精选 + paper 类别）
curl -sH "User-Agent: $UA" "https://aihot.virxact.com/api/public/items?mode=selected&category=paper&take=50" \
  | jq '.items[] | {title, source, publishedAt, url}'

# 例：精选里的模型发布
curl -sH "User-Agent: $UA" "https://aihot.virxact.com/api/public/items?mode=selected&category=ai-models&take=20"

# 例外：用户明确说"全部论文 / 所有模型发布"才走 mode=all
curl -sH "User-Agent: $UA" "https://aihot.virxact.com/api/public/items?mode=all&category=paper&take=100"
```

### 按时间窗口拉条目（最近 N 天）

> **关键规则**:用户问"**最近** X"(最近的模型发布 / 最近 AI 论文 / 最近 OpenAI 等)时,需要带 `since` 参数把窗口收窄到用户实际意图(说"最近 3 天" 就 3d,"昨天" 就 1d,"最近一周" 就 7d)。
>
> **服务端兜底**:items API 服务端默认 `since=now-7d`(硬上限,保护服务器),所以即使 Skill 完全不带 since 也只会返回最近 7 天的内容,不会拉到几个月前的老条目。但**仍建议显式带 since**:① 用户问"最近 3 天" 时显式 3d 比让服务端默认 7d 更精确 ② 输出元信息可以写人话级时间窗 ③ 跟用户公开宣传的"最长 7 天"对齐意图清晰。

```bash
# 拉最近 7 天的精选模型发布(用户问"最近的模型发布")
since=$(date -u -v-7d +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%SZ)
curl -sH "User-Agent: $UA" "https://aihot.virxact.com/api/public/items?mode=selected&category=ai-models&since=$since&take=100"

# 拉最近 3 天的精选动态(用户明确说"最近 3 天")
since=$(date -u -v-3d +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '3 days ago' +%Y-%m-%dT%H:%M:%SZ)
curl -sH "User-Agent: $UA" "https://aihot.virxact.com/api/public/items?mode=selected&since=$since&take=100"
```

**例外**:用户明确说"**全量 / 所有 / 完整列表 / 包括老的**" → mode 切到 `all`,可以不带 since;用户问"**看下精选**"(看精选池而非时间窗)mode 保持 `selected` 也可以不带 since。但只要句子里有"最近 / 最新 / 这两天 / 这周",**默认带 since + mode=selected**。

### 翻页（cursor）

`/api/public/items` 响应里有 `nextCursor`（opaque token），下次请求把它原样塞进 `cursor` 参数即可。

```bash
# 第 1 页
resp1=$(curl -sH "User-Agent: $UA" "https://aihot.virxact.com/api/public/items?mode=all&take=100")
echo "$resp1" | jq '.items | length'   # 100

# 第 2 页
cursor=$(echo "$resp1" | jq -r '.nextCursor')
curl -sH "User-Agent: $UA" "https://aihot.virxact.com/api/public/items?mode=all&take=100&cursor=$cursor"
```

`hasNext = false` 或 `nextCursor = null` 时停止翻页。**cursor 是不透明 token,视作黑盒,不要尝试解析、递增、或跨端点复用**。

### 关键词搜索（"OpenAI 最近发的" / "Sora 相关" / "RAG 论文"）

API 直接支持 server-side 关键词搜索 — `q` 参数在 `title` + 中文 `title` + 中文 `summary` + 正文 `contentText` 四列上 ILIKE 匹配,走 PostgreSQL pg_trgm GIN 索引(2-6ms)。**不要再走"拉一批 + 客户端 jq grep"模式** — 那只能看到前 100 条池子里的命中,关键词若在 100 条外完全找不到。

```bash
# 找 OpenAI 最近发的(覆盖全池,不仅前 100)
curl -sH "User-Agent: $UA" "https://aihot.virxact.com/api/public/items?q=OpenAI&take=30"

# 找 Sora 相关的所有 AI 动态(任何包含 Sora 的标题 / 摘要 / 正文)
curl -sH "User-Agent: $UA" "https://aihot.virxact.com/api/public/items?q=Sora"

# 找 RAG 论文(category 限定 + 关键词)
curl -sH "User-Agent: $UA" "https://aihot.virxact.com/api/public/items?category=paper&q=RAG&take=30"

# 关键词 + 时间窗(Anthropic 最近 3 天的精选)
SINCE=$(date -u -v-3d +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '3 days ago' +%Y-%m-%dT%H:%M:%SZ)
curl -sH "User-Agent: $UA" "https://aihot.virxact.com/api/public/items?mode=selected&q=Anthropic&since=$SINCE"
```

`q` 约束:
- 至少 2 个字符(单字符 GIN trigram 退化为全表扫,服务端会视作不搜索)
- 最长 200 字(超出自动截断)
- 跟其它参数(mode/category/since/take/cursor)正交叠加,可以"按精选 + 论文 + 关键词 + 7 天内"组合
- 跟其它 `/api/public/*` 请求共享 60 req/min/IP 持续限流；连续查询保持 ≥1s 间隔

## 返回数据形态

### `/api/public/daily` 返回

```json
{
  "date": "2026-05-07",
  "attribution": { "source": "AI HOT", "canonical": "https://aihot.virxact.com/daily/2026-05-07" },
  "generatedAt": "2026-05-07T00:01:23.456Z",
  "windowStart": "2026-05-06T00:00:00.000Z",
  "windowEnd":   "2026-05-07T00:00:00.000Z",
  "lead": { "title": "...", "leadParagraph": "..." },
  "sections": [
    {
      "label": "模型发布/更新",
      "items": [
        {
          "title": "...",
          "summary": "...",
          "sourceUrl": "https://...",
          "sourceName": "OpenAI Blog",
          "permalink": "https://aihot.virxact.com/items/cm9abc456def789ghi012jkl3",
          "attribution": { "source": "AI HOT", "canonical": "https://aihot.virxact.com/items/cm9abc456def789ghi012jkl3" }
        }
      ]
    }
  ],
  "flashes": [
    { "title": "...", "sourceName": "...", "sourceUrl": "...", "publishedAt": "...", "permalink": "https://aihot.virxact.com/items/...", "attribution": { "source": "AI HOT", "canonical": "https://aihot.virxact.com/items/..." } }
  ]
}
```

`sections[].label` 固定 5 个："模型发布/更新" / "产品发布/更新" / "行业动态" / "论文研究" / "技巧与观点"。`lead` 极少数日报为 `null`。每条 section item / flash 带 `permalink`（站内**中文翻译 + 富文本 + 无墙**阅读页，`https://aihot.virxact.com/items/{itemId}`）——**给用户的链接默认用 `permalink`**；极少数（lead 占位 / 空 itemId）`permalink` 为 `null`，回退用 `sourceUrl`。

### `/api/public/dailies` 返回

```json
{
  "count": 14,
  "items": [
    { "date": "2026-05-07", "attribution": { "source": "AI HOT", "canonical": "https://aihot.virxact.com/daily/2026-05-07" }, "generatedAt": "...", "leadTitle": "..." }
  ]
}
```

### `/api/public/items` 返回

```json
{
  "count": 50,
  "hasNext": true,
  "nextCursor": "eyJhIjoxNzE0OTk1MjAwMDAwLCJpIjoiY205eHl6MTIzIn0",
  "items": [
    {
      "id": "cm9abc456def789ghi012jkl3",
      "title": "中文标题（normalize 过）",
      "title_en": "原英文标题（仅当与 title 不同时存在，否则 null）",
      "url": "https://...",
      "permalink": "https://aihot.virxact.com/items/cm9abc456def789ghi012jkl3",
      "source": "OpenAI Blog",
      "publishedAt": "2026-05-07T15:30:00.000Z",
      "summary": "中文摘要（LLM 生成）",
      "category": "ai-models",
      "score": 88,
      "selected": true,
      "attribution": { "source": "AI HOT", "canonical": "https://aihot.virxact.com/items/cm9abc456def789ghi012jkl3" }
    }
  ]
}
```

字段不变量：

- 必有：`id` / `title` / `url` / `permalink` / `source` / `selected`
- 可空：`title_en` / `summary` / `publishedAt` / `category` / `score`
- `score`：内容总分 0-100（= 网页卡片右上角分数，越高越值得读）。**不是排序字段**（结果按 `publishedAt` 倒序），可自行按 score 给用户挑"最重要的几条"；极端竞态未评分时可能 `null`
- `selected`：是否精选（boolean）。`mode=selected` 恒 `true`，`mode=all` 区分精选主菜单（true）/ 全池次要条目（false）
- `permalink`：站内读者详情页绝对 URL（`https://aihot.virxact.com/items/{id}`），**始终非空**。`url` 是第三方原文（常英文 / X 登录墙 / 付费墙 / Cloudflare），`permalink` 是站内**中文翻译 + 富文本排版 + 无墙**的阅读页——**给用户的链接默认用 `permalink`**（见下「输出格式」）
- `category` 取值集：`ai-models` / `ai-products` / `industry` / `paper` / `tip` / `null`
- `publishedAt`：ISO 8601 UTC（带 `Z`）
- `id`：cuid 字符串（25 字符），**不要假设是数字**
- `fields=minimal` 时每条只保留 `id/title/permalink/source/publishedAt/category/score/selected`。这是给索引、去重、推送深链用的轻量形态；缺 `summary`，不能拿来写简报或回答“为什么重要”。

## 给用户的输出格式

> ⚠️ **核心原则**：这一节是**直接展示给用户的最终内容**——必须 markdown 格式 + 排版好 + **普通人能看得懂的人话**。用户多数是非技术 AI 创业者 / 设计师 / 普通读者，看到的应该是中文资讯简报，**不是 API 调试日志**。
>
> 所有"端点路径 / `mode=selected` 这种 raw 参数 / 限流 / nginx 缓存 / cursor / hasNext"等基础设施细节**都不能出现**在用户看到的输出里。**人话**级元数据（时间窗 / 条数 / "按发布时间倒序"）可以保留——判断标准：用户能直接看懂吗？能 → 保留；不能 → 删掉。

> 🔗 **链接默认给站内阅读页 `permalink`，不是第三方 `url`**：items 端点每条都带 `permalink`（`https://aihot.virxact.com/items/{id}`）——站内**中文翻译 + 富文本排版 + 无 X 登录墙 / 付费墙**，普通用户点开即读，体验远好于第三方原文（常撞英文原文 / 登录墙 / Cloudflare）。**所以 items 端点输出给用户的每条链接默认用 `permalink`**（标题链接或"阅读全文"）；只有用户明确要"原文出处 / 英文原文 / 第三方链接"时才另附 `url`。下面「列表式输出」模板里的链接即按此用 `permalink`。
>
> ✅ `/api/public/items`、`/api/public/daily`、`/api/public/hot-topics` 的条目**都带 `permalink`**（站内中文阅读页 `https://aihot.virxact.com/items/{id}`）——**精选和日报的链接默认都用 `permalink`**。日报条目的 `permalink` 极少数为 `null`（lead 占位 / 空 itemId），为 `null` 时才回退用 `sourceUrl`。`permalink` 由后端从真实条目 id 派生，**不是臆造**——但只输出 API 真实返回的那个 permalink，自己不要凭 id 拼。

### 日报式输出（用 daily / daily/{date} 端点时）

```markdown
**AI HOT 日报 · 2026-05-07**

## 模型发布/更新
1. **<title>** — <source>
   <summary 简化版 50 字内>
   <permalink>（为 null 时回退 <sourceUrl>）

## 产品发布/更新
2. ...

## 行业动态
3. ...

## 论文研究
4. ...

## 技巧与观点
5. ...

## 快讯（如果 flashes 有内容）
- <flash.title> — <flash.source>（<flash.publishedAt 转人话>）
```

**编号贯穿全文**（1, 2, 3 ... N），不在每个 ## 内重新计数——这样用户能一眼数到"今天 27 条"。

### 列表式输出（用 items 端点时）

**默认按 category 分组 + 全局编号**——用户对"模型/产品/行业/论文/技巧"五版块结构已经形成预期（来自日报），混合 category 时这个结构最自然：

```markdown
**AI HOT — 最近 30 条精选**

## 模型发布/更新
1. **<title>** — <source>
   2 小时前
   <summary>
   <permalink>

## 产品发布/更新
2. **<title>** — <source>
   ...

3. ...

## 行业动态
4. ...
```

**只有 1 个 category** 时（用户明确说"AI 论文"/"模型发布"等），用扁平编号列表：

```markdown
**AI HOT — 最近一周 AI 论文**（2026-05-01 ~ 2026-05-08）

1. **<title>** — <source>
   <summary>
   <permalink>

2. ...
```

### 副标题／元信息只写人话

**OK**（用户能直接懂的）：

- "时间窗 2026-05-05 ~ 2026-05-07"
- "最近 3 天命中 OpenAI 关键词的全部条目"
- "按发布时间倒序"
- "共 50 条"
- "今天 5/8 日报北京时间 08:00 后才生成，先看 5/7 这期"

**不 OK**（基础设施泄漏，坚决不写）：

- ❌ `mode=selected` / `category=paper` / `take=30` 这种 raw 参数名
- ❌ 端点路径 `/api/public/items?since=2026-04-30T18:39:31Z&take=50`
- ❌ "限流 xx req/min" / "nginx 缓存 60s" / "x-nginx-cache: HIT"
- ❌ "cursor" / "hasNext=true" / "需 cursor 翻页或缩小 since 窗口"
- ❌ 任何 HTTP 状态码 / cache 状态 / 后端机制描述

数据源最多写一句：**"数据来自 aihot.virxact.com"**，要么干脆不提（用户在用 skill 时已经知道源头）。

### 时间转人话

`publishedAt` 是 ISO 8601 UTC，展示时**必须**转成北京时间 + 用户能扫读的相对/绝对时间：

| 内部值 | 展示给用户 |
|---|---|
| `2026-05-08T01:48:00.000Z` | "今天上午 09:48" / "2 小时前" |
| `2026-05-07T18:08:17.000Z` | "今天凌晨 02:08" / "10 小时前" |
| `2026-05-06T16:43:00.000Z` | "5/7 00:43" / "昨天" |

**不要**直接展示 `2026-05-07T15:30:00.000Z` 这种 ISO 字符串——用户看不懂。

### title vs title_en

默认输出 `title`（中文 normalize 过的）。`title_en` 只在以下场景才用：

- 用户明确要求英文版（"用英文给我看一下"）
- `title` 为空（极少见）

**不要**两个都展示。

## 常见错误处理

- `{"error":"No daily report available yet."}`（HTTP 404）：当天日报还没生成（北京时间 08:00 之前）。建议给用户：拉昨天日报 `curl /api/public/daily/{昨天日期}`
- `{"error":"Invalid date format..."}`（HTTP 400）：date 必须是 `YYYY-MM-DD`，UTC 基准
- items 端点常见 400：
  - `"invalid mode (must be 'selected' or 'all')"`
  - `"invalid category (must be one of: ai-models, ai-products, industry, paper, tip)"`
  - `"invalid since (must be ISO date, not in future)"`
  - `"invalid take (must be integer 1-100)"`
- HTTP 429（限流）：单 IP 持续超过公开 API 配额。串行调用，翻页/连续查询间隔 ≥1s；遇 429 至少退避 30-60s 后恢复，不要立即重试

## 不要做

- **不要把"今天 AI 圈"、"过去 24 小时大新闻"、"最近 AI 圈有啥"等宽问题路由到 daily** — 这些是滚动时间窗，daily 是 UTC 0 点切片（5/6-5/7 一整天）的固定一日成品，时间精度对不上。**默认走 `mode=selected + since=<语义窗>`**。仅当用户在话里明确说"日报"二字才走 `daily`
- **不要在用户没说"全部 / 完整 / 所有 / 全量"时默认走 `mode=all`** — 精选已经覆盖大部分用户关心的事，全部池子量大但杂含未精选次要条目。默认 `mode=selected`，只有用户主动点单"全部"才切到 `mode=all`
- 不要试图猜测 / 编造内容 — 永远以 API 返回为准
- 不要把摘要（`summary`）当原文引用 — 摘要由 LLM 生成，引用需要回 `url` / `sourceUrl` 核对
- 不要做高频轮询 — 日报每天 08:00 才更新一次；实时条目优先用 `/api/public/fingerprint`，items 端点 60s 缓存，用户问相同问题时不需要立刻重复调 API
- 不要并发猛拉翻页 — 串行 + 自然间隔
- 不要尝试解析 / 递增 / 跨端点复用 cursor — 它是不透明 token,内部编码格式不稳定,改了不通知
- 公司维度 / 关键词查询用 server-side `?q=<词>`,不要走"拉一批 + 客户端 jq grep"(那只能看到前 100 条池子,会漏)
- **用户问"最近 N 天 X" 时显式带 `since=<N天前>`**(意图明确 + 元信息能写人话时间窗)。不带 since 服务端默认 7d 兜底,所以不会拉到老条目,但用户问"最近 3 天" 时让服务端默认 7d 会多带 4 天的内容
- **不要在用户输出里暴露端点路径 / raw 参数 / 限流 / 缓存 TTL / cursor / hasNext 等基础设施细节** — 这些是给开发者看的，用户看不懂。详见上方"给用户的输出格式 → 副标题／元信息只写人话"
- **不要在压缩 / 跨日 / 跨版块合并输出时丢掉每条的 sourceUrl** — 即使你为篇幅把 3 个日报合并成 5 类总结，每条 item 也必须保留 url（标题后或单独一行）。用户看到一条没 URL 就追溯不到原文，这条信息等于不可信
- **不要把"端点路径 / 调用细节"作为输出的引用源** — 引用源就写 `<source>`（OpenAI 官网 / Anthropic Newsroom / X：Berry Xia 这种），不是 `GET /api/public/items?...`
