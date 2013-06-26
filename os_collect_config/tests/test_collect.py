import fixtures
import testtools
from testtools import matchers
import urlparse
import uuid

from os_apply_config import collect


META_DATA = {'local-ipv4':     '192.0.2.1',
             'reservation-id': uuid.uuid1(),
             'local-hostname': 'foo',
             'ami-launch-index': '0',
             'public-hostname': 'foo',
             'hostname': 'foo',
             'ami-id': uuid.uuid1(),
             'instance-action': 'none',
             'public-ipv4': '192.0.2.1',
             'instance-type': 'flavor.small',
             'instance-id': uuid.uuid1()}


class FakeResponse(dict):
    status = 200


class FakeHttp(object):

    def request(self, url):
        url = urlparse.urlparse(url)

        if url.path == '/latest/meta-data/':
            return (FakeResponse(), "\n".join(META_DATA.keys()))

        path = url.path
        path = path.replace('/latest/meta-data/', '')
        return (FakeResponse(), META_DATA[path])


class TestCollect(testtools.TestCase):
    def test_collect_ec2(self):
        self.useFixture(fixtures.MonkeyPatch('httplib2.Http', FakeHttp))
        ec2 = collect.collect_ec2()
        self.assertThat(ec2, matchers.IsInstance(dict))
        for md_key, md_value in iter(META_DATA.items()):
            self.assertIn(md_key, ec2)
            self.assertEquals(ec2[md_key], META_DATA[md_key])
