# Hamstercage - Config Management for Pets, not Cattle

## Overview
If you work professionally with many machines and config, you like will have heard "cattle, not pets" as the philosophy for managing machines, VMs, etc., and you're likely using Ansible, Puppet, SaltStack, or another configuration management system that allows you to express configuration as code. This approach works well when you have many targets that share many traits, you have a lab where you can test configuration changes, and you have full time staff to take care of it all.

However, if you're running a handful of boxes or VPSes for a small organisation, or just for yourself and your friends and family, your workflow might actually look quite different: you make changes to the live configuration of your web server, for example, and after you're satisfied that everything is working, you might want to save the key bits of config somewhere safe, so you can refer back to it later. Setting up any of the heavy tools can be cumbersome, especially for making quick provisional changes: in the worstcase scenario, you modify a file in the source repo, commit it, then run the tool to apply it to your machine.

Hamstercage aims to make it easy to save and restore your config by using a Git repo, by editing the config files directly on the target machine, then saving the new config into the repository. In other words: pets, not cattle.

Hamstercage is geared towards managing config files as complete files. To keep things simple, there are no facilities to update individual lines in files, update system configuration settings through some API, or other more complex logic. Hamstercage can be used to manage shell script files or binaries for custom tools, however.

To allow one repository to be used for multiple targets, sets of files can be managed. Each set is called a tag. You can select the tags to use each time you run Hamstercage. The manifest also contains a list of hostnames and the tags to use for each. This makes it possible to run the same Hamstercage command on multiple hosts, and have files be applied to each according to their respective purpose. 

## Theory of Operation

Hamstercage keeps a list of files under management in a manifest file, by default `hamstercage.yaml`. The various Hamstercage commands can be used to add, update, and remove files from the manifest, but you can always make changes manually, for example to correct the owner or mode of a file.

Managed files are kept not as a single list, but as multiple lists, one for each tag. A tag is simply a label for a set of files. You are free to choose tags to organize sets of files as you see fit, for example, by purpose, application, operating system, or any other metric.

In addition to the managed files, the manifest also contains a list of hostnames, with the tags that should be applied to each hostname. This allows you to run the same Hamstercage command across multiple hosts and have files applied according to the hosts' respective tags.

The contents of files is kept alongside the manifest, using the path of the target. For example, a target file `/etc/bash_profile` would be stored in `repo/all/etc/bash_profile`.

## Installation

Hamstercage is a Python module. You can install it from this source repository, or from PyPi.

TODO: show actual installation commands

## Using Hamstercage

After installation, Hamstercage is available on the path as `hamstercage`.

### Creating a new Hamstercage repo

Hamstercage needs a manifest file in order to track files managed through it. You can create this file manually, or you can have Hamstercage create a template file for you:

```shell
hamstercage init
```

This creates `hamstercage.yaml` in the current directory.

## Reference

Hamstercage commands take a number of options and parameters.

### General Options

#### Target Directory `-d` / `--directory`

The directory where the managed files live, default `/`. You can set this to a different path when restoring config from a backup, or when managing a jail or container from the outside.

#### Hostname `-n` / `--hostname`

The hostname of the local host. By default the value of `hostname(1)`. When applying files to the target directory, the hostname is used to obtain the default list of tags to use. Specifying this can be useful when restoring a host from backup, or when working on a container or jail.

#### Manifest File `-f` / `--file`

The name of the manifest file that tracks all managed files, as well as settings for the repository. Default is `./hamstercage.yaml`.

#### Repository Base Directory `-r` / `--rep`

All managed files are stored under this directory. The default is the same directory the manifest file lives in.

#### Tags `-t` / `--tag`

When adding files or applying them to the target directory, one or more tags can be specified. See the `add` and `apply` commands.

### Verbose output `-v` / `--verbose`

By default, Hamstercage will only print warnings or error. With this flag, progress will be reported on all operations.

### Commands

#### Adding Files `add`

```shell
hamstercage -t mytag add file...
```

Add one or more files to the repository. You need to specify exactly one tag, which determines the tag the file will be added to. The file will be added to the manifest, and the contents of the file copied to the repository.

#### Applying Files `apply`

```shell
hamstercage apply [file...]
```

Apply files from the repository to the target. Without any further options and parameters, will apply all files from the default tags for this hostname. Specify one or more tags to limit files to those in those tags, or specify filenames that should be applied.

Adding a file that is already in the manifest for the given tag is an error.

#### Determining Differences `diff`

```shell
hamstercage diff [file...]
```
Prints out a unified diff between all files in the repository and in the target. This allows you to preview what changed `apply` or `save` will make.

#### Initialize a New Repository `init`

```shell
hamstercage init
```

Creates a new manifest file, by default `./hamstercage.yaml`. Combine this with `git init` to create a new Hamstercage repository.

#### List Entries `list`

```shell
hamstercage list [-l]
```
Lists all entries in the manifest. When `-l` is given, will print more details on each entry.

#### Remove Files From Repository `remove`

```shell
hamstercage -t tag remove file...
```

Removes one or more files from the specified tag. Does not change files in the target.

#### Save Target to Repository `save`

```shell
hamstercage save [file...]
```

Updates the manifest entries and repository files from the target.

# Developing Hamstercage

## Poetry For Dependency Management and Building

The project uses [Poetry](https://python-poetry.org), which you should install locally. After installing Poetry, you can install all necessary dependencies:
```shell
poetry install
```


## Source Code Formatting With Black

The GitHub workflow checks source code formatting with [black](https://github.com/psf/black).

To format all code automatically:
```shell
poetry run black .
```

When working on the code, you might want to [configure your IDE to automatically reformat the code with black](https://black.readthedocs.io/en/stable/integrations/editors.html).