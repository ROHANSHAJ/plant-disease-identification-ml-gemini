import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, ImageOps
import cv2
import google.generativeai as genai
import numpy as np
import threading
import time
import io

class PlantDoctorPro:
    def __init__(self, root):
        self.root = root
        self.root.title("Plant Doctor Pro ")
        self.root.state('zoomed')  # Start maximized
        self.root.minsize(1200, 800)
        
        # Configure Gemini 1.5 Flash
        self.api_key = "  ############  "  # Replace with your actual API key
        self.model = None
        self.api_configured = False
        self.disease_name = ""  # To store identified disease name
        
        # Image handling
        self.current_frame = None
        self.captured_image = None
        self.displayed_image = None
        self.original_size = (0, 0)
        
        # Camera setup
        self.cap = None
        self.available_cameras = self.detect_cameras()
        self.current_cam = 0 if self.available_cameras else -1
        self.camera_active = False
        
        # UI setup
        self.setup_ui()
        self.init_gemini()
        if self.available_cameras:
            self.init_camera()
        else:
            messagebox.showwarning("No Cameras", "No cameras detected")

    def detect_cameras(self):
        """Detect available cameras with error handling"""
        cameras = []
        max_tested = 4
        
        for i in range(max_tested):
            try:
                cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                if cap.isOpened():
                    cameras.append(i)
                    cap.release()
                time.sleep(0.1)
            except:
                continue
                
        return cameras

    def safe_camera_release(self):
        """Safely release camera resources"""
        if self.cap:
            try:
                self.cap.release()
            except:
                pass
            self.cap = None

    def init_camera(self):
        """Initialize camera with error handling"""
        if self.current_cam == -1 or not self.available_cameras:
            self.status_label.config(text="No camera available")
            return
            
        self.camera_active = False
        self.safe_camera_release()
        
        try:
            self.cap = cv2.VideoCapture(self.current_cam, cv2.CAP_DSHOW)
            
            if self.cap.isOpened():
                self.camera_active = True
                self.status_label.config(text=f"Using Camera {self.current_cam}")
                self.update_camera_display()
            else:
                self.status_label.config(text="Failed to open camera")
                self.safe_camera_release()
                
        except Exception as e:
            self.status_label.config(text=f"Camera error: {str(e)}")
            self.safe_camera_release()

    def update_camera_display(self):
        """Update the display with camera frames"""
        if self.camera_active:
            ret, frame = self.cap.read()
            if ret:
                self.current_frame = frame.copy()
                self.display_image(self.current_frame, self.camera_view)
            else:
                self.status_label.config(text="Camera error")
                self.camera_active = False
            
            self.root.after(33, self.update_camera_display)

    def display_image(self, image, target_label):
        """Display an image in the specified label with smart resizing"""
        if image is None:
            return
            
        # Convert to PIL Image if needed
        if isinstance(image, np.ndarray):
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(image)
        else:
            pil_image = image.copy()
            
        # Store original size
        self.original_size = pil_image.size
        
        # Get container dimensions
        container_width = target_label.winfo_width()
        container_height = target_label.winfo_height()
        
        if container_width <= 1 or container_height <= 1:
            return
            
        # Calculate aspect ratio
        img_width, img_height = pil_image.size
        aspect_ratio = img_width / img_height
        container_aspect = container_width / container_height
        
        # Resize to fit container while preserving aspect ratio
        if aspect_ratio > container_aspect:
            new_width = container_width
            new_height = int(container_width / aspect_ratio)
        else:
            new_height = container_height
            new_width = int(container_height * aspect_ratio)
        
        # Apply high-quality resizing
        pil_image = pil_image.resize((new_width, new_height), Image.LANCZOS)
        imgtk = ImageTk.PhotoImage(image=pil_image)
        
        target_label.imgtk = imgtk
        target_label.configure(image=imgtk)

    def init_gemini(self):
        """Initialize Gemini API with the key from code"""
        if not self.api_key:
            messagebox.showerror("API Error", "API key not found in code")
            self.api_configured = False
            return
            
        try:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-1.5-flash')
            
            # Test the API with a simple request
            try:
                self.model.generate_content("Test connection")
                self.api_configured = True
                self.status_label.config(text="Gemini API initialized")
            except Exception as e:
                messagebox.showerror("API Error", f"API key validation failed: {str(e)}")
                self.api_configured = False
                self.status_label.config(text="API key invalid")
                
        except Exception as e:
            messagebox.showerror("API Error", f"Failed to initialize Gemini API: {str(e)}")
            self.api_configured = False
            self.status_label.config(text="Gemini API initialization failed")

    def capture_image(self):
        """Capture the current frame and analyze"""
        if self.current_frame is None or self.current_frame.size == 0:
            messagebox.showwarning("No Frame", "No camera frame available to capture")
            return
        
        self.captured_image = Image.fromarray(cv2.cvtColor(self.current_frame, cv2.COLOR_BGR2RGB))
        self.display_image(self.captured_image, self.analysis_view)
    
        # Display disease name placeholder
        self.disease_name = "Identifying disease..."
        self.disease_label.config(text=self.disease_name)
    
        self.analyze_image()

    def upload_image(self):
        """Upload an image file for analysis"""
        file_path = filedialog.askopenfilename(
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.webp *.tiff")]
        )
        if file_path:
            try:
                self.captured_image = Image.open(file_path)
                self.display_image(self.captured_image, self.analysis_view)
                
                # Display disease name placeholder
                self.disease_name = "Identifying disease..."
                self.disease_label.config(text=self.disease_name)
                
                self.analyze_image()
            except Exception as e:
                messagebox.showerror("Upload Error", f"Failed to load image: {str(e)}")

    def analyze_image(self):
        """Analyze the captured image using Gemini API"""
        if not self.captured_image:
            return
            
        if not self.api_configured:
            messagebox.showwarning("API Error", "Gemini API not configured")
            return
        
        self.analysis_text.config(state=tk.NORMAL)
        self.analysis_text.delete(1.0, tk.END)
        self.analysis_text.insert(tk.END, "Analyzing image... Please wait...")
        self.analysis_text.config(state=tk.DISABLED)
        self.status_label.config(text="Analyzing image...")
        
        threading.Thread(target=self._perform_analysis, daemon=True).start()

    def _perform_analysis(self):
        """Perform the actual analysis in a background thread"""
        try:
            # Convert PIL Image to bytes for Gemini API
            img_byte_arr = io.BytesIO()
            self.captured_image.save(img_byte_arr, format='PNG')
            img_data = img_byte_arr.getvalue()
            
            # Prepare the prompt
            prompt = (
                "Generate a professional plant health report with these exact sections:\n"
                "1. Disease Identification (only name)"
                "2. Key Symptoms (3-5 concise bullet points describing observable traits)\n"
                "3. Immediate Treatment Recommendations (3-5 practical,steps in bullet points prioritizing safety and effectiveness)\n"
                "4. Prevention Methods (3-5 bullet points for long-term plant health)\n"
                "5. Additional Notes (3-5 bullet points for relevant observations or follow-up advice and suggest most likely disease if uncertain)\n\n"
                "Format cleanly without asterisks or markdown. Use proper spacing between sections . "
                "Use professional language for farmers or horticulturists."
            )
            
            # Send to Gemini API
            response = self.model.generate_content([prompt, {"mime_type": "image/png", "data": img_data}])
            
            # Extract disease name from the first line of the response
            full_response = response.text
            if "1. Disease Identification" in full_response:
                disease_section = full_response.split("1. Disease Identification")[1].split("2. Key Symptoms")[0]
                disease_lines = [line.strip() for line in disease_section.split('\n') if line.strip()]
                if disease_lines:
                    self.disease_name = disease_lines[0]
            
            # Update UI with results
            self.root.after(0, lambda: self._update_analysis_results(full_response))
            
        except Exception as e:
            self.root.after(0, lambda: self._handle_analysis_error(e))

    def _update_analysis_results(self, results):
        """Update the analysis results in the UI"""
        self.analysis_text.config(state=tk.NORMAL)
        self.analysis_text.delete(1.0, tk.END)
        self.analysis_text.insert(tk.END, results)
        self.analysis_text.config(state=tk.DISABLED)
        self.disease_label.config(text=self.disease_name)
        self.status_label.config(text="Analysis complete")

    def _handle_analysis_error(self, error):
        """Handle analysis errors in the UI"""
        messagebox.showerror("Analysis Error", f"Failed to analyze image: {str(error)}")
        self.analysis_text.config(state=tk.NORMAL)
        self.analysis_text.delete(1.0, tk.END)
        self.analysis_text.config(state=tk.DISABLED)
        self.disease_label.config(text="Analysis failed")
        self.status_label.config(text="Analysis failed")

    def change_camera(self):
        """Change the active camera"""
        if not self.available_cameras:
            return
        
        selected = self.cam_combobox.get()
        new_cam = int(selected.replace("Camera ", ""))
        
        if new_cam != self.current_cam:
            self.current_cam = new_cam
            self.init_camera()

    def on_close(self):
        """Clean up resources on application close"""
        self.camera_active = False
        self.safe_camera_release()
        self.root.quit()

    def setup_ui(self):
        """Set up the main UI"""
        # Configure styles
        style = ttk.Style()
        style.configure('TButton', font=('Arial', 11), padding=6)
        style.configure('Title.TLabel', font=('Arial', 12, 'bold'))
        style.configure('Disease.TLabel', font=('Arial', 12, 'bold'), foreground='red')
        style.configure('Status.TLabel', font=('Arial', 10))
        style.configure('TFrame', background='#f0f0f0')
        
        # Main container
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(expand=True, fill='both', padx=10, pady=10)
        
        # Control panel at top
        self.create_control_panel()
        
        # Split view container
        self.split_container = ttk.PanedWindow(self.main_frame, orient=tk.HORIZONTAL)
        self.split_container.pack(expand=True, fill='both', pady=(10, 0))
        
        # Camera view frame
        self.camera_frame = ttk.Frame(self.split_container, width=400)
        self.split_container.add(self.camera_frame, weight=1)
        
        # Analysis view frame
        self.result_frame = ttk.Frame(self.split_container, width=400)
        self.split_container.add(self.result_frame, weight=1)
        
        # Create camera view
        self.create_camera_view()
        
        # Create analysis view
        self.create_analysis_view()
        
        # Status bar
        self.status_label = ttk.Label(
            self.main_frame, 
            text="Ready", 
            style='Status.TLabel',
            relief='sunken',
            padding=5
        )
        self.status_label.pack(fill='x', pady=(5, 0))
        
        # Bind resize event
        self.root.bind('<Configure>', self.on_resize)

    def create_control_panel(self):
        """Create the top control panel"""
        control_frame = ttk.Frame(self.main_frame)
        control_frame.pack(fill='x', pady=(0, 10))
        
        # Camera selection
        cam_frame = ttk.Frame(control_frame)
        cam_frame.pack(side='left', padx=5)
        
        ttk.Label(cam_frame, text="Camera:", style='Title.TLabel').pack(side='left')
        self.cam_combobox = ttk.Combobox(
            cam_frame, 
            values=[f"Camera {i}" for i in self.available_cameras],
            state='readonly',
            font=('Arial', 10),
            width=12
        )
        self.cam_combobox.pack(side='left', padx=5)
        if self.available_cameras:
            self.cam_combobox.current(0)
        self.cam_combobox.bind('<<ComboboxSelected>>', lambda e: self.change_camera())
        
        # Action buttons
        action_frame = ttk.Frame(control_frame)
        action_frame.pack(side='right', padx=5)
        
        ttk.Button(
            action_frame, 
            text="📷 Capture & Analyze", 
            command=self.capture_image,
            style='TButton'
        ).pack(side='left', padx=5)
        
        ttk.Button(
            action_frame, 
            text="📁 Upload Image", 
            command=self.upload_image,
            style='TButton'
        ).pack(side='left', padx=5)
        
        ttk.Button(
            action_frame, 
            text="🔄 Restart", 
            command=self.restart_app,
            style='TButton'
        ).pack(side='left', padx=5)
        
        ttk.Button(
            action_frame, 
            text="❌ Exit", 
            command=self.on_close,
            style='TButton'
        ).pack(side='left', padx=5)

    def create_camera_view(self):
        """Create the camera view panel"""
        # Title
        ttk.Label(
            self.camera_frame, 
            text="Live Camera View", 
            style='Title.TLabel'
        ).pack(anchor='nw', pady=(0, 5))
        
        # Image display
        self.camera_view = ttk.Label(self.camera_frame)
        self.camera_view.pack(expand=True, fill='both')
        
        # Add border
        self.camera_view.config(relief='sunken', borderwidth=2)

    def create_analysis_view(self):
        """Create the analysis view panel"""
        # Title
        ttk.Label(
            self.result_frame, 
            text="Analysis Results", 
            style='Title.TLabel'
        ).pack(anchor='nw', pady=(0, 5))
        
        # Disease name display
        self.disease_label = ttk.Label(
            self.result_frame,
            text="",
            style='Disease.TLabel'
        )
        self.disease_label.pack(anchor='nw', pady=(0, 5))
        
        # Split view for image and text
        analysis_panes = ttk.PanedWindow(self.result_frame, orient=tk.VERTICAL)
        analysis_panes.pack(expand=True, fill='both')
        
        # Image display frame
        img_frame = ttk.Frame(analysis_panes)
        analysis_panes.add(img_frame, weight=1)
        
        self.analysis_view = ttk.Label(img_frame)
        self.analysis_view.pack(expand=True, fill='both')
        self.analysis_view.config(relief='sunken', borderwidth=2)
        
        # Text results frame
        text_frame = ttk.Frame(analysis_panes)
        analysis_panes.add(text_frame, weight=1)
        
        # Analysis text with scrollbar
        text_container = ttk.Frame(text_frame)
        text_container.pack(expand=True, fill='both')
        
        self.analysis_text = tk.Text(
            text_container, 
            wrap='word', 
            font=('Arial', 10),
            padx=5, 
            pady=5
        )
        self.analysis_text.pack(side='left', expand=True, fill='both')
        self.analysis_text.config(state=tk.DISABLED)
        
        scrollbar = ttk.Scrollbar(text_container, command=self.analysis_text.yview)
        scrollbar.pack(side='right', fill='y')
        self.analysis_text.config(yscrollcommand=scrollbar.set)
        
        # Add border to text area
        text_container.config(relief='sunken', borderwidth=2)

    def on_resize(self, event=None):
        """Handle window resize events"""
        if self.camera_active and self.current_frame is not None:
            self.display_image(self.current_frame, self.camera_view)
        if self.captured_image is not None:
            self.display_image(self.captured_image, self.analysis_view)

    def restart_app(self):
        """Restart the application"""
        self.on_close()
        self.root.destroy()
        root = tk.Tk()
        app = PlantDoctorPro(root)
        root.mainloop()

if __name__ == "__main__":
    root = tk.Tk()
    app = PlantDoctorPro(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
