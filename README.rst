theCore embedded framework CLI tools
====================================

Usage:

::

    usage: tcore [-h] {bootstrap,purge,init,fetch,compile,flash,runenv} ...

    theCore framework CLI

    positional arguments:
      {bootstrap,purge,init,fetch,compile,flash,runenv}
                            theCore subcommands
        bootstrap           Installs theCore development environment
        purge               Deletes theCore development environment
        init                Initialize project based on theCore
        fetch               Fetches given theCore revision, globally changing its
                            state. Such change will be visible for every theCore-
                            based project of current user
        compile             Build project
        flash               flash project on the target
        runenv              Run arbitrary command inside theCore environment

    optional arguments:
      -h, --help            show this help message and exit

Boostrap theCore
----------------

::

    usage: tcore bootstrap [-h] [-f]

    optional arguments:
      -h, --help   show this help message and exit
      -f, --force  Force (re)install theCore dev environment

Purge theCore
-------------

::

    usage: tcore purge [-h]

    optional arguments:
      -h, --help  show this help message and exit

Fetch theCore
-------------

::

   usage: tcore fetch [-h] [-r REMOTE] [-e REF]

   optional arguments:
     -h, --help            show this help message and exit
     -r REMOTE, --remote REMOTE
                           Git remote to fetch theCore, defaults to `upstream`
     -e REF, --ref REF     Optional Git reference: commit id, branch or tag. If
                           not given, `develop` branch will be used.

Initialize project
------------------

::

    usage: tcore init [-h] [-r REMOTE] [-o OUTDIR]

    optional arguments:
      -h, --help            show this help message and exit
      -r REMOTE, --remote REMOTE
                            Git remote to download project from
      -o OUTDIR, --outdir OUTDIR
                            Output directory to place a project in

Compile project
---------------

::

    usage: tcore compile [-h] [-s SOURCE] [-b BUILDDIR]
                         [--buildtype {debug,release,min_size,none}] [-t TARGET]
                         [-j JOBS] [-l] [-c]

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
      -j JOBS, --jobs JOBS  Specifies the number of `make` jobs (commands) to run
                            simultaneously. Default is 1.
      -l, --list-targets    List supported targets
      -c, --clean           Clean build

Flash binary
------------

::

    usage: tcore flash [-h] [-s SOURCE] [-b BUILDDIR] [-l] [-d DEBUGGER]
                       [-c DEBUGGER_CONFIG] [-u]

    optional arguments:
      -h, --help            show this help message and exit
      -s SOURCE, --source SOURCE
                            Path to the source code. Defaults to current
                            directory.
      -b BUILDDIR, --builddir BUILDDIR
                            Explicit path to the build directory where binary
                            files are placed. By default the `build` directory and
                            subdirectories are scanned for binaries.
      -l, --list-bin        List built binaries and avaliable debuggers to perform
                            flash operation
      -d DEBUGGER, --debugger DEBUGGER
                            Use debugger to perform flash. By default the first
                            supported debugger in meta.json is used
      -c DEBUGGER_CONFIG, --debugger-config DEBUGGER_CONFIG
                            Specify debugger configuration. For example, different
                            configurations can represent different debugger
                            versions. By default, first suitable debugger
                            configuration, defined in meta.json, will be used
      -u, --sudo            Run flash command with root privileges using sudo.

Run custom command within theCore environment
---------------------------------------------

::

    usage: tcore runenv [-h] [-s] command [command ...]

    positional arguments:
      command     Command to execute.

    optional arguments:
      -h, --help  show this help message and exit
      -s, --sudo  Run command with root privileges using sudo.
