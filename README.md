# Package Monitor

**WARNING - This app is currently in alpha state and not yet released - use at your own risk**

An app for keeping track of installed packages and outstanding updates with Alliance Auth.

![release](https://img.shields.io/pypi/v/aa-package-monitor?label=release) ![python](https://img.shields.io/pypi/pyversions/aa-package-monitor) ![django](https://img.shields.io/pypi/djversions/aa-package-monitor?label=django) ![pipeline](https://gitlab.com/ErikKalkoken/aa-package-monitor/badges/master/pipeline.svg) ![coverage](https://gitlab.com/ErikKalkoken/aa-package-monitor/badges/master/coverage.svg) ![license](https://img.shields.io/badge/license-MIT-green) ![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)

## Overview

Features:

- Shows list of distributions packages for all installed apps
- Checks for new stable releases of installed packages on PyPI
- Notifies user which installed packages are outdated and should be updated
- Takes into account all dependencies when recommending new versions
- Shows the number of outdated packages as badge in the sidebar
- Ability to add distribution pages to the monitor which are not related to Django apps

## Screenshot

![screenshot](https://i.imgur.com/H5NXUhI.png)

## Installation

- Install directly from this repo
- app name to be added to `INSTALLED_APPS` is `"package_monitor"`
- Add the following lines to your local.py to enable checking for updates:

    ```Python
    CELERYBEAT_SCHEDULE['package_monitor_update_distributions'] = {
        'task': 'package_monitor.tasks.update_distributions',
        'schedule': crontab(hour='*/1'),
    }
    ```

- If you want to include additional distribution packages in the monitor add the following settings to your local.py (example to include celery and redis). This is optional:

    ```Python
    PACKAGE_MONITOR_INCLUDE_PACKAGES = ["celery", "redis"]
    ```

- Run migration and restart supervisors to complete the installation
