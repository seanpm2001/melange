#! /usr/bin/env python
# -*- coding: utf-8 -*-

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA 02110-1301, USA.

import os.path
import thread
from operator import itemgetter

import time
import math

import gobject
gobject.threads_init()

import gtk

import cream
import cream.manifest
import cream.ipc
import cream.gui
import cream.util, cream.util.pywmctrl

from cream.contrib.melange.dialogs import AddWidgetDialog

from widget import Widget
from container import ContainerWindow
from chrome import Background, Thingy
from httpserver import HttpServer
from common import HTTPSERVER_HOST, HTTPSERVER_PORT, \
                   ORIENTATION_HORIZONTAL, ORIENTATION_VERTICAL, \
                   MODE_NORMAL, MODE_EDIT, \
                   STATE_HIDDEN, STATE_MOVE, STATE_NONE, STATE_VISIBLE,\
                   MOVE_TIMESTEP

from container import ORIENTATION_TOP, ORIENTATION_BOTTOM, ORIENTATION_LEFT, ORIENTATION_RIGHT, ORIENTATION_CENTER

class WidgetManager(gobject.GObject):

    __gtype_name__ = 'WidgetManager'
    __gsignals__ = {
        'widget-added': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (Widget,)),
        'widget-removed': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (Widget,)),
        }

    def __init__(self):

        gobject.GObject.__init__(self)

        self.screen_width, self.screen_height = gtk.gdk.screen_width(), gtk.gdk.screen_height()

        self._signal_handlers = {}
        self._widgets = {}


    def keys(self):
        return self._widgets.keys()


    def values(self):
        return self._widgets.values()


    def items(self):
        return self._widgets.items()


    def has_key(self, key):
        return self._widgets.has_key(key)


    def __getitem__(self, key):
        return self._widgets[key]


    def __setitem__(self, key, value):
        self._widgets[key] = value


    def __delitem__(self, key):
        del self._widgets[key]


    def add(self, widget, x=None, y=None):

        self[widget.instance_id] = widget

        self._signal_handlers[widget] = {}

        #self._signal_handlers[widget]['begin-move'] = widget.connect('move-request', self.begin_move_cb)
        self._signal_handlers[widget]['end-move'] = widget.connect('end-move', self.end_move_cb)
        self._signal_handlers[widget]['move-request'] = widget.connect('move-request', self.move_request_cb)
        self._signal_handlers[widget]['remove-request'] = widget.connect('remove-request', self.remove_request_cb)

        if x and y:
            widget.set_position(x, y) # TODO: Use own moving algorithms.

        self.emit('widget-added', widget)


    def end_move_cb(self, widget):
        pass


    def move_request_cb(self, widget, x, y):

        old_x, old_y = widget.get_position()
        new_x = old_x + x
        new_y = old_y + y

        widget.set_position(new_x, new_y)


    def remove_request_cb(self, widget):

        widget.remove()
        self.remove(widget)


    def remove(self, widget):

        del self[widget.instance_id]

        widget.disconnect(self._signal_handlers[widget]['end-move'])
        widget.disconnect(self._signal_handlers[widget]['move-request'])
        widget.disconnect(self._signal_handlers[widget]['remove-request'])

        self.emit('widget-removed', widget)


class ContainerWidgetManager(WidgetManager):

    __gtype_name__ = 'ContainerWidgetManager'
    __gsignals__ = {
        'container-empty': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ())
        }

    def __init__(self, x, y, orientation=ORIENTATION_HORIZONTAL):

        WidgetManager.__init__(self)

        self.display = gtk.gdk.display_get_default()

        self.orientation = orientation
        self.position = (x - 10, y - 10)
        self.size = (100, 100)
        self.stack = []
        self.state = STATE_NONE

        self.container = ContainerWindow()
        self.container.move(*self.position)
        self.container.show_all()

        self.container.connect('begin-move', lambda source: self.begin_move())
        self.container.connect('end-move', lambda source: self.end_move())


    def begin_move(self):

        #def update(source, state):
        #    self.window.set_opacity(1 - state * .5)

        #t = cream.gui.Timeline(500, cream.gui.CURVE_SINE)
        #t.connect('update', update)
        #t.run()

        self.state = STATE_MOVE
        self.move()


    def end_move(self):

        #def update(source, state):
        #    self.window.set_opacity(.5 + state * .5)

        #t = cream.gui.Timeline(500, cream.gui.CURVE_SINE)
        #t.connect('update', update)
        #t.run()

        self.state = STATE_VISIBLE


    def move(self):

        def move_cb(old_x, old_y):
            new_x, new_y = self.display.get_pointer()[1:3]
            move_x = new_x - old_x
            move_y = new_y - old_y

            if self.state == STATE_MOVE:
                x, y = self.get_position()
                res_x = max(10, min(self.screen_width - self.get_size()[0] - 10, x + move_x))
                res_y = max(10, min(self.screen_height - self.get_size()[1] - 10, y + move_y))
                self.set_position(res_x, res_y)
                if res_x == 10:
                    self.container.set_orientation(ORIENTATION_LEFT)
                elif res_y == 10:
                    self.container.set_orientation(ORIENTATION_TOP)
                elif res_x == self.screen_width - self.get_size()[0] - 10:
                    self.container.set_orientation(ORIENTATION_RIGHT)
                elif res_y == self.screen_height - self.get_size()[1] - 10:
                    self.container.set_orientation(ORIENTATION_BOTTOM)
                else:
                    self.container.set_orientation(ORIENTATION_CENTER)
                self.recalculate(animate=False)
                gobject.timeout_add(MOVE_TIMESTEP, move_cb, new_x, new_y)

        move_cb(*self.display.get_pointer()[1:3])


    def get_position(self):
        x, y = self.position
        return (x + 10, y + 10)


    def set_position(self, x, y):
        self.position = (x - 10, y - 10)

        self.container.move(x - 10, y - 10)


    def get_size(self):
        return self.size


    def set_size(self, width, height):

        def resize(width, height):
            try:
                self.container.js_context.resize(width, height)
                return False
            except:
                return True

        self.size = (width, height)
        self.container.set_size_request(width + 20, height + 20)
        self.container.resize(width + 20, height + 20)

        gobject.timeout_add(10, resize, width, height)


    def add(self, widget, x=None, y=None):

        widget.window.set_transient_for(self.container)
        widget.window.present()
        # TODO: Fix stacking order.

        WidgetManager.add(self, widget, x, y)
        self.stack.append(widget)

        self.recalculate(exclude=[widget])


    def remove(self, widget):

        WidgetManager.remove(self, widget)
        self.stack.remove(widget)

        if len(self.stack) <= 1:
            for w in self.stack:
                WidgetManager.remove(self, w)
                self.stack.remove(w)
            self.emit('container-empty')
            return

        self.recalculate()


    def recalculate(self, exclude=[], animate=True):

        width = 0
        height = 0

        for c, widget in enumerate(self.stack):
            if self.orientation == ORIENTATION_HORIZONTAL:
                width += widget.get_size()[0]
                height = max(height, widget.get_size()[1])
            else:
                width = max(width, widget.get_size()[0])
                height += widget.get_size()[1]

        self.set_size(width, height)


        for c, widget in enumerate(self.stack):
            if widget in exclude:
                continue
            x, y = self.get_position()

            for i in xrange(0, c):
                w = self.stack[i]
                if self.orientation == ORIENTATION_HORIZONTAL:
                    x += w.get_size()[0]
                else:
                    y += w.get_size()[1]

            if self.orientation == ORIENTATION_HORIZONTAL:
                y += (height - widget.get_size()[1]) / 2
            else:
                x += (width - widget.get_size()[0]) / 2

            if animate:
                self.move_widget(widget, x, y)
            else:
                widget.set_position(x, y)


    def end_move_cb(self, widget):

        self.recalculate()


    def move_widget(self, widget, x, y):

        def update(source, state):
            widget.set_position((x - start_x) * state + start_x, (y - start_y) * state + start_y)

        start_x, start_y = widget.get_position()

        if (start_x, start_y) == (x, y):
            return

        t = cream.gui.Timeline(400, cream.gui.CURVE_SINE)
        t.connect('update', update)
        t.run()


    def move_request_cb(self, widget, x, y):

        old_x, old_y = widget.get_position()
        new_x = old_x + x
        new_y = old_y + y

        widget.set_position(new_x, new_y)

        w_center = (new_x + (widget.get_size()[0]/2), new_y + (widget.get_size()[1]/2))

        c_x, c_y = self.get_position()
        c_width, c_height = self.get_size()

        if w_center[0] < c_x or w_center[0] > c_x + c_width or w_center[1] < c_y or w_center[1] > c_y + c_height:
            self.remove(widget)
            self.recalculate()
            return



        if self.orientation == ORIENTATION_HORIZONTAL:
            thres = widget.get_position()[0] + widget.get_size()[0] / 2
        else:
            thres = widget.get_position()[1] + widget.get_size()[1] / 2

        i = self.stack.index(widget)

        if i > 0:
            w = self.stack[i-1]

            if self.orientation == ORIENTATION_HORIZONTAL:
                w_thres = w.get_position()[0] + w.get_size()[0] / 2
            else:
                w_thres = w.get_position()[1] + w.get_size()[1] / 2

            if thres < w_thres:
                self.stack.remove(widget)
                self.stack.insert(i-1, widget)
                self.recalculate(exclude=[widget])
        if i < (len(self.stack) - 1):
            w = self.stack[i+1]

            if self.orientation == ORIENTATION_HORIZONTAL:
                w_thres = w.get_position()[0] + w.get_size()[0] / 2
            else:
                w_thres = w.get_position()[1] + w.get_size()[1] / 2

            if thres > w_thres:
                self.stack.remove(widget)
                self.stack.insert(i+1, widget)
                self.recalculate(exclude=[widget])


    def __del__(self):

        self.container.destroy()


class CommonWidgetManager(WidgetManager):

    def __init__(self):

        WidgetManager.__init__(self)

        self.containers = []


    def move_request_cb(self, widget, x, y):

        old_x, old_y = widget.get_position()
        new_x = old_x + x
        new_y = old_y + y

        width, height = widget.get_size()

        centers = {
            'left': (new_x, new_y + height / 2),
            'right': (new_x + width, new_y + height / 2),
            'top': (new_x + width / 2, new_y),
            'bottom': (new_x + width / 2, new_y + height)
        }

        distances = []

        for k, w in self._widgets.iteritems():
            if not w == widget:
                w_name = w.context.manifest['name']
                w_x, w_y = w.get_position()
                w_width, w_height = w.get_size()

                w_centers = {
                    'left': (w_x, w_y + w_height / 2),
                    'right': (w_x + w_width, w_y + w_height / 2),
                    'top': (w_x + w_width / 2, w_y),
                    'bottom': (w_x + w_width / 2, w_y + w_height)
                }

                w_distances = [
                    ('left', int(math.sqrt(abs(w_centers['left'][0] - centers['right'][0]) ** 2 + abs(w_centers['left'][1] - centers['right'][1]) ** 2))),
                    ('right', int(math.sqrt(abs(w_centers['right'][0] - centers['left'][0]) ** 2 + abs(w_centers['right'][1] - centers['left'][1]) ** 2))),
                    ('top', int(math.sqrt(abs(w_centers['top'][0] - centers['bottom'][0]) ** 2 + abs(w_centers['top'][1] - centers['bottom'][1]) ** 2))),
                    ('bottom', int(math.sqrt(abs(w_centers['bottom'][0] - centers['top'][0]) ** 2 + abs(w_centers['bottom'][1] - centers['top'][1]) ** 2)))
                ]

                w_distances.sort(key=lambda x:(x[1], x[0]))
                distances.append((w_distances[0], w))

        if distances:
            distances.sort(key=lambda x:(x[0][1]))
            nearest = distances[0]

            if nearest[0][1] <= 5:
                self.remove(widget)
                self.remove(nearest[1])

                orientation = ORIENTATION_HORIZONTAL
                if nearest[0][0] in ['top', 'bottom']:
                    orientation = ORIENTATION_VERTICAL

                container = ContainerWidgetManager(nearest[1].get_position()[0], nearest[1].get_position()[1], orientation)
                container.connect('widget-removed', lambda manager, widget: self.add(widget))
                container.connect('container-empty', self.container_empty_cb)
                self.containers.append(container)
                container.add(nearest[1])
                container.add(widget)

                widget.set_position(new_x, new_y)
                return

        center = (new_x + (width/2), new_y + (height/2))

        for c in self.containers:
            c_x, c_y = c.get_position()
            c_width, c_height = c.get_size()

            if center[0] > c_x and center[0] < c_x + c_width and center[1] > c_y and center[1] < c_y + c_height:
                self.remove(widget)
                c.add(widget)
                widget.set_position(int(new_x), int(new_y))
                return

        widget.set_position(int(new_x), int(new_y))


    def container_empty_cb(self, container):

        container.container.destroy()
        self.containers.remove(container)
        del container


class Melange(cream.Module, cream.ipc.Object):
    """ The main class of the Melange module. """

    mode = MODE_NORMAL

    def __init__(self):

        cream.Module.__init__(self)

        cream.ipc.Object.__init__(self,
            'org.cream.Melange',
            '/org/cream/Melange'
        )

        self.run_server()

        self.screen = cream.util.pywmctrl.Screen()
        self.display = gtk.gdk.display_get_default()

        # Scan for themes...
        theme_dir = os.path.join(self.context.working_directory, 'themes')
        self.themes = cream.manifest.ManifestDB(theme_dir, type='org.cream.melange.Theme')

        # Scan for widgets...
        self.available_widgets = cream.manifest.ManifestDB('widgets', type='org.cream.melange.Widget')

        self.background = Background()
        self.background.initialize()

        self.widgets = {}
        self.widget_manager = CommonWidgetManager()
        self.widget_manager.connect('widget-added', lambda widget_manager, widget: widget.window.set_transient_for(self.background.window))

        self.add_widget_dialog = AddWidgetDialog()

        self.thingy = Thingy()
        self.thingy.thingy_window.set_transient_for(self.background.window)
        self.thingy.control_window.set_transient_for(self.background.window)

        self.thingy.connect('toggle-overlay', lambda *args: self.toggle_overlay())
        self.thingy.connect('show-settings', lambda *args: self.config.show_dialog())
        self.thingy.connect('show-add-widgets', lambda *args: self.add_widget())

        # Load widgets stored in configuration.
        for widget in self.config.widgets:
            self.load_widget(**widget)

        widgets = sorted(self.available_widgets.by_id.itervalues(), key=itemgetter('name'))
        for widget in widgets:
            if widget.has_key('icon'):
                icon_path = os.path.join(widget['path'], widget['icon'])
                pixbuf = gtk.gdk.pixbuf_new_from_file(icon_path).scale_simple(28, 28, gtk.gdk.INTERP_HYPER)
            else:
                pixbuf = gtk.gdk.pixbuf_new_from_file(os.path.join(self.context.working_directory, 'melange.png')).scale_simple(28, 28, gtk.gdk.INTERP_HYPER)
            #label = "<b>{0}</b>\n{1}".format(w['name'], w['description'])
            label = "<b>{0}</b>\n{1}".format(widget['name'], '')
            #self.liststore.append((w['id'], w['id'], w['name'], w['description'], pb, label))
            self.add_widget_dialog.liststore.append((widget['id'], widget['id'], widget['name'], str(widget['description']), pixbuf, label))

        self.hotkeys.connect('hotkey-activated', self.hotkey_activated_cb)


    def run_server(self):
        server = HttpServer(self)
        thread.start_new_thread(server.run, (HTTPSERVER_HOST, HTTPSERVER_PORT))


    def add_widget(self):

        self.add_widget_dialog.show_all()

        if self.add_widget_dialog.run() == 1:
            selection = self.add_widget_dialog.treeview.get_selection()
            model, iter = selection.get_selected()

            id = model.get_value(iter, 2)
            self.load_widget(id, False, False)
        self.add_widget_dialog.hide()


    def hotkey_activated_cb(self, source, action):

        if action == 'toggle_overlay':
            self.toggle_overlay()


    @cream.ipc.method('', '')
    def debug_memory(self):

        from guppy import hpy
        h = hpy()
        print h.heap()


    @cream.ipc.method('svv', '')
    def load_widget(self, name, x=None, y=None):
        """
        Load a widget with the given name at the specified coordinates (optional).

        :param name: The name of the widget.
        :param x: The x-coordinate.
        :param y: The y-coordinate.

        :type name: `str`
        :type x: `int`
        :type y: `int`
        """

        x, y = int(x), int(y)

        self.messages.debug("Loading widget '%s'..." % name)

        widget = Widget(self.available_widgets.get_by_name(name)._path, backref=self)
        self.widget_manager.add(widget, x, y)
        self.widgets[widget.instance_id] = widget

        widget.show()


    @cream.ipc.method('', 'a{sa{ss}}')
    def list_widgets(self):
        """
        List all available widgets.

        :return: List of widgets.
        :rtype: `list`
        """

        res = {}

        for id, w in self.available_widgets.by_id.iteritems():
            res[id] = {
                'name': w['name'],
                'description': '',
                'path': '',
                'id': w['id'],
                }

        return res


    @cream.ipc.method('', '')
    def toggle_overlay(self):
        """ Show the overlay window. """

        if self.mode == MODE_NORMAL:
            self.mode = MODE_EDIT
            self.thingy.slide_in()
            self.screen.toggle_showing_desktop(True)
            self.background.show()
        else:
            self.mode = MODE_NORMAL
            self.thingy.slide_out()
            self.screen.toggle_showing_desktop(False)
            self.background.hide()


    def quit(self):
        """ Quit the module. """

        self.config.widgets = self.widgets.values()
        cream.Module.quit(self)


if __name__ == '__main__':
    cream.util.set_process_name('melange')
    melange = Melange()
    melange.main()

