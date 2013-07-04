class SourceNotAvailable(RuntimeError):
    """The requested data source is unavailable."""


class Ec2MetadataNotAvailable(SourceNotAvailable):
    """The EC2 metadata service is not available."""


class CfnMetadataNotAvailable(SourceNotAvailable):
    """The cfn metadata service is not available."""


class CfnMetadataNotConfigured(SourceNotAvailable):
    """The cfn metadata service is not fully configured."""


class HeatLocalMetadataNotAvailable(SourceNotAvailable):
    """The local Heat metadata is not available."""
