from .factories import DistributionFactory


def create_testdata():
    DistributionFactory(
        name="dummy-2",
        installed_version="0.1.0",
        latest_version="0.2.0",
        is_outdated=True,
    )
    DistributionFactory(
        name="dummy-1",
        app_list=["app_1"],
        installed_version="0.1.0",
        latest_version="0.1.0",
        is_outdated=False,
    )
    DistributionFactory(name="dummy-3", installed_version="0.1.0", is_outdated=None)
