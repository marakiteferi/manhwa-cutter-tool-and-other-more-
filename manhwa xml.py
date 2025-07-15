import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import json
from datetime import datetime
import xml.etree.ElementTree as ET
from pathlib import Path
import uuid

# --- Core Logic (SRT Parser is unchanged) ---

def parse_srt_file(filepath):
    """Parses an SRT file, converting timestamps to total seconds (float)."""
    if not filepath:
        raise ValueError("SRT file path is missing.")
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        content = f.read()

    entries = []
    blocks = content.strip().split('\n\n')
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) >= 3:
            try:
                time_line = lines[1].split(' --> ')
                start_time_str = time_line[0].replace(',', '.')
                end_time_str = time_line[1].replace(',', '.')
                start_dt = datetime.strptime(start_time_str, "%H:%M:%S.%f")
                end_dt = datetime.strptime(end_time_str, "%H:%M:%S.%f")
                start_seconds = start_dt.hour * 3600 + start_dt.minute * 60 + start_dt.second + start_dt.microsecond / 1_000_000
                end_seconds = end_dt.hour * 3600 + end_dt.minute * 60 + end_dt.second + end_dt.microsecond / 1_000_000
                entries.append({
                    'start': start_seconds,
                    'end': end_seconds,
                    'text': ' '.join(lines[2:])
                })
            except (ValueError, IndexError):
                print(f"Skipping malformed SRT block: {block}")
                continue
    return entries

# --- XML Generation (Updated for Gapless Timeline) ---

def generate_premiere_xml(subtitles, image_map, image_folder, output_path, frame_rate=30, width=1920, height=1080):
    """Generates a native Premiere Pro compatible XML file with no gaps."""
    
    xmeml = ET.Element("xmeml", version="4")
    sequence = ET.SubElement(xmeml, "sequence", id="seq-1")
    
    sequence.set("TL.SQAudioVisibleBase", "0")
    sequence.set("TL.SQVideoVisibleBase", "0")
    sequence.set("Monitor.ProgramZoomRect", "0 0 1920 1080")
    
    max_duration_seconds = max(entry['end'] for entry in subtitles) if subtitles else 0
    duration_frames = int(max_duration_seconds * frame_rate)
    ET.SubElement(sequence, "duration").text = str(duration_frames)
    
    rate = ET.SubElement(sequence, "rate")
    ET.SubElement(rate, "timebase").text = str(frame_rate)
    ET.SubElement(rate, "ntsc").text = "FALSE"
    
    ET.SubElement(sequence, "name").text = "Automated Manhwa Timeline (Gapless)"
    
    media = ET.SubElement(sequence, "media")
    video = ET.SubElement(media, "video")
    
    v_format = ET.SubElement(video, "format")
    sample_chars = ET.SubElement(v_format, "samplecharacteristics")
    ET.SubElement(sample_chars, "width").text = str(width)
    ET.SubElement(sample_chars, "height").text = str(height)
    
    track = ET.SubElement(video, "track")
    
    # --- Populate Track with Clips (GAPLESS LOGIC) ---
    for i, entry in enumerate(subtitles):
        start_seconds = entry['start']
        
        # 💡 NEW: Determine the end time.
        # If it's the last clip, use its original end time.
        # Otherwise, use the start time of the next clip.
        is_last_clip = (i == len(subtitles) - 1)
        if is_last_clip:
            end_seconds = entry['end']
        else:
            end_seconds = subtitles[i+1]['start']

        # Ensure clip has a non-zero duration
        if end_seconds <= start_seconds:
            continue
            
        start_time_key = datetime.strftime(datetime(1900,1,1) + (datetime.fromtimestamp(start_seconds) - datetime.fromtimestamp(0)), "%H:%M:%S")
        images_for_this_subtitle = image_map.get(start_time_key, [])
        
        for img_name_raw in images_for_this_subtitle:
            img_name = img_name_raw.strip()
            image_path = Path(image_folder) / img_name
            
            if not image_path.exists():
                raise FileNotFoundError(f"Image not found: {image_path}")

            clip_item = ET.SubElement(track, "clipitem", id=f"clip-{uuid.uuid4().hex[:8]}")
            
            ET.SubElement(clip_item, "start").text = str(int(start_seconds * frame_rate))
            ET.SubElement(clip_item, "end").text = str(int(end_seconds * frame_rate))
            ET.SubElement(clip_item, "in").text = "0"
            ET.SubElement(clip_item, "out").text = str(int((end_seconds - start_seconds) * frame_rate))
            
            file_elem = ET.SubElement(clip_item, "file", id=f"file-{uuid.uuid4().hex[:8]}")
            ET.SubElement(file_elem, "name").text = img_name
            ET.SubElement(file_elem, "pathurl").text = image_path.as_uri()
            
            file_rate = ET.SubElement(file_elem, "rate")
            ET.SubElement(file_rate, "timebase").text = str(frame_rate)
            
            file_media = ET.SubElement(file_elem, "media")
            ET.SubElement(file_media, "video")

    tree = ET.ElementTree(xmeml)
    ET.indent(tree, space="  ")
    tree.write(output_path, encoding="utf-8", xml_declaration=True)


# --- GUI (No changes needed here) ---
class AutoEditorApp:
    def __init__(self, master):
        self.master = master
        master.title("Manhwa Premiere Pro XML Generator")
        master.geometry("550x400")
        
        self.style = ttk.Style(master)
        self.style.theme_use('clam') 

        main_frame = ttk.Frame(master, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        self.srt_path = tk.StringVar()
        self.image_folder = tk.StringVar()
        self.json_path = tk.StringVar()
        self.output_path = tk.StringVar()
        self.frame_rate = tk.StringVar(value="30")
        self.width = tk.StringVar(value="1920")
        self.height = tk.StringVar(value="1080")
        
        ttk.Label(main_frame, text="1. Subtitle File (.srt):").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Label(main_frame, text="2. Image Folder:").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Label(main_frame, text="3. Mapping File (.json):").grid(row=2, column=0, sticky="w", pady=2)
        ttk.Label(main_frame, text="4. Output File (.xml):").grid(row=3, column=0, sticky="w", pady=2)
        
        ttk.Label(main_frame, textvariable=self.srt_path, relief="sunken", background="#eee", anchor="w", width=40).grid(row=0, column=1, sticky="ew", pady=2)
        ttk.Label(main_frame, textvariable=self.image_folder, relief="sunken", background="#eee", anchor="w").grid(row=1, column=1, sticky="ew", pady=2)
        ttk.Label(main_frame, textvariable=self.json_path, relief="sunken", background="#eee", anchor="w").grid(row=2, column=1, sticky="ew", pady=2)
        ttk.Label(main_frame, textvariable=self.output_path, relief="sunken", background="#eee", anchor="w").grid(row=3, column=1, sticky="ew", pady=2)

        ttk.Button(main_frame, text="Browse...", command=self.select_srt).grid(row=0, column=2, sticky="ew", padx=(5,0))
        ttk.Button(main_frame, text="Browse...", command=self.select_image_folder).grid(row=1, column=2, sticky="ew", padx=(5,0))
        ttk.Button(main_frame, text="Browse...", command=self.select_json).grid(row=2, column=2, sticky="ew", padx=(5,0))
        ttk.Button(main_frame, text="Save As...", command=self.select_output_path).grid(row=3, column=2, sticky="ew", padx=(5,0))
        
        settings_frame = ttk.LabelFrame(main_frame, text="Timeline Settings", padding="10")
        settings_frame.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(20, 10))
        
        ttk.Label(settings_frame, text="Frame Rate:").pack(side="left", padx=5)
        ttk.Entry(settings_frame, textvariable=self.frame_rate, width=5).pack(side="left")
        ttk.Label(settings_frame, text="Resolution:").pack(side="left", padx=(15, 5))
        ttk.Entry(settings_frame, textvariable=self.width, width=7).pack(side="left")
        ttk.Label(settings_frame, text="x").pack(side="left", padx=2)
        ttk.Entry(settings_frame, textvariable=self.height, width=7).pack(side="left")
        
        ttk.Button(main_frame, text="🚀 Generate Premiere XML", command=self.generate, style='Accent.TButton').grid(row=5, column=0, columnspan=3, sticky="ew", pady=(10,0))
        self.style.configure('Accent.TButton', font=('Helvetica', 12, 'bold'))

    def select_srt(self):
        path = filedialog.askopenfilename(filetypes=[("SRT files", "*.srt"), ("All files", "*.*")])
        if path: self.srt_path.set(path)

    def select_image_folder(self):
        path = filedialog.askdirectory()
        if path: self.image_folder.set(path)

    def select_json(self):
        path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if path: self.json_path.set(path)

    def select_output_path(self):
        path = filedialog.asksaveasfilename(defaultextension=".xml", filetypes=[("Premiere XML files", "*.xml")])
        if path: self.output_path.set(path)

    def generate(self):
        try:
            for path_var in [self.srt_path, self.image_folder, self.json_path, self.output_path]:
                if not path_var.get():
                    raise ValueError("All paths must be selected before generating.")
            
            fps = int(self.frame_rate.get())
            vid_width = int(self.width.get())
            vid_height = int(self.height.get())

            subtitles = parse_srt_file(self.srt_path.get())
            with open(self.json_path.get(), 'r', encoding='utf-8') as f:
                image_map = json.load(f)
            
            generate_premiere_xml(subtitles, image_map, self.image_folder.get(), self.output_path.get(), frame_rate=fps, width=vid_width, height=vid_height)
            
            messagebox.showinfo("Success", f"Premiere Pro XML generated successfully!\n\nFile saved at:\n{self.output_path.get()}")
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred:\n\n{type(e).__name__}: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = AutoEditorApp(root)
    root.mainloop()