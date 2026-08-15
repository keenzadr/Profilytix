"""Errors raised while writing a report.

This lives apart from `__init__.py` so writers can import the exception without
importing the registry that imports them.
"""

from __future__ import annotations


class ReportExportError(Exception):
    """A report could not be written, with a reason worth showing the user."""
