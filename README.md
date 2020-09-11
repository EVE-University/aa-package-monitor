# App Monitor

This app helps keep track of outstanding updates for all installed packages.

**This app is currently in alpha state and not yet released - use at your own risk**

## Features

- Shows list of distributions packages for all installed apps
- Checks for new stable releases of installed packages on PyPI
- Notifies user which installed packages are outdated and should be updated
- Takes into account all dependencies when recommending new versions

## Screenshot

![screenshot](https://i.imgur.com/H5NXUhI.png)

## Installation

- Install directly from this repo
- app name to be added to `INSTALLED_APPS` is `"app_monitor"`
- Add the following lines to your local.py to enable checking for updates:

    ```Python
    CELERYBEAT_SCHEDULE['app_monitor_update_distributions'] = {
        'task': 'app_monitor.tasks.update_distributions',
        'schedule': crontab(hour='*/1'),
    }
    ```

- Installation requires a migration
