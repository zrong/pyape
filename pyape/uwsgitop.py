# -*- coding: utf-8 -*-
#!/usr/bin/env python
###########################################
# 修改自 https://github.com/xrmx/uwsgitop
# 将其模块化，改为 Python3 Only
# 2018-11-09 zrong
###########################################

import argparse
import urllib.request as urllib2
import socket
import json
import curses
import time
import atexit
import sys
import traceback
from collections import defaultdict
import errno


def human_size(n):
    # G
    if n >= (1024*1024*1024):
        return "%.1fG" % (n/(1024*1024*1024))
    # M
    if n >= (1024*1024):
        return "%.1fM" % (n/(1024*1024))
    # K
    if n >= 1024:
        return "%.1fK" % (n/1024)
    return "%d" % n


def inet_addr(arg):
    sfamily = socket.AF_INET
    host, port = arg.rsplit(':', 1)
    addr = (host, int(port))
    return sfamily, addr, host


def unix_addr(arg):
    sfamily = socket.AF_UNIX
    addr = arg
    return sfamily, addr, socket.gethostname()


def abstract_unix_addr(arg):
    sfamily = socket.AF_UNIX
    addr = '\0' + arg[1:]
    return sfamily, addr, socket.gethostname()


def parse_address(address):
    http_stats = False
    sfamily = None
    if address.startswith('http://'):
        http_stats = True
        addr = address
        host = addr.split('//')[1].split(':')[0]
    elif ':' in address:
        sfamily, addr, host = inet_addr(address)
    elif address.startswith('@'):
        sfamily, addr, host = abstract_unix_addr(address)
    else:
        sfamily, addr, host = unix_addr(address)
    return http_stats, sfamily, addr, host


def init_screen():
    screen = curses.initscr()
    curses.noecho()
    curses.start_color()
    curses.use_default_colors()

    try:
        # busy
        curses.init_pair(1, curses.COLOR_GREEN, -1)
        # cheap
        curses.init_pair(2, curses.COLOR_MAGENTA, -1)
        # unused
        curses.init_pair(3, curses.COLOR_RED, -1)
        # sig
        curses.init_pair(4, curses.COLOR_YELLOW, -1)
        # pause
        curses.init_pair(5, curses.COLOR_BLUE, -1)
    except curses.error:
        # the terminal doesn't support colors
        pass

    try:
        curses.curs_set(0)
    except:
        pass
    screen.clear()
    return screen


def reqcount(item):
    return item['requests']


def calc_percent(tot, req):
    if tot == 0:
        return 0.0
    return (100 * float(req)) / float(tot)


def merge_worker_with_cores(workers, rps_per_worker, cores, rps_per_core):
    workers_by_id = dict([(w['id'], w) for w in workers])
    new_workers = []
    for wid, w_cores in cores.items():
        for core in w_cores:
            cid = core['id']
            data = dict(workers_by_id.get(wid))
            data.update(core)
            if data['status'] == 'busy' and not core['in_request']:
                data['status'] = '-'
            new_wid = "{0}:{1}".format(wid, cid)
            data['id'] = new_wid
            rps_per_worker[new_wid] = rps_per_core[wid, cid]
            new_workers.append(data)
    workers[:] = new_workers


def reads(http_stats, addr, sfamily):
    js = ''

    if http_stats:
        r = urllib2.urlopen(addr)
        js = r.read().decode('utf8', 'ignore')
    else:
        s = socket.socket(sfamily, socket.SOCK_STREAM)
        s.connect(addr)

        while True:
            data = s.recv(4096)
            if len(data) < 1:
                break
            js += data.decode('utf8', 'ignore')
        s.close()
    return js


def call(address, frequency):
    # RPS calculation
    last_tot_time = time.time()
    last_reqnumber_per_worker = defaultdict(int)
    last_reqnumber_per_core = defaultdict(int)

    # 0 - do not show async core
    # 1 - merge core statistics with worker statistics
    # 2 - display active cores under workers
    async_mode = 0
    fast_screen = 0

    screen = init_screen()
    http_stats, sfamily, addr, host = parse_address(address)

    need_reset = True

    def game_over():
        if need_reset:
            curses.echo()
            curses.endwin()

    def exc_hook(type, value, tb):
        need_reset = False
        if screen:
            curses.echo()
            curses.endwin()
        traceback.print_exception(type, value, tb)

    atexit.register(game_over)
    sys.excepthook = exc_hook

    while True:

        if fast_screen == 1:
            screen.timeout(100)
        else:
            screen.timeout(frequency * 1000)

        screen.clear()

        js = ''
        try:
            js = reads(http_stats, addr, sfamily)
        except IOError as e:
            if e.errno != errno.EINTR:
                raise
            continue
        except:
            raise Exception("unable to get uWSGI statistics")

        dd = json.loads(js)

        uversion = ''
        if 'version' in dd:
            uversion = '-' + dd['version']

        if 'listen_queue' not in dd:
            dd['listen_queue'] = 0

        cwd = ""
        if 'cwd' in dd:
            cwd = "- cwd: %s" % dd['cwd']

        uid = ""
        if 'uid' in dd:
            uid = "- uid: %d" % dd['uid']

        gid = ""
        if 'gid' in dd:
            gid = "- gid: %d" % dd['gid']

        masterpid = ""
        if 'pid' in dd:
            masterpid = "- masterpid: %d" % dd['pid']

        screen.addstr(1, 0, "node: %s %s %s %s %s" % (host, cwd, uid, gid, masterpid))

        if 'vassals' in dd:
            screen.addstr(0, 0, "uwsgi%s - %s - emperor: %s - tyrant: %d" % (uversion, time.ctime(), dd['emperor'], dd['emperor_tyrant']))
            if dd['vassals']:
                vassal_spaces = max([len(v['id']) for v in dd['vassals']])
                screen.addstr(2, 0, " VASSAL%s\tPID\t" % (' ' * (vassal_spaces-6)), curses.A_REVERSE)
                pos = 3
                for vassal in dd['vassals']:
                    screen.addstr(pos, 0, " %s\t%d" % (vassal['id'].ljust(vassal_spaces), vassal['pid']))
                    pos += 1

        elif 'workers' in dd:
            tot = sum([worker['requests'] for worker in dd['workers']])

            rps_per_worker = {}
            rps_per_core = {}
            cores = defaultdict(list)
            dt = time.time() - last_tot_time
            total_rps = 0
            for worker in dd['workers']:
                wid = worker['id']
                curr_reqnumber = worker['requests']
                last_reqnumber = last_reqnumber_per_worker[wid]
                rps_per_worker[wid] = (curr_reqnumber - last_reqnumber) / dt
                total_rps += rps_per_worker[wid]
                last_reqnumber_per_worker[wid] = curr_reqnumber
                if not async_mode:
                    continue
                for core in worker.get('cores', []):
                    if not core['requests']:
                        # ignore unused cores
                        continue
                    wcid = (wid, core['id'])
                    curr_reqnumber = core['requests']
                    last_reqnumber = last_reqnumber_per_core[wcid]
                    rps_per_core[wcid] = (curr_reqnumber - last_reqnumber) / dt
                    last_reqnumber_per_core[wcid] = curr_reqnumber
                    cores[wid].append(core)
                cores[wid].sort(key=reqcount)

            last_tot_time = time.time()

            if async_mode == 1:
                merge_worker_with_cores(dd['workers'], rps_per_worker,
                                        cores, rps_per_core)

            tx = human_size(sum([worker['tx'] for worker in dd['workers']]))
            screen.addstr(0, 0, "uwsgi%s - %s - req: %d - RPS: %d - lq: %d - tx: %s" % (uversion, time.ctime(), tot, int(round(total_rps)), dd['listen_queue'], tx))
            screen.addstr(2, 0, " WID\t%\tPID\tREQ\tRPS\tEXC\tSIG\tSTATUS\tAVG\tRSS\tVSZ\tTX\tReSpwn\tHC\tRunT\tLastSpwn", curses.A_REVERSE)
            pos = 3

            dd['workers'].sort(key=reqcount, reverse=True)
            for worker in dd['workers']:
                sigs = 0
                wtx = human_size(worker['tx'])
                wlastspawn = "--:--:--"

                wrunt = worker['running_time']/1000
                if wrunt > 9999999:
                    wrunt = "%sm" % str(int(wrunt / (1000*60)))
                else:
                    wrunt = str(wrunt)

                if worker['last_spawn']:
                    wlastspawn = time.strftime("%H:%M:%S", time.localtime(worker['last_spawn']))

                color = curses.color_pair(0)
                if 'signals' in worker:
                    sigs = worker['signals']
                if worker['status'] == 'busy':
                    color = curses.color_pair(1)
                if worker['status'] == 'cheap':
                    color = curses.color_pair(2)
                if worker['status'].startswith('sig'):
                    color = curses.color_pair(4)
                if worker['status'] == 'pause':
                    color = curses.color_pair(5)

                wid = worker['id']

                rps = int(round(rps_per_worker[wid]))

                try:
                    screen.addstr(pos, 0, " %s\t%.1f\t%d\t%d\t%d\t%d\t%d\t%s\t%dms\t%s\t%s\t%s\t%s\t%s\t%s\t%s" % (
                        wid, calc_percent(tot, worker['requests']),  worker['pid'], worker['requests'], rps, worker['exceptions'], sigs, worker['status'],
                        worker['avg_rt']/1000, human_size(worker['rss']), human_size(worker['vsz']),
                        wtx, worker['respawn_count'], worker['harakiri_count'], wrunt, wlastspawn
                    ), color)
                except:
                    pass
                pos += 1
                if async_mode != 2:
                    continue
                for core in cores[wid]:
                    color = curses.color_pair(0)
                    if core['in_request']:
                        status = 'busy'
                        color = curses.color_pair(1)
                    else:
                        status = 'idle'

                    cid = core['id']
                    rps = int(round(rps_per_core[wid, cid]))
                    try:
                        screen.addstr(pos, 0, "  :%s\t%.1f\t-\t%d\t%d\t-\t-\t%s\t-\t-\t-\t-\t-" % (
                            cid, calc_percent(tot, core['requests']),  core['requests'], rps, status,
                        ), color)
                    except:
                        pass
                    pos += 1

        screen.refresh()

        ch = screen.getch()
        if ch == ord('q'):
            game_over()
            break
        elif ch == ord('a'):
            async_mode = (async_mode + 1) % 3
        elif ch == ord('f'):
            fast_screen = (fast_screen + 1) % 2
