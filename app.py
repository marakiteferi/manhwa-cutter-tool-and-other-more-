import customtkinter as ctk
from tkinter import filedialog, Canvas
from PIL import Image, ImageTk
import os

class ManhwaCropper(ctk.CTk):
    def __init__(self):
        super().__init__()

        # ---- Window Setup ----
        self.title("Manhwa Cropper - Custom Save Location")
        self.geometry("1000x800")
        ctk.set_appearance_mode("Dark")

        # ---- Internal State Variables ----
        self.image_paths = []
        self.current_image_index = 0
        self.crop_counter = 1
        
        # --- NEW: Variable to store the chosen save directory ---
        self.output_directory = None

        # Zoom & Pan State
        self.original_pil_image = None
        self.display_image_tk = None
        self.zoom_level = 1.0
        self.image_x = 0
        self.image_y = 0
        self.pan_start_x = 0
        self.pan_start_y = 0

        # Cropping rectangle
        self.rect_id = None
        self.crop_start_x, self.crop_start_y, self.crop_end_x, self.crop_end_y = 0, 0, 0, 0

        # ---- UI Widgets ----
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.control_frame = ctk.CTkFrame(self)
        self.control_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        self.load_button = ctk.CTkButton(self.control_frame, text="Load Images", command=self.load_images)
        self.load_button.pack(side="left", padx=5)
        self.prev_button = ctk.CTkButton(self.control_frame, text="< Prev", command=self.prev_image, state="disabled")
        self.prev_button.pack(side="left", padx=5)
        self.next_button = ctk.CTkButton(self.control_frame, text="Next >", command=self.next_image, state="disabled")
        self.next_button.pack(side="left", padx=5)
        
        # --- NEW: Button to change the save location ---
        self.save_loc_button = ctk.CTkButton(self.control_frame, text="Change Save Location", command=self.prompt_for_output_directory)
        self.save_loc_button.pack(side="left", padx=(5, 10))

        self.status_label = ctk.CTkLabel(self.control_frame, text="Load a chapter to begin...", anchor="w")
        self.status_label.pack(side="left", fill="x", expand=True)

        self.canvas = Canvas(self, bg="gray20", highlightthickness=0)
        self.canvas.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

        # ---- Bindings ----
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_press)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_release)
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        self.canvas.bind("<Button-4>", self.on_mouse_wheel)
        self.canvas.bind("<Button-5>", self.on_mouse_wheel)
        self.canvas.bind("<ButtonPress-2>", self.on_pan_start)
        self.canvas.bind("<B2-Motion>", self.on_pan_drag)
        self.bind("<Left>", lambda event: self.prev_image())
        self.bind("<Right>", lambda event: self.next_image())
        self.bind("<Control-s>", lambda event: self.save_crop())

    def prompt_for_output_directory(self):
        """Opens a dialog to choose a save directory."""
        path = filedialog.askdirectory(title="Select Output Folder")
        if path:
            self.output_directory = path
            self.status_label.configure(text=f"Saving panels to: {self.output_directory}")
        return path

    def load_images(self):
        """Loads images and prompts for save location if not already set."""
        image_paths = filedialog.askopenfilenames(
            title="Select Manhwa Pages",
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.webp")]
        )
        if not image_paths: return

        self.image_paths = image_paths
        self.current_image_index = 0
        self.crop_counter = 1
        
        # --- MODIFIED: Ask for save location only if it's not set ---
        if not self.output_directory:
            if not self.prompt_for_output_directory():
                self.image_paths = [] # User cancelled folder selection, so unload images
                return

        self.load_and_fit_image()
        self.update_button_states()

    def save_crop(self):
        """Saves the crop to the user-defined directory."""
        if not self.original_pil_image or self.rect_id is None:
            self.status_label.configure(text="Error: No image or region selected.")
            return

        # --- MODIFIED: Check for save directory before saving ---
        if not self.output_directory:
            self.status_label.configure(text="Error: Please set a save location first.")
            if not self.prompt_for_output_directory():
                return # User cancelled

        # Translate canvas coordinates to original image coordinates
        orig_x1 = (min(self.crop_start_x, self.crop_end_x) - self.image_x) / self.zoom_level
        orig_y1 = (min(self.crop_start_y, self.crop_end_y) - self.image_y) / self.zoom_level
        orig_x2 = (max(self.crop_start_x, self.crop_end_x) - self.image_x) / self.zoom_level
        orig_y2 = max(self.crop_start_y, self.crop_end_y)
        orig_y2 = (max(self.crop_start_y, self.crop_end_y) - self.image_y) / self.zoom_level

        cropped_image = self.original_pil_image.crop((orig_x1, orig_y1, orig_x2, orig_y2))
        
        # --- MODIFIED: Use the stored output directory ---
        save_path = os.path.join(self.output_directory, f"panel_{self.crop_counter:03d}.png")
        cropped_image.save(save_path, "PNG")
        
        self.status_label.configure(text=f"Saved {os.path.basename(save_path)}!")
        self.crop_counter += 1
        
        self.redraw_canvas()
        self.rect_id = None

    # --- No changes to the functions below this line ---
    def load_and_fit_image(self):
        image_path = self.image_paths[self.current_image_index]
        self.original_pil_image = Image.open(image_path)
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        if canvas_width == 1 or canvas_height == 1: # Window not ready
            self.after(50, self.load_and_fit_image)
            return
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

    def redraw_canvas(self):
        if not self.original_pil_image: return
        self.canvas.delete("all")
        img_width, img_height = self.original_pil_image.size
        new_width = int(img_width * self.zoom_level)
        new_height = int(img_height * self.zoom_level)
        resized_image = self.original_pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        self.display_image_tk = ImageTk.PhotoImage(resized_image)
        self.canvas.create_image(self.image_x, self.image_y, anchor="nw", image=self.display_image_tk)

    def on_mouse_wheel(self, event):
        zoom_factor = 1.1
        if event.num == 5 or event.delta == -120: self.zoom_level /= zoom_factor
        if event.num == 4 or event.delta == 120: self.zoom_level *= zoom_factor
        self.zoom_level = max(0.1, self.zoom_level)
        self.redraw_canvas()

    def on_pan_start(self, event):
        self.pan_start_x = event.x - self.image_x
        self.pan_start_y = event.y - self.image_y

    def on_pan_drag(self, event):
        self.image_x = event.x - self.pan_start_x
        self.image_y = event.y - self.pan_start_y
        self.redraw_canvas()

    def on_mouse_press(self, event):
        self.crop_start_x, self.crop_start_y = event.x, event.y
        if self.rect_id: self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(self.crop_start_x, self.crop_start_y, self.crop_start_x, self.crop_start_y, outline="red", width=2)

    def on_mouse_drag(self, event):
        self.crop_end_x, self.crop_end_y = event.x, event.y
        self.canvas.coords(self.rect_id, self.crop_start_x, self.crop_start_y, self.crop_end_x, self.crop_end_y)

    def on_mouse_release(self, event):
        self.crop_end_x, self.crop_end_y = event.x, event.y
        self.status_label.configure(text=f"Region selected. Press Ctrl+S to save.")
        
    def prev_image(self):
        if self.current_image_index > 0:
            self.current_image_index -= 1
            self.load_and_fit_image()
            self.update_button_states()

    def next_image(self):
        if self.current_image_index < len(self.image_paths) - 1:
            self.current_image_index += 1
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