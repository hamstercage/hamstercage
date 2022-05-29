# Hamstercage - Config Management for Pets, not Cattle

## Overview
If you work professionally with many machines and config, you like will have heard "cattle, not pets" as the philosophy for managing machines, VMs, etc., and you're likely using Ansible, Puppet, SaltStack, or another configuration management system that allows you to express configuration as code. This approach works well when you have many targets that share many traits, you have a lab where you can test configuration changes, and you have full time staff to take care of it all.

However, if you're running a handful of boxes or VPSes for a small organisation, or just for yourself and your friends and family, your workflow might actually look quite different: you make changes to the live configuration of your web server, for example, and after you're satisfied that everything is working, you might want to save the key bits of config somewhere safe, so you can refer back to it later. Setting up any of the heavy tools can be cumbersome, especially for making quick provisional changes: in the worstcase scenario, you modify a file in the source repo, commit it, then run the tool to apply it to your machine.

Hamstercage aims to make it easy to save and restore your config by using a Git repo, by editing the config files directly on the target machine, then saving the new config into the repository. In other words: pets, not cattle.

Hamstercage is geared towards managing config files as complete files. To keep things simple, there are no facilities to update individual lines in files, update system configuration settings through some API, or other more complex logic. Hamstercage can be used to manage shell script files or binaries for custom tools, however.

To allow one repository to be used for multiple targets, sets of files can be managed. Each set is called a tag. You can select the tags to use each time you run Hamstercage. The manifest also contains a list of hostnames and the tags to use for each. This makes it possible to run the same Hamstercage command on multiple hosts, and have files be applied to each according to their respective purpose. 

## Theory of Operation

Hamstercage keeps a list of files under management in a **manifest** file, by default `hamstercage.yaml`. The various Hamstercage commands can be used to add, update, and remove files from the manifest, but you can always make changes manually, for example to correct the owner or mode of a file.

Managed files are kept not as a single list, but as multiple lists, one for each **tag**. A tag is simply a label for a set of files. You are free to choose tags to organize sets of files as you see fit, for example, by purpose, application, operating system, or any other metric.

In addition to the managed files, the manifest also contains a list of **hostnames**, with the tags that should be applied to each hostname. This allows you to run the same Hamstercage command across multiple hosts and have files applied according to the hosts' respective tags.

The contents of files is kept alongside the manifest, using the path of the target. For example, a target file `/etc/bash_profile` would be stored in `repo/all/etc/bash_profile`.

While Hamstercage manages files very efficiently, there are some configuration tasks that require manipulation of existing files, refreshing a set of files, or restarting a daemon. Hamstercage does not attempt to implement any such actions. **Hooks** allow you to supply your own custom logic for these kinds of actions. You can define hooks to run before or after a command is executed (for example before a `save` or after an `apply`). Hooks are defined on tags, so you can cater the commands to the set of files that are managed. Hooks can be individual shell commands, any executable including scripts, or Python programs that are executed inside Hamstercages Python process.

## Installation

Hamstercage is a Python module. You can install it from this source repository, or from PyPi.


```shell
pip install hamstercage
```

## Using Hamstercage

After installation, Hamstercage is available on the path as `hamstercage`.

### Creating a new Hamstercage repo

Hamstercage needs a manifest file in order to track files managed through it. You can create this file manually, or you can have Hamstercage create a template file for you:

```shell
hamstercage init
```

This creates `hamstercage.yaml` in the current directory.

### The Hamstercage Manifest

All information about file entries is stored in the manifest file `hamstercage.yaml`. This [YAML](https://yaml.org) file consists of these top-level entries:
* `hosts`: each entry describes one host, in particular the set of tags that apply to it
* `tags`: each entry contains a list of files managed for this tag

This is a very minimal example with one host, one tag and one file:
```yaml
hosts:
  testing.example.com:
    description: ''
    tags:
    - all
tags:
  all:
    description: files that apply to all hosts
    entries:
      foo.txt:
        group: staff
        mode: 0o644
        owner: stb
        type: file
```

#### Hosts

Each entry in this dict defines one host. Hosts are distinguished by their fully-qualified hostname. When running Hamstercage, you can override the hostname by specifying the `-h` option. Each host definition can have these fields:
* `description`: allows you to add a description or note to this entry. Optional.
* `tags`: a list of one or more tags to apply to this host.

#### Tags

Each entry in this dict defines one tag. Tag names can be freely chosen; it is recommended to stick to alpha-numeric identifiers though, to keep the names compatible with shell scripts, etc. Each entry has these fields:
* `description`: allows you to add a description or note to this entry. Optional.
* `entries`: a dict of files managed through this tag. See below for details.
* `hooks`: a dict of hook scripts that will be run. See below for details.

#### Tags: Entries

The entries field in a tag entry describes files, directories, and symbolic links that are managed through that tag. Each entry can have these fields:
* `group`: the group name owning this file.
* `mode`: the access mode for this file. You need to specify the mode as an octal number (`0o644`) or as a string in quotes (`"644"`). If you simply give a number, it will be interpreted as a base-10 integer, leading to unexpected mode bits
* `owner`: the user name owning this file.
* `target`: the path the link points to, only applicable to `type`=`link`
* `type`: must be one of `dir`, `file`, or `link`.

Note that Hamstercage only manages symbolic links (soft links). Hard links are not supported.

#### Tags: Hooks

The `hooks` dict in a tag allows you to hook scripts into Hamstercages execution. The name of each entry defines when to run the script; the contents of the dict define what command to execute.

The name consists of two parts separated by a dash: the prefix `pre` or `post`, and the name of the Hamstercage command. For example, the hook defined by the name `pre-save` will be executed when you run `hamstercage save`, just before the contents of the files will be copied from the target system to the repository. A hook `post-apply` will be run right after all files have been updated by the command `hamstercage apply`.

Hamstercage searches for a matching hook definition in this order:
1. for the exact match *step*`-`*command* (for example, `pre-save`)
2. for the wildcard match `*-`*command* (for example, `*-save`)
3. for the wildcard match *step*`-*` (for example, `pre-*`)
4. for the fallback wildcard `*`.

The first match found will be executed.

Each entry has these fields:
* `command`: the command or script to execute.
* `description`: allows you to add a description or note to this entry. Optional.
* `type`: the type of command or script to run.
  * `exec`: run the program specified by `command`. If `command` is not an absolute path, the system will search for it on the `PATH`. See [subprocess.Popen](https://docs.python.org/3/library/subprocess.html#subprocess.Popen) for details. The command will be invoked with the Hamstercage command, the step, and the tag the hook is defined in as parameters, for example `.../myhook.sh apply post all`.
  * `python`: `command` should specify a Python script. A relative path is interpreted relative to the repository directory. See below for global variables available to the script.
  * `shell`: run `command` through the shell. Typically, this will be the shell of the user running Hamstercage.

The `exec` and `shell` hooks receive the following environment variables:
* `HAMSTERCAGE_CMD`: the command being executed
* `HAMSTERCAGE_MANIFEST`: the manifest file path name
* `HAMSTERCAGE_HOOK`: the name of the hook entry
* `HAMSTERCAGE_REPO`: the repo directory, which is the directory the manifest file lives in
* `HAMSTERCAGE_STEP`: the step (`pre` or `post`)
* `HAMSTERCAGE_TAG`: the tag name this hook is defined in

The `python` script receives these global variables:
* `cmd`: the command being executed
* `manifest`: the manifest object
* `hook`: the name of the hook entry
* `repo`: the repo directory, which is the directory the manifest file lives in
* `step`: the step (`pre` or `post`)
* `tag`: the tag object this hook is defined in
* `__file__`: the Python hook file
* `__name__`: the constant `__hamstercage__`.



## Command Reference

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