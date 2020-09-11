import fastentrypoints  # noqa: F401
import sys
from setuptools import setup
from setuptools import find_packages

required = []
dependency_links = []
EGG_MARK = '#egg='
with open('requirements.txt') as reqs:
    for line in reqs.read().split('\n'):
        if line.startswith('-e git:') or line.startswith('-e git+') or \
                line.startswith('git:') or line.startswith('git+'):
            if EGG_MARK in line:
                package_name = line[line.find(EGG_MARK) + len(EGG_MARK):]
                required.append(package_name)
                dependency_links.append(line)
            else:
                print('Dependency to a git repository should have the format:')
                print('git+ssh://git@github.com/xxxxx/xxxxxx#egg=package_name')
                sys.exit(1)
        else:
            required.append(line)

setup(
    name='acquisition',
    packages=find_packages(),
    install_requires=required,
    include_package_data=True,
    dependency_links=dependency_links,
    zip_safe=False,
    url="https://github.com/metwork-framework/acquisition",
    entry_points={
        "console_scripts": [
            "inject_file = acquisition.inject_file:main",
            "reinject_step = acquisition.reinject_step:main",
            "switch_step = acquisition.switch_step:main",
            "archive_step = acquisition.archive_step:main",
            "copy_step = acquisition.copy_step:main",
            "move_step = acquisition.move_step:main",
            "fork_step = acquisition.fork_step:main",
            "delete_step = acquisition.delete_step:main",
            "ungzip_step = acquisition.ungzip_step:main",
            "unbzip2_step = acquisition.unbzip2_step:main",
        ]
    }
)
