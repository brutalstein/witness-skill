class WitnessError(Exception):
    """Base exception for expected Witness failures."""


class ConfigurationError(WitnessError):
    """The invocation or environment is not configured correctly."""


class DetectionError(WitnessError):
    """The target could not be inspected or profiled."""


class AdapterError(WitnessError):
    """An adapter could not operate the target infrastructure."""


class ReasoningError(WitnessError):
    """The configured LLM provider failed or returned unusable output."""
