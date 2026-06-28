class YCloudError(RuntimeError):
    """Base exception for YCloud-related errors."""
    pass


class YCloudConfigurationError(YCloudError):
    """Missing or invalid configuration."""
    pass


class YCloudApiError(YCloudError):
    """Error returned by the YCloud API."""
    pass


class YCloudWebhookError(YCloudError):
    """Error validating or parsing webhook payloads."""
    pass
