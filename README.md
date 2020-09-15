# Package Monitor

**WARNING - This app is currently in alpha state and not yet released - use at your own risk**

An app for keeping track of installed packages and outstanding updates with Alliance Auth.

![release](https://img.shields.io/pypi/v/aa-package-monitor?label=release) ![python](https://img.shields.io/pypi/pyversions/aa-package-monitor) ![django](https://img.shields.io/pypi/djversions/aa-package-monitor?label=django) ![pipeline](https://gitlab.com/ErikKalkoken/aa-package-monitor/badges/master/pipeline.svg) ![coverage](https://gitlab.com/ErikKalkoken/aa-package-monitor/badges/master/coverage.svg) ![license](https://img.shields.io/badge/license-MIT-green) ![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)

## Contents

- [Overview](#overview)
- [Screenshots](#screenshots)
- [Installation](#installation)
- [Settings](#settings)
- [Permissions](#permissions)
- [Management Commands](#management-commands)
- [Change Log](CHANGELOG.md)

## Overview

Package Monitor is an app for Alliance Auth that helps you keep your installation up-to-date. It shows you all installed distributions packages and will automatically notify you, when there are updates available.

Features:

- Shows list of installed distributions packages with related Django apps (if any)
- Identifies new valid releases for installed packages on PyPI
- Notifies user which installed packages are outdated and should be updated
- Shows the number of outdated packages as badge in the sidebar
- Takes into account the requirements of all installed packages and the current Python version when recommending updates
- Option to add distribution pages to the monitor which are not related to Django apps
- Option to show all known distribution packages (as opposed to only the ones that belong to installed Django apps)
- Copy the respective command for a package update to your clipboard directly from the package list

While it is possible to monitor all installed distribution packages, for most users we recommend the default mode - which only monitors packages that relate to currently installed apps - and maybe add some important packages like celery and redis.

## Screenshot

![screenshot](https://i.imgur.com/9ZMz1ji.png)

## Installation

### Step 1 - Check Preconditions

Please make sure you meet all preconditions before proceeding:

- Package Monitor is a plugin for [Alliance Auth](https://gitlab.com/allianceauth/allianceauth). If you don't have Alliance Auth running already, please install it first before proceeding. (see the official [AA installation guide](https://allianceauth.readthedocs.io/en/latest/installation/auth/allianceauth/) for details)

### Step 2 - Install app

Make sure you are in the virtual environment (venv) of your Alliance Auth installation. Then install the newest release from PYPI:

```bash
pip install aa-package-monitor
```

### Step 3 - Configure settings

- Add `'package_monitor'` to `INSTALLED_APPS`
- Add the following lines to your local.py to enable checking for updates:

    ```Python
    CELERYBEAT_SCHEDULE['package_monitor_update_distributions'] = {
        'task': 'package_monitor.tasks.update_distributions',
        'schedule': crontab(minute='*/60'),
    }
    ```

- Optional: Add additional settings if you want to change any defaults. See [Settings](#settings) for the full list.

### Step 4 - Finalize installation

Run migrations & copy static files

```bash
python manage.py migrate
python manage.py collectstatic
```

Restart your supervisor services for Auth

### Step 5 - Initial data load

Last, but not least perform an initial data load of all distribution packages by running the following command:

```bash
python manage.py package_monitor_refresh
```

## Settings

Here is a list of available settings for this app. They can be configured by adding them to your AA settings file (`local.py`).

Note that all settings are optional and the app will use the documented default settings if they are not used.

Name | Description | Default
-- | -- | --
`PACKAGE_MONITOR_INCLUDE_PACKAGES`| Names of additional distribution packages to be monitored, e.g. `["celery", "redis]`  | `None`
`PACKAGE_MONITOR_SHOW_ALL_PACKAGES`| Whether to show all distribution packages, as opposed to only showing packages that contain Django apps  | `False`

## Permissions

This is an overview of all permissions used by this app. Note that all permissions are in the "general" section.

Name | Purpose | Code
-- | -- | --
Can access this app and view | User can access the app and also request updates to the list of distribution packages |  `general.basic_access`

## Management Commands

The following management commands are included in this app:

Command | Description
-- | --
`package_monitor_refresh`| Refreshes all data about distribution packages. This command does functionally the same as the hourly update and is helpful to use after you have completed updating outdated packages to quickly see the result of your actions on the website.
