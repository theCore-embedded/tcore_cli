#!/usr/bin/python3

import argparse
import re
import sys
import os
import logging
import coloredlogs
import subprocess
import requests
import stat
import json
import shutil

# Common vars

CORE_INSTALL_DIR        = os.path.expanduser('~/.theCore/')
CORE_SRC_DIR            = CORE_INSTALL_DIR + 'theCore'
CORE_INSTALLFILE        = CORE_INSTALL_DIR + 'installfile.json'
CORE_UPSTREAM           = 'https://github.com/forGGe/theCore'
CORE_THIRDPARTY_DIR     = CORE_INSTALL_DIR + 'thirdparties'
NIX_DIR                 = '/nix'
NIX_INSTALL_SCRIPT      = '/tmp/nix_install.sh'
NIX_SOURCE_FILE         = os.path.expanduser('~/.nix-profile/etc/profile.d/nix.sh')
VERSION                 = '0.0.1'

# Logging

logger = logging.getLogger('tcore')
logger.setLevel(logging.DEBUG)

console_log = logging.StreamHandler()
console_log.setLevel(logging.DEBUG)

formatter = coloredlogs.ColoredFormatter('%(asctime)s [%(levelname)-8s] %(message)s')
console_log.setFormatter(formatter)

logger.addHandler(console_log)

# Utilities

def run_with_nix(cmd):
    nix_cmd = '. {} && {}'.format(NIX_SOURCE_FILE, cmd)
    rc = subprocess.call(nix_cmd, shell = True)

    if rc != 0:
        logger.error('failed to run command: ' + nix_cmd)
        exit(1)

def run_with_nix_shell(cmd):
    run_with_nix('nix-shell --run \\"{}\\" {}'.format(cmd, CORE_SRC_DIR))

# Commands

def do_bootstrap(args):
    if args.force:
        logger.warn('force (re)install theCore dev environment')

    # Check if nix exists

    if os.path.isdir(NIX_DIR) and not args.force:
        logger.info('Nix is already installed')
    else:
        logger.info('Installing Nix ... ')
        r = requests.get('https://nixos.org/nix/install')

        with open(NIX_INSTALL_SCRIPT, 'w') as fl:
            fl.write(r.text)

        os.chmod(NIX_INSTALL_SCRIPT, stat.S_IRWXU)
        rc = subprocess.call(NIX_INSTALL_SCRIPT, shell=True)

        if rc != 0:
            logger.error('failed to install Nix')
            exit(1)

    # Check if theCore is downloaded

    if os.path.isfile(CORE_INSTALLFILE) and not args.force:
        logger.info('theCore is already downloaded')
    else:
        if os.path.isdir(CORE_SRC_DIR):
            logger.info('remove old theCore files')
            shutil.rmtree(CORE_SRC_DIR)
        
        if os.path.isfile(CORE_INSTALLFILE):
            logger.info('remove theCore installfile')
            os.remove(CORE_INSTALLFILE)

        logger.info('downloading theCore')
        os.makedirs(CORE_SRC_DIR)
        run_with_nix('nix-env -i git')
        run_with_nix('git clone {} {}'.format(CORE_UPSTREAM, CORE_SRC_DIR))

        # Initial install file contents
        installfile_content = { 'tcore_ver': VERSION }

        with open(CORE_INSTALLFILE, 'w') as installfile:
            installfile.write(json.dumps(installfile_content, indent=4) + '\n')

        # Initialize Nix (download all dependencies)
        run_with_nix_shell('true')

def do_init(args):
    logger.warn('TODO: implement')

def do_purge(args):
    logger.warn('TODO: implement')

def do_compile(args):
    logger.warn('TODO: implement')
    logger.warn(args.source)
    logger.warn(args.builddir)

# Command line parsing

parser = argparse.ArgumentParser(description = 'theCore framework CLI')
subparsers = parser.add_subparsers(help = 'theCore subcommands')

bootstrap_parser = subparsers.add_parser('bootstrap', 
    help = 'Installs theCore development environment')
bootstrap_parser.add_argument('-f', '--force', action = 'store_true', 
    help = 'Force (re)install theCore dev environment')
bootstrap_parser.set_defaults(handler = do_bootstrap)

purge_parser = subparsers.add_parser('purge', 
    help = 'Deletes theCore development environment')
purge_parser.set_defaults(handler = do_purge)

init_parser = subparsers.add_parser('init', 
    help = 'Initialize project based on theCore')
init_parser.add_argument('-r', '--remote', type = str, 
    help = 'Git remote to download project from')
init_parser.set_defaults(handler = do_init)

compile_parser = subparsers.add_parser('compile', 
    help = 'Build project')
compile_parser.add_argument('-s', '--source', type = str, 
    help = 'Path to the source code. Defaults to current directory.', 
    default = os.getcwd())
compile_parser.add_argument('-b', '--builddir', type = str, 
    help = 'Path to the build directory. Defaults to ./build-<target_name>,' 
            + ' where <target_name> is the selected target.', 
    default = os.getcwd() + '/build')
compile_parser.add_argument('-t', '--target', type = str, 
    help = 'Target name to compile for')
compile_parser.add_argument('-l', '--list-targets', action = 'store_true', 
    help = 'List supported targets')

compile_parser.set_defaults(handler = do_compile)

args = parser.parse_args()

if args.handler:
    # I
    args.handler(args)
