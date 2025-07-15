import customtkinter as ctk
from tkinter import filedialog, Canvas
from PIL import Image, ImageTk
import os

class ManhwaCropper(ctk.CTk):
    def __init__(self):
        super().__init__()

        # ---- Window Setup ----
        self.title("Manhwa Cropper MVP")
        self.geometry("1000x800")
        ctk.set_appearance_mode("Dark")

        # ---- Internal State Variables ----
        self.image_paths = []
        self.current_image_index = 0
        self.current_pil_image = None
        self.display_image_tk = None
        self.crop_counter = 1
        
        # Cropping rectangle coordinates
        self.rect_id = None
        self.crop_start_x = 0
        self.crop_start_y = 0
        self.crop_end_x = 0
        self.crop_end_y = 0

        # ---- UI Widgets ----
        # Main layout: A frame for controls on top, and a canvas for the image below
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Top control frame
        self.control_frame = ctk.CTkFrame(self)
        self.control_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        self.load_button = ctk.CTkButton(self.control_frame, text="Load Images", command=self.load_images)
        self.load_button.pack(side="left", padx=5)

        self.prev_button = ctk.CTkButton(self.control_frame, text="< Prev", command=self.prev_image, state="disabled")
        self.prev_button.pack(side="left", padx=5)

        self.next_button = ctk.CTkButton(self.control_frame, text="Next >", command=self.next_image, state="disabled")
        self.next_button.pack(side="left", padx=5)
        
        self.status_label = ctk.CTkLabel(self.control_frame, text="Load a chapter to begin...", anchor="w")
        self.status_label.pack(side="left", padx=10, fill="x", expand=True)

        # Canvas for displaying the image and cropping
        self.canvas = Canvas(self, bg="gray20", highlightthickness=0)
        self.canvas.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

        # ---- Bindings ----
        # Mouse bindings for drawing the crop rectangle
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_press)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_release)

        # Keyboard shortcuts
        self.bind("<Left>", lambda event: self.prev_image())
        self.bind("<Right>", lambda event: self.next_image())
        self.bind("<Control-s>", lambda event: self.save_crop()) # Ctrl+S to save

    def load_images(self):
        """Opens a file dialog to select multiple images and loads them."""
        # Ask for image files (PNG, JPG, etc.)
        self.image_paths = filedialog.askopenfilenames(
            title="Select Manhwa Pages",
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.webp")]
        )
        
        if not self.image_paths:
            return # User cancelled

        self.current_image_index = 0
        self.crop_counter = 1 # Reset counter for new batch
        
        # Create output directory if it doesn't exist
        if not os.path.exists("output"):
            os.makedirs("output")
            
        self.display_current_image()
        self.update_button_states()

    def display_current_image(self):
        """Loads the image from the current path and displays it on the canvas."""
        if not self.image_paths:
            return

        image_path = self.image_paths[self.current_image_index]
        self.current_pil_image = Image.open(image_path)
        
        # Convert the PIL image to a Tkinter-compatible photo image
        self.display_image_tk = ImageTk.PhotoImage(self.current_pil_image)
        
        # Configure canvas to the image size and display it
        self.canvas.config(width=self.display_image_tk.width(), height=self.display_image_tk.height())
        self.canvas.create_image(0, 0, anchor="nw", image=self.display_image_tk)
        
        self.update_status_label()

    def prev_image(self):
        """Navigates to the previous image."""
        if self.current_image_index > 0:
            self.current_image_index -= 1
            self.display_current_image()
            self.update_button_states()

    def next_image(self):
        """Navigates to the next image."""
        if self.current_image_index < len(self.image_paths) - 1:
            self.current_image_index += 1
            self.display_current_image()
            self.update_button_states()

    def on_mouse_press(self, event):
        """Starts drawing the cropping rectangle."""
        self.crop_start_x = event.x
        self.crop_start_y = event.y
        
        # Delete old rectangle if it exists
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        
        # Create a new rectangle
        self.rect_id = self.canvas.create_rectangle(
            self.crop_start_x, self.crop_start_y, self.crop_start_x, self.crop_start_y,
            outline="red", width=2
        )

    def on_mouse_drag(self, event):
        """Updates the rectangle's dimensions as the mouse is dragged."""
        self.crop_end_x = event.x
        self.crop_end_y = event.y
        
        # Update the rectangle on the canvas
        self.canvas.coords(self.rect_id, self.crop_start_x, self.crop_start_y, self.crop_end_x, self.crop_end_y)

    def on_mouse_release(self, event):
        """Finalizes the crop coordinates when the mouse is released."""
        self.crop_end_x = event.x
        self.crop_end_y = event.y
        self.status_label.configure(text=f"Region selected. Press Ctrl+S to save.")

    def save_crop(self):
        """Crops the selected region from the original image and saves it."""
        if not self.current_pil_image or self.rect_id is None:
            self.status_label.configure(text="Error: No image loaded or no region selected.")
            return

        # Ensure coordinates are properly ordered (top-left to bottom-right)
        x1 = min(self.crop_start_x, self.crop_end_x)
        y1 = min(self.crop_start_y, self.crop_end_y)
        x2 = max(self.crop_start_x, self.crop_end_x)
        y2 = max(self.crop_start_y, self.crop_end_y)
        
        # Crop the original PIL image (not the displayed one) for full quality
        cropped_image = self.current_pil_image.crop((x1, y1, x2, y2))
        
        # Save with sequential filename
        save_path = os.path.join("output", f"panel_{self.crop_counter:03d}.png")
        cropped_image.save(save_path, "PNG")
        
        self.status_label.configure(text=f"Saved {os.path.basename(save_path)}!")
        self.crop_counter += 1
        
        # Clear the rectangle from the canvas
        self.canvas.delete(self.rect_id)
        self.rect_id = None
        
    def update_button_states(self):
        """Enable or disable navigation buttons based on the current index."""
        self.prev_button.configure(state="normal" if self.current_image_index > 0 else "disabled")
        self.next_button.configure(state="normal" if self.current_image_index < len(self.image_paths) - 1 else "disabled")

    def update_status_label(self):
        """Updates the top status label with current image info."""
        if not self.image_paths:
            return
        filename = os.path.basename(self.image_paths[self.current_image_index])
        self.status_label.configure(text=f"Viewing: {filename} [{self.current_image_index + 1}/{len(self.image_paths)}]")


if __name__ == "__main__":
    app = ManhwaCropper()
    app.mainloop()