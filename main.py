import pywintypes
from kivy.config import Config

import os

import win32api
import win32con
import win32gui
import win32ui
import win32process
import win32com.client

from kivy.app import App
from kivy.core.window import Window
from kivy.animation import Animation
from kivy.properties import StringProperty, ObjectProperty, NumericProperty, BooleanProperty, ListProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.scatter import Scatter
from kivy.uix.widget import Widget
from win32comext.shell import shell

from hover import HoverBehavior

#######################################
# Kivy Config
#######################################


Config.set('input', 'mouse', 'mouse,disable_multitouch')

#######################################
# Constants
#######################################
# Windows
GW_OWNER = win32con.GW_OWNER
GWL_EXSTYLE = win32con.GWL_EXSTYLE
WS_EX_TOOLWINDOW = win32con.WS_EX_TOOLWINDOW
WS_EX_NOREDIRECTIONBITMAP = 0x00200000
SHGFI_ICON = 0x000000100
SHGFI_ICONLOCATION = 0x000001000
SHIL_EXTRALARGE = 0x00002
SW_MAXIMIZE = win32con.SW_MAXIMIZE
SW_RESTORE = win32con.SW_RESTORE
WPF_RESTORETOMAXIMIZED = win32con.WPF_RESTORETOMAXIMIZED
SW_SHOWMINIMIZED = win32con.SW_SHOWMINIMIZED

# TaskBoard default values
TASK_WIDTH = 100
TASK_HEIGHT = 50
INITIAL_PLACE_HEIGT = 100


#######################################
# Global functions
#######################################

def get_task_list_as_hwnd():
    """Return list of window handles which should be the task.

    The task should match all the following conditions:
        - Visible
        - Non child, which means it does not have the owner window
        - Non untitled system window, which means it is not a window like the property window"""

    # Callback function
    # Append the window handle to the outer scope var 'task_list_as_hwnd', if it should be the task.
    def accumulate_hwnd_for_task(hwnd, extra):
        if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindow(hwnd, GW_OWNER) == 0 \
                and win32gui.GetWindowLong(hwnd, GWL_EXSTYLE) & (WS_EX_NOREDIRECTIONBITMAP | WS_EX_TOOLWINDOW) == 0:
            task_list_as_hwnd.append(hwnd)

    # main logic
    task_list_as_hwnd = []
    win32gui.EnumWindows(accumulate_hwnd_for_task, None)
    return task_list_as_hwnd


def get_icon_from_window(hwnd):
    """Create the icon file in a temp directory for the window handle and return its path.

    Actually, it is not unclear how the Windows API works to retrieve the icon info and save it as icon.
    """
    hicon = win32api.SendMessage(hwnd, win32con.WM_GETICON, win32con.ICON_BIG)
    if hicon == 0:
        hicon = win32api.SendMessage(hwnd, win32con.WM_GETICON, win32con.ICON_SMALL)
    if hicon == 0:
        hicon = win32gui.GetClassLong(hwnd, win32con.GCL_HICON)
    if hicon == 0:
        hicon = win32gui.GetClassLong(hwnd, win32con.GCL_HICONSM)
    if hicon == 0:
        hicon = get_hicon_from_exe(hwnd)
    if hicon == 0:
        return None

    ico_x = win32api.GetSystemMetrics(win32con.SM_CXICON)
    # creating a destination memory DC
    hdc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
    hbmp = win32ui.CreateBitmap()
    hbmp.CreateCompatibleBitmap(hdc, ico_x, ico_x)
    hdc = hdc.CreateCompatibleDC()
    hdc.SelectObject(hbmp)
    hdc.DrawIcon((0, 0), hicon)
    temp_dir = os.getenv("temp")
    file_path = temp_dir + "\Icontemp" + str(hwnd) + ".bmp"
    hbmp.SaveBitmapFile(hdc, file_path)
    return file_path


def get_hicon_from_exe(hwnd):
    tid, pid = win32process.GetWindowThreadProcessId(hwnd)
    hprc = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ, 0, pid)
    path = win32process.GetModuleFileNameEx(hprc, 0)

    ret, info = shell.SHGetFileInfo(path, 0, SHGFI_ICONLOCATION | SHGFI_ICON | SHIL_EXTRALARGE)
    hicon, iicon, dwattr, name, typename = info

    return hicon


def get_exe_path(hwnd):
    tid, pid = win32process.GetWindowThreadProcessId(hwnd)
    hprc = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ, 0, pid)
    path = win32process.GetModuleFileNameEx(hprc, 0)
    return path


#######################################
# Classes
#######################################
class Board(FloatLayout):
    """A board to attach task icons."""

    selecting = BooleanProperty(False)
    select_box = ObjectProperty(None)
    sub_menu = ObjectProperty(None)

    def propose_pos(self):
        try:
            prop_y, prop_x = max([(c.y, c.right) for c in self.children if type(c) == Task])
        except ValueError:
            prop_x, prop_y = 0, 0

        if prop_x + TASK_WIDTH > Window.width:
            prop_x = 0
            prop_y += TASK_HEIGHT

        return prop_x, max(prop_y, INITIAL_PLACE_HEIGT)

    def refresh(self, *args):
        """According to the windows status, add or remove the tasks, and update the task_name."""

        new_hwnd_set = set(get_task_list_as_hwnd())
        for c in filter(lambda x: isinstance(x, Task), self.children[:]):
            if c.window_handle in new_hwnd_set:
                new_hwnd_set.remove(c.window_handle)
                c.task_name = win32gui.GetWindowText(c.window_handle)
            else:
                self.remove_widget(c)

        for wh in new_hwnd_set:
            tsk = Task(window_handle=wh, task_name=win32gui.GetWindowText(wh), icon_source=get_icon_from_window(wh))
            tsk.pos = self.propose_pos()
            self.add_widget(tsk)

    def restart(self, *args):
        """Restart the Task Board"""

        self.clear_widgets([t for t in self.children if isinstance(t, Task)])
        self.refresh()

    def draw_select_box(self, touch):

        # Draw the Select Box
        left = min(touch.x, touch.ox)
        bottom = min(touch.y, touch.oy)
        width = abs(touch.x - touch.ox)
        height = abs(touch.y - touch.oy)

        self.select_box.pos = left, bottom
        self.select_box.size = width, height

        # Select tasks
        for c in filter(lambda x: isinstance(x, Task), self.children):
            if c.collide_widget(self.select_box):
                c.selected = True
            else:
                c.selected = False

    def on_touch_down(self, touch):
        """Return True when clicked on the Board directly."""

        # Depending on what object is clicked, do the right behavior
        for c in filter(lambda x: isinstance(x, Task), self.children[:]):
            if c.collide_point(*touch.pos):
                # If clicking on a unselected task, minimize the select box to select only the one
                if not c.selected:
                    self.select_box = SelectBox(size=(0, 0))
                    self.draw_select_box(touch)
                # If clicking on any task, break without drawing the select box
                return super().on_touch_down(touch)
        else:
            # If clicking on the board, minimize the select box to redraw and deselect all tasks
            self.selecting = True
            self.select_box = SelectBox(size=(0, 0))
            self.add_widget(self.select_box)
            self.draw_select_box(touch)
            return True

    def on_touch_move(self, touch):
        if self.selecting:
            self.draw_select_box(touch)

        for c in filter(lambda x: isinstance(x, Task), self.children[:]):
            if c.selected and not self.selecting and self.children[0] is not c:
                c.x += touch.dx
                c.y += touch.dy

        return super().on_touch_move(touch)

    def on_touch_up(self, touch):

        if touch.is_mouse_scrolling:
            # ToDo: implement zoom function
            return super().on_touch_up(touch)

        # Clean up select box
        if self.selecting:
            self.draw_select_box(touch)
            self.remove_widget(self.select_box)
            self.selecting = False

        for c in filter(lambda x: isinstance(x, Task), self.children[:]):
            if c.collide_point(*touch.pos):
                if touch.opos == touch.pos:
                    if touch.button == 'left':
                        # If it is left_click without move, make it foreground
                        c.set_foreground_task()
                    elif touch.button == 'right':
                        sub_menu = MenuModal(title='Close', func=c.close_task)
                        sub_menu.open()
                break
        else:
            if touch.button == 'right':
                sub_menu = MenuModal(title='Restart', func=self.restart)
                sub_menu.open()
                pass

        return super().on_touch_up(touch)


class SelectBox(Scatter):
    """Represent Select Box, which is used to select the task icons to move them together.

    Note that Scatter grabs the touch."""
    pass


class MenuModal(ModalView):
    # super class's kivy properties
    auto_dismiss = True

    # kivy properties
    title = StringProperty("")
    func = ObjectProperty(None)

    def open(self, *largs):
        """Show the sub menu on the mouse pos.

        See the source code of ModalView for details and differences."""

        if self._window is not None:
            return
        # search window
        self._window = self._search_window()
        if not self._window:
            return
        self._window.add_widget(self)
        self._window.bind(
            # on_resize=self._align_center,
            on_resize=self.dismiss,
            on_keyboard=self._handle_keyboard)
        # self.center = self._window.center
        self.x, self.top = self._window.mouse_pos
        # self.fbind('center', self._align_center)
        # self.fbind('size', self._align_center)
        a = Animation(_anim_alpha=1., d=self._anim_duration)
        a.bind(on_complete=lambda *x: self.dispatch('on_open'))
        a.start(self)
        return


class Task(HoverBehavior, Scatter):
    """An icon representing a window that is displayed on the Windows task bar.

    Note that Scatter grabs the touch.
    """

    # super class's kivy property
    do_rotation = False
    # do_translation = False
    # do_scale = False

    # kivy property
    window_handle = NumericProperty(0)
    task_name = StringProperty(None)
    icon_source = ObjectProperty(None)
    selected = BooleanProperty(False)
    sub_menu = ObjectProperty(None)
    label_task_name = ObjectProperty(None)

    def set_foreground_task(self):
        """Set the task to foreground regardless of the window state."""

        try:
            # Get window status
            placement = win32gui.GetWindowPlacement(self.window_handle)
            # print("placement: ", placement)
            if placement[1] & SW_SHOWMINIMIZED:
                if placement[0] & WPF_RESTORETOMAXIMIZED:
                    # Before minimized, it was maximized
                    win32gui.ShowWindow(self.window_handle, win32con.SW_MAXIMIZE)
                else:
                    # Before minimized, it was not maximized
                    win32gui.ShowWindow(self.window_handle, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(self.window_handle)

        except pywintypes.error:
            pass

    def close_task(self):
        try:
            self.set_foreground_task()
            exe = get_exe_path(self.window_handle)  # type: str

            if exe.casefold().endswith("excel.exe"):
                wsh = win32com.client.Dispatch("WScript.Shell")
                wsh.SendKeys('^{F4}')
            else:
                win32gui.PostMessage(self.window_handle, win32con.WM_CLOSE, 0, 0)

        except pywintypes.error:
            pass

    def show_task_name(self):
        self.label_task_name = TooltipLabel(text=self.task_name)
        if self.parent:
            self.parent.add_widget(self.label_task_name)
            self.label_task_name.pos = self.to_window(*Window.mouse_pos)

    def hide_task_name(self):
        if isinstance(self.label_task_name, Label):
            self.label_task_name.parent.remove_widget(self.label_task_name)
            self.label_task_name = object()

    def on_hover_still(self, *args):
        self.show_task_name()

    def on_hover_around(self, *args):
        self.hide_task_name()

    def on_parent(self, *args):
        if self.parent is None:
            self.hide_task_name()


class TooltipLabel(Label):
    pass


class TaskBoardApp(App):
    def build(self):
        # Config the Window
        Window.maximize()
        Window.bind(focus=self.root.refresh)

        # Attaching task labels on the board.
        self.root.refresh()

        return self.root


#######################################
# Run myself
#######################################

if __name__ == '__main__':
    TaskBoardApp().run()
