from typing import Iterable

import factory
import factory.fuzzy
from packaging.requirements import Requirement

from package_monitor.core import DistributionPackage
from package_monitor.models import Distribution

from .stubs import ImportlibDistributionStub, Pypi, PypiInfo, PypiRelease, PypiUrl

faker = factory.faker.faker.Faker()


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

    project_url = factory.LazyAttribute(lambda o: f"https://pypi.org/project/{o.name}/")


class PypiFactory(factory.Factory):
    class Meta:
        model = Pypi
        exclude = ("distribution",)

    info = factory.LazyAttribute(
        lambda o: PypiInfoFactory(
            name=o.distribution.name,
            version=o.distribution.current,
            description=o.distribution.summary,
            home_page=o.distribution.homepage_url,
        )
    )
    last_serial = factory.fuzzy.FuzzyInteger(1_000_000, 10_000_000)
    requires_dist = factory.LazyAttribute(
        lambda o: [str(obj) for obj in o.distribution.requirements]
    )
    requires_python = "~=3.7"
    releases = factory.LazyAttribute(
        lambda o: {o.distribution.current: [PypiReleaseFactory()]}
    )
    urls = factory.LazyAttribute(lambda o: [PypiUrlFactory()])


class ImportlibDistributionStubFactory(factory.Factory):
    class Meta:
        model = ImportlibDistributionStub

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


class DistributionPackageFactory(factory.Factory):
    class Meta:
        model = DistributionPackage
        exclude = ("requires",)

    requires = ""  # excluded

    name = factory.Faker("last_name")
    is_editable = False
    latest = factory.LazyAttribute(lambda o: o.current)
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


class DistributionFactory(factory.django.DjangoModelFactory):
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


def make_packages(*packages: Iterable[DistributionPackage]):
    return {obj.name_normalized: obj for obj in packages}
