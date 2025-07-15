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


class EnhancedSubtitleImageMapper:
    def __init__(self, master):
        self.master = master
        self.master.title("Enhanced Subtitle-Image Mapper v3.0")
        self.master.geometry("1200x800")

        # --- Data Holders ---
        self.srt_path = ""
        self.image_folder = ""
        self.subtitles = []
        self.image_files = []
        self.current_sub_index = 0
        self.current_img_index = 0
        self.mapping = {}
        self.thumbnail_widgets = []

        # --- UI Setup ---
        self.style = ttk.Style(self.master)
        self.style.theme_use('clam')
        self.style.configure("Selected.TFrame", background="#cce5ff") # Highlight color
        self._create_widgets()
        self._bind_keys()
        self._update_ui_state()

    # --- Setup Methods ---
    def _create_widgets(self):
        # Main layout frames
        top_frame = ttk.Frame(self.master, padding="10")
        top_frame.pack(fill=tk.X)
        
        main_paned_window = ttk.PanedWindow(self.master, orient=tk.HORIZONTAL)
        main_paned_window.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # --- Top Frame: File Loading and Saving ---
        ttk.Button(top_frame, text="Load SRT File", command=self.load_srt).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_frame, text="Load Image Folder", command=self.load_images).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_frame, text="Load Existing JSON", command=self.load_mapping).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_frame, text="Export JSON Mapping", command=self.export_mapping).pack(side=tk.RIGHT, padx=5)
        
        self.auto_advance_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(top_frame, text="Auto-Advance Subtitle on Assign", variable=self.auto_advance_var).pack(side=tk.RIGHT, padx=20)

        # --- Left Pane: Subtitles and Assigned Images ---
        left_pane = ttk.Frame(main_paned_window)
        main_paned_window.add(left_pane, weight=1)
        left_pane.grid_rowconfigure(2, weight=1)
        
        self.progress_label = ttk.Label(left_pane, text="Load data to begin", font=("Helvetica", 10, "italic"))
        self.progress_label.pack(fill=tk.X, pady=5, padx=5)
        
        self.subtitle_frame = ttk.Frame(left_pane, padding=10, relief="groove", borderwidth=2)
        self.subtitle_frame.pack(fill=tk.X, pady=10, padx=5)
        self.subtitle_label = ttk.Label(self.subtitle_frame, text="Subtitle content will appear here", wraplength=400, justify='left', font=("Helvetica", 14))
        self.subtitle_label.pack(fill=tk.X)

        nav_frame = ttk.Frame(left_pane)
        nav_frame.pack(pady=5)
        self.prev_sub_btn = ttk.Button(nav_frame, text="◀ Previous Subtitle (Up)", command=self.prev_subtitle)
        self.prev_sub_btn.pack(side=tk.LEFT, padx=5)
        self.next_sub_btn = ttk.Button(nav_frame, text="Next Subtitle (Down) ▶", command=self.next_subtitle)
        self.next_sub_btn.pack(side=tk.LEFT, padx=5)

        assigned_frame = ttk.LabelFrame(left_pane, text="Assigned Images for this Subtitle")
        assigned_frame.pack(fill=tk.BOTH, expand=True, pady=10, padx=5)
        self.assigned_listbox = tk.Listbox(assigned_frame)
        self.assigned_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(assigned_frame, orient="vertical", command=self.assigned_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.assigned_listbox.config(yscrollcommand=scrollbar.set)
        
        ttk.Button(left_pane, text="Clear Assignments for this Subtitle (Delete)", command=self.clear_assignments_for_current).pack(pady=5)

        # --- Middle Pane: Main Image Viewer ---
        middle_pane = ttk.Frame(main_paned_window)
        main_paned_window.add(middle_pane, weight=2)
        middle_pane.grid_rowconfigure(0, weight=1)
        middle_pane.grid_columnconfigure(0, weight=1)

        self.image_panel = ttk.Label(middle_pane, anchor=tk.CENTER)
        self.image_panel.grid(row=0, column=0, sticky="nsew", pady=10)
        
        img_nav_frame = ttk.Frame(middle_pane)
        img_nav_frame.grid(row=1, column=0, sticky="ew")
        img_nav_frame.grid_columnconfigure(1, weight=1)

        self.prev_img_btn = ttk.Button(img_nav_frame, text="◀ (Left)", command=self.prev_image)
        self.prev_img_btn.grid(row=0, column=0, padx=5)
        self.img_nav_label = ttk.Label(img_nav_frame, text="Image 0/0", anchor=tk.CENTER)
        self.img_nav_label.grid(row=0, column=1, sticky="ew")
        self.next_img_btn = ttk.Button(img_nav_frame, text="(Right) ▶", command=self.next_image)
        self.next_img_btn.grid(row=0, column=2, padx=5)

        ttk.Button(img_nav_frame, text="Assign Current Image (Space)", command=self.assign_image).grid(row=1, column=0, columnspan=3, sticky="ew", pady=5)

        # --- Right Pane: Thumbnail Gallery ---
        right_pane = ttk.Frame(main_paned_window)
        main_paned_window.add(right_pane, weight=1)
        
        # Go To Image field
        goto_frame = ttk.Frame(right_pane, padding=(0, 5))
        goto_frame.pack(fill=tk.X)
        ttk.Label(goto_frame, text="Go to Image (name):").pack(side=tk.LEFT)
        self.goto_entry = ttk.Entry(goto_frame)
        self.goto_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.goto_entry.bind("<Return>", self.go_to_image)

        # Canvas for scrollable thumbnails
        thumb_canvas = tk.Canvas(right_pane)
        thumb_scrollbar = ttk.Scrollbar(right_pane, orient="vertical", command=thumb_canvas.yview)
        self.thumb_frame = ttk.Frame(thumb_canvas) # This frame holds the thumbnails
        
        self.thumb_frame.bind("<Configure>", lambda e: thumb_canvas.configure(scrollregion=thumb_canvas.bbox("all")))
        thumb_canvas.create_window((0, 0), window=self.thumb_frame, anchor="nw")
        thumb_canvas.configure(yscrollcommand=thumb_scrollbar.set)

        thumb_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        thumb_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)


    def _bind_keys(self):
        self.master.bind('<Left>', lambda e: self.prev_image())
        self.master.bind('<Right>', lambda e: self.next_image())
        self.master.bind('<Up>', lambda e: self.prev_subtitle())
        self.master.bind('<Down>', lambda e: self.next_subtitle())
        self.master.bind('<space>', lambda e: self.assign_image())
        self.master.bind('<Delete>', lambda e: self.clear_assignments_for_current())

    def _update_ui_state(self):
        srt_loaded = bool(self.subtitles)
        img_loaded = bool(self.image_files)
        
        state = tk.NORMAL if srt_loaded else tk.DISABLED
        self.prev_sub_btn['state'] = state
        self.next_sub_btn['state'] = state
        
        state = tk.NORMAL if img_loaded else tk.DISABLED
        self.prev_img_btn['state'] = state
        self.next_img_btn['state'] = state
        self.goto_entry['state'] = state

        state = tk.NORMAL if srt_loaded and img_loaded else tk.DISABLED
        # self.assign_btn['state'] = state # Assign button is handled by show_image

    # --- File Handling & Data Loading ---
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
                    messagebox.showwarning("No Images", "No valid image files found.")
                    return
                self.current_img_index = 0
                self.show_image()
                self.populate_thumbnails()
                self._update_ui_state()
            except Exception as e:
                messagebox.showerror("Error Loading Images", f"An error occurred: {e}")

    def populate_thumbnails(self):
        # Clear existing thumbnails
        for widget in self.thumb_frame.winfo_children():
            widget.destroy()
        self.thumbnail_widgets = []

        for index, filename in enumerate(self.image_files):
            try:
                img_path = os.path.join(self.image_folder, filename)
                img = Image.open(img_path)
                img.thumbnail((100, 100))
                img_tk = ImageTk.PhotoImage(img)

                thumb_label = ttk.Label(self.thumb_frame, image=img_tk, text=filename, compound='top', padding=5)
                thumb_label.image = img_tk # Keep reference
                thumb_label.pack(pady=5, padx=5)
                
                # Bind click to both assign and select
                thumb_label.bind("<Button-1>", lambda e, i=index: self.on_thumbnail_click(i))
                self.thumbnail_widgets.append(thumb_label)
            except Exception as e:
                print(f"Could not create thumbnail for {filename}: {e}")

    def load_mapping(self):
        path = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
        if not path: return
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
        if not self.subtitles: return
        
        # Highlight current subtitle
        self.subtitle_frame.configure(style="Selected.TFrame")
        self.master.after(200, lambda: self.subtitle_frame.configure(style="TFrame")) # Flash effect

        sub = self.subtitles[self.current_sub_index]
        time_key = self.get_current_time_key()
        
        self.progress_label.config(text=f"Subtitle {self.current_sub_index + 1} of {len(self.subtitles)}")
        self.subtitle_label.config(text=f"{time_key}\n\n{sub.content.replace('<i>', '').replace('</i>', '')}")
        
        self.assigned_listbox.delete(0, tk.END)
        for img_name in self.mapping.get(time_key, []):
            self.assigned_listbox.insert(tk.END, img_name)
    
    def show_image(self):
        if not self.image_files: return
        self.img_nav_label.config(text=f"Image {self.current_img_index + 1}/{len(self.image_files)}: {self.image_files[self.current_img_index]}")
        
        img_path = os.path.join(self.image_folder, self.image_files[self.current_img_index])
        
        # Update main image viewer
        try:
            img = Image.open(img_path)
            # Calculate aspect ratio to fit the panel
            panel_width = 600
            panel_height = 600
            img.thumbnail((panel_width, panel_height))
            img_tk = ImageTk.PhotoImage(img)
            
            self.image_panel.config(image=img_tk)
            self.image_panel.image = img_tk
        except Exception as e:
            self.image_panel.config(text=f"Error:\nCould not load\n{self.image_files[self.current_img_index]}", image='')
            print(f"Error displaying image: {e}")
        
        # Highlight thumbnail
        for i, thumb in enumerate(self.thumbnail_widgets):
            thumb.configure(relief="flat", borderwidth=0)
        
        if self.thumbnail_widgets:
            current_thumb = self.thumbnail_widgets[self.current_img_index]
            current_thumb.configure(relief="solid", borderwidth=2)


    # --- Core Logic and Navigation ---
    def get_current_time_key(self):
        if not self.subtitles: return ""
        sub = self.subtitles[self.current_sub_index]
        td = sub.start
        total_seconds = int(td.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02}:{minutes:02}:{seconds:02}"

    def assign_image(self, img_index=None):
        if not self.subtitles or not self.image_files: return
        
        if img_index is None:
            img_index = self.current_img_index

        time_key = self.get_current_time_key()
        img_name = self.image_files[img_index]
        
        if time_key not in self.mapping:
            self.mapping[time_key] = []
            
        if img_name not in self.mapping[time_key]:
            self.mapping[time_key].append(img_name)
            self.assigned_listbox.insert(tk.END, img_name)

        if self.auto_advance_var.get():
            self.next_subtitle()

    def on_thumbnail_click(self, index):
        self.current_img_index = index
        self.show_image()
        self.assign_image(index)

    def go_to_image(self, event=None):
        query = self.goto_entry.get()
        if not query: return

        # Find the first filename that contains the query
        for index, filename in enumerate(self.image_files):
            if query in filename:
                self.current_img_index = index
                self.show_image()
                return
        messagebox.showinfo("Not Found", f"No image found containing '{query}'.")

    def clear_assignments_for_current(self):
        time_key = self.get_current_time_key()
        if time_key in self.mapping:
            del self.mapping[time_key]
            self.assigned_listbox.delete(0, tk.END)

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
    app = EnhancedSubtitleImageMapper(root)
    root.mainloop()
