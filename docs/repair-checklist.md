# 修复清单

Date: 2026-06-27
Status: Completed

这份清单按“先修实现缺口，再修文档漂移，再看历史计划是否可合并”整理。

## 优先修复

| Priority | Item | Status | Evidence | Next step |
| --- | --- | --- | --- | --- |
| P1 | 删除已废弃的 `ttyd` 外部安装方案 | Removed | `dotfiles/.chezmoiexternal.toml.tmpl` 已不再包含 `ttyd` | 已删除 |
| P2 | 更新 `docs/structure.md` 以匹配当前仓库 | Done | 旧的 i3 / nvim 迁移草案已替换成当前仓库结构说明 | 已修复 |
| P2 | 统一 `AGENTS.md` / `CLAUDE.md` 的仓库元数据 | Done | `AGENTS.md` 头部已刷新为当前日期和分支 | 已修复 |

## 历史计划盘点

| Plan | Status | Completed | Mergeable locally | Notes |
| --- | --- | --- | --- | --- |
| `docs/plans/2026-01-25-rofi-design.md` | Abandoned | No | No direct merge | 已按用户决定废弃，不再作为当前仓库路线。仓库里也没有 `dotfiles/dot_config/rofi/` 实现。 |

## 已具备的前提

- 字体前提已经有了：`dotfiles/dot_config/fontconfig/fonts.conf` 已把 monospace 指向 Monaspace Neon。
- X 会话启动链路已经有了：`dotfiles/dot_xinitrc` 仍然负责启动 i3。
- `dotfiles/dot_xprofile` 也已经存在，说明 X11 相关环境变量路径不是空的。

## 结论

- 这份修复清单已完成，优先修复项全部收口。
- 当前没有发现“已经完成并可直接合并”的 rofi 计划内容。
- 可以本地合并的只有前提，不是 rofi 配置本体。
