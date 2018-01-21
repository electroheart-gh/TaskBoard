"""Hover Behaviour
    Original code:
        https://gist.github.com/opqopq/15c707dc4cffc2b6455f
"""

from kivy.properties import BooleanProperty, ObjectProperty, Clock, NumericProperty
from kivy.core.window import Window
from kivy.factory import Factory


class HoverBehavior:
    """Kivy behavior to handle mouse hovering on a widget.

    <Property>
    hover:
        True if the mouse is over the widget.

    <Events>
    on_hover_still:
        Fired when hover on the same position for a second.
    on_hover_around:
        Fired when mouse position changed.

    <Not implemented>
    relative:
        If True, check the mouse position by relative coordination.

    topmost:
        If True, only the topmost widget with HoverBehavior can bet set the 'hover' to True.
    """

    hovered = BooleanProperty(False)
    hover_still_time = NumericProperty(0.5)
    hover_timer = ObjectProperty()

    def __init__(self, **kwargs):
        self.register_event_type('on_hover_still')
        self.register_event_type('on_hover_around')
        Window.bind(mouse_pos=self.on_mouse_pos)
        super().__init__(**kwargs)

    def on_mouse_pos(self, *args):
        if not self.get_root_window():
            return  # do proceed if I'm not displayed <=> If have no parent
        pos = args[1]

        # implement tooltip behaviour
        if self.hover_timer:
            Clock.unschedule(self.hover_timer)  # cancel scheduled event since I moved the cursor
        self.dispatch('on_hover_around')  # self.hide_tooltip()  # close if it's opened

        if not self.collide_point(*pos):
            self.hovered = False
            return self.hovered

        for wid in self.walk():
            if wid is not self and issubclass(type(wid), HoverBehavior) and wid.collide_point(*pos):
                self.hovered = False
                return self.hovered

        self.hovered = True
        # implement tooltip behaviour
        self.hover_timer = Clock.schedule_once(self._on_hover_still, self.hover_still_time)

        return self.hovered

    def _on_hover_still(self, *args):
        self.dispatch('on_hover_still')

    def on_hover_still(self, *args):
        pass

    def on_hover_around(self, *args):
        pass


Factory.register('HoverBehavior', HoverBehavior)

if __name__ == '__main__':
    from kivy.uix.floatlayout import FloatLayout
    from kivy.lang import Builder
    from kivy.uix.label import Label
    from kivy.base import runTouchApp


    class HoverLabel(Label, HoverBehavior):
        def on_hovered(self, *args):
            print("on_hovered", args)


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
