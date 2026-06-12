import time
import copy
import asyncio

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger


@register(
    "astrbot_plugin_group_forward",
    "you",
    "将指定 QQ 群的聊天内容转发到其它 QQ 群",
    "v1.0.0",
)
class GroupForwardPlugin(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.config = config
        # 目标群 -> 上次转发时间戳，用于节流
        self._last_sent: dict[str, float] = {}

    # ---------- 工具方法 ----------

    def _build_index(self) -> dict[str, list[str]]:
        """把 rules 整理成 {源群号: [目标群号...]} 的索引。"""
        index: dict[str, list[str]] = {}
        for rule in self.config.get("rules", []):
            source = str(rule.get("source", "")).strip()
            if not source:
                continue
            targets = [str(t).strip() for t in rule.get("targets", []) if str(t).strip()]
            if targets:
                index.setdefault(source, []).extend(targets)
        return index

    def _is_admin(self, event: AstrMessageEvent) -> bool:
        admins = [str(a) for a in self.config.get("admins", [])]
        if event.is_admin():
            return True
        return str(event.get_sender_id()) in admins

    def _passes_filters(self, event: AstrMessageEvent, sender_id: str, text: str) -> bool:
        blacklist = [str(b) for b in self.config.get("blacklist", [])]
        if sender_id in blacklist:
            return False

        whitelist = [str(w) for w in self.config.get("whitelist", [])]
        if whitelist and sender_id not in whitelist:
            return False

        if not self.config.get("forward_self", False):
            if sender_id == str(event.get_self_id()):
                return False

        for kw in self.config.get("keyword_block", []):
            if kw and kw in text:
                return False

        return True

    def _throttle(self, target: str):
        interval = float(self.config.get("throttle_seconds", 0) or 0)
        if interval <= 0:
            return
        last = self._last_sent.get(target, 0.0)
        now = time.time()
        wait = interval - (now - last)
        return wait if wait > 0 else 0

    # ---------- 消息监听与转发 ----------

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def on_group_message(self, event: AstrMessageEvent):
        # 仅处理 aiocqhttp（NapCat / OneBot v11）平台
        if event.get_platform_name() != "aiocqhttp":
            return

        source_group = str(event.get_group_id())
        index = self._build_index()
        targets = index.get(source_group)
        if not targets:
            return

        sender_id = str(event.get_sender_id())
        text = event.message_str or ""
        if not self._passes_filters(event, sender_id, text):
            return

        # 取 OneBot 原始消息段数组，原样转发（保留图片/文件/语音/表情等）
        raw = getattr(event.message_obj, "raw_message", None)
        segments = None
        if isinstance(raw, dict):
            segments = raw.get("message")
        if not segments:
            # 兜底：至少转发纯文本
            segments = [{"type": "text", "data": {"text": text}}]

        client = event.bot

        # 可选增强：@ 转纯文本、合并转发展开
        if self.config.get("at_to_text", True):
            segments = self._at_to_text(segments)
        if self.config.get("expand_forward", True):
            segments = await self._expand_forward(client, segments)

        outgoing = self._with_prefix(event, source_group, sender_id, segments)

        for target in targets:
            if target == source_group:
                continue  # 防止自我回环
            wait = self._throttle(target)
            if wait:
                await asyncio.sleep(wait)
            try:
                await client.send_group_msg(group_id=int(target), message=outgoing)
                self._last_sent[target] = time.time()
            except Exception as e:
                logger.error(f"[group_forward] 转发到群 {target} 失败: {e}")

    def _with_prefix(self, event, source_group, sender_id, segments):
        """在消息段前加上来源前缀。"""
        fmt = self.config.get("prefix_format", "")
        if not fmt:
            return segments
        sender_name = event.get_sender_name() or sender_id
        prefix = fmt.format(
            group_id=source_group,
            sender_id=sender_id,
            sender_name=sender_name,
        )
        new_segments = copy.deepcopy(segments)
        new_segments.insert(0, {"type": "text", "data": {"text": prefix}})
        return new_segments

    def _at_to_text(self, segments):
        """把 at 段转换成纯文本 @昵称。"""
        result = []
        for seg in segments:
            if seg.get("type") == "at":
                data = seg.get("data", {})
                qq = str(data.get("qq", ""))
                if qq == "all":
                    name = "全体成员"
                else:
                    # NapCat 部分版本在 at 段带 name 字段，没有则退回 QQ 号
                    name = data.get("name") or qq
                result.append({"type": "text", "data": {"text": f"@{name} "}})
            else:
                result.append(seg)
        return result

    async def _expand_forward(self, client, segments):
        """把合并转发段展开成可读文本。"""
        expanded = []
        for seg in segments:
            if seg.get("type") != "forward":
                expanded.append(seg)
                continue
            res_id = seg.get("data", {}).get("id")
            if not res_id:
                expanded.append(seg)
                continue
            try:
                detail = await client.get_forward_msg(message_id=res_id)
            except Exception as e:
                logger.error(f"[group_forward] 展开合并转发失败: {e}")
                expanded.append(seg)
                continue
            nodes = detail.get("messages") or detail.get("message") or []
            lines = ["——— 合并转发 ———"]
            for node in nodes:
                sender = node.get("sender", {}) or {}
                name = sender.get("nickname") or sender.get("card") or str(
                    node.get("user_id", "")
                )
                content = self._node_to_text(node.get("message") or node.get("content"))
                lines.append(f"{name}: {content}")
            lines.append("——————————")
            expanded.append({"type": "text", "data": {"text": "\n".join(lines) + "\n"}})
        return expanded

    def _node_to_text(self, message) -> str:
        """把单条转发节点的消息内容转成纯文本摘要。"""
        if isinstance(message, str):
            return message
        if not isinstance(message, list):
            return str(message) if message else ""
        parts = []
        for seg in message:
            t = seg.get("type")
            data = seg.get("data", {})
            if t == "text":
                parts.append(data.get("text", ""))
            elif t == "image":
                parts.append("[图片]")
            elif t == "face":
                parts.append("[表情]")
            elif t == "record":
                parts.append("[语音]")
            elif t == "video":
                parts.append("[视频]")
            elif t == "file":
                parts.append("[文件]")
            elif t == "at":
                qq = str(data.get("qq", ""))
                parts.append("@全体成员" if qq == "all" else f"@{data.get('name') or qq}")
            elif t == "forward":
                parts.append("[合并转发]")
            else:
                parts.append(f"[{t}]")
        return "".join(parts)

    # ---------- 管理指令 ----------

    @filter.command_group("forward")
    def forward(self):
        pass

    @forward.command("list")
    async def forward_list(self, event: AstrMessageEvent):
        if not self._is_admin(event):
            return
        rules = self.config.get("rules", [])
        if not rules:
            yield event.plain_result("当前没有任何转发规则。")
            return
        lines = ["当前转发规则："]
        for i, r in enumerate(rules, 1):
            targets = ",".join(str(t) for t in r.get("targets", []))
            lines.append(f"{i}. {r.get('source')} -> {targets}")
        wl = ",".join(str(w) for w in self.config.get("whitelist", [])) or "无"
        bl = ",".join(str(b) for b in self.config.get("blacklist", [])) or "无"
        lines.append(f"白名单：{wl}")
        lines.append(f"黑名单：{bl}")
        yield event.plain_result("\n".join(lines))

    @forward.command("add")
    async def forward_add(self, event: AstrMessageEvent, source: str, target: str):
        if not self._is_admin(event):
            return
        source, target = str(source), str(target)
        rules = self.config.get("rules", [])
        for r in rules:
            if str(r.get("source")) == source:
                targets = [str(t) for t in r.get("targets", [])]
                if target not in targets:
                    targets.append(target)
                    r["targets"] = targets
                self.config["rules"] = rules
                self.config.save_config()
                yield event.plain_result(f"已添加：{source} -> {target}")
                return
        rules.append({"source": source, "targets": [target]})
        self.config["rules"] = rules
        self.config.save_config()
        yield event.plain_result(f"已新建规则：{source} -> {target}")

    @forward.command("del")
    async def forward_del(self, event: AstrMessageEvent, source: str, target: str):
        if not self._is_admin(event):
            return
        source, target = str(source), str(target)
        rules = self.config.get("rules", [])
        changed = False
        for r in rules:
            if str(r.get("source")) == source:
                targets = [str(t) for t in r.get("targets", []) if str(t) != target]
                if targets != r.get("targets"):
                    r["targets"] = targets
                    changed = True
        # 清掉没有目标的空规则
        rules = [r for r in rules if r.get("targets")]
        self.config["rules"] = rules
        self.config.save_config()
        msg = "已删除。" if changed else "未找到匹配规则。"
        yield event.plain_result(msg)

    @forward.command("wl")
    async def forward_wl(self, event: AstrMessageEvent, action: str, qq: str):
        if not self._is_admin(event):
            return
        yield event.plain_result(self._edit_list("whitelist", "白名单", action, str(qq)))

    @forward.command("bl")
    async def forward_bl(self, event: AstrMessageEvent, action: str, qq: str):
        if not self._is_admin(event):
            return
        yield event.plain_result(self._edit_list("blacklist", "黑名单", action, str(qq)))

    def _edit_list(self, key: str, label: str, action: str, qq: str) -> str:
        items = [str(x) for x in self.config.get(key, [])]
        if action == "add":
            if qq not in items:
                items.append(qq)
            result = f"已加入{label}：{qq}"
        elif action == "del":
            items = [x for x in items if x != qq]
            result = f"已移出{label}：{qq}"
        else:
            return "用法：add <QQ> 或 del <QQ>"
        self.config[key] = items
        self.config.save_config()
        return result
