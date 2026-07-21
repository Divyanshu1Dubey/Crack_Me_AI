"""
Knowledge-base connector registry.

Re-exports every concrete connector so views / management commands can
do `from knowledge_base.connectors import InternalNotesConnector, ...`
without knowing the internal layout of submodules.

Previously this file was empty, which made those imports fail with
ImportError and silently broke the /api/knowledge/ingest/ endpoint
plus the `ingest_source` management command.
"""

from .base import ConnectorBase, RawChunk
from .internal import InternalNotesConnector
from .ncbi import (
    NCBIBookshelfConnector,
    OpenStaxConnector,
    OpenStaxMicrobiologyConnector,
    OpenStaxPsychologyConnector,
    GovernmentGuidelinesConnector,
    UPSCConnector,
    NHMConnector,
    MoHFWConnector,
    ICMRConnector,
    NMCConnector,
)
from .user_uploads import UserUploadsConnector

__all__ = [
    "ConnectorBase",
    "RawChunk",
    "InternalNotesConnector",
    "NCBIBookshelfConnector",
    "OpenStaxConnector",
    "OpenStaxMicrobiologyConnector",
    "OpenStaxPsychologyConnector",
    "GovernmentGuidelinesConnector",
    "UPSCConnector",
    "NHMConnector",
    "MoHFWConnector",
    "ICMRConnector",
    "NMCConnector",
    "UserUploadsConnector",
]
