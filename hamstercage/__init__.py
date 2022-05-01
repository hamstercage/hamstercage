import yaml

from hamstercage.manifest import Manifest, FileMode

__all__ = ["Manifest"]


def representer(dumper, data):
    return yaml.ScalarNode("tag:yaml.org,2002:int", oct(data))


yaml.add_representer(FileMode, representer)
