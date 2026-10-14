class NotFound(Exception):
    """A student, session or question does not exist."""


class BadRequest(Exception):
    """The request is not valid in the current state."""


class BudgetExceeded(Exception):
    """The token budget is used up, or the kill switch is on."""
