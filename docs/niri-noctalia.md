# Niri + Noctalia v5：Tokyo Night 双屏桌面

配置适配本机 Niri 26.04 / Noctalia 5.2.1。使用 v5 原生 TOML、原生锁屏和空闲管理，不依赖旧版 Quickshell IPC、swayidle 或终端屏保。

## 效果

- Tokyo Night 深蓝灰底色，蓝色焦点环、紫色辅助色；12px 圆角、12px 窗口间距、柔和阴影。
- Omarchy Tokyo Night 的 sunset lake 壁纸：主屏独立 4K 裁切，副屏独立竖版裁切，避免将横图拉伸变形。
- 悬浮顶栏：主屏保留媒体/托盘/网络，竖屏精简控件；不启动第二套 Waybar。
- 总览显示模糊壁纸背景；桌面不添加时钟/Dock，保持工作空间干净。
- 屏保式锁屏：空闲 5 分钟后渐暗并安全锁屏，双屏大时钟和日期、紧凑密码框；空闲 10 分钟熄屏，输入自动亮屏。不会自动挂起桌面机。
- 这不是 Omarchy 的 terminaltexteffects 动画屏保；全屏终端动画不能代替安全锁屏。

## 显示器布局

```text
                         HDMI-A-1 顶部 y=-240
┌──────────────────────┐ ┌───────────┐
│ DP-1 / G320PRO        │ │ Dell      │
│ 3840×2160 @ 60 Hz     │ │ S2415H    │
│ scale 1.5            │ │ 1920×1080 │
│ 逻辑 2560×1440        │ │ scale 1   │
│ position (0, 0)      │ │ 旋转 90°  │
└──────────────────────┘ │ 1080×1920 │
                         └───────────┘
                         position (2560, -240)
```

副屏与主屏垂直居中，边缘相邻，鼠标可直接跨屏。Niri 的 `transform "90"` 是**逆时针**；若物理屏幕是顺时针转的，改为 `"270"`。若希望顶部对齐，将副屏 `y=-240` 改成 `y=0`。主屏选择已报告支持的 60Hz，不擅自启用 75Hz。

副屏窗口也遵循 Niri 滚动平铺：移到竖屏后按 `Super+F` 让当前列占满可用宽度，避免半宽窗口过窄。

## 源文件

| 文件 | 用途 |
|---|---|
| `dotfiles/dot_config/niri/config.kdl` | 在当前本机配置基础上保留原有快捷键和 fcitx5 启动，调整双屏、窗口外观和 Noctalia 快捷键 |
| `dotfiles/dot_config/noctalia/desktop.toml.tmpl` | 顶栏、壁纸、锁屏、时钟、空闲管理；home 路径通过 chezmoi 模板渲染 |
| `dotfiles/dot_config/noctalia/palettes/TokyoNight.json` | 自定义 Noctalia v5 配色，不自动修改 GTK、终端或编辑器主题 |
| `dotfiles/dot_local/share/wallpapers/omarchy/` | 原壁纸与横/竖屏裁切，应用到 `~/.local/share/wallpapers/omarchy/` |
| `dotfiles/dot_local/share/applications/alacritty.desktop.tmpl` | 本地管理 Alacritty 桌面条目，使用 mise shim 的绝对路径 |
| `dotfiles/dot_config/systemd/user/symlink_mako.service` | 指向 `/dev/null` 的用户服务 mask，让 Noctalia 接管通知 |

连接器名称针对本机；换显卡接口后需要同时更新 Niri output、Noctalia bar monitor、wallpaper monitors 和 lockscreen widgets output。

## 首次启用（手动执行）

**没有自动执行 `chezmoi apply`。** Niri 会热加载显示布局，鼠标和窗口位置会发生变化，请先保存工作。

Noctalia v5 会最后加载 `~/.local/state/noctalia/settings.toml` 中的 GUI 覆盖。本机现有覆盖包含 `lockscreen_widgets.enabled = false`、旧的显示器尺寸和默认壁纸；不处理它们，新主题的锁屏和壁纸会被覆盖。以下流程停止 Noctalia 后备份旧覆盖，保留其他 state 数据，不删除历史记录。

```bash
# 先查看本次配置差异
chezmoi diff --recursive ~/.config/niri/config.kdl ~/.config/noctalia ~/.local/share/wallpapers/omarchy

# 备份当前配置和 GUI 覆盖
backup="$HOME/.local/share/niri-noctalia-backups/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$backup"
cp -a "$HOME/.config/niri" "$backup/niri"
cp -a "$HOME/.config/noctalia" "$backup/noctalia"

# 防止 GUI 在迁移期间重新写入覆盖
pkill -x noctalia || true
if [ -f "$HOME/.local/state/noctalia/settings.toml" ]; then
    mv "$HOME/.local/state/noctalia/settings.toml" "$backup/settings.toml"
fi

# 仅应用这些目标，避免应用仓库里的无关更改
chezmoi apply --recursive ~/.config/niri/config.kdl ~/.config/noctalia ~/.local/share/wallpapers/omarchy

# 清理旧栏（如果正在运行），启动 v5 Shell
pkill -x waybar || true
noctalia -d
noctalia config validate
```

若你的 `$XDG_STATE_HOME` 非默认位置，上面的 state 路径应相应调整。保留 `$backup` 路径用于回退。不想迁移整个 GUI 覆盖时，可以备份后手动只清理其中的 `[wallpaper.*]` 和 `[lockscreen_widgets.*]` 条目。

建议随后注销重登一次，确认 Niri 启动时只启动 Noctalia 和原有 fcitx5。不要立即挂起：先用 `Super+Alt+L` 手动测试**两个显示器都被锁住且密码能正常解锁**，再保留自动锁屏。配置校验不能代替实际 PAM/锁屏测试。

回退：停止 Noctalia，将备份的 niri/noctalia 配置和 `settings.toml` 还原；如果新 shell 已创建 settings.toml，先将它另外备份。记得也撤销 chezmoi 源文件，否则下次 apply 会重新部署新主题。

## 快捷键

`Mod` 在本机 Niri 会话中为 `Super`。

| 快捷键 | 动作 |
|---|---|
| `Super+T` | 通过 mise shim 打开 Alacritty |
| `Super+D` | Noctalia 应用启动器 |
| `Super+Shift+D` | 壁纸选择面板，可选 ALL 或单个输出 |
| `Super+Shift+S` | 控制中心 |
| `Super+Shift+C` | 剪贴板历史 |
| `Super+Alt+L` | 安全锁屏 |
| `Super+Ctrl+P` | Caffeine 开关：临时禁止自动锁屏/熄屏，用于演示或长时间阅读；完成后关闭 |
| `Super+Shift+←/→` | 切换左/右显示器 |
| `Super+Ctrl+Shift+←/→` | 将当前列移到左/右显示器 |
| `Super+F` | 当前列最大化，特别适合竖屏 |
| `Super+Shift+P` | 原有 Niri 手动熄屏（不等于锁屏） |

## Alacritty 与 mise 的 PATH

本机 Alacritty 通过 mise 的 `cargo:alacritty` 安装。交互式 shell 可以找到它，但 Niri 会话的 PATH 不含 mise 工具目录；单纯在终端里运行 `which alacritty` 成功，不代表 compositor 能执行同一个裸命令。

这里采用稳定 shim，不绑定随升级变化的安装版本目录：

- Niri `Super+T` 使用 `spawn-sh "exec \"$HOME/.local/share/mise/shims/alacritty\""`。
- 桌面条目的 `Exec`、`TryExec` 和 New Terminal 动作使用 `{{ home }}/.local/share/mise/shims/alacritty`，其中 home 由 chezmoi 模板渲染。
- `.chezmoiexternal.toml.tmpl` 不再下载 upstream Alacritty.desktop，避免覆盖本地条目及额外 GitHub API 请求。
- `dotfiles/dot_config/environment.d/10-mise.conf` 仍保留，但修复不依赖当前图形会话是否加载它。

前提是 mise 已安装 Alacritty，并存在 `~/.local/share/mise/shims/alacritty`。缺失时执行 `mise install cargo:alacritty`、`mise reshim`。快捷键是 **Super+T / Super+D**，不是 Ctrl+D。

## 通知服务

Noctalia 与 mako 都会争用 `org.freedesktop.Notifications`，不能同时接管应用通知。本机已执行 `systemctl --user disable --now mako.service`，并由 chezmoi 管理 `~/.config/systemd/user/mako.service -> /dev/null`；这会阻止 mako 登录启动和 D-Bus 激活，不卸载软件包。

应用 mask 后执行 `systemctl --user daemon-reload`，再重启 Noctalia。可以用以下命令确认通知归属并发送测试：

```bash
systemctl --user is-enabled mako.service  # 预期 masked（非零退出码正常）
busctl --user status org.freedesktop.Notifications
notify-send '通知测试' '应由 Noctalia 显示'
```

若改回 mako，先从 chezmoi 源中移除 mask，再取消运行系统的 mask；同时关闭 Noctalia 的通知 daemon，并重启 shell，之后才能启用 mako。否则下次 chezmoi apply 会重新屏蔽 mako。

## 验证

```bash
niri validate -c dotfiles/dot_config/niri/config.kdl
chezmoi execute-template < dotfiles/dot_config/noctalia/desktop.toml.tmpl > /tmp/noctalia-desktop.toml
noctalia config validate /tmp/noctalia-desktop.toml

# 启用之后
niri msg outputs
noctalia msg wallpaper-get DP-1
noctalia msg wallpaper-get HDMI-A-1
noctalia config export
```

本机已应用并验证：Niri 实际输出为主屏 3840×2160 / 1.5 倍缩放，右侧副屏为 1080×1920 / transform 90；Noctalia 实际加载 Tokyo Night 和各屏独立壁纸；通知服务归属为 Noctalia，mako 状态为 masked；通过 Niri 启动命令成功创建了 Alacritty 窗口，且 shim 在精简 PATH 下可运行。没有主动触发锁屏；PAM 密码解锁及空闲后的双屏锁定仍需手动测试。

## 参考

- [Noctalia v5.2.1 壁纸配置](https://github.com/noctalia-dev/noctalia/blob/v5.2.1/docs/user/desktop/wallpaper.mdx)
- [Noctalia v5.2.1 顶栏及 per-monitor overrides](https://github.com/noctalia-dev/noctalia/blob/v5.2.1/docs/user/bar/index.mdx)
- [Noctalia 原生 Idle](https://github.com/noctalia-dev/noctalia/blob/v5.2.1/docs/user/services/idle.mdx)
- [Noctalia Lockscreen Widgets](https://github.com/noctalia-dev/noctalia/blob/v5.2.1/docs/user/lockscreen/widgets.mdx)
- [Noctalia 自定义 Palette](https://github.com/noctalia-dev/noctalia/blob/v5.2.1/docs/user/theming/palette.mdx)
- [Niri Outputs](https://niri-wm.github.io/niri/Configuration:-Outputs)
- [Omarchy Tokyo Night](https://github.com/omacom/omarchy/tree/492b8837deea69663c7a5418871f07ed075a9686/themes/tokyo-night)
