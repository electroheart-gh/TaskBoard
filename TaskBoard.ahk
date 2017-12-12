SetTitleMatchMode, 3

MButton::
WinGet, winState, MinMax, TaskBoard
; If minimized then restore.
if (winState = -1) {
WinRestore, TaskBoard
}
WinActivate TaskBoard
