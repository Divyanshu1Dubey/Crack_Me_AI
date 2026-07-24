"""Custom exceptions for the ingestion app.

These are intentionally distinct from any existing `importer` or
`mce` exceptions — keeping the namespace isolated prevents the new
ingestion app from coupling to UPSC CMS error types.
"""
from __future__ import annotations


class IngestionError(Exception):
    """Base class for all production-ingestion failures."""


class MaterialNotFoundError(IngestionError):
    """The requested MaterialAsset (by sha16 or sha256) does not exist."""


class JobNotFoundError(IngestionError):
    """The requested ImportJob does not exist or is not visible."""


class BatchNotFoundError(IngestionError):
    """The requested BatchRun does not exist."""


class InvalidJobTransitionError(IngestionError):
    """An ImportJob was asked to transition into an invalid state.

    Example: a queued job cannot jump straight to completed; a
    processing job cannot be retried without first cancelling or
    completing.
    """


class CheckpointMismatchError(IngestionError):
    """A checkpoint token did not match; the caller should refresh and retry."""


class MceStageError(IngestionError):
    """An MCE stage raised an unrecoverable error.

    Wrapped by the orchestrator into an ImportJobStage row with
    status='failed'. The orchestrator re-raises so the django-q2
    task marks the job as failed.
    """


class ConservativeGateError(IngestionError):
    """The conservative import gate rejected an operation.

    Triggered by an explicit operator override (manual approval for
    an EF bucket, or attempting to publish an NR row before admin
    approval).
    """
