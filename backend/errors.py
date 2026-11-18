class ApiError(Exception):
    """Error that is rendered to the client as a JSON response."""

    def __init__(self, status, code, message, fields=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.fields = fields or {}

    def to_dict(self):
        err = {"code": self.code, "message": self.message}
        if self.fields:
            err["fields"] = self.fields
        return {"error": err}


def not_found(what="Resource"):
    return ApiError(404, "not_found", f"{what} not found")


def conflict(message):
    return ApiError(409, "conflict", message)


def validation(fields, message="Validation failed"):
    return ApiError(400, "validation_error", message, fields)
