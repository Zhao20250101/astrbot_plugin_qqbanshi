# astrbot_plugin_qqbanshi

将指定 QQ 群的聊天内容转发到其它 QQ 群的 AstrBot 插件。

## 功能

- 一个源群可转发到多个目标群，**每个源群完全独立配置**
- **按内容类型分组开关**，每个群可单独选择转发哪些内容：
  - 文字类（`send_text`）：文字、文件、@、语音
  - 图片类（`send_image`）：图片、表情、视频
  - 聊天记录（`send_forward`）：合并转发消息
  - 未开启的内容类型会被丢弃，不转发；过滤后无内容则整条不转发
- **每个群可选输出形式**：`original` 按原样转发 / `merged` 合并成聊天记录卡片转发
- 群白名单（即 `rules`，只有列入的源群才监听）+ 群黑名单（优先级最高）
- 用户白名单 / 黑名单（按发送者 QQ 过滤）
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

- `rules`：转发规则（即群白名单）。每条含：
  - `source`：源群号
  - `targets`：目标群号列表
  - `send_text` / `send_image` / `send_forward`：三类内容开关（默认都开）
  - `output_mode`：`original` 原样 / `merged` 聊天记录卡片（默认 `original`）
- `group_blacklist`：群黑名单，列入的源群不转发，优先级最高
- `whitelist` / `blacklist`：用户白/黑名单 QQ 号
- `forward_self`：是否转发机器人自己的消息（默认关）
- `prefix_format`：转发前缀模板，变量 `{group_id}` `{sender_id}` `{sender_name}`（`merged` 形式下不加前缀）
- `at_to_text`：把 @某人 转成纯文本昵称（默认开）
- `expand_forward`：展开合并转发为可读文本（默认开，仅该群开启 `send_forward` 时生效）
- `keyword_block`：命中即不转发的关键词
- `throttle_seconds`：同一目标群两次转发的最小间隔
- `admins`：可用管理指令的 QQ 号

## 管理指令

（仅管理员可用）

| 指令 | 说明 |
|---|---|
| `/forward list` | 查看所有规则和名单 |
| `/forward add <源群> <目标群>` | 新增转发（默认转全部内容、原样形式） |
| `/forward del <源群> <目标群>` | 删除转发 |
| `/forward content <源群> <text\|image\|forward> <on\|off>` | 开关某群的内容类型 |
| `/forward mode <源群> <original\|merged>` | 设置某群的输出形式 |
| `/forward gbl add\|del <群号>` | 群黑名单增删 |
| `/forward wl add\|del <QQ>` | 用户白名单增删 |
| `/forward bl add\|del <QQ>` | 用户黑名单增删 |

示例：只让群 `123456` 转发聊天记录、关闭文字和图片，并以卡片形式输出：

```
/forward add 123456 999888
/forward content 123456 text off
/forward content 123456 image off
/forward mode 123456 merged
```

## 注意

- `at_to_text` 开启时，@ 成员会转成纯文本 `@昵称`（昵称取决于 NapCat 是否在 at 段附带 name 字段，否则显示 QQ 号）；关闭则按原始 at 段透传。
- `expand_forward` 开启时，合并转发会调用 NapCat 的 `get_forward_msg` 展开成可读文本；关闭则按原段透传。深层嵌套的合并转发只标记为 `[合并转发]`，不再递归展开。
- `output_mode=merged`（卡片形式）依赖 NapCat 的 `send_group_forward_msg`；若该群同时保留了未展开的合并转发段，部分 NapCat 版本不支持卡片内再嵌套合并转发，建议配合 `expand_forward` 一起开启。
- 内容分组说明：`text` 含文字/文件/@/语音，`image` 含图片/表情/视频，`forward` 为合并转发；其它未知类型（如回复、json 卡片）归入文字类，跟随 `send_text` 开关。
- 转发他人聊天记录涉及隐私，请确保使用场景合规，并在群内告知。
