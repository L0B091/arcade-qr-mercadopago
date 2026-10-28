"""Activación de créditos: simula la tecla de moneda en el emulador activo.

- Usa SendInput de Windows con scancodes (funciona en pantalla completa, DirectInput, etc.).
- Una cola + hilo trabajador: los créditos nunca se pierden ni se pisan.
- Cada crédito pendiente está guardado en SQLite; al reiniciar se vuelven a aplicar.
En Linux/Mac (pruebas) usa un "presionador" simulado que solo escribe en el log.
"""
import ctypes
import logging
import queue
import sys
import threading
import time
from . import config, db

log = logging.getLogger("credits")

# Nombres de proceso de emuladores conocidos (para traer su ventana al frente)
EMULATORS = ["mame", "snes9x", "fceux", "visualboyadvance", "vba", "project64",
             "epsxe", "pcsx2", "fusion", "kega"]

# Scancodes (set 1) de teclas comunes. Agregá más si hace falta.
SCANCODES = {
    **{str(i): sc for i, sc in zip("1234567890", range(0x02, 0x0C))},
    **dict(zip("qwertyuiop", range(0x10, 0x1A))),
    **dict(zip("asdfghjkl", range(0x1E, 0x27))),
    **dict(zip("zxcvbnm", range(0x2C, 0x33))),
    "space": 0x39, "enter": 0x1C, "tab": 0x0F, "shift": 0x2A, "ctrl": 0x1D,
    "f1": 0x3B, "f2": 0x3C, "f3": 0x3D, "f4": 0x3E, "f5": 0x3F, "f6": 0x40,
}


class FakePresser:
    """Para pruebas fuera de Windows: no aprieta nada, solo registra."""
    def __init__(self):
        self.pressed = []

    def press(self, key):
        self.pressed.append(key)
        log.info("[SIMULADO] tecla %s", key)


class WindowsPresser:
    def __init__(self):
        from ctypes import wintypes
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        ULONG_PTR = ctypes.c_size_t

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                        ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                        ("dwExtraInfo", ULONG_PTR)]

        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                        ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                        ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]

        class _U(ctypes.Union):
            _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]

        class INPUT(ctypes.Structure):
            _anonymous_ = ("u",)
            _fields_ = [("type", wintypes.DWORD), ("u", _U)]

        self.INPUT, self.KEYBDINPUT = INPUT, KEYBDINPUT

    def _send(self, scancode, up):
        KEYEVENTF_SCANCODE, KEYEVENTF_KEYUP = 0x0008, 0x0002
        flags = KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if up else 0)
        inp = self.INPUT(type=1, ki=self.KEYBDINPUT(0, scancode, flags, 0, 0))
        if self.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp)) != 1:
            raise OSError(f"SendInput falló: {ctypes.get_last_error()}")

    def focus_emulator(self):
        """Si la ventana activa no es un emulador, busca una y la trae al frente."""
        try:
            import subprocess
            out = subprocess.run(["tasklist", "/fo", "csv", "/nh"], capture_output=True,
                                 text=True, timeout=5).stdout.lower()
            fg = self.user32.GetForegroundWindow()
            pid = ctypes.c_ulong()
            self.user32.GetWindowThreadProcessId(fg, ctypes.byref(pid))
            for line in out.splitlines():
                cols = [c.strip('"') for c in line.split('","')]
                if len(cols) > 1 and cols[1] == str(pid.value):
                    if any(e in cols[0] for e in EMULATORS):
                        return  # ya está al frente un emulador
            # Buscar ventana visible de un emulador
            found = []
            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

            def cb(hwnd, _):
                if self.user32.IsWindowVisible(hwnd):
                    p = ctypes.c_ulong()
                    self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
                    for line in out.splitlines():
                        cols = [c.strip('"') for c in line.split('","')]
                        if len(cols) > 1 and cols[1] == str(p.value) and \
                                any(e in cols[0] for e in EMULATORS):
                            found.append(hwnd)
                            return False
                return True
            self.user32.EnumWindows(WNDENUMPROC(cb), 0)
            if found:
                # Truco de ALT para que Windows permita cambiar el foco
                self._send(0x38, False); self._send(0x38, True)
                self.user32.SetForegroundWindow(found[0])
                time.sleep(0.3)
        except Exception as e:  # el foco nunca debe frenar el crédito
            log.warning("No pude enfocar el emulador: %s", e)

    def press(self, key):
        sc = SCANCODES.get(key.lower())
        if sc is None:
            raise ValueError(f"Tecla no soportada: {key}")
        if config.FOCUS_EMULATOR:
            self.focus_emulator()
        self._send(sc, False)
        time.sleep(config.KEY_PRESS_DURATION)  # los emuladores leen la tecla por frames
        self._send(sc, True)


class CreditWorker:
    def __init__(self, presser=None):
        self.presser = presser or (WindowsPresser() if sys.platform == "win32" else FakePresser())
        self.q = queue.Queue()
        self.thread = threading.Thread(target=self._run, daemon=True, name="credit-worker")

    def start(self):
        # Reaplicar créditos que quedaron pendientes antes de un reinicio
        for p in db.pending_credits():
            log.info("Reaplicando crédito pendiente del pago %s", p["payment_id"])
            self.q.put((p["payment_id"], p["credits"]))
        self.thread.start()

    def enqueue(self, payment_id, credits=1):
        self.q.put((str(payment_id), int(credits)))

    def _run(self):
        while True:
            payment_id, n = self.q.get()
            for attempt in range(5):
                try:
                    for _ in range(n):
                        self.presser.press(config.CREDIT_KEY)
                        time.sleep(config.KEY_PRESS_DELAY)
                    db.mark_credited(payment_id)
                    log.info("CRÉDITO CARGADO: pago %s (%d crédito/s, tecla %s)",
                             payment_id, n, config.CREDIT_KEY)
                    break
                except Exception as e:
                    log.error("Error cargando crédito %s (intento %d): %s",
                              payment_id, attempt + 1, e)
                    time.sleep(2)
            self.q.task_done()
