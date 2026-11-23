# IPv6 sysctl 与 Clash TUN 静默失败

Date: 2026-11-23
Status: Fixed (本机已验证,run_once 脚本负责其他机器)

## 症状

开机后 Clash Verge TUN 模式"看起来开着"但实际不生效:

- GUI `enable_tun_mode: true`、服务端运行配置里 `tun.enable: true` 都在
- 但 `ip addr` 里没有 `Mihomo` 接口,直连 Google 超时
- 核心日志( `/var/lib/clash-verge-service/users/<uid>/logs/` )反复出现:
  `Start TUN listening error: configure tun interface: permission denied`

## 根因链

1. `/etc/sysctl.d/99-disable-ipv6.conf` 写了 `net.ipv6.conf.all.disable_ipv6=1`
   (历史意图:禁用已有接口的 IPv6)。
2. **内核副作用**:写入 `all.disable_ipv6=1` 的同时会把
   `net.ipv6.conf.default.disable_ipv6` 也置 1(隔离 netns 实验证实)。
3. 之后新建的所有接口(包括 mihomo 创建的 `Mihomo` TUN)继承
   `disable_ipv6=1`。
4. mihomo 给 TUN 配置默认的 IPv6 地址 `fdfe:dcba:9876::1/126` 时,
   内核对 `RTM_NEWADDR`(AF_INET6) 返回 `-EACCES`
   (strace netlink 解码可见;此时 IPv4 地址、接口 up 都已成功)。
5. mihomo 把任何 configure 错误视为致命 → 整个 TUN 栈放弃,
   静默降级成纯端口代理。

排查要点:capabilities/seccomp/systemd 沙箱全部正常,EPERM 不在
syscall 返回值里,只在 netlink ACK 包内 — 必须 strace 后解码
`NLMSG_ERROR` 才能定位到具体是哪条 `RTM_NEWADDR` 失败。

## 修复

保留 `all=1` 原意图,**在其后**显式写 `net.ipv6.conf.default.disable_ipv6=0`
(顺序关键:all 的连带写发生在前,归零在后),让之后新建的接口(含 TUN)
保持 IPv6 可用:

```
net.ipv6.conf.all.disable_ipv6=1
net.ipv6.conf.default.disable_ipv6=0
```

运行时立即生效:`sysctl -w net.ipv6.conf.default.disable_ipv6=0`,
再触发一次 TUN(重启核心或 PATCH tun.enable)即可,无需重启系统。

由 `.chezmoiscripts/run_once_after_configure-ipv6-tun-sysctl.sh.tmpl`
负责在多机间落地:只修补已有该文件且 active `all=1` 的机器;
显式写了 `default=1` 的机器(明确要新接口也无 v6)不越权改写。

## 相邻事实(排查时容易误判)

- `default` 注释掉 ≠ 没问题:`all=1` 自己就会把 default 带成 1。
  曾经的修复只注释了 default 行 + 做了运行时 `sysctl -w`,重启即复发。
- NetworkManager 会对它管理的接口(如 wlan0)回写 `disable_ipv6=0`,
  所以物理接口可能"看起来 IPv6 是开的",与 sysctl 文件并存,加剧迷惑。
- 早前 boot 修过一次 SDDM/weston numlock(`run_once_after_configure-sddm-numlock`),
  两者症状无关,但都要重启后验证。
