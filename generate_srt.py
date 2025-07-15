import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import whisper
from datetime import timedelta
import os
import threading
import time

class WhisperSRTGenerator:
    def __init__(self, master):
        self.master = master
        master.title("Whisper SRT Generator")
        master.geometry("650x550")
        
        # Configure styles
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Configure colors
        self.style.configure('TFrame', background='#f0f0f0')
        self.style.configure('TLabel', background='#f0f0f0', font=('Arial', 10))
        self.style.configure('TButton', font=('Arial', 10), padding=6)
        self.style.configure('Accent.TButton', font=('Arial', 10, 'bold'), 
                            background='#4a6fa5', foreground='white')
        self.style.map('Accent.TButton', 
                      background=[('active', '#5a8fc8'), ('pressed', '#3a5f85')])
        self.style.configure('TProgressbar', thickness=25, background='#4a6fa5')
        self.style.configure('TCombobox', padding=5)
        
        # Create main container
        main_frame = ttk.Frame(master, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Input Section
        input_frame = ttk.LabelFrame(main_frame, text="Input Settings", padding=10)
        input_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Audio file selection
        ttk.Label(input_frame, text="Audio File:").grid(row=0, column=0, sticky="w", pady=5)
        self.audio_path = tk.StringVar()
        ttk.Entry(input_frame, textvariable=self.audio_path, width=50).grid(row=0, column=1, padx=5)
        ttk.Button(input_frame, text="Browse...", command=self.select_audio).grid(row=0, column=2)
        
        # Model selection
        ttk.Label(input_frame, text="Model Size:").grid(row=1, column=0, sticky="w", pady=5)
        self.model_var = tk.StringVar(value="base")
        model_combo = ttk.Combobox(input_frame, textvariable=self.model_var, 
                                  values=["tiny", "base", "small", "medium", "large"], width=15)
        model_combo.grid(row=1, column=1, sticky="w", padx=5)
        ttk.Label(input_frame, text="(Larger = more accurate but slower)").grid(row=1, column=2, sticky="w")
        
        # FFmpeg path selection
        ttk.Label(input_frame, text="FFmpeg Path:").grid(row=2, column=0, sticky="w", pady=5)
        self.ffmpeg_path = tk.StringVar()
        ttk.Entry(input_frame, textvariable=self.ffmpeg_path, width=50).grid(row=2, column=1, padx=5)
        ttk.Button(input_frame, text="Browse...", command=self.select_ffmpeg).grid(row=2, column=2)
        
        # Output Section
        output_frame = ttk.LabelFrame(main_frame, text="Output Settings", padding=10)
        output_frame.pack(fill=tk.X, pady=(0, 15))
        
        # SRT file selection
        ttk.Label(output_frame, text="SRT File:").grid(row=0, column=0, sticky="w", pady=5)
        self.srt_path = tk.StringVar()
        ttk.Entry(output_frame, textvariable=self.srt_path, width=50).grid(row=0, column=1, padx=5)
        ttk.Button(output_frame, text="Save As...", command=self.select_srt).grid(row=0, column=2)
        
        # Progress Section
        progress_frame = ttk.LabelFrame(main_frame, text="Progress", padding=10)
        progress_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, 
                                           maximum=100, mode='determinate')
        self.progress_bar.pack(fill=tk.X, pady=5)
        
        # Log area
        self.log_text = tk.Text(progress_frame, height=8, padx=10, pady=10, wrap=tk.WORD)
        self.log_text.pack(fill=tk.X)
        self.log_text.config(state=tk.DISABLED)
        
        # Action Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.generate_btn = ttk.Button(button_frame, text="Generate SRT", 
                                     command=self.start_generation, style='Accent.TButton')
        self.generate_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(button_frame, text="Clear Log", command=self.clear_log).pack(side=tk.LEFT)
        ttk.Button(button_frame, text="Exit", command=master.quit).pack(side=tk.RIGHT)
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(master, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Set default FFmpeg path to Topaz installation
        self.set_default_ffmpeg_path()
    
    def set_default_ffmpeg_path(self):
        """Set default FFmpeg path to Topaz installation if available"""
        topaz_paths = [
            r"C:\Program Files\Topaz Labs LLC\Topaz Video AI\ffmpeg.exe",
            r"C:\Program Files\Topaz Labs LLC\Topaz Video AI\ffmpeg"
        ]
        
        for path in topaz_paths:
            if os.path.exists(path):
                self.ffmpeg_path.set(path)
                self.log_message(f"Using Topaz FFmpeg at: {path}")
                return
        
        self.log_message("Default Topaz FFmpeg not found. Please select manually.")
    
    def log_message(self, message):
        """Add message to log area"""
        self.log_text.config(state=tk.NORMAL)
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.config(state=tk.DISABLED)
        self.log_text.see(tk.END)
        self.status_var.set(message)
    
    def clear_log(self):
        """Clear the log area"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.status_var.set("Log cleared")
    
    def select_audio(self):
        """Select an audio file"""
        filetypes = [
            ("Audio Files", "*.mp3 *.wav *.m4a *.flac"),
            ("All Files", "*.*")
        ]
        path = filedialog.askopenfilename(filetypes=filetypes)
        if path:
            self.audio_path.set(path)
            self.log_message(f"Selected audio: {os.path.basename(path)}")
            
            # Suggest SRT filename
            if not self.srt_path.get():
                base_name = os.path.splitext(os.path.basename(path))[0]
                self.srt_path.set(f"{base_name}.srt")
    
    def select_ffmpeg(self):
        """Select FFmpeg executable"""
        filetypes = [("Executable Files", "*.exe"), ("All Files", "*.*")]
        path = filedialog.askopenfilename(filetypes=filetypes, title="Select FFmpeg Executable")
        if path:
            self.ffmpeg_path.set(path)
            self.log_message(f"Selected FFmpeg: {path}")
    
    def select_srt(self):
        """Select output SRT file"""
        path = filedialog.asksaveasfilename(
            defaultextension=".srt",
            filetypes=[("SRT Files", "*.srt"), ("All Files", "*.*")]
        )
        if path:
            self.srt_path.set(path)
            self.log_message(f"Output will be saved to: {path}")
    
    def start_generation(self):
        """Start the SRT generation in a separate thread"""
        # Validate inputs
        if not self.audio_path.get():
            messagebox.showerror("Error", "Please select an audio file")
            return
        
        if not os.path.exists(self.audio_path.get()):
            messagebox.showerror("Error", "Audio file does not exist")
            return
        
        if not self.srt_path.get():
            messagebox.showerror("Error", "Please specify an output SRT file")
            return
        
        # Disable UI during processing
        self.generate_btn.config(state=tk.DISABLED)
        self.progress_var.set(0)
        self.log_message("Starting SRT generation...")
        
        # Start processing in a separate thread
        thread = threading.Thread(target=self.generate_srt)
        thread.daemon = True
        thread.start()
    
    def generate_srt(self):
        """Generate SRT file using Whisper"""
        try:
            # Get parameters
            audio_path = self.audio_path.get()
            srt_path = self.srt_path.get()
            model_size = self.model_var.get()
            ffmpeg_path = self.ffmpeg_path.get() if self.ffmpeg_path.get() else None
            
            # Set FFmpeg path if provided
            if ffmpeg_path:
                os.environ["PATH"] += os.pathsep + os.path.dirname(ffmpeg_path)
                self.log_message(f"Using FFmpeg from: {ffmpeg_path}")
            
            # Load model
            self.log_message(f"Loading {model_size} model...")
            model = whisper.load_model(model_size)
            
            # Create a progress indicator thread
            self.progress_bar.config(mode='indeterminate')
            self.progress_bar.start(10)
            
            # Transcribe audio
            self.log_message("Transcribing audio... (This may take several minutes)")
            result = model.transcribe(
                audio_path,
                word_timestamps=True,
                fp16=False,  # Disable GPU acceleration for stability
                task="transcribe",
                verbose=False
            )
            
            # Stop the progress indicator
            self.progress_bar.stop()
            self.progress_bar.config(mode='determinate')
            self.progress_var.set(50)  # Mark as 50% complete
            
            # Generate SRT file
            self.log_message("Generating SRT file...")
            with open(srt_path, "w", encoding="utf-8") as srt_file:
                for i, segment in enumerate(result["segments"]):
                    start = timedelta(seconds=segment["start"])
                    end = timedelta(seconds=segment["end"])
                    start_str = str(start).replace(".", ",")[:11]  # Format to HH:MM:SS,mmm
                    end_str = str(end).replace(".", ",")[:11]
                    text = segment["text"].strip()
                    
                    srt_file.write(f"{i+1}\n{start_str} --> {end_str}\n{text}\n\n")
            
            # Success message
            self.progress_var.set(100)
            self.log_message(f"SRT file generated successfully!\nSaved to: {srt_path}")
            messagebox.showinfo("Success", "SRT file generated successfully!")
        
        except Exception as e:
            self.log_message(f"Error: {str(e)}")
            messagebox.showerror("Error", f"An error occurred:\n\n{str(e)}")
        
        finally:
            # Re-enable UI
            self.progress_bar.stop()
            self.progress_bar.config(mode='determinate')
            self.generate_btn.config(state=tk.NORMAL)

if __name__ == "__main__":
    root = tk.Tk()
    app = WhisperSRTGenerator(root)
    root.mainloop()