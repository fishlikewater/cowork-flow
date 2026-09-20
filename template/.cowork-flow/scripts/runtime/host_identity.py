#!/usr/bin/env python3
"""Single declaration of every host's session identity.

One record per host replaces the hand-maintained mirror tables that used to
live in runtime/session_state.py, adapters/host/inject.py,
adapters/host/workflow_state_hook.py and adapters/cli/subagent.py. Adding a
host is one row here; nothing else enumerates hosts by name.

Key ownership is derived, not declared: a hook-payload key belongs to a host
only while that host is its sole declarer. As soon as a second host lists the
same key the key becomes ambiguous, so a generic key such as `session_id`
can never be claimed by whichever table row happened to come first.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class HostIdentity:
    """One host's identity facts.

    id: host-assets.json platform id.
    prefix: context-key prefix. `claude` differs from the platform id on
        purpose and is preserved as-is.
    adapter: label reported by the injection layer (inject.py --host / the
        runtime-context record's adapter field).
    policy_module: workflow-state policy module; None means default_policy.
    injects_context: whether the host routes through inject.py. opencode
        renders context from its own JS plugin, so it is not an --host choice.
    session_env: environment variables carrying a per-session id, in priority
        order, as seen by the host's Bash/CLI processes.
    input_keys: every hook-payload key this host may emit, ambiguous ones
        included. Truthful listing is what makes ownership derivation work.
    process_label_env: optional shared process-level label.
    """

    id: str
    prefix: str
    adapter: str
    policy_module: str | None
    injects_context: bool
    session_env: tuple[str, ...]
    input_keys: tuple[str, ...]
    process_label_env: str | None


# Declared-host channel name: the payload key inject.py stamps and the
# environment variable a caller may set to name the host explicitly.
HOST_HINT_ENV = "COWORK_FLOW_HOST"


# Order is the resolution priority for the env-variable scan and for the
# sole-owner input scan; it mirrors the table order this module replaced.
HOST_IDENTITIES: tuple[HostIdentity, ...] = (
    HostIdentity(
        id="zcode",
        prefix="zcode",
        adapter="zcode.plugin",
        policy_module="adapters.host.zcode_policy",
        injects_context=True,
        session_env=("ZCODE_SESSION_ID",),
        input_keys=("ZCODE_SESSION_ID", "zcode_session_id", "sessionId", "session_id"),
        process_label_env="ZCODE_PROCESS_LABEL",
    ),
    HostIdentity(
        id="opencode",
        prefix="opencode",
        adapter="opencode.task",
        policy_module=None,
        injects_context=False,
        session_env=("OPENCODE_SESSION_ID",),
        input_keys=(
            "OPENCODE_SESSION_ID",
            "opencode_session_id",
            "sessionID",
            "sessionId",
        ),
        process_label_env=None,
    ),
    HostIdentity(
        id="claude-code",
        prefix="claude",
        adapter="claude-code.hooks",
        policy_module="adapters.host.claude_code_policy",
        injects_context=True,
        session_env=("CLAUDE_SESSION_ID", "CLAUDE_CODE_SESSION_ID"),
        input_keys=(
            "CLAUDE_SESSION_ID",
            "claude_session_id",
            "CLAUDE_CODE_SESSION_ID",
            "claude_code_session_id",
        ),
        process_label_env=None,
    ),
    HostIdentity(
        id="codex",
        prefix="codex",
        adapter="codex.spawn_agent",
        policy_module="adapters.host.codex_policy",
        injects_context=True,
        session_env=("CODEX_SESSION_ID", "CODEX_THREAD_ID"),
        input_keys=(
            "CODEX_SESSION_ID",
            "codex_session_id",
            "session_id",
            "CODEX_THREAD_ID",
            "codex_thread_id",
            "thread_id",
            "conversation_id",
        ),
        process_label_env=None,
    ),
    # dsh resolves identity from DSH_SESSION_ID alone; its preset plugin passes
    # only {"cwd": ...} as hook input, so it declares no payload keys.
    HostIdentity(
        id="dsh",
        prefix="dsh",
        adapter="dsh.preset",
        policy_module=None,
        injects_context=True,
        session_env=("DSH_SESSION_ID",),
        input_keys=(),
        process_label_env=None,
    ),
)


_BY_ID = {identity.id: identity for identity in HOST_IDENTITIES}
_BY_PREFIX = {identity.prefix: identity for identity in HOST_IDENTITIES}


def _build_sole_owners() -> dict[str, str]:
    declarers: dict[str, list[str]] = {}
    for identity in HOST_IDENTITIES:
        for key in identity.input_keys:
            owners = declarers.setdefault(key, [])
            if identity.id not in owners:
                owners.append(identity.id)
    return {
        key: owners[0]
        for key, owners in declarers.items()
        if len(owners) == 1
    }


_SOLE_OWNERS = _build_sole_owners()


def identity_for(host_id: str | None) -> HostIdentity | None:
    if not host_id:
        return None
    return _BY_ID.get(host_id)


def identity_for_prefix(prefix: str) -> HostIdentity | None:
    return _BY_PREFIX.get(prefix)


def host_ids() -> tuple[str, ...]:
    return tuple(identity.id for identity in HOST_IDENTITIES)


def context_adapters() -> dict[str, str]:
    """Hosts that route through inject.py, mapped to their adapter label."""
    return {
        identity.id: identity.adapter
        for identity in HOST_IDENTITIES
        if identity.injects_context
    }


def policy_modules() -> dict[str, str]:
    return {
        identity.id: identity.policy_module
        for identity in HOST_IDENTITIES
        if identity.policy_module is not None
    }


def session_env_providers() -> tuple[tuple[str, str], ...]:
    """(context-key prefix, env var name) in resolution priority order."""
    return tuple(
        (identity.prefix, name)
        for identity in HOST_IDENTITIES
        for name in identity.session_env
    )


def process_label_providers() -> tuple[tuple[str, str], ...]:
    return tuple(
        (identity.prefix, identity.process_label_env)
        for identity in HOST_IDENTITIES
        if identity.process_label_env is not None
    )


def declared_host(env: Mapping[str, str]) -> str | None:
    """The host a caller explicitly declared, if any.

    This is the declared-host channel: inject.py stamps it into the payload
    from its required --host argument, and the Bash/CLI side may set it in the
    environment so an ambiguous payload key is read for the right host.
    """
    value = env.get(HOST_HINT_ENV)
    return value.strip() if value and value.strip() else None


def detect_host(env: Mapping[str, str]) -> str | None:
    """The host whose per-session env var is present, or None.

    None is the honest answer when the process carries no host evidence;
    callers must degrade rather than default to some other host.
    """
    for identity in HOST_IDENTITIES:
        for name in identity.session_env:
            if env.get(name):
                return identity.id
    return None


def sole_owner_of(key: str) -> str | None:
    """The only host declaring this payload key, or None when ambiguous."""
    return _SOLE_OWNERS.get(key)


def sole_owned_input_keys(host_id: str) -> tuple[str, ...]:
    return tuple(
        key
        for key in (_BY_ID[host_id].input_keys if host_id in _BY_ID else ())
        if _SOLE_OWNERS.get(key) == host_id
    )


def ambiguous_input_keys() -> tuple[str, ...]:
    """Payload keys declared by more than one host, in declaration order."""
    seen: list[str] = []
    for identity in HOST_IDENTITIES:
        for key in identity.input_keys:
            if key not in _SOLE_OWNERS and key not in seen:
                seen.append(key)
    return tuple(seen)
