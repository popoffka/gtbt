#!/usr/bin/env python3
import json
import os
import string
import sqlite3
from datetime import datetime

import tornado.ioloop
import tornado.web

class StateHandler(tornado.web.RequestHandler):
    def get(self):
        self.write(self.application.get_current_state())

    def post(self):
        self.application.update_state(self.get_argument('new'))
        self.get()

class StatsTextHandler(tornado.web.RequestHandler):
    def get(self):
        self.write('<pre>')
        for (state, start, end) in self.application.get_history():
            self.write('{} — {}: {}\n'.format(start, end, state))
        self.write('</pre>')

class StatsJsonHandler(tornado.web.RequestHandler):
    def get(self):
        # forming JSON using string formatting is pretty disgusting, I know.
        # but this is very likely to be much more efficient than actually
        # creating the whole list in memory.
        last = '['
        for (state, start, end) in self.application.get_history():
            self.write(last)
            last = '{{"start": "{start}", "end": "{end}", "state": "{state}"}},'.format(
                state=state,
                start=start,
                end=end)
        if last != '[':
            self.write(last[:-1])
        else:
            self.write(last)
        self.write(']')


index_path = os.path.join(os.path.dirname(__file__), 'index.html')
report_path = os.path.join(os.path.dirname(__file__), 'report.html')
class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            # well, this isn't very pretty...
            # but it works!
            (r'/()', tornado.web.StaticFileHandler, {'path': index_path}),
            (r'/report()', tornado.web.StaticFileHandler, {'path': report_path}),
            (r'/state', StateHandler),
            (r'/stats', StatsTextHandler),
            (r'/stats.json', StatsJsonHandler)
        ]
        settings = {
            'gzip': True
        }

        tornado.web.Application.__init__(self, handlers, **settings)
        self.db = sqlite3.connect('gtbt.db')
        self.last_update = datetime.fromtimestamp(0)
        self.state = None
        self.ensure_table_existance()

    def get_current_state(self):
        if self.state is None:
            return 'unknown'
        return self.state

    def save_current_state(self):
        if self.state is not None:
            cur = self.db.cursor()
            cur.execute('insert into states values (?, ?, ?)', (self.state, self.last_update, datetime.now()))
            self.db.commit()

    def update_state(self, state):
        # some rudimentary validation
        if not (1 <= len(state) <= 20) or not all(x in string.ascii_letters for x in state):
            return

        self.save_current_state()
        if state == 'none':
            self.state = None
        else:
            self.state = state
        self.last_update = datetime.now()
        print('State changed to {}'.format(self.state))

    def get_history(self):
        cur = self.db.cursor()
        cur.execute('select * from states order by start asc')
        row = cur.fetchone()
        while row is not None:
            yield row
            row = cur.fetchone()

    def ensure_table_existance(self):
        cur = self.db.cursor()
        cur.execute('create table if not exists states (state varchar(20), start timestamp, end timestamp)')
        self.db.commit()

    def close(self):
        self.save_current_state()
        self.db.close()


if __name__ == "__main__":
    app = Application()
    app.listen(8888, address='127.0.0.1')
    try:
        tornado.ioloop.IOLoop.instance().start()
    except KeyboardInterrupt:
        app.close()
        print('dying, bye')
