import factory
import factory.fuzzy
from importlib_metadata import PackagePath

from package_monitor.core import DistributionPackage
from package_monitor.models import Distribution

faker = factory.faker.faker.Faker()


class ImportlibDistributionStub:
    def __init__(
        self,
        name: str,
        version: str,
        files: list,
        requires: list = None,
        homepage_url: str = "",
        description: str = "",
    ) -> None:
        self.metadata = {
            "Name": name,
            "Home-page": homepage_url if homepage_url != "" else "UNKNOWN",
            "Summary": description if description != "" else "UNKNOWN",
        }
        self.version = version
        self.files = [PackagePath(f) for f in files]
        self.requires = requires if requires else None


class ImportlibDistributionStubFactory(factory.Factory):
    class Meta:
        model = ImportlibDistributionStub

    name = factory.Faker("last_name")
    # files = ["dummy_1/file_1.py", "dummy_1/__init__.py"]
    homepage_url = factory.Faker("url")
    description = factory.Faker("sentence")

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


class DistributionPackageFactory(factory.Factory):
    class Meta:
        model = DistributionPackage

    distribution = factory.SubFactory(ImportlibDistributionStubFactory)
    name = factory.LazyAttribute(lambda o: o.distribution.metadata["Name"])
    current = factory.LazyAttribute(lambda o: o.distribution.version)
    latest = factory.LazyAttribute(lambda o: o.current)


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
