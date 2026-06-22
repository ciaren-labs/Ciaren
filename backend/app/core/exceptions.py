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


class UnsupportedFileTypeError(Exception):
    ALLOWED = (".csv", ".xlsx", ".xls", ".parquet")

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
