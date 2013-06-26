class SourceNotAvailable(RuntimeError):
    """The requested data source is unavailable."""


class Ec2MetadataNotAvailable(SourceNotAvailable):
    """The EC2 metadata service is not available."""


class CfnMetadataNotAvailable(SourceNotAvailable):
    """The cfn metadata service is not available."""
