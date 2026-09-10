"""Local, explicit question/answer channel. Only a UI click writes an answer.

Requests contain text and choices, never executable callbacks. Each request has
an immutable identity and expires without selecting a default.
"""
import hashlib
import json
import math
import os
import re
import time
import uuid
from pathlib import Path

from pet_runtime import InstanceLock, runtime_root


def _text(value, limit, required=True):
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        raise ValueError("确认内容为空或过长")
    return value.strip()


def validate_request(data):
    if not isinstance(data, dict):
        raise ValueError("确认内容必须是 JSON 对象")
    options = data.get("options")
    if not isinstance(options, list) or not 2 <= len(options) <= 8:
        raise ValueError("请提供 2 至 8 个选项")
    clean = []
    for option in options:
        if not isinstance(option, dict):
            raise ValueError("选项格式错误")
        clean.append({"id": _text(option.get("id"), 80),
                      "label": _text(option.get("label"), 160),
                      "description": _text(option.get("description", ""), 2000, False)})
    ids = [o["id"] for o in clean]
    if len(set(ids)) != len(ids) or "__custom__" in ids:
        raise ValueError("选项 ID 必须唯一，不能使用 __custom__")
    recommended = data.get("recommended")
    if recommended is not None and recommended not in ids:
        raise ValueError("推荐选项必须引用已有的选项 ID")
    if not isinstance(data.get("allow_custom", False), bool):
        raise ValueError("allow_custom 必须是布尔值")
    return {"title": _text(data.get("title", "请你确认"), 120),
            "question": _text(data.get("question"), 4000),
            "options": clean, "recommended": recommended,
            "allow_custom": data.get("allow_custom", False)}


def fingerprint(request):
    return hashlib.sha256(json.dumps(request, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


class ConfirmationStore:
    def __init__(self, root=None):
        self.root = Path(root or runtime_root()) / "confirmations"

    def _path(self, request_id):
        if not isinstance(request_id, str) or not re.fullmatch(r"[0-9a-f]{32}", request_id):
            raise ValueError("无效的确认 ID")
        return self.root / (request_id + ".json")

    def _write(self, request_id, data):
        path = self._path(request_id)
        self.root.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix("." + uuid.uuid4().hex + ".tmp")
        try:
            temp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)

    def create(self, request, ttl=600):
        request = validate_request(request)
        ttl = float(ttl)
        if not math.isfinite(ttl) or not 30 <= ttl <= 3600:
            raise ValueError("有效期应为 30 至 3600 秒")
        rid = uuid.uuid4().hex
        now = time.time()
        self._write(rid, {"id": rid, "version": 1, "status": "pending",
                          "created_at": now, "expires_at": now + ttl,
                          "request": request, "fingerprint": fingerprint(request)})
        return self.read(rid)

    def read(self, request_id):
        path = self._path(request_id)
        if path.stat().st_size > 48000:
            raise ValueError("确认文件过大")
        data = json.loads(path.read_text(encoding="utf-8"))
        if (not isinstance(data, dict) or data.get("id") != request_id or data.get("version") != 1
                or data.get("status") not in ("pending", "answered", "cancelled")):
            raise ValueError("确认文件格式错误")
        request = validate_request(data.get("request"))
        if request != data["request"] or fingerprint(request) != data.get("fingerprint"):
            raise ValueError("确认内容已变更")
        created, expires = data.get("created_at"), data.get("expires_at")
        if (not isinstance(created, (int, float)) or not isinstance(expires, (int, float))
                or not math.isfinite(created) or not math.isfinite(expires)
                or not 0 < expires - created <= 3600):
            raise ValueError("确认时间错误")
        if data["status"] == "answered":
            answer = data.get("answer", {})
            self._validate_choice(request, answer.get("option_id"), answer.get("text", ""))
            if answer.get("source") not in ("recommended", "manual"):
                raise ValueError("确认来源错误")
            if answer["source"] == "recommended" and answer["option_id"] != request["recommended"]:
                raise ValueError("推荐选项不匹配")
        elif data["status"] == "pending" and expires <= time.time():
            data["status"] = "expired"
        return data

    def pending(self):
        result = []
        for path in self.root.glob("*.json"):
            try:
                data = self.read(path.stem)
                if data["status"] == "pending":
                    result.append(data)
            except (OSError, ValueError, TypeError):
                continue
        return sorted(result, key=lambda d: (d["created_at"], d["id"]))

    @staticmethod
    def _validate_choice(request, option_id, text):
        if option_id == "__custom__" and request["allow_custom"]:
            return _text(text, 4000)
        option = next((o for o in request["options"] if o["id"] == option_id), None)
        if not option or text:
            raise ValueError("请选择当前问题的有效选项")
        return option["label"]

    def answer(self, request_id, expected_fingerprint, option_id, source, text=""):
        # Same-request writes are serialized across windows/processes. Re-read
        # after locking so double clicks, cancellation and expiry cannot race.
        lock = InstanceLock(self.root)
        lock.path = self._path(request_id).with_suffix(".lock")
        if not lock.acquire():
            raise ValueError("正在提交，请稍后查看结果")
        try:
            data = self.read(request_id)
            if data["status"] != "pending" or data["fingerprint"] != expected_fingerprint:
                raise ValueError("该确认已结束或内容已变化，请查看最新问题")
            label = self._validate_choice(data["request"], option_id, text)
            if source not in ("recommended", "manual"):
                raise ValueError("确认来源错误")
            if source == "recommended" and option_id != data["request"]["recommended"]:
                raise ValueError("没有明确的推荐选项，请自行选择")
            data.update(status="answered", answered_at=time.time(),
                        answer={"option_id": option_id, "label": label,
                                "text": text, "source": source})
            self._write(request_id, data)
            return data
        finally:
            lock.release()

    def cancel(self, request_id):
        lock = InstanceLock(self.root)
        lock.path = self._path(request_id).with_suffix(".lock")
        if not lock.acquire():
            raise ValueError("正在提交，请稍后查看结果")
        try:
            data = self.read(request_id)
            if data["status"] == "pending":
                data["status"] = "cancelled"
                self._write(request_id, data)
            return data
        finally:
            lock.release()
