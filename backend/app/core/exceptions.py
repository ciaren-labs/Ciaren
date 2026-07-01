# SPDX-License-Identifier: AGPL-3.0-only
class NotFoundError(Exception):
    def __init__(self, resource: str, resource_id: str) -> None:
        self.resource = resource
        self.resource_id = resource_id
        super().__init__(f"{resource} '{resource_id}' not found")


class ValidationError(Exception):
    """Raised when a request payload is structurally valid but semantically wrong
    (e.g. an unknown transformation type or an invalid node config)."""

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class ConflictError(Exception):
    """Raised when a request would violate a uniqueness constraint
    (e.g. uploading a dataset whose name is already taken)."""

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class MLNotEnabledError(Exception):
    """Raised when an ML feature is requested but the ML extension is unavailable —
    either ``ML_ENABLED`` is off or the ``[ml]`` extra isn't installed. Maps to
    501 Not Implemented so callers can tell it apart from a bad request."""

    def __init__(self, detail: str = "ML support is not enabled on this server.") -> None:
        self.detail = detail
        super().__init__(detail)


class UnsupportedFileTypeError(Exception):
    # Kept in sync with dataset_service._ALLOWED_EXTENSIONS (the upload gate).
    ALLOWED = (".csv", ".tsv", ".xlsx", ".xls", ".parquet", ".json", ".jsonl", ".txt")

    def __init__(self, filename: str) -> None:
        self.filename = filename
        allowed = ", ".join(self.ALLOWED)
        super().__init__(f"'{filename}' has an unsupported file type. Allowed: {allowed}")


class FileTooLargeError(Exception):
    def __init__(self, max_mb: int) -> None:
        self.max_mb = max_mb
        super().__init__(f"File exceeds the {max_mb} MB limit")


class DatasetParseError(Exception):
    def __init__(self, filename: str, detail: str) -> None:
        self.filename = filename
        super().__init__(f"Could not parse '{filename}': {detail}")
