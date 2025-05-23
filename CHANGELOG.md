# CHANGELOG

## [Unreleased]

### New Features

- first version (sources moved from mfdata)
- better python rule
- add some logs
- support multiple switch instances
- better strftime placeholders
- keep original file name in trash directory (#19) (#25)

### Bug Fixes

- fix issue about wrong env name in inject_file
- fix issue in get_config_value with default values
- fix cache issue with python custom functions with same name
- fix issue with decorators and some failure policies
- fix typo in some failure policy configurations
- use failure policy instead of delete in reinject step
- fix #8
- fix #12
- fix typo in debug message (#17)
- fix shameful error in latest fix
- add missing import for python >= 3.9
- fix #20
- fix #20 (#21)
- use MFDATA_DATA_IN_DIR for tmp files
- use MFDATA_DATA_IN_DIR for tmp files (#22)
- replace deprecated utcnow() by now(datetime.UTC)
- fix flake8 error F824


