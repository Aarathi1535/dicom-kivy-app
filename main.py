import os
import pydicom
import numpy as np
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.filechooser import FileChooserIconView
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.uix.slider import Slider
from kivy.graphics.texture import Texture
from kivy.uix.label import Label
from kivy.core.window import Window
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.uix.progressbar import ProgressBar
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.graphics import Color, Rectangle
from kivy.clock import Clock
import threading
import queue
import time

# Custom Label with background color
class ColoredLabel(Label):
    def __init__(self, bg_color=(0.9, 0.9, 0.9, 1), **kwargs):
        super().__init__(**kwargs)
        self.bg_color = bg_color
        
        with self.canvas.before:
            Color(*self.bg_color)
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
        
        self.bind(pos=self.update_bg, size=self.update_bg)
    
    def update_bg(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size

# Dedicated DICOM Video Player Interface
class DICOMVideoPlayerInterface(BoxLayout):
    def __init__(self, main_app, **kwargs):
        super().__init__(**kwargs)
        self.main_app = main_app
        self.orientation = 'vertical'
        self.current_frame = 0
        self.total_frames = 0
        self.video_frames = []
        self.is_playing = False
        self.fps = 25
        self.play_event = None
        self.current_video_file = None
        
        self.build_video_interface()
    
    def build_video_interface(self):
        # Video header
        header = ColoredLabel(
            text="🎥 DICOM Video Player - Professional Medical Video Analysis",
            size_hint_y=None,
            height=40,
            font_size=16,
            bold=True,
            bg_color=(0.2, 0.4, 0.8, 1),
            color=(1, 1, 1, 1)
        )
        self.add_widget(header)
        
        # Main video area
        video_area = BoxLayout(orientation='horizontal')
        
        # Left panel for video files list
        left_video_panel = BoxLayout(orientation='vertical', size_hint=(0.25, 1))
        
        video_list_header = ColoredLabel(
            text="Video Files",
            size_hint_y=None,
            height=30,
            font_size=12,
            bold=True,
            bg_color=(0.7, 0.8, 0.9, 1)
        )
        left_video_panel.add_widget(video_list_header)
        
        video_scroll = ScrollView()
        self.video_files_layout = GridLayout(cols=1, size_hint_y=None, spacing=2)
        self.video_files_layout.bind(minimum_height=self.video_files_layout.setter('height'))
        video_scroll.add_widget(self.video_files_layout)
        left_video_panel.add_widget(video_scroll)
        
        # Center video player
        center_video_area = BoxLayout(orientation='vertical')
        
        # Video display
        self.video_image = Image()
        center_video_area.add_widget(self.video_image)
        
        # Video controls
        self.build_video_controls()
        center_video_area.add_widget(self.video_controls)
        
        # Right panel for video info
        right_video_panel = BoxLayout(orientation='vertical', size_hint=(0.25, 1))
        
        video_info_header = ColoredLabel(
            text="Video Information",
            size_hint_y=None,
            height=30,
            font_size=12,
            bold=True,
            bg_color=(0.7, 0.8, 0.9, 1)
        )
        right_video_panel.add_widget(video_info_header)
        
        video_info_scroll = ScrollView()
        self.video_info_label = Label(
            text="Load a DICOM video to see information",
            halign="left",
            valign="top",
            size_hint_y=None,
            text_size=(200, None),
            font_size=10
        )
        self.video_info_label.bind(texture_size=self.video_info_label.setter("size"))
        video_info_scroll.add_widget(self.video_info_label)
        right_video_panel.add_widget(video_info_scroll)
        
        video_area.add_widget(left_video_panel)
        video_area.add_widget(center_video_area)
        video_area.add_widget(right_video_panel)
        
        self.add_widget(video_area)
        
        # Video toolbar
        self.build_video_toolbar()
    
    def build_video_controls(self):
        self.video_controls = BoxLayout(size_hint_y=None, height=100, orientation='vertical', spacing=5, padding=10)
        
        # Frame slider
        slider_layout = BoxLayout(size_hint_y=None, height=30)
        slider_layout.add_widget(Label(text="Frame:", size_hint_x=None, width=60, font_size=12))
        
        self.frame_slider = Slider(min=0, max=1, value=0, step=1)
        self.frame_slider.bind(value=self.on_frame_change)
        slider_layout.add_widget(self.frame_slider)
        
        self.frame_label = Label(text="0/0", size_hint_x=None, width=80, font_size=12)
        slider_layout.add_widget(self.frame_label)
        
        self.video_controls.add_widget(slider_layout)
        
        # Control buttons
        btn_layout = BoxLayout(size_hint_y=None, height=50, spacing=10)
        
        self.play_btn = Button(text="▶ Play", size_hint_x=None, width=80, background_color=(0.2, 0.8, 0.2, 1), font_size=14)
        self.pause_btn = Button(text="⏸ Pause", size_hint_x=None, width=80, background_color=(0.8, 0.6, 0.2, 1), font_size=14)
        self.stop_btn = Button(text="⏹ Stop", size_hint_x=None, width=80, background_color=(0.8, 0.2, 0.2, 1), font_size=14)
        
        prev_frame_btn = Button(text="⏮ Prev", size_hint_x=None, width=80, background_color=(0.5, 0.5, 0.5, 1))
        next_frame_btn = Button(text="Next ⏭", size_hint_x=None, width=80, background_color=(0.5, 0.5, 0.5, 1))
        
        self.play_btn.bind(on_release=self.play_video)
        self.pause_btn.bind(on_release=self.pause_video)
        self.stop_btn.bind(on_release=self.stop_video)
        prev_frame_btn.bind(on_release=self.prev_frame)
        next_frame_btn.bind(on_release=self.next_frame)
        
        # FPS control
        fps_layout = BoxLayout(size_hint_x=None, width=150)
        fps_layout.add_widget(Label(text="FPS:", size_hint_x=None, width=40, font_size=12))
        
        self.fps_slider = Slider(min=1, max=60, value=25, step=1, size_hint_x=None, width=80)
        self.fps_slider.bind(value=self.on_fps_change)
        fps_layout.add_widget(self.fps_slider)
        
        self.fps_label = Label(text="25", size_hint_x=None, width=30, font_size=12)
        fps_layout.add_widget(self.fps_label)
        
        btn_layout.add_widget(self.play_btn)
        btn_layout.add_widget(self.pause_btn)
        btn_layout.add_widget(self.stop_btn)
        btn_layout.add_widget(Label(text="|", size_hint_x=None, width=20, color=(0.5, 0.5, 0.5, 1)))
        btn_layout.add_widget(prev_frame_btn)
        btn_layout.add_widget(next_frame_btn)
        btn_layout.add_widget(Label(text="|", size_hint_x=None, width=20, color=(0.5, 0.5, 0.5, 1)))
        btn_layout.add_widget(fps_layout)
        btn_layout.add_widget(Label())  # Spacer
        
        self.video_controls.add_widget(btn_layout)
    
    def build_video_toolbar(self):
        toolbar = BoxLayout(size_hint_y=None, height=40, spacing=10, padding=10)
        
        back_btn = Button(text="← Back to Main", size_hint_x=None, width=120, background_color=(0.6, 0.6, 0.6, 1))
        back_btn.bind(on_release=self.return_to_main)
        
        load_video_btn = Button(text="📁 Load Video Files", size_hint_x=None, width=130, background_color=(0.3, 0.7, 0.3, 1))
        load_video_btn.bind(on_release=self.load_video_files)
        
        load_folder_btn = Button(text="📁 Load Video Folder", size_hint_x=None, width=140, background_color=(0.2, 0.8, 0.2, 1))
        load_folder_btn.bind(on_release=self.load_video_folder)
        
        toolbar.add_widget(back_btn)
        toolbar.add_widget(Label(text="|", size_hint_x=None, width=20, color=(0.5, 0.5, 0.5, 1)))
        toolbar.add_widget(load_video_btn)
        toolbar.add_widget(load_folder_btn)
        toolbar.add_widget(Label())  # Spacer
        
        self.add_widget(toolbar)
    
    def return_to_main(self, instance):
        """Return to main DICOM viewer interface"""
        self.main_app.show_main_interface()
    
    def load_video_files(self, instance):
        """Load individual video files"""
        self.main_app.show_file_chooser_for_videos()
    
    def load_video_folder(self, instance):
        """Load video folder"""
        self.main_app.show_folder_chooser_for_videos()
    
    def populate_video_files(self, video_files):
        """Populate the video files list"""
        self.video_files_layout.clear_widgets()
        
        for video_file in video_files:
            try:
                # Get basic info from DICOM
                dcm = pydicom.dcmread(video_file, stop_before_pixels=True, force=True)
                series_desc = getattr(dcm, 'SeriesDescription', 'Video')
                frames = getattr(dcm, 'NumberOfFrames', '?')
                
                video_btn = Button(
                    text=f"🎥 {series_desc}\n{frames} frames\n{os.path.basename(video_file)}",
                    size_hint_y=None,
                    height=80,
                    background_color=(0.85, 0.95, 1.0, 1),
                    font_size=9,
                    halign="center"
                )
                video_btn.bind(on_release=lambda x, f=video_file: self.load_video_file(f))
                self.video_files_layout.add_widget(video_btn)
                
            except Exception as e:
                print(f"Error processing video file {video_file}: {e}")
    
    def load_video_file(self, file_path):
        """Load and display a DICOM video file"""
        try:
            print(f"🎥 Loading DICOM video: {file_path}")
            self.current_video_file = file_path
            dcm = pydicom.dcmread(file_path, force=True)
            
            if hasattr(dcm, 'pixel_array'):
                pixel_array = dcm.pixel_array
                
                if len(pixel_array.shape) >= 3:
                    if len(pixel_array.shape) == 3:  # (frames, height, width)
                        frames = pixel_array
                    else:  # (frames, height, width, channels)
                        frames = pixel_array
                    
                    self.total_frames = frames.shape[0]
                    self.video_frames = []
                    
                    print(f"🎥 Processing {self.total_frames} video frames...")
                    
                    for i in range(self.total_frames):
                        frame = frames[i]
                        
                        # Normalize frame
                        if frame.dtype != np.uint8:
                            frame_min = np.min(frame)
                            frame_max = np.max(frame)
                            if frame_max > frame_min:
                                # Apply window/level if available
                                window_center = getattr(dcm, 'WindowCenter', None)
                                window_width = getattr(dcm, 'WindowWidth', None)
                                
                                if window_center is not None and window_width is not None:
                                    if isinstance(window_center, (list, tuple)):
                                        window_center = window_center[0]
                                    if isinstance(window_width, (list, tuple)):
                                        window_width = window_width[0]
                                    
                                    img_min = window_center - window_width // 2
                                    img_max = window_center + window_width // 2
                                    frame = np.clip(frame, img_min, img_max)
                                    frame = ((frame - img_min) / (img_max - img_min) * 255).astype(np.uint8)
                                else:
                                    frame = ((frame - frame_min) / (frame_max - frame_min) * 255).astype(np.uint8)
                            else:
                                frame = np.full_like(frame, 128, dtype=np.uint8)
                        
                        self.video_frames.append(frame)
                    
                    # Update controls
                    self.frame_slider.max = self.total_frames - 1
                    self.current_frame = 0
                    self.update_frame_display()
                    self.update_video_info(dcm, file_path)
                    
                    # Try to get FPS from DICOM
                    try:
                        frame_time = getattr(dcm, 'FrameTime', None)  # in milliseconds
                        if frame_time:
                            self.fps = 1000 / float(frame_time)
                            self.fps_slider.value = min(60, max(1, self.fps))
                    except:
                        pass
                    
                    print(f"🎥 Video loaded: {self.total_frames} frames, {self.fps} FPS")
                    return True
                else:
                    print("❌ Not a multi-frame DICOM")
                    return False
            else:
                print("❌ No pixel data in DICOM")
                return False
                
        except Exception as e:
            print(f"❌ Error loading DICOM video: {e}")
            return False
    
    def update_frame_display(self):
        """Update the displayed frame"""
        if not self.video_frames or self.current_frame >= len(self.video_frames):
            return
        
        try:
            frame = self.video_frames[self.current_frame]
            
            # Create texture
            if len(frame.shape) == 3:
                if frame.shape[2] == 3:  # RGB
                    texture = Texture.create(size=(frame.shape[1], frame.shape[0]), colorfmt="rgb")
                    texture.blit_buffer(frame.tobytes(), colorfmt="rgb", bufferfmt="ubyte")
                elif frame.shape[2] == 4:  # RGBA
                    texture = Texture.create(size=(frame.shape[1], frame.shape[0]), colorfmt="rgba")
                    texture.blit_buffer(frame.tobytes(), colorfmt="rgba", bufferfmt="ubyte")
                else:
                    # Convert to grayscale
                    frame = np.mean(frame, axis=2).astype(np.uint8)
                    texture = Texture.create(size=(frame.shape[1], frame.shape[0]), colorfmt="luminance")
                    texture.blit_buffer(frame.tobytes(), colorfmt="luminance", bufferfmt="ubyte")
            else:
                texture = Texture.create(size=(frame.shape[1], frame.shape[0]), colorfmt="luminance")
                texture.blit_buffer(frame.tobytes(), colorfmt="luminance", bufferfmt="ubyte")
            
            texture.flip_vertical()
            self.video_image.texture = texture
            
            # Update controls
            self.frame_slider.value = self.current_frame
            self.frame_label.text = f"{self.current_frame + 1}/{self.total_frames}"
            
        except Exception as e:
            print(f"❌ Error displaying frame: {e}")
    
    def update_video_info(self, dcm, file_path):
        """Update video information panel"""
        try:
            info_text = f"""🎥 DICOM VIDEO ANALYSIS

PATIENT:
━━━━━━━━━━━━━━━━━━━━━
Name: {getattr(dcm, 'PatientName', 'N/A')}
ID: {getattr(dcm, 'PatientID', 'N/A')}
Sex: {getattr(dcm, 'PatientSex', 'N/A')}
Age: {getattr(dcm, 'PatientAge', 'N/A')}

STUDY:
━━━━━━━━━━━━━━━━━━━━━
Date: {getattr(dcm, 'StudyDate', 'N/A')}
Description: {getattr(dcm, 'StudyDescription', 'N/A')}

VIDEO DETAILS:
━━━━━━━━━━━━━━━━━━━━━
Modality: {getattr(dcm, 'Modality', 'N/A')}
Series: {getattr(dcm, 'SeriesDescription', 'N/A')}
Total Frames: {getattr(dcm, 'NumberOfFrames', 'N/A')}
Frame Size: {getattr(dcm, 'Rows', 'N/A')} × {getattr(dcm, 'Columns', 'N/A')}

PLAYBACK:
━━━━━━━━━━━━━━━━━━━━━
Current Frame: {self.current_frame + 1}/{self.total_frames}
FPS: {self.fps}
Status: {'Playing' if self.is_playing else 'Stopped'}

FILE:
━━━━━━━━━━━━━━━━━━━━━
{os.path.basename(file_path)}

🎮 CONTROLS:
• Play/Pause/Stop buttons
• Frame slider for navigation
• FPS adjustment
• Arrow keys for frame step
• Spacebar for play/pause"""
            
            self.video_info_label.text = info_text
            
        except Exception as e:
            self.video_info_label.text = f"Error loading video info: {e}"
    
    def on_frame_change(self, instance, value):
        """Handle frame slider change"""
        if not self.is_playing:  # Only allow manual frame change when not playing
            self.current_frame = int(value)
            self.update_frame_display()
    
    def on_fps_change(self, instance, value):
        """Handle FPS slider change"""
        self.fps = int(value)
        self.fps_label.text = str(self.fps)
        
        # Restart playback with new FPS if currently playing
        if self.is_playing:
            self.pause_video(None)
            self.play_video(None)
    
    def play_video(self, instance):
        """Start video playback"""
        if not self.video_frames or self.is_playing:
            return
        
        self.is_playing = True
        interval = 1.0 / self.fps
        self.play_event = Clock.schedule_interval(self.next_frame_auto, interval)
        print(f"🎥 Playing video at {self.fps} FPS")
    
    def pause_video(self, instance):
        """Pause video playback"""
        self.is_playing = False
        if self.play_event:
            Clock.unschedule(self.play_event)
            self.play_event = None
        print("⏸ Video paused")
    
    def stop_video(self, instance):
        """Stop video playback and return to first frame"""
        self.pause_video(instance)
        self.current_frame = 0
        self.update_frame_display()
        print("⏹ Video stopped")
    
    def next_frame_auto(self, dt):
        """Auto-advance to next frame during playback"""
        if self.current_frame < self.total_frames - 1:
            self.current_frame += 1
            self.update_frame_display()
        else:
            # Loop back to beginning
            self.current_frame = 0
            self.update_frame_display()
    
    def next_frame(self, instance):
        """Manual next frame"""
        if self.current_frame < self.total_frames - 1:
            self.current_frame += 1
            self.update_frame_display()
    
    def prev_frame(self, instance):
        """Manual previous frame"""
        if self.current_frame > 0:
            self.current_frame -= 1
            self.update_frame_display()

# DICOM detection functions
def is_dicom_file_ultrafast(file_path):
    """Ultra-fast DICOM detection"""
    try:
        ext = os.path.splitext(file_path)[1].lower()
        if ext in ['.dcm', '.dicom', '.dic', '.ima']:
            return True
            
        try:
            file_size = os.path.getsize(file_path)
            if file_size < 128:
                return False
            if file_size > 500 * 1024 * 1024:
                return False
        except:
            return False
        
        try:
            pydicom.dcmread(file_path, stop_before_pixels=True, force=True)
            return True
        except:
            pass
        
        with open(file_path, 'rb') as f:
            f.seek(128)
            dicm = f.read(4)
            if dicm == b'DICM':
                return True
                
            f.seek(0)
            header = f.read(16)
            if len(header) < 8:
                return False
                
            try:
                group = int.from_bytes(header[0:2], byteorder='little')
                element = int.from_bytes(header[2:4], byteorder='little')
                
                if (group == 0x0008 and element in [0x0000, 0x0001, 0x0005, 0x0008, 0x0016, 0x0018]) or \
                   (group == 0x0002 and element in [0x0000, 0x0001, 0x0002, 0x0003, 0x0010, 0x0012]):
                    return True
            except:
                pass
                
        return False
    except Exception:
        return False

def scan_folder_ultrafast(directory, recursive=False, progress_callback=None):
    """Ultra-fast folder scanning"""
    all_files = []
    dicom_files = []
    
    try:
        if recursive:
            for root, dirs, files in os.walk(directory):
                skip_dirs = {'.git', '__pycache__', 'node_modules', '.vs', 'bin', 'obj', 
                           'temp', 'tmp', 'cache', '.svn', 'backup', 'logs'}
                dirs[:] = [d for d in dirs if d.lower() not in skip_dirs]
                
                for file in files:
                    file_path = os.path.join(root, file)
                    all_files.append(file_path)
        else:
            for file in os.listdir(directory):
                file_path = os.path.join(directory, file)
                if os.path.isfile(file_path):
                    all_files.append(file_path)
    except Exception as e:
        if progress_callback:
            progress_callback(0, f"Error accessing directory: {e}")
        return []
    
    if not all_files:
        return []
    
    potential_dicom = []
    definitely_dicom = []
    
    for file_path in all_files:
        try:
            ext = os.path.splitext(file_path)[1].lower()
            basename = os.path.basename(file_path).lower()
            
            obvious_non_dicom = {'.txt', '.log', '.xml', '.html', '.css', '.js', '.py', 
                               '.exe', '.dll', '.zip', '.rar', '.pdf', '.doc', '.docx', 
                               '.xls', '.xlsx', '.ppt', '.pptx', '.mp3', '.avi',
                               '.mov', '.wav', '.jpg', '.jpeg', '.png', '.gif', '.bmp',
                               '.tiff', '.svg', '.ico', '.ini', '.cfg', '.json'}
            
            if ext in obvious_non_dicom:
                continue
                
            if ext in ['.dcm', '.dicom', '.dic', '.ima']:
                definitely_dicom.append(file_path)
            elif ext == '' or (len(ext) <= 4 and ext not in obvious_non_dicom):
                medical_indicators = ['dicom', 'dcm', 'img', 'image', 'scan', 'slice', 'frame', 'video']
                if any(indicator in basename for indicator in medical_indicators):
                    potential_dicom.insert(0, file_path)
                else:
                    potential_dicom.append(file_path)
                    
        except Exception:
            continue
    
    total_candidates = len(definitely_dicom) + len(potential_dicom)
    processed = 0
    
    if progress_callback:
        progress_callback(5, f"Found {len(definitely_dicom)} definite + {len(potential_dicom)} potential DICOM files")
    
    dicom_files.extend(definitely_dicom)
    processed += len(definitely_dicom)
    
    batch_size = max(1, len(potential_dicom) // 50)
    
    for i in range(0, len(potential_dicom), batch_size):
        batch = potential_dicom[i:i+batch_size]
        
        for file_path in batch:
            if is_dicom_file_ultrafast(file_path):
                dicom_files.append(file_path)
            processed += 1
        
        if progress_callback:
            progress = (processed / total_candidates) * 95 + 5
            progress_callback(progress, f"Scanning: {processed}/{total_candidates} files, found {len(dicom_files)} DICOM files")
        
        time.sleep(0.001)
    
    return dicom_files

def is_dicom_video(file_path):
    """Enhanced DICOM video detection"""
    try:
        dcm = pydicom.dcmread(file_path, stop_before_pixels=True, force=True)
        
        # Check transfer syntax for video formats
        transfer_syntax = getattr(dcm.file_meta, 'TransferSyntaxUID', '')
        video_syntaxes = [
            '1.2.840.10008.1.2.4.100',  # MPEG2 Main Profile @ Main Level
            '1.2.840.10008.1.2.4.101',  # MPEG2 Main Profile @ High Level  
            '1.2.840.10008.1.2.4.102',  # MPEG-4 AVC/H.264 High Profile
            '1.2.840.10008.1.2.4.103',  # MPEG-4 AVC/H.264 BD-compatible
            '1.2.840.10008.1.2.4.104',  # MPEG-4 AVC/H.264 Stereo
            '1.2.840.10008.1.2.4.105',  # HEVC/H.265 Main Profile
            '1.2.840.10008.1.2.4.106'   # HEVC/H.265 Main 10 Profile
        ]
        
        if transfer_syntax in video_syntaxes:
            return True
            
        # Check SOP Class for video
        sop_class = getattr(dcm, 'SOPClassUID', '')
        video_sop_classes = [
            '1.2.840.10008.5.1.4.1.1.77.1.4.1',  # Video Endoscopic Image Storage
            '1.2.840.10008.5.1.4.1.1.77.1.4',     # Video Photographic Image Storage
            '1.2.840.10008.5.1.4.1.1.77.1.1.1',   # Video Endoscopic Image Storage
            '1.2.840.10008.5.1.4.1.1.77.1.2.1',   # Video Microscopic Image Storage
            '1.2.840.10008.5.1.4.1.1.77.1.5.1',   # Ophthalmic Photography 8 Bit
            '1.2.840.10008.5.1.4.1.1.77.1.5.2',   # Ophthalmic Photography 16 Bit
            '1.2.840.10008.5.1.4.1.1.77.1.5.4'    # Ophthalmic Tomography
        ]
        
        if sop_class in video_sop_classes:
            return True
            
        # Check for multi-frame indicators
        frames = getattr(dcm, 'NumberOfFrames', None)
        if frames:
            try:
                frame_count = int(frames)
                if frame_count > 1:
                    # Additional checks for video vs static multi-frame
                    frame_time = getattr(dcm, 'FrameTime', None)
                    frame_increment_pointer = getattr(dcm, 'FrameIncrementPointer', None)
                    if frame_time or frame_increment_pointer or frame_count > 10:
                        return True
            except:
                pass
                
        # Check modality for video-related types
        modality = getattr(dcm, 'Modality', '')
        video_modalities = {'XC', 'VL', 'ES', 'OP', 'US'}  # Video modalities
        if modality in video_modalities:
            try:
                pixel_array = pydicom.dcmread(file_path, force=True).pixel_array
                if len(pixel_array.shape) >= 3 and pixel_array.shape[0] > 1:
                    return True
            except:
                pass
                
        return False
        
    except Exception:
        return False

# Enhanced async loader
class UltraFastDICOMLoader:
    def __init__(self, callback):
        self.callback = callback
        self.queue = queue.Queue()
        self.running = False
        self.should_stop = False
        
    def stop_loading(self):
        self.should_stop = True
        
    def scan_folder_async(self, folder_path, recursive=False):
        if self.running:
            return
            
        self.running = True
        self.should_stop = False
        thread = threading.Thread(target=self._ultra_scan_worker, args=(folder_path, recursive))
        thread.daemon = True
        thread.start()
        
        Clock.schedule_interval(self._check_queue, 0.05)
    
    def load_files_async(self, file_list):
        if self.running:
            return
            
        self.running = True
        self.should_stop = False
        thread = threading.Thread(target=self._ultra_load_worker, args=(file_list,))
        thread.daemon = True
        thread.start()
        
        Clock.schedule_interval(self._check_queue, 0.05)
    
    def _ultra_scan_worker(self, folder_path, recursive):
        try:
            def progress_update(progress, status):
                if not self.should_stop:
                    self.queue.put(('progress', progress, status))
            
            start_time = time.time()
            dicom_files = scan_folder_ultrafast(folder_path, recursive, progress_update)
            scan_time = time.time() - start_time
            
            if not self.should_stop:
                self.queue.put(('scan_complete', dicom_files))
                self.queue.put(('progress', 100, f"⚡ Ultra-fast scan: {scan_time:.1f}s - {len(dicom_files)} DICOM files found"))
        except Exception as e:
            if not self.should_stop:
                self.queue.put(('error', f"Scanning error: {e}"))
        
        self.running = False
    
    def _ultra_load_worker(self, file_list):
        series_dict = {}
        total_files = len(file_list)
        
        try:
            start_time = time.time()
            
            for i, file_path in enumerate(file_list):
                if self.should_stop:
                    break
                    
                try:
                    dcm = pydicom.dcmread(file_path, stop_before_pixels=True, force=True)
                    
                    # Video detection
                    is_video = is_dicom_video(file_path)
                    
                    series_uid = getattr(dcm, 'SeriesInstanceUID', f'Unknown_{hash(file_path)}')
                    series_desc = getattr(dcm, 'SeriesDescription', 'Unnamed Series')
                    series_number = getattr(dcm, 'SeriesNumber', '0')
                    modality = getattr(dcm, 'Modality', 'Unknown')
                    
                    # Video indicators
                    if is_video:
                        frames = getattr(dcm, 'NumberOfFrames', '?')
                        video_indicator = f" [VIDEO-{frames}F]"
                    else:
                        video_indicator = ""
                    
                    if isinstance(series_number, (int, float)):
                        series_key = f"{int(series_number):03d} - {series_desc} ({modality}){video_indicator}"
                    else:
                        series_key = f"000 - {series_desc} ({modality}){video_indicator}"
                    
                    if series_key not in series_dict:
                        series_dict[series_key] = {
                            'files': [],
                            'description': series_desc,
                            'modality': modality,
                            'patient_name': str(getattr(dcm, 'PatientName', 'Unknown')),
                            'patient_id': getattr(dcm, 'PatientID', 'Unknown'),
                            'study_description': getattr(dcm, 'StudyDescription', 'Unknown Study'),
                            'study_date': getattr(dcm, 'StudyDate', 'Unknown'),
                            'series_uid': series_uid,
                            'is_video': is_video,
                            'frame_count': getattr(dcm, 'NumberOfFrames', 1) if is_video else 1
                        }
                    
                    series_dict[series_key]['files'].append(file_path)
                    
                    # Progress update
                    if i % 3 == 0 or i == total_files - 1:
                        progress = ((i + 1) / total_files) * 100
                        status = f"⚡ Processing: {i + 1}/{total_files} files"
                        self.queue.put(('progress', progress, status))
                
                except Exception as e:
                    print(f"Error processing {file_path}: {e}")
                    continue
            
            # Sort files
            if not self.should_stop:
                for series_key in series_dict:
                    try:
                        series_dict[series_key]['files'].sort(key=lambda x: self._get_instance_number(x))
                    except:
                        pass
                
                load_time = time.time() - start_time
                
                print(f"✅ LOAD WORKER COMPLETE: {len(series_dict)} series")
                self.queue.put(('complete', series_dict))
                
                # Force immediate processing
                Clock.schedule_once(lambda dt: self._force_complete_check(), 0)
                
        except Exception as e:
            if not self.should_stop:
                self.queue.put(('error', f"Organization error: {e}"))
        
        self.running = False
    
    def _force_complete_check(self):
        try:
            while True:
                message = self.queue.get_nowait()
                msg_type = message[0]
                
                if msg_type == 'complete':
                    data = message[1]
                    print(f"✅ FORCE PROCESSING COMPLETE: {len(data)} series")
                    self.callback('complete', data)
                    return
                else:
                    if msg_type == 'progress':
                        self.callback('progress', message[1], message[2] if len(message) > 2 else "")
                        
        except queue.Empty:
            pass
    
    def _get_instance_number(self, file_path):
        try:
            dcm = pydicom.dcmread(file_path, stop_before_pixels=True, force=True)
            return int(getattr(dcm, 'InstanceNumber', 0))
        except:
            return 0
    
    def _check_queue(self, dt):
        try:
            processed = 0
            while processed < 10:
                message = self.queue.get_nowait()
                processed += 1
                
                msg_type = message[0]
                
                if msg_type == 'progress':
                    progress = message[1]
                    status = message[2] if len(message) > 2 else ""
                    self.callback('progress', progress, status)
                    
                elif msg_type == 'complete':
                    data = message[1]
                    self.callback('complete', data)
                    Clock.unschedule(self._check_queue)
                    return False
                    
                elif msg_type == 'scan_complete':
                    data = message[1]
                    self.callback('scan_complete', data)
                    Clock.unschedule(self._check_queue)
                    return False
                    
                elif msg_type == 'error':
                    data = message[1]
                    self.callback('error', data)
                    Clock.unschedule(self._check_queue)
                    return False
                    
        except queue.Empty:
            pass
        except Exception as e:
            print(f"Queue check error: {e}")
        
        return True

# Main DICOM Viewer App with Separated Interfaces
class DICOMViewer(App):
    def build(self):
        self.title = "🏥DICOM Viewer - Professional Medical Imaging"
        self.current_files = []
        self.current_index = 0
        self.series_data = {}
        self.progress_popup = None
        
        Window.clearcolor = (0.94, 0.94, 0.94, 1)
        
        # Enhanced loader
        self.async_loader = UltraFastDICOMLoader(self.on_async_update)
        
        # Create main container
        self.root_container = BoxLayout()
        
        # Build main interface
        self.build_main_interface()
        
        # Create video interface (hidden initially)
        self.video_interface = DICOMVideoPlayerInterface(self)
        
        Window.bind(on_key_down=self.on_key_down)
        
        return self.root_container

    def show_main_interface(self):
        """Show the main DICOM viewer interface"""
        self.root_container.clear_widgets()
        self.root_container.add_widget(self.main_interface)

    def show_video_interface(self, video_files=None):
        """Show the dedicated video player interface"""
        self.root_container.clear_widgets()
        self.root_container.add_widget(self.video_interface)
        
        if video_files:
            self.video_interface.populate_video_files(video_files)

    def build_main_interface(self):
        """Build the main interface for regular DICOM images"""
        self.main_interface = BoxLayout(orientation="vertical")
        
        # Main toolbar
        toolbar = self.create_main_toolbar()
        self.main_interface.add_widget(toolbar)
        
        # Content area
        content_area = BoxLayout(orientation="horizontal")
        
        self.left_panel = BoxLayout(orientation="vertical", size_hint=(0.25, 1))
        self.left_panel.opacity = 0
        
        self.center_area = BoxLayout(orientation="vertical")
        self.build_welcome_area()
        
        self.right_panel = BoxLayout(orientation="vertical", size_hint=(0.25, 1))
        self.right_panel.opacity = 0
        
        content_area.add_widget(self.left_panel)
        content_area.add_widget(self.center_area)
        content_area.add_widget(self.right_panel)
        
        self.main_interface.add_widget(content_area)
        
        # Status bar
        self.status_bar = ColoredLabel(
            text="🏥DICOM Viewer Ready - Professional Medical Imaging",
            size_hint_y=None,
            height=25,
            font_size=11,
            bg_color=(0.85, 0.85, 0.85, 1)
        )
        self.main_interface.add_widget(self.status_bar)
        
        # Show main interface initially
        self.root_container.add_widget(self.main_interface)

    def create_main_toolbar(self):
        toolbar = BoxLayout(size_hint_y=None, height=50, spacing=5, padding=[10, 5, 10, 5])
        
        # Open button
        open_btn = Button(
            text="📁 Open Files",
            size_hint_x=None,
            width=100,
            background_color=(0.3, 0.6, 0.9, 1),
            font_size=14
        )
        open_btn.bind(on_release=self.show_file_chooser)
        
        folder_btn = Button(
            text="📁 Open Folder",
            size_hint_x=None,
            width=110,
            background_color=(0.2, 0.8, 0.2, 1),
            font_size=14
        )
        folder_btn.bind(on_release=self.show_folder_chooser)
        
        sep1 = ColoredLabel(text="|", size_hint_x=None, width=20, bg_color=(0.7, 0.7, 0.7, 1))
        
        # Video interface button
        video_btn = Button(
            text="🎥 Video Player",
            size_hint_x=None,
            width=120,
            background_color=(0.8, 0.3, 0.3, 1),
            font_size=14,
            bold=True
        )
        video_btn.bind(on_release=self.launch_video_interface)
        
        sep2 = ColoredLabel(text="|", size_hint_x=None, width=20, bg_color=(0.7, 0.7, 0.7, 1))
        
        # Navigation
        prev_btn = Button(text="◀ Prev", size_hint_x=None, width=70, background_color=(0.5, 0.5, 0.5, 1))
        next_btn = Button(text="Next ▶", size_hint_x=None, width=70, background_color=(0.5, 0.5, 0.5, 1))
        
        prev_btn.bind(on_release=self.prev_image)
        next_btn.bind(on_release=self.next_image)
        
        sep3 = ColoredLabel(text="|", size_hint_x=None, width=20, bg_color=(0.7, 0.7, 0.7, 1))
        
        # Tools
        fit_btn = Button(text="Fit", size_hint_x=None, width=50, background_color=(0.4, 0.4, 0.4, 1))
        
        spacer = Label()
        
        # About
        about_btn = Button(text="ℹ About", size_hint_x=None, width=70, background_color=(0.4, 0.4, 0.4, 1))
        about_btn.bind(on_release=self.show_about)
        
        toolbar.add_widget(open_btn)
        toolbar.add_widget(folder_btn)
        toolbar.add_widget(sep1)
        toolbar.add_widget(video_btn)
        toolbar.add_widget(sep2)
        toolbar.add_widget(prev_btn)
        toolbar.add_widget(next_btn)
        toolbar.add_widget(sep3)
        toolbar.add_widget(fit_btn)
        toolbar.add_widget(spacer)
        toolbar.add_widget(about_btn)
        
        return toolbar

    def launch_video_interface(self, instance):
        """Launch the dedicated video player interface"""
        self.show_video_interface()

    def build_welcome_area(self):
        self.center_area.clear_widgets()
        
        welcome_layout = BoxLayout(orientation="vertical", spacing=30, padding=[50, 50, 50, 50])
        
        # Title area
        title_area = BoxLayout(orientation="vertical", size_hint_y=None, height=150)
        
        logo_label = Label(text="🏥📷🎥", font_size=64, size_hint_y=None, height=80)
        title_label = Label(
            text="🏥DICOM Viewer - Professional Edition",
            font_size=26,
            bold=True,
            color=(0.2, 0.4, 0.8, 1),
            size_hint_y=None,
            height=50
        )
        subtitle_label = Label(
            text="Separate Interfaces for Images & Videos • Professional Medical Workflow",
            font_size=14,
            color=(0.5, 0.5, 0.5, 1),
            size_hint_y=None,
            height=20
        )
        
        title_area.add_widget(logo_label)
        title_area.add_widget(title_label)
        title_area.add_widget(subtitle_label)
        welcome_layout.add_widget(title_area)
        
        # Quick start with separated options
        quick_start = GridLayout(cols=2, spacing=20, size_hint_y=None, height=240, row_default_height=90)
        
        # Image viewing options
        open_files_btn = Button(
            text="📄\nOpen DICOM Files\nStandard Images",
            background_color=(0.3, 0.7, 0.3, 1),
            font_size=14,
            halign="center"
        )
        open_files_btn.bind(on_release=self.show_file_chooser)
        
        open_folder_btn = Button(
            text="📁\nOpen DICOM Folder\nUltra-Fast Scanning",
            background_color=(0.2, 0.8, 0.2, 1),
            font_size=14,
            halign="center",
            bold=True
        )
        open_folder_btn.bind(on_release=self.show_folder_chooser)
        
        # Video viewing options
        video_player_btn = Button(
            text="🎥\nDICOM Video Player\nDedicated Video Interface",
            background_color=(0.8, 0.3, 0.3, 1),
            font_size=14,
            halign="center",
            bold=True
        )
        video_player_btn.bind(on_release=self.launch_video_interface)
        
        about_btn = Button(
            text="ℹ\nAbout & Help\nFeatures & Usage Guide",
            background_color=(0.4, 0.4, 0.8, 1),
            font_size=14,
            halign="center"
        )
        about_btn.bind(on_release=self.show_about)
        
        quick_start.add_widget(open_files_btn)
        quick_start.add_widget(open_folder_btn)
        quick_start.add_widget(video_player_btn)
        quick_start.add_widget(about_btn)
        
        welcome_layout.add_widget(quick_start)
        
        # Feature info
        info_label = ColoredLabel(
            text="🏥 SEPARATED PROFESSIONAL INTERFACES:\n\n📷 IMAGE INTERFACE: Standard DICOM images with series organization\n🎥 VIDEO INTERFACE: Dedicated video player with frame controls\n📁 FOLDER SCANNING: Ultra-fast detection and organization\n⚡ PROFESSIONAL WORKFLOW: Optimized for medical professionals",
            size_hint_y=None,
            height=120,
            bg_color=(0.95, 0.98, 1.0, 1),
            color=(0.1, 0.3, 0.7, 1),
            font_size=12,
            bold=True
        )
        welcome_layout.add_widget(info_label)
        
        self.center_area.add_widget(welcome_layout)

    def show_file_chooser(self, instance):
        """Show file chooser for individual files"""
        content = BoxLayout(orientation="vertical", spacing=10)
        
        filechooser = FileChooserIconView(multiselect=True, size_hint=(1, 0.8))
        
        try:
            documents_path = os.path.expanduser("~/Documents")
            if os.path.exists(documents_path):
                filechooser.path = documents_path
            else:
                filechooser.path = os.path.expanduser("~")
        except:
            filechooser.path = os.getcwd()
            
        content.add_widget(filechooser)
        
        info_label = Label(
            text="📷 Select DICOM files for standard image viewing",
            size_hint_y=None,
            height=30,
            font_size=12,
            color=(0.2, 0.6, 0.2, 1),
            bold=True
        )
        content.add_widget(info_label)
        
        btn_layout = BoxLayout(size_hint=(1, 0.15), spacing=10)
        
        load_btn = Button(text="📷 Load for Image Viewing", background_color=(0.3, 0.7, 0.3, 1), bold=True)
        video_btn = Button(text="🎥 Load for Video Player", background_color=(0.8, 0.3, 0.3, 1), bold=True)
        cancel_btn = Button(text="Cancel", background_color=(0.6, 0.6, 0.6, 1))
        
        btn_layout.add_widget(load_btn)
        btn_layout.add_widget(video_btn)
        btn_layout.add_widget(cancel_btn)
        content.add_widget(btn_layout)
        
        popup = Popup(title="📁 Select DICOM Files", content=content, size_hint=(0.9, 0.8))
        
        def load_for_images(btn):
            if filechooser.selection:
                popup.dismiss()
                self.load_files_with_progress(filechooser.selection)
            else:
                self.show_error("Please select files to load")
        
        def load_for_videos(btn):
            if filechooser.selection:
                popup.dismiss()
                # Filter for video files and launch video interface
                video_files = [f for f in filechooser.selection if self.is_video_file(f)]
                if video_files:
                    self.show_video_interface(video_files)
                else:
                    self.show_error("No DICOM video files found in selection")
            else:
                self.show_error("Please select files to load")
                
        load_btn.bind(on_release=load_for_images)
        video_btn.bind(on_release=load_for_videos)
        cancel_btn.bind(on_release=lambda x: popup.dismiss())
        popup.open()

    def show_file_chooser_for_videos(self):
        """Show file chooser specifically for video files"""
        content = BoxLayout(orientation="vertical", spacing=10)
        
        filechooser = FileChooserIconView(multiselect=True, size_hint=(1, 0.8))
        
        try:
            documents_path = os.path.expanduser("~/Documents")
            if os.path.exists(documents_path):
                filechooser.path = documents_path
            else:
                filechooser.path = os.path.expanduser("~")
        except:
            filechooser.path = os.getcwd()
            
        content.add_widget(filechooser)
        
        info_label = Label(
            text="🎥 Select DICOM video files for video player interface",
            size_hint_y=None,
            height=30,
            font_size=12,
            color=(0.8, 0.2, 0.2, 1),
            bold=True
        )
        content.add_widget(info_label)
        
        btn_layout = BoxLayout(size_hint=(1, 0.15), spacing=10)
        
        load_btn = Button(text="🎥 Load Video Files", background_color=(0.8, 0.3, 0.3, 1), bold=True)
        cancel_btn = Button(text="Cancel", background_color=(0.6, 0.6, 0.6, 1))
        
        btn_layout.add_widget(load_btn)
        btn_layout.add_widget(cancel_btn)
        content.add_widget(btn_layout)
        
        popup = Popup(title="🎥 Select DICOM Video Files", content=content, size_hint=(0.9, 0.8))
        
        def load_videos(btn):
            if filechooser.selection:
                popup.dismiss()
                video_files = [f for f in filechooser.selection if self.is_video_file(f)]
                if video_files:
                    self.video_interface.populate_video_files(video_files)
                else:
                    self.show_error("No DICOM video files found in selection")
            else:
                self.show_error("Please select video files to load")
                
        load_btn.bind(on_release=load_videos)
        cancel_btn.bind(on_release=lambda x: popup.dismiss())
        popup.open()

    def show_folder_chooser(self, instance=None):
        """Show folder chooser for batch processing"""
        content = BoxLayout(orientation="vertical", spacing=10)
        
        filechooser = FileChooserIconView(dirselect=True, size_hint=(1, 0.8))
        
        try:
            documents_path = os.path.expanduser("~/Documents")
            if os.path.exists(documents_path):
                filechooser.path = documents_path
            else:
                filechooser.path = os.path.expanduser("~")
        except:
            filechooser.path = os.getcwd()
            
        content.add_widget(filechooser)
        
        options_layout = BoxLayout(size_hint=(1, 0.1), spacing=10)
        recursive_btn = Button(
            text="📁 Include Subfolders", 
            background_color=(0.5, 0.5, 0.8, 1),
            size_hint=(0.6, 1)
        )
        info_label = Label(
            text="⚡ ULTRA-FAST SCAN",
            font_size=11,
            color=(0.1, 0.8, 0.1, 1),
            bold=True
        )
        options_layout.add_widget(recursive_btn)
        options_layout.add_widget(info_label)
        content.add_widget(options_layout)
        
        btn_layout = BoxLayout(size_hint=(1, 0.12), spacing=5)
        
        scan_btn = Button(text="📷 Scan for Images", background_color=(0.3, 0.7, 0.3, 1), bold=True)
        video_scan_btn = Button(text="🎥 Scan for Videos", background_color=(0.8, 0.3, 0.3, 1), bold=True)
        both_btn = Button(text="📁 Scan All", background_color=(0.1, 0.9, 0.1, 1), bold=True)
        cancel_btn = Button(text="Cancel", background_color=(0.6, 0.6, 0.6, 1))
        
        btn_layout.add_widget(scan_btn)
        btn_layout.add_widget(video_scan_btn)
        btn_layout.add_widget(both_btn)
        btn_layout.add_widget(cancel_btn)
        content.add_widget(btn_layout)
        
        popup = Popup(title="📁 Select DICOM Folder", content=content, size_hint=(0.8, 0.7))
        
        recursive = [False]
        
        def toggle_recursive(btn):
            recursive[0] = not recursive[0]
            btn.background_color = (0.3, 0.7, 0.3, 1) if recursive[0] else (0.5, 0.5, 0.8, 1)
            btn.text = "✓ Include Subfolders" if recursive[0] else "📁 Include Subfolders"
        
        def scan_for_images(btn):
            if filechooser.selection:
                popup.dismiss()
                self.scan_folder_with_progress(filechooser.selection[0], recursive[0])
            else:
                self.show_error("Please select a folder to scan")
        
        def scan_for_videos(btn):
            if filechooser.selection:
                popup.dismiss()
                self.scan_folder_for_videos(filechooser.selection[0], recursive[0])
            else:
                self.show_error("Please select a folder to scan")
        
        def scan_all(btn):
            if filechooser.selection:
                popup.dismiss()
                self.scan_folder_with_progress(filechooser.selection[0], recursive[0], show_video_option=True)
            else:
                self.show_error("Please select a folder to scan")
            
        recursive_btn.bind(on_release=toggle_recursive)
        scan_btn.bind(on_release=scan_for_images)
        video_scan_btn.bind(on_release=scan_for_videos)
        both_btn.bind(on_release=scan_all)
        cancel_btn.bind(on_release=lambda x: popup.dismiss())
        popup.open()

    def show_folder_chooser_for_videos(self):
        """Show folder chooser specifically for videos"""
        content = BoxLayout(orientation="vertical", spacing=10)
        
        filechooser = FileChooserIconView(dirselect=True, size_hint=(1, 0.8))
        
        try:
            documents_path = os.path.expanduser("~/Documents")
            if os.path.exists(documents_path):
                filechooser.path = documents_path
            else:
                filechooser.path = os.path.expanduser("~")
        except:
            filechooser.path = os.getcwd()
            
        content.add_widget(filechooser)
        
        options_layout = BoxLayout(size_hint=(1, 0.1), spacing=10)
        recursive_btn = Button(
            text="📁 Include Subfolders", 
            background_color=(0.5, 0.5, 0.8, 1),
            size_hint=(0.7, 1)
        )
        info_label = Label(
            text="🎥 VIDEO SCAN",
            font_size=11,
            color=(0.8, 0.1, 0.1, 1),
            bold=True
        )
        options_layout.add_widget(recursive_btn)
        options_layout.add_widget(info_label)
        content.add_widget(options_layout)
        
        btn_layout = BoxLayout(size_hint=(1, 0.1), spacing=10)
        
        scan_btn = Button(text="🎥 SCAN FOR VIDEOS", background_color=(0.8, 0.1, 0.1, 1), bold=True)
        cancel_btn = Button(text="Cancel", background_color=(0.6, 0.6, 0.6, 1))
        
        btn_layout.add_widget(scan_btn)
        btn_layout.add_widget(cancel_btn)
        content.add_widget(btn_layout)
        
        popup = Popup(title="🎥 Scan Folder for DICOM Videos", content=content, size_hint=(0.8, 0.7))
        
        recursive = [False]
        
        def toggle_recursive(btn):
            recursive[0] = not recursive[0]
            btn.background_color = (0.3, 0.7, 0.3, 1) if recursive[0] else (0.5, 0.5, 0.8, 1)
            btn.text = "✓ Include Subfolders" if recursive[0] else "📁 Include Subfolders"
        
        def scan_videos(btn):
            if filechooser.selection:
                popup.dismiss()
                self.scan_folder_for_videos(filechooser.selection[0], recursive[0])
            else:
                self.show_error("Please select a folder to scan")
            
        recursive_btn.bind(on_release=toggle_recursive)
        scan_btn.bind(on_release=scan_videos)
        cancel_btn.bind(on_release=lambda x: popup.dismiss())
        popup.open()

    def is_video_file(self, file_path):
        """Check if a file is a DICOM video"""
        try:
            return is_dicom_video(file_path)
        except:
            return False

    def scan_folder_with_progress(self, folder_path, recursive=False, show_video_option=False):
        """Scan folder for images with progress dialog"""
        self.show_video_option_after_scan = show_video_option
        self.show_progress_dialog("📁 DICOM Folder Scan", "Ultra-fast DICOM detection...", True)
        self.async_loader.scan_folder_async(folder_path, recursive)

    def scan_folder_for_videos(self, folder_path, recursive=False):
        """Scan folder specifically for videos"""
        def scan_video_worker():
            try:
                print(f"🎥 Scanning for DICOM videos in: {folder_path}")
                
                dicom_files = scan_folder_ultrafast(folder_path, recursive)
                video_files = []
                
                for file_path in dicom_files:
                    if is_dicom_video(file_path):
                        video_files.append(file_path)
                
                Clock.schedule_once(lambda dt: self.video_scan_complete(video_files), 0)
                
            except Exception:
                Clock.schedule_once(lambda dt: self.show_error(f"Video scan error"), 0)
        
        self.show_progress_dialog("🎥 Video Scan", "Scanning for DICOM videos...", True)
        
        thread = threading.Thread(target=scan_video_worker)
        thread.daemon = True
        thread.start()

    def video_scan_complete(self, video_files):
        """Handle completion of video scan"""
        if self.progress_popup:
            self.progress_popup.dismiss()
            self.progress_popup = None
        
        if video_files:
            self.show_video_interface(video_files)
        else:
            self.show_error("No DICOM video files found in the selected folder.")

    def load_files_with_progress(self, file_list):
        """Load files with progress dialog"""
        potential_dicom = [f for f in file_list if os.path.isfile(f)]
        
        if potential_dicom:
            self.show_progress_dialog("📷 Loading Files", "Loading DICOM files...", True)
            self.async_loader.load_files_async(potential_dicom)
        else:
            self.show_error("No valid files found in selection")

    def show_progress_dialog(self, title, message, cancelable=False):
        content = BoxLayout(orientation="vertical", spacing=20, padding=20)
        
        msg_label = Label(text=message, size_hint_y=None, height=40, font_size=14, bold=True)
        content.add_widget(msg_label)
        
        self.progress_bar = ProgressBar(size_hint_y=None, height=30)
        content.add_widget(self.progress_bar)
        
        self.progress_status = Label(text="🏥 Initializing...", size_hint_y=None, height=30, font_size=12, bold=True)
        content.add_widget(self.progress_status)
        
        if cancelable:
            cancel_btn = Button(
                text="Cancel", 
                size_hint_y=None, 
                height=40,
                background_color=(0.7, 0.3, 0.3, 1)
            )
            cancel_btn.bind(on_release=self.cancel_loading)
            content.add_widget(cancel_btn)
        
        self.progress_popup = Popup(
            title=title,
            content=content,
            size_hint=(0.6, 0.45 if cancelable else 0.35),
            auto_dismiss=False
        )
        self.progress_popup.open()

    def cancel_loading(self, instance):
        if self.async_loader:
            self.async_loader.stop_loading()
        if self.progress_popup:
            self.progress_popup.dismiss()
            self.progress_popup = None
        self.status_bar.text = "🏥 Operation cancelled - Ready for next scan"

    def on_async_update(self, msg_type, data, status=None):
        """Handle async updates"""
        if msg_type == 'progress':
            if self.progress_popup:
                self.progress_bar.value = data
                self.progress_status.text = status if status else "Processing..."
                
        elif msg_type == 'scan_complete':
            if self.progress_popup:
                self.progress_popup.dismiss()
                self.progress_popup = None
            
            if data:
                if hasattr(self, 'show_video_option_after_scan') and self.show_video_option_after_scan:
                    # Show option to choose interface
                    self.show_interface_choice(data)
                else:
                    self.status_bar.text = f"📁 Scan found {len(data)} DICOM files, organizing..."
                    self.load_files_with_progress(data)
            else:
                self.show_error("No DICOM files found in selected folder")
                
        elif msg_type == 'complete':
            if self.progress_popup:
                self.progress_popup.dismiss()
                self.progress_popup = None
            
            if data:
                self.build_viewer_interface(data)
            else:
                self.show_error("No valid DICOM files found")
                
        elif msg_type == 'error':
            if self.progress_popup:
                self.progress_popup.dismiss()
                self.progress_popup = None
            self.show_error(data)

    def show_interface_choice(self, dicom_files):
        """Show choice between image and video interface"""
        # Separate videos and images
        video_files = [f for f in dicom_files if is_dicom_video(f)]
        image_files = [f for f in dicom_files if not is_dicom_video(f)]
        
        content = BoxLayout(orientation="vertical", spacing=20, padding=20)
        
        info_label = Label(
            text=f"📁 Scan Results:\n📷 {len(image_files)} Image files\n🎥 {len(video_files)} Video files\n\nChoose interface:",
            size_hint_y=None,
            height=100,
            font_size=14,
            halign="center"
        )
        content.add_widget(info_label)
        
        btn_layout = BoxLayout(size_hint_y=None, height=60, spacing=10)
        
        if image_files:
            image_btn = Button(text=f"📷 Image Interface\n({len(image_files)} files)", background_color=(0.3, 0.7, 0.3, 1))
            image_btn.bind(on_release=lambda x: [popup.dismiss(), self.load_files_with_progress(image_files)])
            btn_layout.add_widget(image_btn)
        
        if video_files:
            video_btn = Button(text=f"🎥 Video Interface\n({len(video_files)} files)", background_color=(0.8, 0.3, 0.3, 1))
            video_btn.bind(on_release=lambda x: [popup.dismiss(), self.show_video_interface(video_files)])
            btn_layout.add_widget(video_btn)
        
        if image_files and video_files:
            both_btn = Button(text="📷 Load Images\n(Videos available via Video Player)", background_color=(0.5, 0.5, 0.8, 1))
            both_btn.bind(on_release=lambda x: [popup.dismiss(), self.load_files_with_progress(image_files)])
            btn_layout.add_widget(both_btn)
        
        content.add_widget(btn_layout)
        
        popup = Popup(title="🏥 Choose Interface", content=content, size_hint=(0.7, 0.5))
        popup.open()

    def build_viewer_interface(self, series_dict):
        """Build the main image viewer interface"""
        self.series_data = series_dict
        
        self.left_panel.opacity = 1
        self.right_panel.opacity = 1
        
        self.build_series_panel()
        self.build_main_viewer()
        self.build_info_panel()
        
        if series_dict:
            first_series_key = list(series_dict.keys())[0]
            first_series = series_dict[first_series_key]
            self.load_series(first_series)
        
        total_images = sum(len(s['files']) for s in series_dict.values())
        image_count = sum(1 for s in series_dict.values() if not s.get('is_video', False))
        
        self.status_bar.text = f"🏥 Loading complete: {len(series_dict)} series, {total_images} images loaded"

    def build_series_panel(self):
        self.left_panel.clear_widgets()
        
        header = ColoredLabel(
            text=f"📷 Image Series ({len(self.series_data)})",
            size_hint_y=None,
            height=35,
            font_size=14,
            bold=True,
            bg_color=(0.75, 0.85, 0.75, 1)
        )
        self.left_panel.add_widget(header)
        
        scroll = ScrollView()
        series_layout = GridLayout(cols=1, size_hint_y=None, spacing=2)
        series_layout.bind(minimum_height=series_layout.setter('height'))
        
        for series_key, series_info in self.series_data.items():
            # Only show non-video series in main interface
            if not series_info.get('is_video', False):
                series_btn = Button(
                    text=f"📷 {series_key}\n{len(series_info['files'])} images",
                    size_hint_y=None,
                    height=80,
                    background_color=(0.95, 0.98, 0.95, 1),
                    font_size=9,
                    halign="center"
                )
                series_btn.bind(on_release=lambda x, s=series_info: self.load_series(s))
                series_layout.add_widget(series_btn)
        
        scroll.add_widget(series_layout)
        self.left_panel.add_widget(scroll)

    def build_main_viewer(self):
        self.center_area.clear_widgets()
        
        self.viewer_container = BoxLayout()
        self.image = Image()
        self.viewer_container.add_widget(self.image)
        self.center_area.add_widget(self.viewer_container)

    def build_info_panel(self):
        self.right_panel.clear_widgets()
        
        header = ColoredLabel(
            text="📋 Medical Information",
            size_hint_y=None,
            height=35,
            font_size=14,
            bold=True,
            bg_color=(0.75, 0.8, 0.9, 1)
        )
        self.right_panel.add_widget(header)
        
        info_scroll = ScrollView()
        self.info_label = Label(
            text="Select a series to view medical information",
            halign="left",
            valign="top",
            size_hint_y=None,
            text_size=(200, None),
            font_size=10
        )
        self.info_label.bind(texture_size=self.info_label.setter("size"))
        info_scroll.add_widget(self.info_label)
        self.right_panel.add_widget(info_scroll)

    def load_series(self, series_info):
        """Load a series for viewing"""
        self.current_files = series_info['files']
        self.current_index = 0
        self.show_current_item()

    def show_current_item(self):
        """Show current image"""
        if not self.current_files:
            return
            
        current_file = self.current_files[self.current_index]
        self.show_image_item(current_file)

    def show_image_item(self, file_path):
        """Display a DICOM image"""
        try:
            def load_image():
                try:
                    dcm = pydicom.dcmread(file_path, force=True)
                    
                    if hasattr(dcm, 'pixel_array'):
                        pixel_array = dcm.pixel_array
                        
                        # Handle multi-frame (but show first frame only)
                        if len(pixel_array.shape) > 2:
                            if len(pixel_array.shape) == 3:
                                pixel_array = pixel_array[0]
                            else:
                                pixel_array = pixel_array[0]
                        
                        # Enhanced normalization
                        if pixel_array.dtype != np.uint8:
                            pixel_min = np.min(pixel_array)
                            pixel_max = np.max(pixel_array)
                            if pixel_max > pixel_min:
                                try:
                                    window_center = getattr(dcm, 'WindowCenter', None)
                                    window_width = getattr(dcm, 'WindowWidth', None)
                                    
                                    if window_center is not None and window_width is not None:
                                        if isinstance(window_center, (list, tuple)):
                                            window_center = window_center[0]
                                        if isinstance(window_width, (list, tuple)):
                                            window_width = window_width[0]
                                        
                                        img_min = window_center - window_width // 2
                                        img_max = window_center + window_width // 2
                                        img = np.clip(pixel_array, img_min, img_max)
                                        img = ((img - img_min) / (img_max - img_min) * 255).astype(np.uint8)
                                    else:
                                        img = ((pixel_array - pixel_min) / (pixel_max - pixel_min) * 255).astype(np.uint8)
                                except:
                                    img = ((pixel_array - pixel_min) / (pixel_max - pixel_min) * 255).astype(np.uint8)
                            else:
                                img = np.full_like(pixel_array, 128, dtype=np.uint8)
                        else:
                            img = pixel_array
                        
                        Clock.schedule_once(lambda dt: self.update_image_display(img, dcm, file_path), 0)
                    
                except Exception as e:
                    error_msg = f"Error loading {os.path.basename(file_path)}: {e}"
                    Clock.schedule_once(lambda dt: self.show_error(error_msg), 0)
            
            thread = threading.Thread(target=load_image)
            thread.daemon = True
            thread.start()
            
        except Exception as e:
            self.show_error(f"Image loading error: {e}")

    def update_image_display(self, img, dcm, file_path):
        """Update image display"""
        try:
            if len(img.shape) == 3:
                if img.shape[2] == 3:  # RGB
                    texture = Texture.create(size=(img.shape[1], img.shape[0]), colorfmt="rgb")
                    texture.blit_buffer(img.tobytes(), colorfmt="rgb", bufferfmt="ubyte")
                elif img.shape[2] == 4:  # RGBA
                    texture = Texture.create(size=(img.shape[1], img.shape[0]), colorfmt="rgba")
                    texture.blit_buffer(img.tobytes(), colorfmt="rgba", bufferfmt="ubyte")
                else:
                    img = np.mean(img, axis=2).astype(np.uint8)
                    texture = Texture.create(size=(img.shape[1], img.shape[0]), colorfmt="luminance")
                    texture.blit_buffer(img.tobytes(), colorfmt="luminance", bufferfmt="ubyte")
            else:
                texture = Texture.create(size=(img.shape[1], img.shape[0]), colorfmt="luminance")
                texture.blit_buffer(img.tobytes(), colorfmt="luminance", bufferfmt="ubyte")
            
            texture.flip_vertical()
            self.image.texture = texture
            
            self.update_info_display(dcm, file_path)
            
        except Exception as e:
            self.show_error(f"Display update error: {e}")

    def update_info_display(self, dcm, file_path):
        """Update medical information display"""
        try:
            frames = getattr(dcm, 'NumberOfFrames', '1')
            
            info_text = f"""📷 DICOM IMAGE

PATIENT:
━━━━━━━━━━━━━━━━━━━━━
Name: {getattr(dcm, 'PatientName', 'N/A')}
ID: {getattr(dcm, 'PatientID', 'N/A')}
Sex: {getattr(dcm, 'PatientSex', 'N/A')}
Age: {getattr(dcm, 'PatientAge', 'N/A')}

STUDY:
━━━━━━━━━━━━━━━━━━━━━
Date: {getattr(dcm, 'StudyDate', 'N/A')}
Description: {getattr(dcm, 'StudyDescription', 'N/A')}
ID: {getattr(dcm, 'StudyID', 'N/A')}

SERIES:
━━━━━━━━━━━━━━━━━━━━━
Modality: {getattr(dcm, 'Modality', 'N/A')}
Description: {getattr(dcm, 'SeriesDescription', 'N/A')}
Number: {getattr(dcm, 'SeriesNumber', 'N/A')}

IMAGE:
━━━━━━━━━━━━━━━━━━━━━
Instance: {getattr(dcm, 'InstanceNumber', 'N/A')}
Size: {getattr(dcm, 'Rows', 'N/A')} × {getattr(dcm, 'Columns', 'N/A')}
Frames: {frames}

NAVIGATION:
━━━━━━━━━━━━━━━━━━━━━
Item: {self.current_index + 1} / {len(self.current_files)}
File: {os.path.basename(file_path)}

🏥 Use ← → keys or toolbar buttons
🎥 Use Video Player for video files"""
            
            self.info_label.text = info_text
            
        except Exception as e:
            self.info_label.text = f"Error loading info: {e}"

    def prev_image(self, instance=None):
        if self.current_files and self.current_index > 0:
            self.current_index -= 1
            self.show_current_item()

    def next_image(self, instance=None):
        if self.current_files and self.current_index < len(self.current_files) - 1:
            self.current_index += 1
            self.show_current_item()

    def show_about(self, instance):
        content = Label(
            text="""🏥 DICOM Viewer - Professional Edition

SEPARATED INTERFACES:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📷 IMAGE INTERFACE:
• Standard DICOM image viewing
• Series-based organization
• Professional medical metadata
• Window/level processing
• Ultra-fast folder scanning

🎥 VIDEO INTERFACE:
• Dedicated DICOM video player
• Frame-by-frame navigation
• Play/Pause/Stop controls
• Adjustable playback speed (FPS)
• Professional video analysis tools

PROFESSIONAL WORKFLOW:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Separate optimized interfaces
• Automatic content detection
• Choice of viewing modes
• Medical-grade image processing
• Professional metadata display

SUPPORTED FORMATS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Standard DICOM images (CT, MR, US, etc.)
• DICOM Video (Endoscopic, Photographic)
• Multi-frame DICOM files
• All medical imaging modalities

CONTROLS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Arrow Keys: Navigate images/frames
• Toolbar: Quick access to all functions
• Separate interfaces for optimal workflow

🏥 Built for Medical Excellence & Professional Use""",
            halign="center",
            font_size=10
        )
        
        popup = Popup(title="🏥 About DICOM Viewer", content=content, size_hint=(0.8, 0.9))
        popup.open()

    def show_error(self, message):
        popup = Popup(title="Error", content=Label(text=str(message)), size_hint=(0.6, 0.4))
        popup.open()

    def on_key_down(self, window, key, scancode, codepoint, modifier):
        # Check which interface is active
        if len(self.root_container.children) > 0:
            current_interface = self.root_container.children[0]
            
            if isinstance(current_interface, DICOMVideoPlayerInterface):
                # Video interface controls
                if key == 275:  # Right arrow
                    current_interface.next_frame(None)
                elif key == 276:  # Left arrow
                    current_interface.prev_frame(None)
                elif key == 32:  # Spacebar
                    if current_interface.is_playing:
                        current_interface.pause_video(None)
                    else:
                        current_interface.play_video(None)
            else:
                # Main image interface controls
                if key == 275:  # Right arrow
                    self.next_image()
                elif key == 276:  # Left arrow
                    self.prev_image()
                elif key == 32:  # Spacebar - switch to video interface
                    self.launch_video_interface(None)
            
            if key == 27:  # Escape
                if self.progress_popup:
                    self.cancel_loading(None)

if __name__ == "__main__":
    print("="*70)
    print("🏥 🏥 🏥DICOM VIEWER - SEPARATED INTERFACES 🏥 🏥 🏥")
    print("="*70)
    print("📷 IMAGE INTERFACE:")
    print("   • Professional DICOM image viewing")
    print("   • Series organization and metadata")
    print("   • Ultra-fast folder scanning")
    print("   • Medical-grade image processing")
    print("")
    print("🎥 VIDEO INTERFACE:")
    print("   • Dedicated DICOM video player")
    print("   • Full playback controls")
    print("   • Frame-by-frame analysis")
    print("   • Professional video workflow")
    print("="*70)
    print("🎮 CONTROLS:")
    print("   • Arrow Keys: Navigate content")
    print("   • Spacebar: Video play/pause or switch interface")
    print("   • Separate optimized interfaces")
    print("="*70)
    DICOMViewer().run()
