from typing import Iterable

from .schemas import Workspace

_workspaces = [
    Workspace(id="default", name="Default Workspace", description="Sample workspace"),
]


def list_workspaces() -> Iterable[Workspace]:
    return list(_workspaces)
