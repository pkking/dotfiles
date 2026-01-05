# Chezmoi 目录结构设计

为了将现有的 dotfiles 仓库转换为由 [chezmoi](https://www.chezmoi.io/) 管理的结构，我们将遵循以下设计。

## 1. 核心原则
- **Source State**: 所有的配置文件将存放在 `dot_` 开头的目录或文件中（chezmoi 的标准做法）。
- **模板化**: 对于不同环境可能变化的部分（如 email, name），使用 `.tmpl` 文件。
- **模块化**: 按应用（i3, nvim, tmux 等）组织配置。

## 2. 目标目录结构预览

迁移后的仓库结构预计如下：

```text
.
├── .chezmoi.yaml.tmpl      # chezmoi 配置文件模板
├── .chezmoiroot            # (可选) 如果我们想把源码放在子目录
├── README.md               # 项目说明
├── docs/                   # 文档目录
│   └── structure.md        # 本设计文档
├── dot_gitconfig.tmpl      # Git 配置模板
├── dot_tmux.conf           # Tmux 配置
├── dot_config/             # 对应 ~/.config/
│   ├── i3/                 # i3 配置
│   │   ├── config
│   │   └── i3blocks.conf
│   └── nvim/               # Neovim 配置
│       └── init.vim
└── helpers/                # 现有的辅助脚本
```

## 3. 配置文件设计 (`.chezmoi.yaml.tmpl`)

我们将提供一个交互式的配置，允许用户在初始化时输入个人信息。

```yaml
data:
    email: "your_email@example.com"
    name: "Your Name"
```

## 4. 迁移路径
1. **初始化**: 创建 `.chezmoi.yaml.tmpl`。
2. **转换**: 将现有的 `dotfiles/` 下的文件移动到根目录，并重命名（例如 `dotfiles/gitconfig` -> `dot_gitconfig`）。
3. **整理**: 将 `i3/` 和 `nvim/` 移动到 `dot_config/` 下对应的位置。
4. **验证**: 使用 `chezmoi source-path` 和 `chezmoi apply --dry-run` 验证。
