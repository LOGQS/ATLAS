# screen_capture.py
import tkinter as tk
from PIL import ImageGrab, ImageTk

class ScreenCaptureOverlay:
    def __init__(self, parent):
        self.parent = parent
        self.root = tk.Toplevel(parent)
        self.root.withdraw()
        self.root.overrideredirect(True)
        self.root.attributes('-alpha', 0.3)
        self.root.attributes('-topmost', True)

        self.screenshot = ImageGrab.grab()
        self.photo = ImageTk.PhotoImage(self.screenshot)

        self.canvas = tk.Canvas(self.root, width=self.screenshot.width, height=self.screenshot.height)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.create_image(0, 0, image=self.photo, anchor=tk.NW)

        self.rect = None
        self.start_x = None
        self.start_y = None

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)

        self.root.geometry(f"{self.screenshot.width}x{self.screenshot.height}+0+0")
        self.root.deiconify()

    def on_press(self, event):
        self.start_x = self.canvas.canvasx(event.x)
        self.start_y = self.canvas.canvasy(event.y)
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline='red')

    def on_drag(self, event):
        cur_x = self.canvas.canvasx(event.x)
        cur_y = self.canvas.canvasy(event.y)
        self.canvas.coords(self.rect, self.start_x, self.start_y, cur_x, cur_y)

    def on_release(self, event):
        end_x = self.canvas.canvasx(event.x)
        end_y = self.canvas.canvasy(event.y)
        x1 = min(self.start_x, end_x)
        y1 = min(self.start_y, end_y)
        x2 = max(self.start_x, end_x)
        y2 = max(self.start_y, end_y)
        self.selected_area = (int(x1), int(y1), int(x2), int(y2))
        self.root.destroy()

    def get_screenshot(self):
        if hasattr(self, 'selected_area'):
            return self.screenshot.crop(self.selected_area)
        return None