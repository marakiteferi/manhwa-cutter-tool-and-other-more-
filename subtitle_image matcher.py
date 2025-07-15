import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import re

# --- Dependency Checks ---
try:
    from PIL import Image, ImageTk
except ImportError:
    messagebox.showerror("Missing Dependency", "The 'Pillow' module is not installed. Please run:\n\n    pip install Pillow")
    exit(1)

try:
    import srt
except ImportError:
    messagebox.showerror("Missing Dependency", "The 'srt' module is not installed. Please run:\n\n    pip install srt")
    exit(1)


class SubtitleImageMapper:
    def __init__(self, master):
        self.master = master
        self.master.title("Advanced Subtitle-Image Mapper v2.0")
        self.master.geometry("900x700")

        # --- Data Holders ---
        self.srt_path = ""
        self.image_folder = ""
        self.subtitles = []
        self.image_files = []
        self.current_sub_index = 0
        self.current_img_index = 0
        self.mapping = {}

        # --- UI Setup ---
        self.style = ttk.Style(self.master)
        self.style.theme_use('clam')
        self._create_widgets()
        self._bind_keys()
        self._update_ui_state()

    # --- Setup Methods ---
    def _create_widgets(self):
        # Main layout frames
        top_frame = ttk.Frame(self.master, padding="10")
        top_frame.pack(fill=tk.X)
        main_frame = ttk.Frame(self.master, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_columnconfigure(1, weight=1)
        main_frame.grid_rowconfigure(1, weight=1)

        # --- Top Frame: File Loading and Saving ---
        ttk.Button(top_frame, text="Load SRT File", command=self.load_srt).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_frame, text="Load Image Folder", command=self.load_images).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_frame, text="Load Existing JSON", command=self.load_mapping).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_frame, text="Export JSON Mapping", command=self.export_mapping).pack(side=tk.RIGHT, padx=5)

        # --- Main Frame: Left Side (Subtitles and Assigned Images) ---
        left_pane = ttk.Frame(main_frame)
        left_pane.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 10))
        left_pane.grid_rowconfigure(2, weight=1)
        
        # Subtitle Info
        self.progress_label = ttk.Label(left_pane, text="Load data to begin", font=("Helvetica", 10, "italic"))
        self.progress_label.pack(fill=tk.X, pady=5)
        
        self.subtitle_label = ttk.Label(left_pane, text="Subtitle content will appear here", wraplength=400, justify='left', font=("Helvetica", 12))
        self.subtitle_label.pack(fill=tk.X, pady=10)

        nav_frame = ttk.Frame(left_pane)
        nav_frame.pack(pady=5)
        self.prev_sub_btn = ttk.Button(nav_frame, text="◀ Previous Subtitle (Up)", command=self.prev_subtitle)
        self.prev_sub_btn.pack(side=tk.LEFT, padx=5)
        self.next_sub_btn = ttk.Button(nav_frame, text="Next Subtitle (Down) ▶", command=self.next_subtitle)
        self.next_sub_btn.pack(side=tk.LEFT, padx=5)

        # Assigned Images
        assigned_frame = ttk.LabelFrame(left_pane, text="Assigned Images for this Subtitle")
        assigned_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.assigned_listbox = tk.Listbox(assigned_frame)
        self.assigned_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(assigned_frame, orient="vertical", command=self.assigned_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.assigned_listbox.config(yscrollcommand=scrollbar.set)
        
        ttk.Button(left_pane, text="Clear Assignments for this Subtitle", command=self.clear_assignments_for_current).pack(pady=5)

        # --- Main Frame: Right Side (Image Browser) ---
        right_pane = ttk.Frame(main_frame)
        right_pane.grid(row=0, column=1, rowspan=2, sticky="nsew")
        right_pane.grid_rowconfigure(0, weight=1)

        self.image_panel = ttk.Label(right_pane)
        self.image_panel.grid(row=0, column=0, columnspan=3, sticky="nsew", pady=10)
        
        self.img_nav_label = ttk.Label(right_pane, text="Image 0/0")
        self.img_nav_label.grid(row=1, column=0, columnspan=3, pady=5)
        
        self.prev_img_btn = ttk.Button(right_pane, text="◀ Previous (Left)", command=self.prev_image)
        self.prev_img_btn.grid(row=2, column=0, sticky="ew")
        self.assign_btn = ttk.Button(right_pane, text="Assign Image (Space)", command=self.assign_image)
        self.assign_btn.grid(row=2, column=1, sticky="ew", padx=5)
        self.next_img_btn = ttk.Button(right_pane, text="Next (Right) ▶", command=self.next_image)
        self.next_img_btn.grid(row=2, column=2, sticky="ew")

    def _bind_keys(self):
        """Bind keyboard shortcuts for faster workflow."""
        self.master.bind('<Left>', lambda e: self.prev_image())
        self.master.bind('<Right>', lambda e: self.next_image())
        self.master.bind('<Up>', lambda e: self.prev_subtitle())
        self.master.bind('<Down>', lambda e: self.next_subtitle())
        self.master.bind('<space>', lambda e: self.assign_image())
        self.master.bind('<Delete>', lambda e: self.remove_selected_assignment())

    def _update_ui_state(self):
        """Enable or disable buttons based on loaded data."""
        srt_loaded = bool(self.subtitles)
        img_loaded = bool(self.image_files)
        
        self.prev_sub_btn['state'] = tk.NORMAL if srt_loaded else tk.DISABLED
        self.next_sub_btn['state'] = tk.NORMAL if srt_loaded else tk.DISABLED
        self.prev_img_btn['state'] = tk.NORMAL if img_loaded else tk.DISABLED
        self.next_img_btn['state'] = tk.NORMAL if img_loaded else tk.DISABLED
        self.assign_btn['state'] = tk.NORMAL if srt_loaded and img_loaded else tk.DISABLED

    # --- File Handling ---
    def load_srt(self):
        path = filedialog.askopenfilename(filetypes=[("SRT Files", "*.srt")])
        if path:
            self.srt_path = path
            with open(path, 'r', encoding='utf-8-sig') as f:
                self.subtitles = list(srt.parse(f.read()))
            self.current_sub_index = 0
            self.update_subtitle_display()
            self._update_ui_state()

    def _natural_sort_key(self, s):
        """Key for natural sorting of filenames like '1.jpg', '2.jpg', '10.jpg'."""
        return [int(text) if text.isdigit() else text.lower() for text in re.split(r'([0-9]+)', s)]

    def load_images(self):
        folder = filedialog.askdirectory()
        if folder:
            self.image_folder = folder
            valid_exts = (".png", ".jpg", ".jpeg", ".webp")
            try:
                self.image_files = sorted(
                    [f for f in os.listdir(folder) if f.lower().endswith(valid_exts)],
                    key=self._natural_sort_key
                )
                if not self.image_files:
                    messagebox.showwarning("No Images", "No valid image files found in the selected folder.")
                    return
                self.current_img_index = 0
                self.show_image()
                self._update_ui_state()
            except ValueError:
                 messagebox.showerror("Sort Error", "Could not sort image files numerically. Please ensure filenames are consistently named (e.g., '1.jpg', '2.jpg', etc., or 'panel_01.jpg').")


    def load_mapping(self):
        path = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
        if not path:
            return
        if not self.subtitles:
            messagebox.showwarning("Load SRT First", "Please load an SRT file before loading a mapping.")
            return
        with open(path, 'r', encoding='utf-8') as f:
            self.mapping = json.load(f)
        self.update_subtitle_display()
        messagebox.showinfo("Success", "JSON mapping loaded successfully.")


    def export_mapping(self):
        if not self.mapping:
            messagebox.showwarning("Empty Mapping", "There is nothing to export.")
            return
        save_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON Files", "*.json")])
        if save_path:
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(self.mapping, f, indent=2, sort_keys=True)
            messagebox.showinfo("Exported", f"Mapping saved to {save_path}")

    # --- UI Update and Display ---
    def update_subtitle_display(self):
        if self.current_sub_index < len(self.subtitles):
            sub = self.subtitles[self.current_sub_index]
            time_key = self.get_current_time_key()
            
            # Update progress and subtitle content
            self.progress_label.config(text=f"Subtitle {self.current_sub_index + 1} of {len(self.subtitles)}")
            self.subtitle_label.config(text=f"{time_key}\n\n{sub.content.replace('<i>', '').replace('</i>', '')}")
            
            # Update the listbox with assigned images
            self.assigned_listbox.delete(0, tk.END)
            assigned_images = self.mapping.get(time_key, [])
            for img_name in assigned_images:
                self.assigned_listbox.insert(tk.END, img_name)
        else:
            messagebox.showinfo("Done", "All subtitles processed.")
    
    def show_image(self):
        if not self.image_files: return
        self.img_nav_label.config(text=f"Image {self.current_img_index + 1}/{len(self.image_files)}")
        img_path = os.path.join(self.image_folder, self.image_files[self.current_img_index])
        
        img = Image.open(img_path)
        img.thumbnail((450, 450)) # Maintain aspect ratio
        img_tk = ImageTk.PhotoImage(img)
        
        self.image_panel.config(image=img_tk)
        self.image_panel.image = img_tk # Keep a reference!

    # --- Core Logic and Navigation ---
    def get_current_time_key(self):
        """Generates a robust HH:MM:SS key from a timedelta object."""
        if not self.subtitles: return ""
        sub = self.subtitles[self.current_sub_index]
        td = sub.start
        total_seconds = int(td.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02}:{minutes:02}:{seconds:02}"

    def assign_image(self):
        if not self.subtitles or not self.image_files: return
        
        time_key = self.get_current_time_key()
        img_name = self.image_files[self.current_img_index]
        
        if time_key not in self.mapping:
            self.mapping[time_key] = []
            
        if img_name not in self.mapping[time_key]:
            self.mapping[time_key].append(img_name)
            self.assigned_listbox.insert(tk.END, img_name)

    def remove_selected_assignment(self):
        selected_indices = self.assigned_listbox.curselection()
        if not selected_indices: return

        selected_img_name = self.assigned_listbox.get(selected_indices[0])
        time_key = self.get_current_time_key()

        if time_key in self.mapping and selected_img_name in self.mapping[time_key]:
            self.mapping[time_key].remove(selected_img_name)
            if not self.mapping[time_key]: # If list is now empty, remove the key
                del self.mapping[time_key]
            self.assigned_listbox.delete(selected_indices[0])

    def clear_assignments_for_current(self):
        time_key = self.get_current_time_key()
        if time_key in self.mapping:
            del self.mapping[time_key]
            self.assigned_listbox.delete(0, tk.END)
            messagebox.showinfo("Cleared", f"All assignments cleared for {time_key}")

    def next_image(self):
        if self.current_img_index < len(self.image_files) - 1:
            self.current_img_index += 1
            self.show_image()

    def prev_image(self):
        if self.current_img_index > 0:
            self.current_img_index -= 1
            self.show_image()

    def next_subtitle(self):
        if self.current_sub_index < len(self.subtitles) - 1:
            self.current_sub_index += 1
            self.update_subtitle_display()
    
    def prev_subtitle(self):
        if self.current_sub_index > 0:
            self.current_sub_index -= 1
            self.update_subtitle_display()


if __name__ == '__main__':
    root = tk.Tk()
    app = SubtitleImageMapper(root)
    root.mainloop()