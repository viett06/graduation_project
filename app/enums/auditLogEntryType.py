from enum import Enum


class AuditLogEntryType(str, Enum):
    BANK = "BANK"
    INTEREST_RATE = "INTEREST_RATE"