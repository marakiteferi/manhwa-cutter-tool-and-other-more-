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
    """
    Parses an SRT file, converting timestamps to total seconds (float).
    Handles timestamps with or without milliseconds.
    """
    if not filepath:
        raise ValueError("SRT file path is missing.")
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        content = f.read()

    entries = []
    blocks = content.strip().split('\n\n')
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) >= 2: # A valid block needs at least a number and a time line.
            try:
                time_line = lines[1].split(' --> ')
                start_time_str = time_line[0].replace(',', '.')
                end_time_str = time_line[1].replace(',', '.')

                # --- FIX: Handle timestamps with or without milliseconds ---
                try:
                    start_dt = datetime.strptime(start_time_str, "%H:%M:%S.%f")
                except ValueError:
                    start_dt = datetime.strptime(start_time_str, "%H:%M:%S")

                try:
                    end_dt = datetime.strptime(end_time_str, "%H:%M:%S.%f")
                except ValueError:
                    end_dt = datetime.strptime(end_time_str, "%H:%M:%S")
                # --- END FIX ---

                start_seconds = start_dt.hour * 3600 + start_dt.minute * 60 + start_dt.second + start_dt.microsecond / 1_000_000
                end_seconds = end_dt.hour * 3600 + end_dt.minute * 60 + end_dt.second + end_dt.microsecond / 1_000_000
                
                # The text part is optional
                text_content = ' '.join(lines[2:]) if len(lines) >= 3 else ""

                entries.append({
                    'start': start_seconds,
                    'end': end_seconds,
                    'text': text_content
                })
            except (ValueError, IndexError) as e:
                print(f"Skipping malformed SRT block: {block} | Error: {e}")
                continue
    return entries

# --- XML Generation (Updated for Sequential Images) ---

# --- XML Generation (Updated for Merging Consecutive Clips) ---

def generate_premiere_xml(subtitles, image_map, image_folder, output_path, frame_rate=30, width=1920, height=1080):
    """
    Generates a native Premiere Pro compatible XML file.
    - When multiple images are assigned to a subtitle, they are placed sequentially.
    - **NEW:** When consecutive subtitles use the *exact same image(s)*, they are merged
      into a single continuous clip to avoid unnecessary cuts.
    """
    
    xmeml = ET.Element("xmeml", version="4")
    sequence = ET.SubElement(xmeml, "sequence", id="seq-1")
    
    sequence.set("TL.SQAudioVisibleBase", "0")
    sequence.set("TL.SQVideoVisible-Base", "0")
    sequence.set("Monitor.ProgramZoomRect", f"0 0 {width} {height}")
    
    max_duration_seconds = max(entry['end'] for entry in subtitles) if subtitles else 0
    duration_frames = int(max_duration_seconds * frame_rate)
    ET.SubElement(sequence, "duration").text = str(duration_frames)
    
    rate = ET.SubElement(sequence, "rate")
    ET.SubElement(rate, "timebase").text = str(frame_rate)
    ET.SubElement(rate, "ntsc").text = "FALSE"
    
    ET.SubElement(sequence, "name").text = "Automated Manhwa Timeline (Merged)"
    
    media = ET.SubElement(sequence, "media")
    video = ET.SubElement(media, "video")
    
    v_format = ET.SubElement(video, "format")
    sample_chars = ET.SubElement(v_format, "samplecharacteristics")
    ET.SubElement(sample_chars, "width").text = str(width)
    ET.SubElement(sample_chars, "height").text = str(height)
    
    track = ET.SubElement(video, "track")
    
    # --- LOGIC: Use a while loop to handle merging ---
    i = 0
    while i < len(subtitles):
        current_entry = subtitles[i]
        
        # This key generation truncates milliseconds to match the JSON key format.
        start_time_key = datetime.utcfromtimestamp(current_entry['start']).strftime("%H:%M:%S")
        images_for_current_entry = image_map.get(start_time_key, [])

        if not images_for_current_entry:
            print(f"Warning: No image mapping for key: {start_time_key} (at {current_entry['start']:.3f}s). Skipping.")
            i += 1
            continue

        # --- LOGIC: Find the end of the consecutive block with the same image(s) ---
        end_index = i
        for j in range(i + 1, len(subtitles)):
            next_entry = subtitles[j]
            next_start_time_key = datetime.utcfromtimestamp(next_entry['start']).strftime("%H:%M:%S")
            images_for_next_entry = image_map.get(next_start_time_key, [])
            
            # If the image list is identical, extend the block
            if images_for_current_entry == images_for_next_entry:
                end_index = j
            else:
                # If they are different, the block ends here
                break
        
        # --- LOGIC: Calculate the total time slot for the entire merged block ---
        block_start_seconds = current_entry['start']
        
        is_last_block_in_timeline = (end_index == len(subtitles) - 1)
        if is_last_block_in_timeline:
            # The final block ends at the 'end' time of its last subtitle
            block_end_seconds = subtitles[end_index]['end']
        else:
            # The block ends at the 'start' time of the next, different subtitle
            block_end_seconds = subtitles[end_index + 1]['start']
            
        total_block_duration = block_end_seconds - block_start_seconds

        if total_block_duration <= 0:
            i = end_index + 1 # Move to the next block
            continue

        # --- Place the image(s) for the entire block sequentially ---
        num_images = len(images_for_current_entry)
        image_duration_seconds = total_block_duration / num_images

        for j, img_name_raw in enumerate(images_for_current_entry):
            img_name = img_name_raw.strip()
            image_path = Path(image_folder) / img_name
            
            if not image_path.exists():
                print(f"Warning: Image not found and will be skipped: {image_path}")
                continue

            clip_start_seconds = block_start_seconds + (j * image_duration_seconds)
            clip_end_seconds = clip_start_seconds + image_duration_seconds

            clip_item = ET.SubElement(track, "clipitem", id=f"clip-{uuid.uuid4().hex[:8]}")
            
            ET.SubElement(clip_item, "start").text = str(int(clip_start_seconds * frame_rate))
            ET.SubElement(clip_item, "end").text = str(int(clip_end_seconds * frame_rate))
            ET.SubElement(clip_item, "in").text = "0"
            ET.SubElement(clip_item, "out").text = str(int((clip_end_seconds - clip_start_seconds) * frame_rate))
            
            file_elem = ET.SubElement(clip_item, "file", id=f"file-{uuid.uuid4().hex[:8]}")
            ET.SubElement(file_elem, "name").text = img_name
            ET.SubElement(file_elem, "pathurl").text = image_path.as_uri()
            
            file_rate = ET.SubElement(file_elem, "rate")
            ET.SubElement(file_rate, "timebase").text = str(frame_rate)
            
            file_media = ET.SubElement(file_elem, "media")
            ET.SubElement(file_media, "video")

        # Move the main loop index past the block we just processed
        i = end_index + 1

    tree = ET.ElementTree(xmeml)
    ET.indent(tree, space="  ")
    tree.write(output_path, encoding="utf-8", xml_declaration=True)
# --- GUI (Unchanged) ---
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
            if not subtitles:
                raise ValueError("Could not parse any valid entries from the SRT file.")

            with open(self.json_path.get(), 'r', encoding='utf-8') as f:
                image_map = json.load(f)
            
            generate_premiere_xml(subtitles, image_map, self.image_folder.get(), self.output_path.get(), frame_rate=fps, width=vid_width, height=vid_height)
            
            messagebox.showinfo("Success", f"Premiere Pro XML generated successfully!\n\nFile saved at:\n{self.output_path.get()}")
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred:\n\n{type(e).__name__}: {e}")

# --- Main Execution Block ---
if __name__ == "__main__":
    root = tk.Tk()
    app = AutoEditorApp(root)
    root.mainloop() # This line is essential for the GUI to run
