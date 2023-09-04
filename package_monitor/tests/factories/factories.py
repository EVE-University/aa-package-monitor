from typing import Generic, TypeVar

import factory
import factory.fuzzy
from packaging.requirements import Requirement

from package_monitor.core.distribution_packages import DistributionPackage
from package_monitor.models import Distribution

from .stubs import MetadataDistributionStub, Pypi, PypiInfo, PypiRelease, PypiUrl

T = TypeVar("T")

faker = factory.faker.faker.Faker()


class BaseMetaFactory(Generic[T], factory.base.FactoryMetaClass):
    def __call__(cls, *args, **kwargs) -> T:
        return super().__call__(*args, **kwargs)


class PypiReleaseFactory(factory.Factory):
    class Meta:
        model = PypiRelease

    comment_text = factory.faker.Faker("sentence")
    yanked = False


class PypiUrlFactory(factory.Factory):
    class Meta:
        model = PypiUrl

    url = factory.faker.Faker("url")


class PypiInfoFactory(factory.Factory):
    class Meta:
        model = PypiInfo
        exclude = ("requirements",)

    project_url = factory.LazyAttribute(lambda o: f"https://pypi.org/project/{o.name}/")
    requires_dist = factory.LazyAttribute(
        lambda o: [str(obj) for obj in o.requirements]
    )
    requires_python = "~=3.7"


class PypiFactory(factory.Factory, metaclass=BaseMetaFactory[Pypi]):
    """A data object on PyPI. Create from DistributionPackage"""

    class Meta:
        model = Pypi
        exclude = ("distribution",)

    info = factory.LazyAttribute(
        lambda o: PypiInfoFactory(
            name=o.distribution.name,
            version=o.distribution.current,
            description=o.distribution.summary,
            home_page=o.distribution.homepage_url,
            requirements=o.distribution.requirements,
        )
    )
    last_serial = factory.fuzzy.FuzzyInteger(1_000_000, 10_000_000)
    releases = factory.LazyAttribute(
        lambda o: {o.distribution.current: [PypiReleaseFactory()]}
    )
    urls = factory.LazyAttribute(lambda o: [PypiUrlFactory()])


class MetadataDistributionStubFactory(
    factory.Factory, metaclass=BaseMetaFactory[MetadataDistributionStub]
):
    class Meta:
        model = MetadataDistributionStub

    name = factory.Faker("last_name")
    # files = ["dummy_1/file_1.py", "dummy_1/__init__.py"]
    homepage_url = factory.Faker("url")
    summary = factory.Faker("sentence")

    @factory.lazy_attribute
    def version(self):
        int_fuzzer = factory.fuzzy.FuzzyInteger(0, 20)
        major = int_fuzzer.fuzz()
        minor = int_fuzzer.fuzz()
        patch = int_fuzzer.fuzz()
        return f"{major}.{minor}.{patch}"

    @factory.lazy_attribute
    def files(self):
        path = faker.words(1)[0]
        files = faker.words(3)
        return [f"{path}/{file}.py" for file in files]

    @classmethod
    def _adjust_kwargs(cls, **kwargs):
        requires = kwargs.get("requires")
        if requires and (
            isinstance(requires, str) or not hasattr(requires, "__iter__")
        ):
            raise RuntimeError(f"requires need to be an iterable: {requires}")
        return kwargs


class DistributionPackageFactory(
    factory.Factory, metaclass=BaseMetaFactory[DistributionPackage]
):
    class Meta:
        model = DistributionPackage
        exclude = ("requires",)

    requires = ""  # excluded

    name = factory.Faker("last_name")
    is_editable = False
    # latest = factory.LazyAttribute(lambda o: o.current)
    homepage_url = factory.Faker("url")
    summary = factory.Faker("sentence")

    @factory.lazy_attribute
    def current(self):
        int_fuzzer = factory.fuzzy.FuzzyInteger(0, 20)
        major = int_fuzzer.fuzz()
        minor = int_fuzzer.fuzz()
        patch = int_fuzzer.fuzz()
        return f"{major}.{minor}.{patch}"

    @factory.lazy_attribute
    def requirements(self):
        if self.requires:
            return [Requirement(obj) for obj in self.requires]
        return []


class DistributionFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[Distribution]
):
    class Meta:
        model = Distribution
        django_get_or_create = ("name",)

    name = factory.Faker("last_name")
    description = factory.Faker("paragraph")
    latest_version = factory.LazyAttribute(lambda o: o.installed_version)
    is_outdated = False
    website_url = factory.Faker("uri")

    @factory.lazy_attribute
    def installed_version(self):
        int_fuzzer = factory.fuzzy.FuzzyInteger(0, 20)
        major = int_fuzzer.fuzz()
        minor = int_fuzzer.fuzz()
        patch = int_fuzzer.fuzz()
        return f"{major}.{minor}.{patch}"


def make_packages(*packages: DistributionPackage):
    return {obj.name_normalized: obj for obj in packages}
