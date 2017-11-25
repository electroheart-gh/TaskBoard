from kivy.config import Config

import os

import win32api
import win32con
import win32gui

import win32ui

import win32process

from kivy.app import App
from kivy.core.window import Window
from kivy.animation import Animation
from kivy.properties import StringProperty, ObjectProperty, NumericProperty, BooleanProperty
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.modalview import ModalView
from kivy.uix.scatter import Scatter
from win32comext.shell import shell

from hover import HoverBehavior

#######################################
# Kivy Config
#######################################
Config.set('input', 'mouse', 'mouse,multitouch_on_demand')

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


#######################################
# Classes
#######################################
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

        if prop_x + self.children[0].width > Window.width:
            prop_x = 0
            prop_y += self.children[0].height

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

            Window.bind(focus=self.refresh)

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
        """Always return True for the time being.

        It does not matter because the Board is on the most background."""

        # When right click on board, do nothing
        if touch.button == 'right':
            return True

        super().on_touch_down(touch)

        # Depending on what object is clicked, do the right behavior
        for c in filter(lambda x: isinstance(x, Task), self.children[:]):
            if c.collide_point(*touch.pos):
                # If clicking on a unselected task, minimize the select box to select only the one
                if not c.selected:
                    self.select_box = SelectBox(size=(0, 0))
                    self.draw_select_box(touch)
                # If clicking on any task, break without drawing the select box
                break
        # If clicking on the board, minimize the select box to redraw and deselect all tasks
        else:
            self.selecting = True
            self.select_box = SelectBox(size=(0, 0))
            self.add_widget(self.select_box)
            self.draw_select_box(touch)

        return True

    def on_touch_move(self, touch):
        super().on_touch_move(touch)
        if self.selecting:
            self.draw_select_box(touch)
        return True

    def on_touch_up(self, touch):

        # When right click on board, show sub menu
        if touch.button == 'right':
            # ToDo: change refresh to redraw
            self.sub_menu = MenuModal(title='Refresh', func=self.refresh)
            self.sub_menu.open()
            return True

        super().on_touch_up(touch)

        # Clean up select box
        if self.selecting:
            self.draw_select_box(touch)
            self.remove_widget(self.select_box)
            self.selecting = False

        return True


class SelectBox(Scatter):
    pass


class Task(Scatter, HoverBehavior):
    """An icon representing a window that is displayed on the Windows task bar."""

    # super class's kivy property
    do_rotation = False

    # kivy property
    window_handle = NumericProperty(0)
    task_name = StringProperty(None)
    icon_source = ObjectProperty(None)
    selected = BooleanProperty(False)

    def on_touch_down(self, touch):
        """Call super class method since nothing to do special.

        Return the result of super() in order to work translation as scatter expected.
        If returning false, translation works for all overlapped widgets."""

        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        """Return False for the left-button move.

        It is because move action should be propagated to all task widgets."""

        super().on_touch_move(touch)

        if self.selected and not self.parent.selecting and self.parent.children[0] is not self:
            # print(self.task_name, self.parent.children[0].task_name)
            self.x += touch.dx
            self.y += touch.dy

        return False

    def on_touch_up(self, touch):
        """Return true when the touch collides me.

        It is because only one task window should be activated at one time."""

        super().on_touch_up(touch)
        if self.collide_point(*touch.pos):
            if touch.is_mouse_scrolling:
                # Nothing to do for future use
                pass
            elif touch.opos == touch.pos:
                # If it is _click_, make it foreground regardless of the window state
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
            return True
        else:
            return False


class TaskBoardApp(App):
    def build(self):
        # Config the Window
        Window.maximize()

        # Attaching task labels on the board.
        self.root.refresh()
        return self.root


#######################################
# Run myself
#######################################

if __name__ == '__main__':
    TaskBoardApp().run()
