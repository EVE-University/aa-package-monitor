import json

import factory
import factory.fuzzy

from package_monitor.models import Distribution


class DistributionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Distribution
        django_get_or_create = ("name",)

    name = factory.Faker("last_name")
    description = factory.Faker("paragraph")
    latest_version = factory.LazyAttribute(lambda o: o.installed_version)
    is_outdated = False
    website_url = factory.Faker("uri")

    class Params:
        app_list = []

    @factory.lazy_attribute
    def installed_version(self):
        int_fuzzer = factory.fuzzy.FuzzyInteger(0, 20)
        major = int_fuzzer.fuzz()
        minor = int_fuzzer.fuzz()
        patch = int_fuzzer.fuzz()
        return f"{major}.{minor}.{patch}"

    @factory.lazy_attribute
    def apps(self):
        return json.dumps(self.app_list)
