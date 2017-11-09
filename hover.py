"""Hover Behaviour
"""

from kivy.properties import BooleanProperty, ObjectProperty
from kivy.core.window import Window
from kivy.factory import Factory


class HoverBehavior:
    """Kivy behavior to handle mouse hovering on a widget.

    hover:
        True if the mouse is over the widget.

    relative:
        If True, check the mouse position by relative coordination.

    topmost:
        If True, only the topmost widget with HoverBehavior can bet set the 'hover' to True.
    """

    hovered = BooleanProperty(False)
    border_point = ObjectProperty(None)

    topmost = True

    '''Contains the last relevant point received by the Hoverable. This can
    be used in `on_enter` or `on_leave` in order to know where was dispatched the event.
    '''

    def __init__(self, **kwargs):
        Window.bind(mouse_pos=self.on_mouse_pos)
        super().__init__(**kwargs)

    def on_mouse_pos(self, *args):
        if not self.get_root_window():
            return  # do proceed if I'm not displayed <=> If have no parent
        pos = args[1]

        if not self.collide_point(*pos):
            self.hovered = False
            return self.hovered

        for wid in self.walk():
            if wid is not self and issubclass(type(wid), HoverBehavior) and wid.collide_point(*pos):
                self.hovered = False
                return self.hovered

        self.hovered = True
        return self.hovered

        # if self.collide_point(*pos):
        #     for wid in self.walk():
        #         if wid is not self and issubclass(type(wid), HoverBehavior) and wid.collide_point(*pos):
        #             self.hovered = False
        #             break
        #     else:
        #         self.hovered = True
        # else:
        #     self.hovered = False


Factory.register('HoverBehavior', HoverBehavior)

if __name__ == '__main__':
    from kivy.uix.floatlayout import FloatLayout
    from kivy.lang import Builder
    from kivy.uix.label import Label
    from kivy.base import runTouchApp


    class HoverLabel(Label, HoverBehavior):
        def on_hovered(self, *args):
            print("on_hovered", args)

        def on_enter(self, *args):
            print("You are in, through this point", self.border_point)

        def on_leave(self, *args):
            print("You left through this point", self.border_point)


    Builder.load_string('''
<HoverLabel>:
    text: "inside" if self.hovered else "outside"
    pos: 200,200
    size_hint: None, None
    size: 100, 30
    canvas.before:
        Color:
            rgb: 1,0,0
        Rectangle:
            size: self.size
            pos: self.pos
    ''')
    fl = FloatLayout()
    fl.add_widget(HoverLabel())
    runTouchApp(fl)
