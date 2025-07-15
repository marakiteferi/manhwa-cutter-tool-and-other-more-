import customtkinter as ctk
from tkinter import filedialog, Canvas
from PIL import Image, ImageTk
import os
import cv2  # OpenCV for image processing
import numpy as np  # NumPy for numerical operations
import copy  # For deep copying states for undo/redo

class ManhwaCropper(ctk.CTk):
    def __init__(self):
        super().__init__()

        # ---- Window Setup ----
        self.title("Manhwa Cropper V2 - Auto-Detect")
        self.geometry("1100x800")
        ctk.set_appearance_mode("Dark")

        # ---- Internal State Variables ----
        self.image_paths = []
        self.current_image_index = 0
        self.crop_counter = 1
        self.output_directory = None
        self.selections = []
        self.current_rect_id = None
        self.original_pil_image = None
        self.display_image_tk = None
        self.zoom_level = 1.0
        self.image_x, self.image_y = 0, 0
        self.pan_start_x, self.pan_start_y = 0, 0

        # Undo/Redo State
        self.undo_stack = []
        self.redo_stack = []

        # ---- UI Widgets ----
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.control_frame = ctk.CTkFrame(self)
        self.control_frame.grid(row=0, column=0, columnspan=2, padx=10, pady=10, sticky="ew")

        # UI Buttons
        self.detect_button = ctk.CTkButton(self.control_frame, text="Auto-Detect Panels", command=self.run_auto_detect)
        self.detect_button.pack(side="left", padx=5)
        self.undo_button = ctk.CTkButton(self.control_frame, text="Undo (Ctrl+Z)", command=self.undo_action, state="disabled")
        self.undo_button.pack(side="left", padx=5)
        self.redo_button = ctk.CTkButton(self.control_frame, text="Redo (Ctrl+Y)", command=self.redo_action, state="disabled")
        self.redo_button.pack(side="left", padx=5)
        self.load_button = ctk.CTkButton(self.control_frame, text="Load Images", command=self.load_images)
        self.load_button.pack(side="left", padx=5)
        self.prev_button = ctk.CTkButton(self.control_frame, text="< Prev (a)", command=self.prev_image, state="disabled")
        self.prev_button.pack(side="left", padx=5)
        self.next_button = ctk.CTkButton(self.control_frame, text="Next (d) >", command=self.next_image, state="disabled")
        self.next_button.pack(side="left", padx=5)
        self.save_button = ctk.CTkButton(self.control_frame, text="Save All (s)", command=self.save_all_crops)
        self.save_button.pack(side="left", padx=5)
        self.clear_button = ctk.CTkButton(self.control_frame, text="Clear (Esc)", command=self.clear_selections)
        self.clear_button.pack(side="left", padx=5)
        self.save_loc_button = ctk.CTkButton(self.control_frame, text="Change Save Location", command=self.prompt_for_output_directory)
        self.save_loc_button.pack(side="left", padx=(5, 10))
        self.status_label = ctk.CTkLabel(self.control_frame, text="Load a chapter to begin...", anchor="w")
        self.status_label.pack(side="left", fill="x", expand=True)

        self.canvas = Canvas(self, bg="gray20", highlightthickness=0)
        self.canvas.grid(row=1, column=0, sticky="nsew")
        self.y_slider = ctk.CTkSlider(self, orientation="vertical", command=self.on_y_slider_move)
        self.y_slider.grid(row=1, column=1, sticky="ns")
        self.x_slider = ctk.CTkSlider(self, orientation="horizontal", command=self.on_x_slider_move)
        self.x_slider.grid(row=2, column=0, sticky="ew")
        self.y_slider.grid_remove()
        self.x_slider.grid_remove()

        # ---- Bindings ----
        self.bind("<a>", lambda event: self.prev_image())
        self.bind("<d>", lambda event: self.next_image())
        self.bind("<s>", lambda event: self.save_all_crops())
        self.bind("<Escape>", lambda event: self.clear_selections())
        self.bind("<Control-z>", lambda event: self.undo_action())
        self.bind("<Control-y>", lambda event: self.redo_action())
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_press)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_release)
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel) # This line now works
        self.canvas.bind("<Button-4>", self.on_mouse_wheel)
        self.canvas.bind("<Button-5>", self.on_mouse_wheel)
        self.canvas.bind("<ButtonPress-2>", self.on_pan_start)
        self.canvas.bind("<B2-Motion>", self.on_pan_drag)
        self.canvas.bind("<Configure>", self.on_canvas_resize)

    # --- UNDO/REDO LOGIC ---
    def save_state_for_undo(self):
        self.undo_stack.append(copy.deepcopy(self.selections))
        self.redo_stack.clear()
        self.update_undo_redo_buttons()

    def undo_action(self):
        if not self.undo_stack: return
        self.redo_stack.append(copy.deepcopy(self.selections))
        last_state = self.undo_stack.pop()
        self.selections = last_state
        self.redraw_canvas()
        self.update_undo_redo_buttons()

    def redo_action(self):
        if not self.redo_stack: return
        self.undo_stack.append(copy.deepcopy(self.selections))
        next_state = self.redo_stack.pop()
        self.selections = next_state
        self.redraw_canvas()
        self.update_undo_redo_buttons()

    def update_undo_redo_buttons(self):
        self.undo_button.configure(state="normal" if self.undo_stack else "disabled")
        self.redo_button.configure(state="normal" if self.redo_stack else "disabled")

    # --- AUTO-DETECT LOGIC ---
    def run_auto_detect(self):
        if not self.original_pil_image:
            self.status_label.configure(text="Error: Load an image first.")
            return
        self.save_state_for_undo()
        self.clear_selections(update_status=False, save_state=False)
        self.status_label.configure(text="Detecting panels...")
        self.update()
        open_cv_image = cv2.cvtColor(np.array(self.original_pil_image), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(open_cv_image, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)
        thresh_inv = cv2.bitwise_not(thresh)
        contours, _ = cv2.findContours(thresh_inv, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        detected_boxes = []
        img_area = self.original_pil_image.size[0] * self.original_pil_image.size[1]
        for cnt in contours:
            if cv2.contourArea(cnt) > img_area * 0.001:
                x, y, w, h = cv2.boundingRect(cnt)
                detected_boxes.append((x, y, x + w, y + h))
        detected_boxes.sort(key=lambda b: (b[1], b[0]))
        for box in detected_boxes:
            x1, y1, x2, y2 = box
            canvas_x1 = (x1 * self.zoom_level) + self.image_x
            canvas_y1 = (y1 * self.zoom_level) + self.image_y
            canvas_x2 = (x2 * self.zoom_level) + self.image_x
            canvas_y2 = (y2 * self.zoom_level) + self.image_y
            rect_id = self.canvas.create_rectangle(canvas_x1, canvas_y1, canvas_x2, canvas_y2, outline="red", width=2)
            self.selections.append({'id': rect_id, 'coords': (canvas_x1, canvas_y1, canvas_x2, canvas_y2)})
        self.status_label.configure(text=f"Detected {len(self.selections)} panels.")
        self.update_undo_redo_buttons()
    
    # --- ALL OTHER METHODS ---
    def on_x_slider_move(self, value):
        self.image_x = value
        self.redraw_canvas()

    def on_y_slider_move(self, value):
        self.image_y = value
        self.redraw_canvas()

    def on_canvas_resize(self, event):
        self.update_sliders()
        self.redraw_canvas()

    def update_sliders(self):
        if not self.original_pil_image: return
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        img_width, img_height = self.original_pil_image.size
        new_width = int(img_width * self.zoom_level)
        new_height = int(img_height * self.zoom_level)
        if new_width > canvas_width:
            self.x_slider.grid()
            self.x_slider.configure(from_=canvas_width - new_width, to=0)
            self.x_slider.set(self.image_x)
        else:
            self.x_slider.grid_remove()
        if new_height > canvas_height:
            self.y_slider.grid()
            self.y_slider.configure(from_=canvas_height - new_height, to=0)
            self.y_slider.set(self.image_y)
        else:
            self.y_slider.grid_remove()

    def on_pan_start(self, event):
        self.pan_start_x, self.pan_start_y = event.x - self.image_x, event.y - self.image_y

    def on_pan_drag(self, event):
        self.image_x = event.x - self.pan_start_x
        self.image_y = event.y - self.pan_start_y
        self.redraw_canvas()
        self.x_slider.set(self.image_x)
        self.y_slider.set(self.image_y)

    def on_mouse_wheel(self, event):
        zoom_factor = 1.1
        if event.num == 5 or event.delta == -120: self.zoom_level /= zoom_factor
        if event.num == 4 or event.delta == 120: self.zoom_level *= zoom_factor
        self.zoom_level = max(0.1, self.zoom_level)
        self.redraw_canvas()

    def on_mouse_press(self, event):
        self.crop_start_x, self.crop_start_y = event.x, event.y
        self.current_rect_id = self.canvas.create_rectangle(self.crop_start_x, self.crop_start_y, self.crop_start_x, self.crop_start_y, outline="red", width=2)

    def on_mouse_drag(self, event):
        if self.current_rect_id:
            self.canvas.coords(self.current_rect_id, self.crop_start_x, self.crop_start_y, event.x, event.y)

    def on_mouse_release(self, event):
        if self.current_rect_id:
            self.save_state_for_undo()
            coords = (self.crop_start_x, self.crop_start_y, event.x, event.y)
            self.selections.append({'id': self.current_rect_id, 'coords': coords})
            self.current_rect_id = None
            self.status_label.configure(text=f"{len(self.selections)} region(s) selected.")
            self.update_undo_redo_buttons()

    def redraw_canvas(self):
        if not self.original_pil_image: return
        self.canvas.delete("all")
        img_width, img_height = self.original_pil_image.size
        new_width = int(img_width * self.zoom_level)
        new_height = int(img_height * self.zoom_level)
        resized_image = self.original_pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        self.display_image_tk = ImageTk.PhotoImage(resized_image)
        self.canvas.create_image(self.image_x, self.image_y, anchor="nw", image=self.display_image_tk)
        for selection in self.selections:
            rect_id = self.canvas.create_rectangle(*selection['coords'], outline="red", width=2)
            selection['id'] = rect_id
        self.update_sliders()

    def clear_selections(self, update_status=True, save_state=True):
        if save_state and self.selections:
            self.save_state_for_undo()
        for selection in self.selections:
            self.canvas.delete(selection['id'])
        self.selections.clear()
        if update_status:
            self.status_label.configure(text="Selections cleared.")
        self.update_undo_redo_buttons()
    
    def save_all_crops(self):
        if not self.selections:
            self.status_label.configure(text="No regions selected to save.")
            return
        if not self.output_directory and not self.prompt_for_output_directory():
            return
        saved_count = 0
        for selection in self.selections:
            coords = selection['coords']
            x1 = (min(coords[0], coords[2]) - self.image_x) / self.zoom_level
            y1 = (min(coords[1], coords[3]) - self.image_y) / self.zoom_level
            x2 = (max(coords[0], coords[2]) - self.image_x) / self.zoom_level
            y2 = (max(coords[1], coords[3]) - self.image_y) / self.zoom_level
            cropped_image = self.original_pil_image.crop((x1, y1, x2, y2))
            save_path = os.path.join(self.output_directory, f"panel_{self.crop_counter:03d}.png")
            cropped_image.save(save_path, "PNG")
            self.crop_counter += 1
            saved_count += 1
        self.status_label.configure(text=f"Saved {saved_count} panels!")
        self.clear_selections(update_status=False, save_state=True)

    def prompt_for_output_directory(self):
        path = filedialog.askdirectory(title="Select Output Folder")
        if path:
            self.output_directory = path
            self.status_label.configure(text=f"Saving panels to: {self.output_directory}")
        return path

    def load_images(self):
        image_paths = filedialog.askopenfilenames(title="Select Manhwa Pages", filetypes=[("Image Files", "*.png *.jpg *.jpeg *.webp")])
        if not image_paths: return
        self.image_paths = image_paths
        self.current_image_index = 0
        self.crop_counter = 1
        if not self.output_directory and not self.prompt_for_output_directory():
            self.image_paths = []
            return
        self.load_and_fit_image()
        self.update_button_states()

    def load_and_fit_image(self):
        image_path = self.image_paths[self.current_image_index]
        self.original_pil_image = Image.open(image_path)
        self.after(50, self._fit_image_to_canvas)

    def _fit_image_to_canvas(self):
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        img_width, img_height = self.original_pil_image.size
        width_ratio = canvas_width / img_width
        height_ratio = canvas_height / img_height
        self.zoom_level = min(width_ratio, height_ratio)
        new_width = int(img_width * self.zoom_level)
        new_height = int(img_height * self.zoom_level)
        self.image_x = (canvas_width - new_width) / 2
        self.image_y = (canvas_height - new_height) / 2
        self.redraw_canvas()
        self.update_status_label()

    def next_image(self):
        if self.current_image_index < len(self.image_paths) - 1:
            self.clear_selections(update_status=False, save_state=False)
            self.undo_stack.clear()
            self.redo_stack.clear()
            self.update_undo_redo_buttons()
            self.current_image_index += 1
            self.load_and_fit_image()
            self.update_button_states()

    def prev_image(self):
        if self.current_image_index > 0:
            self.clear_selections(update_status=False, save_state=False)
            self.undo_stack.clear()
            self.redo_stack.clear()
            self.update_undo_redo_buttons()
            self.current_image_index -= 1
            self.load_and_fit_image()
            self.update_button_states()

    def update_button_states(self):
        self.prev_button.configure(state="normal" if self.current_image_index > 0 else "disabled")
        self.next_button.configure(state="normal" if self.current_image_index < len(self.image_paths) - 1 else "disabled")

    def update_status_label(self):
        if not self.image_paths: return
        filename = os.path.basename(self.image_paths[self.current_image_index])
        self.status_label.configure(text=f"Viewing: {filename} [{self.current_image_index + 1}/{len(self.image_paths)}]")

if __name__ == "__main__":
    app = ManhwaCropper()
    app.mainloop()