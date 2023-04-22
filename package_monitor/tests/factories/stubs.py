from collections import defaultdict
from collections.abc import MutableMapping
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

from importlib_metadata import PackagePath


class DjangoAppConfigStub:
    class ModuleStub:
        def __init__(self, file: str) -> None:
            self.__file__ = file

    def __init__(self, name: str, file: str) -> None:
        self.name = name
        self.module = self.ModuleStub(file)


@dataclass
class PypiUrl:
    url: str
    # incomplete


@dataclass
class PypiRelease:
    comment_text: str
    yanked: bool
    requires_python: str = ""
    # yanked_reason: str = None
    # incomplete


@dataclass
class PypiInfo:
    name: str
    version: str
    description: str = ""
    home_page: str = ""
    # summary: str
    # author: str
    # author_email: str
    # license: str
    # yanked: bool
    # yanked_reason: str = None
    # maintainer: str = None
    # maintainer_email: str = None
    # ...


@dataclass
class Pypi:
    info: PypiInfo
    last_serial: int
    releases: Dict[str, PypiRelease]
    urls: List[PypiUrl]
    requires_dist: List[str] = field(default=list)
    requires_python: str = ""

    def asdict(self) -> dict:
        return asdict(self)


class PackageMetadataStub(MutableMapping):
    """A PackageMetadata stub implementing the interface
    for importlib_metadata.PackageMetadata.

    This is a dict-like type, which allows multiple values per key.
    """

    def __init__(self):
        self._d = defaultdict(list)

    def __setitem__(self, key, value):
        self._d[key].append(value)

    def __getitem__(self, key):
        if key not in self._d:
            return None
        return self._d[key][0]

    def __delitem__(self, __key) -> None:
        raise NotImplementedError()

    def __len__(self) -> int:
        return len(self._d)

    def __iter__(self):
        return self.keys()

    def items(self):
        results = []
        for key, values in self._d.items():
            for value in values:
                results.append((key, value))
        return results

    def keys(self):
        return [o[0] for o in self.items()]

    def values(self):
        return [o[1] for o in self.items()]


class ImportlibDistributionStub:
    def __init__(
        self,
        name: str,
        version: str,
        files: list,
        requires: list = None,
        homepage_url: str = "",
        summary: str = "",
    ) -> None:
        self.metadata = {
            "Name": name,
            "Home-page": homepage_url if homepage_url != "" else "UNKNOWN",
            "Summary": summary if summary != "" else "UNKNOWN",
            "Version": version if version != "" else "UNKNOWN",
        }
        self.files = [PackagePath(f) for f in files]
        self.requires = requires if requires else None
        self._files_content = {}

    @property
    def name(self):
        return self.metadata["Name"]

    @property
    def version(self):
        return self.metadata["Version"]

    def read_text(self, filename: str) -> Optional[str]:
        if filename in self._files_content:
            return self._files_content[filename]
        return ""
