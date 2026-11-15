"""
Error hierarchy for SCDRC system.
"""

class SCDRCError(Exception):
    """Base exception for all SCDRC errors."""
    pass


class BlackboardError(SCDRCError):
    """Base exception for Blackboard operations."""
    pass


class BlackboardPermissionError(BlackboardError):
    """Raised when an agent attempts to write an EntryType it does not own."""
    pass


class BlackboardValidationError(BlackboardError):
    """Raised when an entry payload fails schema validation."""
    pass


class BlackboardStateError(BlackboardError):
    """Raised when an invalid state transition or operation occurs."""
    pass


class GroundingValidationError(SCDRCError):
    """Raised when the Coordinator output is not strictly grounded in Blackboard entries."""
    pass


class AgentExecutionError(SCDRCError):
    """Raised when an agent fails during execution."""
    pass


class AgentTimeoutError(AgentExecutionError):
    """Raised when an agent times out."""
    pass


class RepositoryError(SCDRCError):
    """Raised on database / repository operation failures."""
    pass
