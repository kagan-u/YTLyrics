class Cancelled(Exception):
    """Raised when the user cancels a job."""


class FetchError(Exception):
    """Raised when audio/lyrics fetching fails."""


class RenderError(Exception):
    """Raised when video rendering fails."""
