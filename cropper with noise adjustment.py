import customtkinter as ctk
from tkinter import filedialog, Canvas, TclError
from PIL import Image, ImageTk
import os
import cv2
import numpy as np
import copy

# --- Settings Window Class (Updated for Real-Time Preview) ---
class DetectionSettingsWindow(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.transient(master)
        self.title("Detection Settings")
        self.geometry("400x280")
        self.app = master
        self.grid_columnconfigure(1, weight=1)

        # Minimum Area Setting
        self.area_label = ctk.CTkLabel(self, text="Minimum Panel Size (%):")
        self.area_label.grid(row=0, column=0, padx=10, pady=(10,0), sticky="w")
        self.area_value_label = ctk.CTkLabel(self, text=f"{self.app.min_area_perc:.1f}")
        self.area_value_label.grid(row=0, column=2, padx=10, pady=(10,0))
        self.area_slider = ctk.CTkSlider(self, from_=0, to=5, command=self.update_area)
        self.area_slider.set(self.app.min_area_perc)
        self.area_slider.grid(row=1, column=0, columnspan=3, padx=10, pady=(0,10), sticky="ew")

        # Minimum Solidity Setting
        self.solidity_label = ctk.CTkLabel(self, text="Required Solidity (%):")
        self.solidity_label.grid(row=2, column=0, padx=10, pady=(10,0), sticky="w")
        self.solidity_value_label = ctk.CTkLabel(self, text=f"{self.app.min_solidity*100:.0f}")
        self.solidity_value_label.grid(row=2, column=2, padx=10, pady=(10,0))
        self.solidity_slider = ctk.CTkSlider(self, from_=0, to=1, command=self.update_solidity)
        self.solidity_slider.set(self.app.min_solidity)
        self.solidity_slider.grid(row=3, column=0, columnspan=3, padx=10, pady=(0,10), sticky="ew")

        # --- NEW: Morphological Closing Setting ---
        self.closing_label = ctk.CTkLabel(self, text="Border Closing (px):")
        self.closing_label.grid(row=4, column=0, padx=10, pady=(10,0), sticky="w")
        self.closing_value_label = ctk.CTkLabel(self, text=f"{self.app.closing_kernel_size}")
        self.closing_value_label.grid(row=4, column=2, padx=10, pady=(10,0))
        self.closing_slider = ctk.CTkSlider(self, from_=1, to=15, number_of_steps=7, command=self.update_closing)
        self.closing_slider.set(self.app.closing_kernel_size)
        self.closing_slider.grid(row=5, column=0, columnspan=3, padx=10, pady=(0,10), sticky="ew")

    def update_area(self, value):
        self.app.min_area_perc = value
        self.area_value_label.configure(text=f"{value:.1f}")
        self.app.request_detection_update()

    def update_solidity(self, value):
        self.app.min_solidity = value
        self.solidity_value_label.configure(text=f"{value*100:.0f}")
        self.app.request_detection_update()

    def update_closing(self, value):
        # Ensure the kernel size is an odd number
        kernel_size = int(value)
        if kernel_size % 2 == 0:
            kernel_size += 1
        self.app.closing_kernel_size = kernel_size
        self.closing_value_label.configure(text=f"{kernel_size}")
        self.app.request_detection_update()

# --- Main Application Class (Updated) ---
class ManhwaCropper(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Manhwa Cropper V7 - Real-Time Preview")
        self.geometry("1400x850")
        ctk.set_appearance_mode("Dark")

        # --- Detection settings state ---
        self.min_area_perc, self.min_solidity, self.max_aspect_ratio = 0.1, 0.85, 25
        self.closing_kernel_size = 3 # NEW: Default kernel size for closing operation
        self.settings_window = None
        self.debounce_timer = None # NEW: For real-time preview

        # --- Other state variables ---
        self.image_paths, self.current_image_index, self.crop_counter = [], 0, 1
        self.output_directory = None
        self.original_pil_image, self.display_image_tk = None, None
        self.zoom_level, self.image_x, self.image_y = 1.0, 0, 0
        self.pan_start_x, self.pan_start_y = 0, 0
        self.undo_stack, self.redo_stack = [], []
        self.selections, self.active_selections = [], []
        self.drag_mode, self.drag_start_pos, self.drag_original_coords = None, None, {}
        self.handle_size, self.new_rect_id = 8, None
        self.detected_panels_per_image, self.batch_review_index = [], 0
        self.in_batch_review_mode = False

        # --- UI Layout ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.toolbar_frame = ctk.CTkFrame(self, width=200)
        self.toolbar_frame.grid(row=0, column=0, rowspan=2, padx=10, pady=10, sticky="ns")
        self.canvas = Canvas(self, bg="gray20", highlightthickness=0)
        self.canvas.grid(row=0, column=1, padx=(0, 10), pady=10, sticky="nsew")
        self.status_frame = ctk.CTkFrame(self, height=30)
        self.status_frame.grid(row=1, column=1, padx=(0, 10), pady=(0, 10), sticky="ew")
        self.status_label = ctk.CTkLabel(self.status_frame, text="Load a chapter to begin...", anchor="w")
        self.status_label.pack(side="left", padx=10)
        self.populate_toolbar()
        self.setup_bindings()

    def populate_toolbar(self):
        # File Operations
        file_label = ctk.CTkLabel(self.toolbar_frame, text="File", font=ctk.CTkFont(weight="bold"))
        file_label.pack(pady=(5, 2), padx=10, anchor="w")
        self.load_button = ctk.CTkButton(self.toolbar_frame, text="Load (Ctrl+O)", command=self.load_images)
        self.load_button.pack(fill="x", padx=10, pady=5)
        self.save_page_button = ctk.CTkButton(self.toolbar_frame, text="Save Page (Ctrl+E)", command=self.save_current_page_crops, state="disabled")
        self.save_page_button.pack(fill="x", padx=10, pady=5)
        # Detection
        detect_label = ctk.CTkLabel(self.toolbar_frame, text="Detection", font=ctk.CTkFont(weight="bold"))
        detect_label.pack(pady=(15, 2), padx=10, anchor="w")
        self.detect_button = ctk.CTkButton(self.toolbar_frame, text="Detect Page (Ctrl+D)", command=self.run_auto_detect_single_page)
        self.detect_button.pack(fill="x", padx=10, pady=5)
        self.batch_detect_btn = ctk.CTkButton(self.toolbar_frame, text="Batch Detect (Ctrl+B)", command=self.batch_detect_all)
        self.batch_detect_btn.pack(fill="x", padx=10, pady=5)
        self.approve_btn = ctk.CTkButton(self.toolbar_frame, text="Approve (Ctrl+S)", command=self.approve_and_next, state="disabled", fg_color="#388E3C", hover_color="#2E7D32")
        self.approve_btn.pack(fill="x", padx=10, pady=5)
        # Editing
        edit_label = ctk.CTkLabel(self.toolbar_frame, text="Editing", font=ctk.CTkFont(weight="bold"))
        edit_label.pack(pady=(15, 2), padx=10, anchor="w")
        self.undo_button = ctk.CTkButton(self.toolbar_frame, text="Undo (Ctrl+Z)", command=self.undo_action, state="disabled")
        self.undo_button.pack(fill="x", padx=10, pady=5)
        self.redo_button = ctk.CTkButton(self.toolbar_frame, text="Redo (Ctrl+Y)", command=self.redo_action, state="disabled")
        self.redo_button.pack(fill="x", padx=10, pady=5)
        self.delete_button = ctk.CTkButton(self.toolbar_frame, text="Delete (Del)", command=self.delete_selection, state="disabled", fg_color="#D32F2F", hover_color="#B71C1C")
        self.delete_button.pack(fill="x", padx=10, pady=5)
        # Navigation
        nav_label = ctk.CTkLabel(self.toolbar_frame, text="Navigation", font=ctk.CTkFont(weight="bold"))
        nav_label.pack(pady=(15, 2), padx=10, anchor="w")
        self.prev_button = ctk.CTkButton(self.toolbar_frame, text="< Prev (A)", command=self.prev_image, state="disabled")
        self.prev_button.pack(fill="x", padx=10, pady=5)
        self.next_button = ctk.CTkButton(self.toolbar_frame, text="Next (D) >", command=self.next_image, state="disabled")
        self.next_button.pack(fill="x", padx=10, pady=5)
        # Settings
        self.settings_button = ctk.CTkButton(self.toolbar_frame, text="Settings (Ctrl+T)", command=self.open_settings)
        self.settings_button.pack(side="bottom", fill="x", padx=10, pady=10)

    def setup_bindings(self):
        self.bind("<Control-o>", lambda e: self.load_images())
        self.bind("<Control-d>", lambda e: self.run_auto_detect_single_page() if self.detect_button.cget("state") == "normal" else None)
        self.bind("<Control-b>", lambda e: self.batch_detect_all() if self.batch_detect_btn.cget("state") == "normal" else None)
        self.bind("<Control-e>", lambda e: self.save_current_page_crops() if self.save_page_button.cget("state") == "normal" else None)
        self.bind("<Control-s>", lambda e: self.approve_and_next() if self.approve_btn.cget("state") == "normal" else None)
        self.bind("<Control-t>", lambda e: self.open_settings())
        self.bind("<Control-z>", lambda e: self.undo_action())
        self.bind("<Control-y>", lambda e: self.redo_action())
        self.bind("<Delete>", lambda e: self.delete_selection())
        self.bind("<Escape>", lambda e: self.clear_selections(save_state=False))
        self.bind("<a>", lambda e: self.prev_image()); self.bind("<d>", lambda e: self.next_image())
        self.bind("<Left>", lambda e: self.prev_image()); self.bind("<Right>", lambda e: self.next_image())
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_press)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_release)
        self.canvas.bind("<Motion>", self.on_mouse_move)
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        self.canvas.bind("<Button-4>", self.on_mouse_wheel); self.canvas.bind("<Button-5>", self.on_mouse_wheel)
        self.canvas.bind("<ButtonPress-2>", self.on_pan_start); self.canvas.bind("<B2-Motion>", self.on_pan_drag)
        self.canvas.bind("<Configure>", self.on_canvas_resize)

    def _run_detection_logic(self, pil_image):
        """Encapsulates the OpenCV detection logic, returns image-space boxes."""
        open_cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(open_cv_image, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)

        # --- NEW: Morphological Closing Operation ---
        # This helps close small gaps in the borders of panels.
        kernel = np.ones((self.closing_kernel_size, self.closing_kernel_size), np.uint8)
        closing = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(closing, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        img_w, img_h = pil_image.size
        min_area = (self.min_area_perc / 100.0) * (img_w * img_h)
        boxes = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < min_area: continue
            x, y, w, h = cv2.boundingRect(cnt)
            if h == 0 or w == 0: continue
            hull = cv2.convexHull(cnt)
            solidity = area / cv2.contourArea(hull) if cv2.contourArea(hull) > 0 else 0
            ar = w / float(h)
            if solidity < self.min_solidity: continue
            if ar > self.max_aspect_ratio or ar < (1 / self.max_aspect_ratio): continue
            boxes.append((x, y, x + w, y + h))
        
        boxes.sort(key=lambda b: (b[1], b[0]))
        return boxes

    def request_detection_update(self):
        """Debounces requests to update the detection preview."""
        if self.debounce_timer:
            self.after_cancel(self.debounce_timer)
        
        # Only run preview if an image is loaded and we are not in batch mode
        if self.original_pil_image and not self.in_batch_review_mode:
             self.debounce_timer = self.after(300, self.run_auto_detect_single_page)

    # --- All other methods are included below without logical changes ---
    def canvas_to_image_coords(self, canvas_coords):
        x1, y1, x2, y2 = canvas_coords
        img_x1 = (x1 - self.image_x) / self.zoom_level
        img_y1 = (y1 - self.image_y) / self.zoom_level
        img_x2 = (x2 - self.image_x) / self.zoom_level
        img_y2 = (y2 - self.image_y) / self.zoom_level
        return (img_x1, img_y1, img_x2, img_y2)

    def image_to_canvas_coords(self, image_coords):
        img_x1, img_y1, img_x2, img_y2 = image_coords
        can_x1 = (img_x1 * self.zoom_level) + self.image_x
        can_y1 = (img_y1 * self.zoom_level) + self.image_y
        can_x2 = (img_x2 * self.zoom_level) + self.image_x
        can_y2 = (img_y2 * self.zoom_level) + self.image_y
        return (can_x1, can_y1, can_x2, can_y2)

    def redraw_canvas(self, event=None):
        if not self.original_pil_image: return
        self.canvas.delete("image")
        iw, ih = self.original_pil_image.size; nw, nh = int(iw * self.zoom_level), int(ih * self.zoom_level)
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        if cw < 2 or ch < 2: return
        self.image_x = min(0, max(cw - nw, self.image_x))
        self.image_y = min(0, max(ch - nh, self.image_y))
        resized_image = self.original_pil_image.resize((nw, nh), Image.Resampling.LANCZOS)
        self.display_image_tk = ImageTk.PhotoImage(resized_image)
        self.canvas.create_image(self.image_x, self.image_y, anchor="nw", image=self.display_image_tk, tags="image")
        for s in self.selections:
            new_canvas_coords = self.image_to_canvas_coords(s['image_coords'])
            self.canvas.coords(s['id'], new_canvas_coords)
        self.update_selection_visuals()

    def get_selection_at_pos(self, x, y):
        for s in reversed(self.selections):
            try:
                x1, y1, x2, y2 = self.canvas.bbox(s['id'])
            except TclError:
                continue
            h = self.handle_size
            if len(self.active_selections) <= 1:
                if abs(x - x1) < h and abs(y - y1) < h: return s, 'resize-nw'
                if abs(x - x2) < h and abs(y - y1) < h: return s, 'resize-ne'
                if abs(x - x1) < h and abs(y - y2) < h: return s, 'resize-sw'
                if abs(x - x2) < h and abs(y - y2) < h: return s, 'resize-se'
                if abs(y - y1) < h and x1 < x < x2: return s, 'resize-n'
                if abs(y - y2) < h and x1 < x < x2: return s, 'resize-s'
                if abs(x - x1) < h and y1 < y < y2: return s, 'resize-w'
                if abs(x - x2) < h and y1 < y < y2: return s, 'resize-e'
            if x1 < x < x2 and y1 < y < y2: return s, 'move'
        return None, None
        
    def on_mouse_press(self, event):
        self.drag_start_pos = (event.x, event.y)
        ctrl_pressed = (event.state & 0x0004) != 0
        selection, mode = self.get_selection_at_pos(event.x, event.y)
        if selection:
            self.save_state_for_undo()
            self.drag_mode = mode
            if not ctrl_pressed and selection not in self.active_selections:
                self.active_selections = [selection]
            elif ctrl_pressed:
                if selection in self.active_selections: self.active_selections.remove(selection)
                else: self.active_selections.append(selection)
            self.drag_original_coords.clear()
            for s in self.active_selections:
                self.drag_original_coords[s['id']] = s['image_coords']
                self.canvas.tag_raise(s['id'])
        else:
            if not ctrl_pressed: self.active_selections.clear()
            self.drag_mode = 'new'
            self.new_rect_id = self.canvas.create_rectangle(event.x, event.y, event.x, event.y, outline="cyan", width=2)
        self.update_selection_visuals()

    def on_mouse_drag(self, event):
        if not self.drag_mode or not self.drag_start_pos: return
        if self.drag_mode == 'new' and self.new_rect_id:
            x1, y1 = self.drag_start_pos
            self.canvas.coords(self.new_rect_id, x1, y1, event.x, event.y)
        elif self.active_selections:
            dx_img = (event.x - self.drag_start_pos[0]) / self.zoom_level
            dy_img = (event.y - self.drag_start_pos[1]) / self.zoom_level
            if self.drag_mode == 'move':
                for s in self.active_selections:
                    ox1, oy1, ox2, oy2 = self.drag_original_coords[s['id']]
                    s['image_coords'] = (ox1 + dx_img, oy1 + dy_img, ox2 + dx_img, oy2 + dy_img)
                    self.canvas.coords(s['id'], self.image_to_canvas_coords(s['image_coords']))
            elif 'resize' in self.drag_mode and len(self.active_selections) == 1:
                s = self.active_selections[0]
                x1, y1, x2, y2 = self.drag_original_coords[s['id']]
                if 'n' in self.drag_mode: y1 += dy_img
                if 's' in self.drag_mode: y2 += dy_img
                if 'w' in self.drag_mode: x1 += dx_img
                if 'e' in self.drag_mode: x2 += dx_img
                s['image_coords'] = (x1, y1, x2, y2)
                self.canvas.coords(s['id'], self.image_to_canvas_coords(s['image_coords']))
    
    def on_mouse_release(self, event):
        if self.drag_mode == 'new' and self.new_rect_id:
            canvas_coords = self.canvas.coords(self.new_rect_id)
            if abs(canvas_coords[0] - canvas_coords[2]) < 5 or abs(canvas_coords[1] - canvas_coords[3]) < 5:
                self.canvas.delete(self.new_rect_id)
            else:
                final_canvas_coords = (min(canvas_coords[0], canvas_coords[2]), min(canvas_coords[1], canvas_coords[3]),
                                       max(canvas_coords[0], canvas_coords[2]), max(canvas_coords[1], canvas_coords[3]))
                self.canvas.coords(self.new_rect_id, final_canvas_coords)
                new_selection = {'id': self.new_rect_id, 'image_coords': self.canvas_to_image_coords(final_canvas_coords)}
                self.selections.append(new_selection)
                self.active_selections = [new_selection]
                self.save_state_for_undo()
        elif self.active_selections:
             for s in self.active_selections:
                 current_canvas_coords = self.canvas.coords(s['id'])
                 normalized_canvas = (min(current_canvas_coords[0], current_canvas_coords[2]), min(current_canvas_coords[1], current_canvas_coords[3]),
                                      max(current_canvas_coords[0], current_canvas_coords[2]), max(current_canvas_coords[1], current_canvas_coords[3]))
                 s['image_coords'] = self.canvas_to_image_coords(normalized_canvas)
             self.update_undo_redo_buttons()
        self.drag_mode = None; self.drag_start_pos = None; self.new_rect_id = None; self.drag_original_coords.clear()
        self.update_selection_visuals()

    def on_mouse_move(self, event):
        if self.drag_mode: return
        selection, mode = self.get_selection_at_pos(event.x, event.y)
        new_cursor = 'left_ptr'
        if len(self.active_selections) > 1 and mode == 'move':
            new_cursor = 'fleur'
        elif len(self.active_selections) == 1 and mode:
             cursors = {'move': 'fleur', 'resize-n': 'sb_v_double_arrow', 'resize-s': 'sb_v_double_arrow',
                        'resize-e': 'sb_h_double_arrow', 'resize-w': 'sb_h_double_arrow',
                        'resize-nw': 'size_nw_se', 'resize-se': 'size_nw_se',
                        'resize-ne': 'size_ne_sw', 'resize-sw': 'size_ne_sw'}
             new_cursor = cursors.get(mode, 'left_ptr')
        if self.canvas['cursor'] != new_cursor:
            self.canvas.config(cursor=new_cursor)
            
    def batch_detect_all(self):
        if not self.image_paths: return
        self.detected_panels_per_image = []
        self.status_label.configure(text="Batch detecting on all pages...")
        self.update()
        original_idx = self.current_image_index
        for idx, path in enumerate(self.image_paths):
            self.status_label.configure(text=f"Detecting on page {idx + 1}/{len(self.image_paths)}...")
            self.update_idletasks()
            temp_image = Image.open(path).convert("RGB")
            boxes = self._run_detection_logic(temp_image)
            self.detected_panels_per_image.append(boxes)
        self.current_image_index = original_idx
        self.in_batch_review_mode = True
        self.batch_review_index = 0
        self.start_batch_review()

    def start_batch_review(self):
        if self.batch_review_index >= len(self.image_paths):
            self.status_label.configure(text="✅ Batch review complete.")
            self.in_batch_review_mode = False
            self.clear_selections(save_state=False)
            self.update_button_states()
            return
        self.current_image_index = self.batch_review_index
        self.load_and_display_image()
        self.update()
        panels_for_this_page = self.detected_panels_per_image[self.batch_review_index]
        for image_coords in panels_for_this_page:
            canvas_coords = self.image_to_canvas_coords(image_coords)
            rect_id = self.canvas.create_rectangle(canvas_coords, outline="red", width=2)
            self.selections.append({'id': rect_id, 'image_coords': image_coords})
        self.active_selections = list(self.selections)
        self.update_selection_visuals()
        self.status_label.configure(text=f"Reviewing page {self.batch_review_index + 1}/{len(self.image_paths)}. Adjust and approve.")
        self.update_button_states()

    def approve_and_next(self):
        if self.approve_btn.cget("state") == "disabled": return
        self.save_current_page_crops(show_status=False)
        self.batch_review_index += 1
        self.start_batch_review()

    def save_current_page_crops(self, show_status=True):
        if not self.selections: return
        self.selections.sort(key=lambda s: (s['image_coords'][1], s['image_coords'][0]))
        if not self.output_directory and not self.prompt_for_output_directory(): return
        saved_count = 0
        for s in self.selections:
            img_w, img_h = self.original_pil_image.size
            x1, y1, x2, y2 = s['image_coords']
            x1, y1, x2, y2 = max(0, x1), max(0, y1), min(img_w, x2), min(img_h, y2)
            if x1 < x2 and y1 < y2:
                cropped_image = self.original_pil_image.crop((x1, y1, x2, y2))
                save_path = os.path.join(self.output_directory, f"panel_{self.crop_counter:03d}.png")
                cropped_image.save(save_path, "PNG")
                self.crop_counter += 1
                saved_count += 1
        if show_status:
            self.status_label.configure(text=f"Saved {saved_count} panels for page {self.current_image_index + 1}.")
    
    def run_auto_detect_single_page(self, event=None):
        if not self.original_pil_image or self.detect_button.cget("state") == "disabled": return
        self.save_state_for_undo()
        self.clear_selections(update_status=False, save_state=False)
        self.status_label.configure(text="Detecting panels on current page...")
        self.update()
        boxes = self._run_detection_logic(self.original_pil_image)
        for image_coords in boxes:
            canvas_coords = self.image_to_canvas_coords(image_coords)
            rect_id = self.canvas.create_rectangle(canvas_coords, outline="red", width=2)
            self.selections.append({'id': rect_id, 'image_coords': image_coords})
        self.status_label.configure(text=f"Detected {len(self.selections)} panels.")
        self.update_undo_redo_buttons()

    def clear_selections(self, update_status=True, save_state=True):
        if save_state and self.selections: self.save_state_for_undo()
        for s in self.selections:
            self.canvas.delete(s['id'])
        self.selections.clear()
        self.active_selections.clear()
        if update_status: self.status_label.configure(text="Selections cleared.")
        self.update_selection_visuals()
        self.update_undo_redo_buttons()
    
    def delete_selection(self):
        if not self.active_selections: return
        self.save_state_for_undo()
        for s in list(self.active_selections):
            self.canvas.delete(s['id'])
            if s in self.selections: self.selections.remove(s)
        self.active_selections.clear()
        self.update_selection_visuals()
        self.update_undo_redo_buttons()

    def load_and_display_image(self):
        self.clear_selections(save_state=False)
        self.undo_stack.clear(); self.redo_stack.clear()
        self.update_undo_redo_buttons()
        path = self.image_paths[self.current_image_index]
        self.original_pil_image = Image.open(path).convert("RGB")
        self.after(10, self.fit_image_to_canvas)
        self.update_button_states()
        self.update_status_label()
        
    def fit_image_to_canvas(self):
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        if not self.original_pil_image or cw < 2 or ch < 2: return
        iw, ih = self.original_pil_image.size
        wr, hr = cw / iw, ch / ih
        self.zoom_level = min(wr, hr)
        self.image_x = (cw - int(iw * self.zoom_level)) / 2
        self.image_y = (ch - int(ih * self.zoom_level)) / 2
        self.redraw_canvas()

    def update_button_states(self):
        has_images = bool(self.image_paths)
        nav_state = "disabled" if self.in_batch_review_mode else "normal"
        self.prev_button.configure(state=nav_state if self.current_image_index > 0 else "disabled")
        self.next_button.configure(state=nav_state if self.current_image_index < len(self.image_paths) - 1 else "disabled")
        self.batch_detect_btn.configure(state="normal" if has_images else "disabled")
        self.detect_button.configure(state="normal" if has_images else "disabled")
        self.approve_btn.configure(state="normal" if self.in_batch_review_mode else "disabled")

    def open_settings(self):
        if self.settings_window is None or not self.settings_window.winfo_exists():
            self.settings_window = DetectionSettingsWindow(self)
        self.settings_window.focus()

    def save_state_for_undo(self): 
        self.undo_stack.append([s.copy() for s in self.selections])
        self.redo_stack.clear()
        self.update_undo_redo_buttons()

    def undo_action(self, event=None):
        if not self.undo_stack: return
        self.redo_stack.append([s.copy() for s in self.selections])
        self.clear_selections(save_state=False, update_status=False)
        self.selections = self.undo_stack.pop()
        for s in self.selections:
            s['id'] = self.canvas.create_rectangle(self.image_to_canvas_coords(s['image_coords']), outline="red", width=2)
        self.redraw_canvas()
        self.update_undo_redo_buttons()

    def redo_action(self, event=None):
        if not self.redo_stack: return
        self.undo_stack.append([s.copy() for s in self.selections])
        self.clear_selections(save_state=False, update_status=False)
        self.selections = self.redo_stack.pop()
        for s in self.selections:
            s['id'] = self.canvas.create_rectangle(self.image_to_canvas_coords(s['image_coords']), outline="red", width=2)
        self.redraw_canvas()
        self.update_undo_redo_buttons()

    def update_undo_redo_buttons(self):
        self.undo_button.configure(state="normal" if self.undo_stack else "disabled")
        self.redo_button.configure(state="normal" if self.redo_stack else "disabled")
        
    def update_selection_visuals(self):
        for s in self.selections:
            if s in self.active_selections:
                self.canvas.itemconfig(s['id'], outline="cyan", width=3)
            else:
                self.canvas.itemconfig(s['id'], outline="red", width=2)
        has_active_selection = len(self.active_selections) > 0
        has_any_selection = len(self.selections) > 0
        self.delete_button.configure(state="normal" if has_active_selection else "disabled")
        self.save_page_button.configure(state="normal" if has_any_selection else "disabled")
        
    def on_canvas_resize(self, event):
        self.fit_image_to_canvas()

    def on_pan_start(self, event):
        self.pan_start_x = event.x - self.image_x
        self.pan_start_y = event.y - self.image_y

    def on_pan_drag(self, event):
        self.image_x = event.x - self.pan_start_x
        self.image_y = event.y - self.pan_start_y
        self.redraw_canvas()

    def on_mouse_wheel(self, event):
        factor = 1.1 if (event.num == 4 or event.delta > 0) else 1/1.1
        self.zoom_level *= factor
        self.redraw_canvas()
        
    def prompt_for_output_directory(self):
        path = filedialog.askdirectory(title="Select Output Folder")
        if path: 
            self.output_directory = path
            return True
        return False

    def load_images(self):
        paths = filedialog.askopenfilenames(title="Select Manhwa Pages", filetypes=[("Image Files", "*.png *.jpg *.jpeg *.webp")])
        if not paths: return
        self.image_paths = sorted(list(paths))
        self.current_image_index = 0
        self.crop_counter = 1
        if not self.output_directory and not self.prompt_for_output_directory():
            self.image_paths = []
            return
        self.in_batch_review_mode = False
        self.load_and_display_image()

    def next_image(self):
        if self.next_button.cget("state") == "disabled": return
        if self.current_image_index < len(self.image_paths) - 1:
            self.current_image_index += 1
            self.load_and_display_image()
            
    def prev_image(self):
        if self.prev_button.cget("state") == "disabled": return
        if self.current_image_index > 0:
            self.current_image_index -= 1
            self.load_and_display_image()
            
    def update_status_label(self):
        if not self.image_paths: return
        fn = os.path.basename(self.image_paths[self.current_image_index])
        if not self.in_batch_review_mode:
            self.status_label.configure(text=f"Viewing: {fn} [{self.current_image_index + 1}/{len(self.image_paths)}]")

if __name__ == "__main__":
    app = ManhwaCropper()
    app.mainloop()