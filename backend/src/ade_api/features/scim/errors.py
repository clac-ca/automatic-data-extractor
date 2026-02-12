from __future__ import annotations


class ScimApiError(RuntimeError):
    """Error mapped to SCIM error envelope responses."""

    def __init__(self, *, status_code: int, detail: str, scim_type: str | None = None) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.scim_type = scim_type


__all__ = ["ScimApiError"]
