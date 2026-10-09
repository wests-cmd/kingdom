"""Windows desktop input, bound to an exact foreground window and owner approval."""
import os


def validate_input(params):
    action=params.get('action');title=params.get('window_title')
    if not isinstance(title,str) or not title.strip() or len(title)>500: raise ValueError('Supply the exact foreground window title')
    if action=='click':
        if any(type(params.get(name)) is not int or params[name]<0 for name in ('x','y')): raise ValueError('Click coordinates must be nonnegative integers')
    elif action=='type_text':
        text=params.get('text')
        if not isinstance(text,str) or not text or len(text)>4000 or any(ord(char)<32 for char in text):
            raise ValueError('Type at most 4000 printable characters; submit or newline keys require a separate approved action')
    elif action=='key':
        if params.get('key') not in {'enter','tab','escape','backspace','ctrl+a','ctrl+c','ctrl+v','ctrl+s','ctrl+z'}:
            raise ValueError('Unsupported desktop key')
    else: raise ValueError('Choose click, type_text or key')
    return params


def desktop_input(params):
    validate_input(params)
    if os.name!='nt': raise RuntimeError('Native desktop input is currently supported only on Windows with an interactive desktop')
    import ctypes
    from ctypes import wintypes
    user32=ctypes.windll.user32
    user32.GetForegroundWindow.restype=wintypes.HWND
    user32.GetWindowTextW.argtypes=[wintypes.HWND,wintypes.LPWSTR,ctypes.c_int]
    user32.GetWindowRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
    user32.WindowFromPoint.argtypes=[wintypes.POINT]
    user32.WindowFromPoint.restype=wintypes.HWND
    user32.GetAncestor.argtypes=[wintypes.HWND,wintypes.UINT]
    user32.GetAncestor.restype=wintypes.HWND
    window=user32.GetForegroundWindow()
    title=ctypes.create_unicode_buffer(501)
    user32.GetWindowTextW(window,title,501)
    if not window or title.value!=params['window_title']:
        raise PermissionError('Foreground window changed or does not match the approved title; no input was sent')
    def still_focused():
        if user32.GetForegroundWindow()!=window: raise PermissionError('Foreground window changed; input stopped')
    action=params['action']
    if action=='click':
        width,height=user32.GetSystemMetrics(0),user32.GetSystemMetrics(1)
        if params['x']>=width or params['y']>=height: raise ValueError('Click is outside the primary screen')
        rect=wintypes.RECT()
        if not user32.GetWindowRect(window,ctypes.byref(rect)) or not (rect.left<=params['x']<rect.right and rect.top<=params['y']<rect.bottom):
            raise ValueError('Click is outside the approved foreground window')
        target=user32.WindowFromPoint(wintypes.POINT(params['x'],params['y']))
        if user32.GetAncestor(target,2)!=window:raise PermissionError('Another window covers the approved click target')
        still_focused()
        if not user32.SetCursorPos(params['x'],params['y']): raise RuntimeError('Could not position pointer')
        still_focused();user32.mouse_event(0x0002,0,0,0,0);user32.mouse_event(0x0004,0,0,0,0)
    elif action=='key':
        key=params['key'];control=key.startswith('ctrl+')
        code={'enter':0x0D,'tab':0x09,'escape':0x1B,'backspace':0x08}.get(key,ord(key[-1].upper()))
        still_focused()
        if control:user32.keybd_event(0x11,0,0,0)
        try:user32.keybd_event(code,0,0,0);user32.keybd_event(code,0,2,0)
        finally:
            if control:user32.keybd_event(0x11,0,2,0)
    else:
        class KeyboardInput(ctypes.Structure):
            _fields_=[('wVk',wintypes.WORD),('wScan',wintypes.WORD),('dwFlags',wintypes.DWORD),('time',wintypes.DWORD),('dwExtraInfo',ctypes.c_size_t)]
        class MouseInput(ctypes.Structure):
            _fields_=[('dx',wintypes.LONG),('dy',wintypes.LONG),('mouseData',wintypes.DWORD),('dwFlags',wintypes.DWORD),('time',wintypes.DWORD),('dwExtraInfo',ctypes.c_size_t)]
        class InputUnion(ctypes.Union):_fields_=[('ki',KeyboardInput),('mi',MouseInput)]
        class Input(ctypes.Structure):_fields_=[('type',wintypes.DWORD),('data',InputUnion)]
        units=params['text'].encode('utf-16-le')
        for index in range(0,len(units),2):
            still_focused();unit=int.from_bytes(units[index:index+2],'little')
            events=(Input*2)(Input(1,InputUnion(ki=KeyboardInput(0,unit,4,0,0))),Input(1,InputUnion(ki=KeyboardInput(0,unit,6,0,0))))
            if user32.SendInput(2,events,ctypes.sizeof(Input))!=2:raise RuntimeError('Windows rejected input; check application privilege level')
    return {'action':action,'window_title':title.value,'input_sent':True,
            'scope':'Input sent to the approved foreground window; this receipt does not verify the application accepted it or completed the objective'}
