# Copyright (c) 2013 Hewlett-Packard Development Company, L.P.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.


class SourceNotAvailable(RuntimeError):
    """The requested data source is unavailable."""


class SourceNotConfigured(RuntimeError):
    """The requested data source is not configured."""


class Ec2MetadataNotAvailable(SourceNotAvailable):
    """The EC2 metadata service is not available."""


class CfnMetadataNotAvailable(SourceNotAvailable):
    """The cfn metadata service is not available."""


class HeatMetadataNotAvailable(SourceNotAvailable):
    """The heat metadata service is not available."""


class CfnMetadataNotConfigured(SourceNotConfigured):
    """The cfn metadata service is not fully configured."""


class HeatMetadataNotConfigured(SourceNotConfigured):
    """The heat metadata service is not fully configured."""


class HeatLocalMetadataNotAvailable(SourceNotAvailable):
    """The local Heat metadata is not available."""


class LocalMetadataNotAvailable(SourceNotAvailable):
    """The local metadata is not available."""


class RequestMetadataNotAvailable(SourceNotAvailable):
    """The request metadata is not available."""


class RequestMetadataNotConfigured(SourceNotAvailable):
    """The request metadata is not fully configured."""


class ZaqarMetadataNotConfigured(SourceNotConfigured):
    """The zaqar metadata service is not fully configured."""


class ZaqarMetadataNotAvailable(SourceNotAvailable):
    """The Zaqar metadata is not available."""


class InvalidArguments(ValueError):
    """Invalid arguments."""
