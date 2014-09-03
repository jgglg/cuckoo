#!/usr/bin/env python
# Copyright (C) 2010-2014 Cuckoo Foundation.
# This file is part of Cuckoo Sandbox - http://www.cuckoosandbox.org
# See the file 'docs/LICENSE' for copying permission.

import argparse
import logging
import os
import shutil
import sys

try:
    from lib.cuckoo.common.logo import logo
    from lib.cuckoo.common.constants import CUCKOO_VERSION, CUCKOO_ROOT
    from lib.cuckoo.common.exceptions import CuckooCriticalError
    from lib.cuckoo.common.exceptions import CuckooDependencyError
    from lib.cuckoo.core.database import Database
    from lib.cuckoo.core.startup import check_working_directory, check_configs
    from lib.cuckoo.core.startup import check_version, create_structure
    from lib.cuckoo.core.startup import init_logging, init_modules
    from lib.cuckoo.core.startup import init_tasks, init_yara
    from lib.cuckoo.core.scheduler import Scheduler
    from lib.cuckoo.core.resultserver import ResultServer

    import bson

    bson  # Pretend like it's actually being used (for static checkers.)
except (CuckooDependencyError, ImportError) as e:
    sys.exit("ERROR: Missing dependency: {0}".format(e))

log = logging.getLogger()

def cuckoo_init(quiet=False, debug=False, artwork=False, test=False):
    cur_path = os.getcwd()
    os.chdir(CUCKOO_ROOT)

    logo()
    check_working_directory()
    check_configs()
    check_version()
    create_structure()

    if artwork:
        import time
        try:
            while True:
                time.sleep(1)
                logo()
        except KeyboardInterrupt:
            return

    init_logging()

    if quiet:
        log.setLevel(logging.WARN)
    elif debug:
        log.setLevel(logging.DEBUG)

    init_modules()
    init_tasks()
    init_yara()

    # This is just a temporary hack, we need an actual test suite to integrate
    # with Travis-CI.
    if test:
        return

    ResultServer()

    os.chdir(cur_path)


def cuckoo_main(max_analysis_count=0):
    cur_path = os.getcwd()
    os.chdir(CUCKOO_ROOT)

    try:
        sched = Scheduler(max_analysis_count)
        sched.start()
    except KeyboardInterrupt:
        sched.stop()

    os.chdir(cur_path)


def cuckoo_clean():
    paths = [
        os.path.join(CUCKOO_ROOT, "db"),
        os.path.join(CUCKOO_ROOT, "log"),
        os.path.join(CUCKOO_ROOT, "storage"),
    ]

    # Delete various directories.
    for path in paths:
        if os.path.isdir(path):
            shutil.rmtree(path)

    # Delete all compiled Python objects ("*.pyc".)
    for dirpath, dirnames, filenames in os.walk(CUCKOO_ROOT):
        for fname in filenames:
            if not fname.endswith(".pyc"):
                continue

            try:
                os.unlink(os.path.join(dirpath, fname))
            except IOError as e:
                log.debug("Error removing file %s: %s",
                          os.path.join(dirpath, fname), e)

    # Initialize the database connection.
    db = Database()

    # Drop all tasks.
    db.drop_tasks()

    # Drop all samples.
    db.drop_samples()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-q", "--quiet", help="Display only error messages", action="store_true", required=False)
    parser.add_argument("-d", "--debug", help="Display debug messages", action="store_true", required=False)
    parser.add_argument("-v", "--version", action="version", version="You are running Cuckoo Sandbox {0}".format(CUCKOO_VERSION))
    parser.add_argument("-a", "--artwork", help="Show artwork", action="store_true", required=False)
    parser.add_argument("-t", "--test", help="Test startup", action="store_true", required=False)
    parser.add_argument("-m", "--max-analysis-count", help="Maximum number of analyses", type=int, required=False)
    parser.add_argument("--clean", help="Remove all tasks and samples and their associated data", action='store_true', required=False)
    args = parser.parse_args()

    if args.clean:
        cuckoo_clean()
        sys.exit(0)

    try:
        cuckoo_init(quiet=args.quiet, debug=args.debug, artwork=args.artwork,
                    test=args.test)

        if not args.artwork and not args.test:
            cuckoo_main(max_analysis_count=args.max_analysis_count)
    except CuckooCriticalError as e:
        message = "{0}: {1}".format(e.__class__.__name__, e)
        if len(log.handlers):
            log.critical(message)
        else:
            sys.stderr.write("{0}\n".format(message))

        sys.exit(1)
