#!/bin/bash

# Fix "may have been in progress in another thread when fork() was called# fix" when run in macOS High Sierra
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES

basedir=$(pwd)
if [ -r "$basedir/uwsgi.pid" ]; then
    echo 'uwsgi is running!'
    exit 0
fi
uwsgi="$basedir/venv/bin/uwsgi"
if [ ! -x "$uwsgi" ]; then
    uwsgi=$(which uwsgi)
fi
$uwsgi $basedir/uwsgi.ini