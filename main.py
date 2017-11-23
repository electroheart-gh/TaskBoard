from kivy.config import Config

import os

import win32api
import win32con
import win32gui

import win32ui

import win32process

from kivy.app import App
from kivy.core.window import Window
from kivy.properties import StringProperty, ObjectProperty, NumericProperty, BooleanProperty
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.scatter import Scatter
# from kivy.uix.widget import Widget
from win32comext.shell import shell

from hover import HoverBehavior

#######################################
#
#######################################
Config.set('input', 'mouse', 'mouse,multitouch_on_demand')

#######################################
# Constants
#######################################

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

TASK_WIDTH = 100
TASK_HEIGHT = 50


#######################################
# Global functions
#######################################

def get_task_list_as_hwnd():
    """Return list of window handles which should be the task."""

    def accumulate_hwnd_for_task(hwnd, extra):
        """Append the window handle to the outer scope variable, if it should be the task."""
        if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindow(hwnd, GW_OWNER) == 0 \
                and win32gui.GetWindowLong(hwnd, GWL_EXSTYLE) & (WS_EX_NOREDIRECTIONBITMAP | WS_EX_TOOLWINDOW) == 0:
            # title.append(win32gui.GetWindowText(hwnd))
            # print(win32gui.GetWindowText(hwnd))
            task_list_as_hwnd.append(hwnd)

    task_list_as_hwnd = []
    win32gui.EnumWindows(accumulate_hwnd_for_task, None)
    return task_list_as_hwnd


def get_icon_from_window(hwnd):
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
class Board(FloatLayout):
    """A board to attach task labels on."""

    # focus = BooleanProperty(False)
    selecting = BooleanProperty(False)
    select_box = ObjectProperty(None)

    def propose_pos(self):
        try:
            prop_y, prop_x = max([(c.y, c.right) for c in self.children if type(c) == Task])
        except ValueError:
            prop_x, prop_y = 0, 0

        if prop_x + self.children[0].width > Window.width:
            prop_x = 0
            prop_y += self.children[0].height

        return prop_x, max(prop_y, 20)

    def redraw(self, *args):
        """According to the windows status, update the task_name, add or remove the Tasks."""

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

            Window.bind(focus=self.redraw)

    def draw_select_box(self, touch):

        # Initialize Select Box
        # if self.select_box is None:
        #     self.select_box = SelectBox(size=(0, 0))
        #     self.add_widget(self.select_box)

        # Draw Select Box
        left = min(touch.x, touch.ox)
        bottom = min(touch.y, touch.oy)
        width = abs(touch.x - touch.ox)
        height = abs(touch.y - touch.oy)

        self.select_box.pos = left, bottom
        self.select_box.size = width, height

        # Select task
        for c in filter(lambda x: isinstance(x, Task), self.children):
            if c.collide_widget(self.select_box):
                c.selected = True
            else:
                c.selected = False

        return None

    def on_touch_down(self, touch):
        super().on_touch_down(touch)

        # If not clicking on a task icon, initialize select box
        for c in filter(lambda x: isinstance(x, Task), self.children[:]):
            if c.collide_point(*touch.pos):
                if not c.selected:
                    self.select_box = SelectBox(size=(0, 0))
                    self.draw_select_box(touch)
                break
        else:
            self.selecting = True
            self.select_box = SelectBox(size=(0, 0))
            self.add_widget(self.select_box)
            self.draw_select_box(touch)

        return False

    def on_touch_move(self, touch):
        super().on_touch_move(touch)
        if self.selecting:
            self.draw_select_box(touch)
        return False

    def on_touch_up(self, touch):
        super().on_touch_up(touch)

        # Clean up select box
        if self.selecting:
            self.draw_select_box(touch)
            self.remove_widget(self.select_box)
            self.selecting = False

        return False


class SelectBox(Scatter):
    pass


class Task(Scatter, HoverBehavior):
    """A label representing a window to work on."""

    do_rotation = False

    window_handle = NumericProperty(0)
    task_name = StringProperty(None)
    icon_source = ObjectProperty(None)
    selected = BooleanProperty(False)

    # def init_pos(self):
    #     init_x = max([c.right for c in self.parent.children])
    #     init_y = max([c.y for c in self.parent.children])
    #     print("xy: ", init_x, init_y)
    #     return init_x, init_y

    def on_window_handle(self, instance, hwnd):
        print(self.task_name)
        # self.task_name = win32gui.GetWindowText(hwnd)
        # self.icon_source = get_icon_from_window(hwnd)

    def on_task_name(self, instance, hwnd):
        print(self.task_name)

    def on_touch_down(self, touch):
        super().on_touch_down(touch)
        print("touch down on task")

    def on_touch_move(self, touch):
        super().on_touch_move(touch)
        if self.selected and not self.parent.selecting and self.parent.children[0] is not self:
            self.x += touch.dx
            self.y += touch.dy
        return False

    def on_touch_up(self, touch):
        super().on_touch_up(touch)
        if self.collide_point(*touch.pos):
            if touch.is_mouse_scrolling:
                print("touch up!", touch.ox, touch.x, self)
            elif touch.opos == touch.pos:
                # ret = win32gui.BringWindowToTop(self.window_handle)
                # print("ShowWindow: ", ret)
                # ret = win32gui.SetWindowPlacement(self.window_handle, placement)
                # print("SetWindowPlacement: ", ret)

                placement = win32gui.GetWindowPlacement(self.window_handle)
                print("placement: ", placement)
                if placement[1] & SW_SHOWMINIMIZED:
                    if placement[0] & WPF_RESTORETOMAXIMIZED:
                        ret = win32gui.ShowWindow(self.window_handle, win32con.SW_MAXIMIZE)
                    else:
                        ret = win32gui.ShowWindow(self.window_handle, win32con.SW_RESTORE)
                ret = win32gui.SetForegroundWindow(self.window_handle)
                print("SetForegroundWindow: ", ret)

            return True
        else:
            return False


class TaskBoardApp(App):
    def build(self):
        """Assuming Kivy Window and widget tree in kv file initiated first,
        then configure the Window and attach the task labels on the board.
        """
        #
        # Config the Window
        # Window.fullscreen = 'auto'
        Window.top = 300
        Window.left = 100
        Window.size = 1000, 500

        # Window.bind(mouse_pos=lambda x, y: print("on_show"))
        # Window.bind(focus=lambda x, y: print("on_focus"))

        # Attaching task labels on the board.
        self.root.redraw()
        return self.root

        # Attaching task labels on the board.
        # board = self.root  # type: Board

        # Get the task list and attach the labels for them.
        # for wh in get_task_list_as_hwnd():
        #     tsk = Task(window_handle=wh, task_name=win32gui.GetWindowText(wh), icon_source=get_icon_from_window(wh))
        #     tsk.pos = board.propose_pos()
        #     board.add_widget(tsk)
        #
        # return board

    def on_pause(self):
        # save board contents
        print("on_pause")

        return True

    def on_resume(self):
        # get task list again
        # load board contents
        # combine both info
        return True


#######################################
# Others
#######################################

if __name__ == '__main__':
    TaskBoardApp().run()
    # print_window_titles()
    # icon32_from_path(r"C:\Users\JUNJI\tools\MSIAfterburnerSetup\MSIAfterburnerSetup430.exe")
    # icon32_from_path(r"C:\Users\JUNJI\tools\MSIAfterburnerSetup\MSIAfterburnerSetup430.exe")
