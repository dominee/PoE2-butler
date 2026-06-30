"""Structured audit lines for operator mutations in the admin console."""

from __future__ import annotations

import logging

_log = logging.getLogger("admin.audit")


def audit_action(*, actor: str, action: str, detail: str = "") -> None:
    _log.info("admin_action actor=%s action=%s detail=%s", actor, action, detail)
