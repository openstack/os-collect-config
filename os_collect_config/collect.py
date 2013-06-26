import httplib2
import json


EC2_METADATA_URL = 'http://169.254.169.254/latest/meta-data'


def _fetch_metadata(sub_url):
    h = httplib2.Http()
    (resp, content) = h.request('%s%s' % (EC2_METADATA_URL, sub_url))
    if resp.status != 200:
        raise Exception('Error fetching %s' % sub_url)
    return content


def collect_ec2():
    ec2_metadata = {}
    root_list = _fetch_metadata('/')
    for item in root_list.split("\n"):
        ec2_metadata[item] = _fetch_metadata('/%s' % item)
    return ec2_metadata


def __main__():
    print json.dumps(collect_ec2())


if __name__ == '__main__':
    __main__()
