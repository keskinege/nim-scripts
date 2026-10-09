from __future__ import annotations


class NimctlError(Exception):
    exit_code = 1


class UsageError(NimctlError):
    exit_code = 2


class ConfigError(NimctlError):
    exit_code = 1


class DeploymentFailed(NimctlError):
    exit_code = 1


def exit_code_for_status(status: int) -> int:
    if 300 <= status < 400:
        return 3
    if status in (401, 403):
        return 3
    if status == 404:
        return 4
    if status == 409:
        return 5
    if 500 <= status < 600:
        return 6
    return 1


class HttpError(NimctlError):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"HTTP {status}: {message}")
        self.status = status
        self.exit_code = exit_code_for_status(status)
