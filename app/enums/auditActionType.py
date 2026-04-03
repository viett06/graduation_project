from enum import Enum


class AuditActionType(str, Enum):
    UPDATE = "UPDATE"
    DELETE = "DELETE"

