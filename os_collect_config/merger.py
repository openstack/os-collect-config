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


from oslo_log import log


logger = log.getLogger(__name__)


def merged_list_from_content(final_content, deployment_keys, collector_name):
    final_list = []
    for depkey in deployment_keys:
        if depkey in final_content:
            deployments = final_content[depkey]
            if not isinstance(deployments, list):
                logger.warn(
                    'Deployment-key %s was found but does not contain a '
                    'list.' % (depkey,))
                continue
            logger.debug(
                'Deployment found for %s' % (depkey,))
            for deployment in deployments:
                if 'name' not in deployment:
                    logger.warn(
                        'No name found for a deployment under %s.' %
                        (depkey,))
                    continue
                if deployment.get('group', 'Heat::Ungrouped') in (
                        'os-apply-config', 'Heat::Ungrouped'):
                    final_list.append((deployment['name'],
                                       deployment['config']))
    final_list.insert(0, (collector_name, final_content))
    return final_list