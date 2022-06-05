from dataclasses import dataclass, field
from typing import List

import importlib_metadata
from packaging.requirements import Requirement


@dataclass
class DistributionPackage:
    name: str
    current: str
    distribution: importlib_metadata.Distribution
    requirements: List[Requirement] = field(default_factory=list)
    apps: List[str] = field(default_factory=list)
    latest: str = ""
