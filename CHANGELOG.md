# Change Log

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project adheres to [Semantic Versioning](http://semver.org/).

## [Unreleased] - yyyy-mm-dd

### Added

### Changed

### Fixed

## [1.7.1] - 2023-01-03

### Fixed

- Fetching info from PyPI for a package breaks when history contains releases with invalid versions

## [1.7.0] - 2022-09-15

### Added

- Ability to notify admins when an update is available for a currently installed distribution package (#7)

## [1.6.2] - 2022-09-12

### Changed

- Additional technical improvements & changes

## [1.6.1] - 2022-09-11

### Changed

- Technical improvements
- Better tests

## [1.6.0] - 2022-08-30

### Added

- Ability to exclude distribution packages via new setting
- Ability to exclude editable packages via new setting

### Changed

- No longer shows editable packages by default

## [1.5.0] - 2022-08-02

### Update notes

This version is changing the default to showing all packages. So if you have been using the default you might suddenly see a lot of missing updates after installing this patch. Our main rationale for changing this is that during the update to AA3 we have seen many users running outdated packages, which have caused problems.

### Changed

- Changing the default to showing all packages.
- Unused `filterDropDown.js` removed from template (!6)

## [1.4.2] - 2022-06-18

### Changed

- Migrated to clipboard-js library (Thank you @ppfeufer for the contribution)
- Add wheel to PyPI deployment

## [1.4.1] - 2022-06-05

### Changed

- Reverted copy-to-clipboard logic back execCommand approach. While this approach is officially deprecated, it works in more scenarios (e.g. does not requires HTTPS).

### Fixed

- `KeyError: 'latest'`

## [1.4.0] - 2022-06-04

### Added

- It is now possible to get the pip install command for installing all outdated packages together.

### Changed

- Install command is now shown in the tooltip

## [1.3.0] - 2022-03-01

### Changed

- Dropped support for Python 3.6
- Dropped support for Django 3.1

## [1.2.2] - 2021-12-09

### Fixed

- Modal for refreshing distributions now shows an error when the server is not reachable

## [1.2.1] - 2021-10-30

### Changed

- Added tests for AA 2.9 / Django 3.2 to CI
- Remove packaging as dependency (!2)

## [1.2.0] - 2021-07-20

### Changed

- Removed support for Django 2
- Add isort to CI
- Integrated allianceauth-app-utils

### Fixed

- Fix "Column 'website_url' cannot be null" (#5)

## [1.1.0] - 2020-11-11

### Added

- Shows the effective requirements of packages under "Used By" as tool tip [#1](https://gitlab.com/ErikKalkoken/aa-package-monitor/-/issues/1)

### Fixed

- KeyError: 'latest': [#2](https://gitlab.com/ErikKalkoken/aa-package-monitor/-/issues/2)

## [1.0.1] - 2020-11-05

### Fixed

- Spinner optimizes for light/dark mode
- Does no longer show vertical slider on full page
- Does no longer try to process distribution packages that have no name
- Fix white spaces and EOF in all files

## [1.0.0] - 2020-10-24

### Changed

- Will now show "update available" tab as default if there are updates
- Improved styling
- Improved text matrix

## [1.0.0b2] - 2020-09-22

### Changed

- Removed dependency conflict with Auth and Django 3

### Fixed

- Did not always recognize packages with capitals correctly (e.g. "Django").

## [1.0.0b1] - 2020-09-16

### Important Note for alpha users

Users of the alpha release will need to "migrate zero" their old installation before installing the beta version, because the migrations have been recreated from scratch for the beta.

### Added

- Initial beta release
