theCore embedded framework CLI tools
====================================

Usage:

::

    usage: tcore [-h] {bootstrap,purge,init,compile,runenv} ...

    theCore framework CLI

    positional arguments:
    {bootstrap,purge,init,compile,runenv}
                            theCore subcommands
        bootstrap           Installs theCore development environment
        purge               Deletes theCore development environment
        init                Initialize project based on theCore
        compile             Build project
        runenv              Run arbitrary command inside theCore environment

    optional arguments:
    -h, --help            show this help message and exit


Boostrap theCore
----------------

To install theCore and all the dependencies, use ``bootstrap`` subcommand::

    usage: tcore bootstrap [-h] [-f]

    optional arguments:
    -h, --help   show this help message and exit
    -f, --force  Force (re)install theCore dev environment

Initialize project
------------------

New project can be downloaded or initialized using following commands::

    usage: tcore init [-h] [-r REMOTE] [-o OUTDIR]

    optional arguments:
    -h, --help            show this help message and exit
    -r REMOTE, --remote REMOTE
                            Git remote to download project from
    -o OUTDIR, --outdir OUTDIR
                            Output directory to place a project in

Compile project
---------------

If created, embedded project can be compiled using ``compile`` command::

    usage: tcore compile [-h] [-s SOURCE] [-b BUILDDIR]
                         [--buildtype {debug,release,min_size,none}] [-t TARGET]
                         [-l] [-c]

    optional arguments:
      -h, --help            show this help message and exit
      -s SOURCE, --source SOURCE
                            Path to the source code. Defaults to current
                            directory.
      -b BUILDDIR, --builddir BUILDDIR
                            Path to the build directory. Defaults to
                            ./build/<target_name>-<build_type>, where
                            <target_name> is the selected target and <build_type>
                            is a build type supplied with --buildtype parameter
      --buildtype {debug,release,min_size,none}
                            Build type. Default is none
      -t TARGET, --target TARGET
                            Target name to compile for
      -l, --list-targets    List supported targets
      -c, --clean           Clean build


Run custom command within theCore environment
---------------------------------------------

Arbitrary command can be executed with ``runenv`` subcommand::

    usage: tcore runenv [-h] [-s] command [command ...]

    positional arguments:
      command     Command to execute.

    optional arguments:
      -h, --help  show this help message and exit
      -s, --sudo  Run command with root privileges using sudo.
