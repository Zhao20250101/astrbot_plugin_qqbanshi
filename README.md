# astrbot_plugin_qqbanshi

将指定 QQ 群的聊天内容转发到其它 QQ 群的 AstrBot 插件。

## 功能

- 全内容转发：文本、图片、表情、@、文件、语音等（直接复用 NapCat 上报的原始消息���）
- 一个源群可转发到多个目标群
- 白名单 / 黑名单（按发送者 QQ 过滤）
- 关键词屏蔽
- 防回环（不转发机器人自身消息、跳过源群=目标群）
- 节流，规避风控
- 配置文件 + 聊天指令双方式管理

## 前置要求

- AstrBot 通过 **aiocqhttp（OneBot v11 / NapCat）** 接入 QQ
- **机器人账号必须同时在源群和目标群中**

## 安装

把整个 `astrbot_plugin_qqbanshi` 目录放到 AstrBot 的 `data/plugins/` 下，重启或在管理面板重载插件。

## 配置

在插件配置面板填写（也可用指令动态修改）：

- `rules`：转发规则，每条含 `source`（源群号）和 `targets`（目标群号列表）
- `whitelist` / `blacklist`：白/黑名单 QQ 号
- `forward_self`：是否转发机器人自己的消息（默认关）
- `prefix_format`：转发前缀模板，变量 `{group_id}` `{sender_id}` `{sender_name}`
- `at_to_text`：把 @某人 转成纯文本昵称（默认开）
- `expand_forward`：展开合并转发为可读文本（默认开）
- `keyword_block`：命中即不转发的关键词
- `throttle_seconds`：同一目标群两次转发的最小间隔
- `admins`：可用管理指令的 QQ 号

## 管理指令

（仅管理员可用）

| 指令 | 说明 |
|---|---|
| `/forward list` | 查看所有规则和名单 |
| `/forward add <源群> <目标群>` | 新增转发 |
| `/forward del <源群> <目标群>` | 删除转发 |
| `/forward wl add\|del <QQ>` | 白名单增删 |
| `/forward bl add\|del <QQ>` | 黑名单增删 |

## 注意

- `at_to_text` 开启时，@ 成员会转成纯文本 `@昵称`（昵称取决于 NapCat 是否在 at 段附带 name 字段，否则显示 QQ 号）；关闭则按原始 at 段透传。
- `expand_forward` 开启时，合并转发会调用 NapCat 的 `get_forward_msg` 展开成可读文本；关闭则按原段透传。深层嵌套的合并转发只标记为 `[合并转发]`，不再递归展开。
- 转发他人聊天记录涉及隐私，请确保使用场景合规，并在群内告知。
