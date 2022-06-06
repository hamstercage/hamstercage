# Hamstercage – Config Management for Pets, not Cattle

[![](https://img.shields.io/github/workflow/status/hamstercage/hamstercage/Build%20and%20Publish%20to%20PyPI?style=for-the-badge)](https://github.com/hamstercage/hamstercage/actions)
[![](https://img.shields.io/pypi/v/hamstercage?style=for-the-badge)](https://pypi.org/project/hamstercage/)
[![](https://img.shields.io/badge/Twitter-1DA1F2?style=for-the-badge&logo=twitter&logoColor=white)](https://twitter.com/hamstercageio)
## Overview
If you work professionally with many machines and config, you like will have heard "cattle, not pets" as the philosophy for managing machines, VMs, etc., and you're likely using Ansible, Puppet, SaltStack, or another configuration management system that allows you to express configuration as code. This approach works well when you have many targets that share many traits, you have a lab where you can test configuration changes, and you have full time staff to take care of it all.

However, if you're running a handful of boxes or VPSes for a small organisation, or just for yourself and your friends and family, your workflow might actually look quite different: you make changes to the live configuration of your web server, for example, and after you're satisfied that everything is working, you might want to save the key bits of config somewhere safe, so you can refer back to it later. Setting up any of the heavy tools can be cumbersome, especially for making quick provisional changes: in the worstcase scenario, you modify a file in the source repo, commit it, then run the tool to apply it to your machine.

Hamstercage aims to make it easy to save and restore your config by using a Git repo, by editing the config files directly on the target machine, then saving the new config into the repository. In other words: pets, not cattle.

Hamstercage is geared towards managing config files as complete files. To keep things simple, there are no facilities to update individual lines in files, update system configuration settings through some API, or other more complex logic. Hamstercage can be used to manage shell script files or binaries for custom tools, however.

To allow one repository to be used for multiple targets, sets of files can be managed. Each set is called a tag. You can select the tags to use each time you run Hamstercage. The manifest also contains a list of hostnames and the tags to use for each. This makes it possible to run the same Hamstercage command on multiple hosts, and have files be applied to each according to their respective purpose. 

## Installation and Usage

See [Hamstercage Documentation](https://hamstercage.io/documentation/) and the [Hamstercage Homepage](https://hamstercage.io/).

## Quick Start

```shell
pip install hamstercage
mkdir hamsters
cd hamsters
git init
hamstercage init
hamstercage -t all add /etc/profile
git add .
git commit
```

## Developing Hamstercage

### Installing Development Snapshots

The GitHub workflow automatically builds a snapshot version on each push to the main branch. To work with these snapshots, install them from [Test PyPI](https://test.pypi.org/project/hamstercage/):
```shell
sudo pip install --upgrade --index-url https://test.pypi.org/simple/ hamstercage
```

### Poetry For Dependency Management and Building

The project uses [Poetry](https://python-poetry.org), which you should install locally. After installing Poetry, you can install all necessary dependencies:
```shell
poetry install
```

### Source Code Formatting With Black

The GitHub workflow checks source code formatting with [black](https://github.com/psf/black).

To format all code automatically:
```shell
poetry run black .
```

When working on the code, you might want to [configure your IDE to automatically reformat the code with black](https://black.readthedocs.io/en/stable/integrations/editors.html).
