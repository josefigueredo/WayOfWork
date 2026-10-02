"""Read-only data sources. None of them writes outside the wow work directory."""


class SourceUnavailable(Exception):
    """A source could not be read; the message says why and never contains secrets."""
