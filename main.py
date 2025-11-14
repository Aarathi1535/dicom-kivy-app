# secure_dicom_viewer_complete.py
# Complete Thread-Safe Secure DICOM Viewer with Authentication and Embedded Storage

import os
import json
import shutil
import hashlib
import threading
from datetime import datetime

import numpy as np
import pydicom

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle
from kivy.graphics.texture import Texture
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.filechooser import FileChooserIconView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.progressbar import ProgressBar
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

# ============== Windows/System-Safe Helpers ==============

def safe_exists(path):
    """Safe file existence check that handles locked files"""
    try:
        return os.path.exists(path)
    except Exception:
        return False

def is_windows():
    """Check if running on Windows"""
    return os.name == "nt"

def is_windows_locked_or_system(path):
    """Check if path is a Windows system/locked file to avoid access errors"""
    up = os.path.abspath(path)
    if not is_windows():
        return False
    
    # Known protected paths
    protected_roots = [
        r"C:\Windows",
        r"C:\$Recycle.Bin", 
        r"C:\System Volume Information",
        r"C:\swapfile.sys",
        r"C:\pagefile.sys",
    ]
    
    for pr in protected_roots:
        if up == pr or up.startswith(pr + os.sep):
            return True
    
    # Check file attributes
    try:
        import ctypes
        from ctypes import wintypes
        FILE_ATTRIBUTE_SYSTEM = 0x4
        FILE_ATTRIBUTE_HIDDEN = 0x2
        GetFileAttributesW = ctypes.windll.kernel32.GetFileAttributesW
        GetFileAttributesW.argtypes = [wintypes.LPCWSTR]
        GetFileAttributesW.restype = wintypes.DWORD
        attrs = GetFileAttributesW(up)
        if attrs == 0xFFFFFFFF:
            return True
        return bool(attrs & (FILE_ATTRIBUTE_SYSTEM | FILE_ATTRIBUTE_HIDDEN))
    except Exception:
        return False

def filtered_walk(source_dir):
    """Safe directory walk that skips system/protected directories"""
    for root, dirs, files in os.walk(source_dir):
        if is_windows():
            dirs[:] = [d for d in dirs if not is_windows_locked_or_system(os.path.join(root, d))]
        yield root, dirs, files

# ============== Authentication Manager ==============

class AuthenticationManager:
    def __init__(self, app_data_dir):
        self.app_data_dir = app_data_dir
        self.users_file = os.path.join(app_data_dir, 'users.json')
        self.sessions_file = os.path.join(app_data_dir, 'sessions.json')
        self.current_user = None
        self.current_role = None
        self.init_default_users()

    def init_default_users(self):
        """Initialize default users if users file doesn't exist"""
        if not os.path.exists(self.users_file):
            default_users = {
                "radiologists": {
                    "rad001": {"password": self.hash_password("rad123"), "name": "Dr. Smith"},
                    "rad002": {"password": self.hash_password("rad456"), "name": "Dr. Johnson"},
                    "rad003": {"password": self.hash_password("rad789"), "name": "Dr. Wilson"}
                },
                "patients": {
                    "pat001": {"password": self.hash_password("pat123"), "name": "John Doe", "assigned_radiologist": "rad001"},
                    "pat002": {"password": self.hash_password("pat456"), "name": "Jane Smith", "assigned_radiologist": "rad001"},
                    "pat003": {"password": self.hash_password("pat789"), "name": "Mike Wilson", "assigned_radiologist": "rad002"},
                    "pat004": {"password": self.hash_password("pat321"), "name": "Sarah Brown", "assigned_radiologist": "rad002"},
                    "pat005": {"password": self.hash_password("pat654"), "name": "David Lee", "assigned_radiologist": "rad003"}
                }
            }
            self.save_json(self.users_file, default_users)

    def hash_password(self, password):
        """Hash password using SHA-256"""
        return hashlib.sha256(password.encode()).hexdigest()

    def save_json(self, filepath, data):
        """Save data to JSON file safely"""
        try:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving JSON: {e}")

    def load_json(self, filepath):
        """Load data from JSON file safely"""
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            print(f"Error loading JSON: {e}")
            return {}

    def authenticate(self, user_id, password, role):
        """Authenticate user with role-based access control"""
        users_data = self.load_json(self.users_file)
        role_key = "radiologists" if role == "radiologist" else "patients"
        
        if role_key in users_data and user_id in users_data[role_key]:
            stored_hash = users_data[role_key][user_id]["password"]
            if stored_hash == self.hash_password(password):
                self.current_user = user_id
                self.current_role = role
                self.save_session()
                return True
        return False

    def save_session(self):
        """Save current user session"""
        session_data = {
            "user": self.current_user,
            "role": self.current_role,
            "timestamp": datetime.now().isoformat()
        }
        self.save_json(self.sessions_file, session_data)

    def get_user_info(self):
        """Get information about current user"""
        if not self.current_user:
            return None
        
        users_data = self.load_json(self.users_file)
        role_key = "radiologists" if self.current_role == "radiologist" else "patients"
        
        if role_key in users_data and self.current_user in users_data[role_key]:
            return users_data[role_key][self.current_user]
        return None

    def get_patient_radiologist(self, patient_id):
        """Get the assigned radiologist for a patient"""
        users_data = self.load_json(self.users_file)
        if "patients" in users_data and patient_id in users_data["patients"]:
            return users_data["patients"][patient_id].get("assigned_radiologist")
        return None

    def logout(self):
        """Logout current user and clear session"""
        self.current_user = None
        self.current_role = None
        try:
            if os.path.exists(self.sessions_file):
                os.remove(self.sessions_file)
        except Exception:
            pass

# ============== Data Manager (Embedded Storage) ==============

class DataManager:
    def __init__(self, app_data_dir):
        self.app_data_dir = app_data_dir
        self.data_dir = os.path.join(app_data_dir, 'medical_data')
        self.images_dir = os.path.join(self.data_dir, 'images')
        self.videos_dir = os.path.join(self.data_dir, 'videos')
        self.metadata_file = os.path.join(app_data_dir, 'metadata.json')
        self.tmp_dir = os.path.join(app_data_dir, 'tmp')
        self.ensure_directories()

    def ensure_directories(self):
        """Create necessary directories for data storage"""
        os.makedirs(self.images_dir, exist_ok=True)
        os.makedirs(self.videos_dir, exist_ok=True)
        os.makedirs(self.tmp_dir, exist_ok=True)

    def series_folder(self, base_dir, patient_id, series_desc, series_uid):
        """Create organized folder structure by series"""
        safe_series = (series_desc or "Series").replace(os.sep, "_").strip()
        uid_tail = (series_uid or "UID").split(".")[-3:]
        uid_suffix = "_".join(uid_tail)
        folder = os.path.join(base_dir, patient_id, f"{safe_series}_{uid_suffix}")
        os.makedirs(folder, exist_ok=True)
        return folder

    def store_dicom_file(self, source_path, patient_id, radiologist_id, study_type="image"):
        """Store DICOM file in organized structure with metadata"""
        try:
            if is_windows_locked_or_system(source_path):
                return None

            # Extract series information
            series_desc, series_uid = "Series", "UID"
            try:
                dcm_meta = pydicom.dcmread(source_path, stop_before_pixels=True, force=True)
                series_desc = getattr(dcm_meta, 'SeriesDescription', 'Series')
                series_uid = getattr(dcm_meta, 'SeriesInstanceUID', 'UID')
            except Exception:
                pass

            # Determine destination directory
            base_dir = self.videos_dir if study_type == "video" else self.images_dir
            dest_dir = self.series_folder(base_dir, patient_id, series_desc, series_uid)

            # Create unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_name = f"{patient_id}_{radiologist_id}_{timestamp}_{os.path.basename(source_path)}"
            dest_path = os.path.join(dest_dir, unique_name)

            # Copy via temporary file to avoid locks
            tmp_path = os.path.join(self.tmp_dir, f"{timestamp}_{os.path.basename(source_path)}")
            with open(source_path, 'rb') as src, open(tmp_path, 'wb') as dst:
                shutil.copyfileobj(src, dst, length=1024 * 1024)
            shutil.move(tmp_path, dest_path)

            # Update metadata
            self.update_metadata(dest_path, patient_id, radiologist_id, study_type)
            return dest_path
        except Exception as e:
            print(f"Error storing DICOM file: {e}")
            return None

    def store_dicom_directory(self, source_dir, patient_id, radiologist_id):
        """Store entire DICOM directory with recursive processing"""
        try:
            stored_files = []
            for root, dirs, files in filtered_walk(source_dir):
                for file in files:
                    source_path = os.path.join(root, file)
                    if is_windows_locked_or_system(source_path):
                        continue
                    if self.is_dicom_file(source_path):
                        study_type = "video" if self.is_dicom_video(source_path) else "image"
                        stored_path = self.store_dicom_file(source_path, patient_id, radiologist_id, study_type)
                        if stored_path:
                            stored_files.append(stored_path)
            return stored_files
        except Exception as e:
            print(f"Error storing DICOM directory: {e}")
            return []

    def update_metadata(self, file_path, patient_id, radiologist_id, study_type):
        """Update metadata database with file information"""
        metadata = self.load_metadata()
        entry = {
            "file_path": file_path,
            "patient_id": patient_id,
            "radiologist_id": radiologist_id,
            "study_type": study_type,
            "upload_timestamp": datetime.now().isoformat(),
            "file_size": os.path.getsize(file_path) if safe_exists(file_path) else 0
        }
        
        # Extract DICOM metadata
        try:
            dcm = pydicom.dcmread(file_path, stop_before_pixels=True, force=True)
            entry.update({
                "patient_name": str(getattr(dcm, 'PatientName', 'Unknown')),
                "study_description": getattr(dcm, 'StudyDescription', 'Unknown'),
                "modality": getattr(dcm, 'Modality', 'Unknown'),
                "study_date": getattr(dcm, 'StudyDate', 'Unknown'),
                "series_description": getattr(dcm, 'SeriesDescription', 'Series'),
                "series_uid": getattr(dcm, 'SeriesInstanceUID', 'UID'),
                "instance_number": int(getattr(dcm, 'InstanceNumber', 0) or 0),
                "number_of_frames": int(getattr(dcm, 'NumberOfFrames', 1) or 1)
            })
        except Exception:
            pass

        # Add to metadata
        if patient_id not in metadata:
            metadata[patient_id] = []
        metadata[patient_id].append(entry)
        self.save_metadata(metadata)

    def load_metadata(self):
        """Load metadata database"""
        try:
            if os.path.exists(self.metadata_file):
                with open(self.metadata_file, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            print(f"Error loading metadata: {e}")
            return {}

    def save_metadata(self, metadata):
        """Save metadata database"""
        try:
            with open(self.metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
        except Exception as e:
            print(f"Error saving metadata: {e}")

    def get_patient_files(self, patient_id, radiologist_id=None):
        """Get organized patient files grouped by series"""
        metadata = self.load_metadata()
        patient_files = []
        
        if patient_id in metadata:
            for entry in metadata[patient_id]:
                if radiologist_id is None or entry.get("radiologist_id") == radiologist_id:
                    if safe_exists(entry["file_path"]):
                        patient_files.append(entry)
        
        # Group by series and sort by instance number
        grouped = {}
        for e in patient_files:
            key = (e.get("series_uid") or "UID", e.get("series_description") or "Series")
            grouped.setdefault(key, []).append(e)
        
        for key in grouped:
            grouped[key].sort(key=lambda x: int(x.get("instance_number", 0)))
        
        return grouped

    def is_dicom_file(self, file_path):
        """Check if file is a valid DICOM file"""
        try:
            if not safe_exists(file_path) or is_windows_locked_or_system(file_path):
                return False
            pydicom.dcmread(file_path, stop_before_pixels=True, force=True)
            return True
        except Exception:
            return False

    def is_dicom_video(self, file_path):
        """Check if DICOM file contains video/multi-frame data"""
        try:
            dcm = pydicom.dcmread(file_path, stop_before_pixels=True, force=True)
            frames = getattr(dcm, 'NumberOfFrames', None)
            if frames and int(frames) > 1:
                return True
            
            # Check SOP Class for video types
            sop_class = getattr(dcm, 'SOPClassUID', '')
            video_sop_classes = [
                '1.2.840.10008.5.1.4.1.1.77.1.4.1',  # Video Endoscopic Image
                '1.2.840.10008.5.1.4.1.1.77.1.4',    # Video Photographic Image
            ]
            return sop_class in video_sop_classes
        except Exception:
            return False

# ============== UI Components ==============

class ColoredLabel(Label):
    """Label with colored background"""
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

class LoginInterface(BoxLayout):
    """Secure login interface with role selection"""
    def __init__(self, app, **kwargs):
        super().__init__(**kwargs)
        self.app = app
        self.orientation = 'vertical'
        self.selected_role = None
        self.build_login_interface()

    def build_login_interface(self):
        # Header
        header = Label(
            text="🏥 MEDICAL DICOM VIEWER\nSecure Authentication System",
            size_hint_y=None, height=100, font_size=24, bold=True,
            color=(0.2, 0.4, 0.8, 1)
        )
        self.add_widget(header)

        # Main login container
        login_container = BoxLayout(orientation='horizontal')
        login_container.add_widget(Label())  # Left spacer

        # Login form
        login_form = BoxLayout(orientation='vertical', size_hint_x=0.45, spacing=8, padding=10)

        # Role selection
        role_label = Label(text="Select Role:", size_hint_y=None, height=30, font_size=16, bold=True)
        login_form.add_widget(role_label)

        role_layout = BoxLayout(size_hint_y=None, height=50, spacing=10)
        self.radiologist_btn = Button(
            text="🩺 Radiologist\n(Upload Access)", 
            background_color=(0.2, 0.8, 0.2, 1), 
            font_size=12
        )
        self.patient_btn = Button(
            text="👤 Patient/Doctor\n(View Only)", 
            background_color=(0.2, 0.6, 0.9, 1), 
            font_size=12
        )
        self.radiologist_btn.bind(on_release=lambda x: self.select_role("radiologist"))
        self.patient_btn.bind(on_release=lambda x: self.select_role("patient"))
        role_layout.add_widget(self.radiologist_btn)
        role_layout.add_widget(self.patient_btn)
        login_form.add_widget(role_layout)

        # Role selection indicator
        self.selected_role_label = Label(
            text="No role selected", size_hint_y=None, height=30, 
            font_size=14, color=(0.8, 0.2, 0.2, 1)
        )
        login_form.add_widget(self.selected_role_label)

        # User ID input
        userid_label = Label(text="User ID:", size_hint_y=None, height=30, font_size=16, bold=True)
        login_form.add_widget(userid_label)
        self.userid_input = TextInput(size_hint_y=None, height=40, font_size=16, multiline=False)
        login_form.add_widget(self.userid_input)

        # Password input
        password_label = Label(text="Password:", size_hint_y=None, height=30, font_size=16, bold=True)
        login_form.add_widget(password_label)
        self.password_input = TextInput(
            size_hint_y=None, height=40, font_size=16, 
            password=True, multiline=False
        )
        login_form.add_widget(self.password_input)

        # Login button
        login_btn = Button(
            text="🔐 LOGIN", size_hint_y=None, height=50, 
            font_size=18, bold=True, background_color=(0.1, 0.7, 0.1, 1)
        )
        login_btn.bind(on_release=self.attempt_login)
        login_form.add_widget(login_btn)

        # Status label
        self.status_label = Label(
            text="", size_hint_y=None, height=30, 
            font_size=14, color=(0.8, 0.2, 0.2, 1)
        )
        login_form.add_widget(self.status_label)

        login_container.add_widget(login_form)
        login_container.add_widget(Label())  # Right spacer
        self.add_widget(login_container)

        # Sample credentials info
        info_text = """
SAMPLE CREDENTIALS:

RADIOLOGISTS (Upload Access):
• ID: rad001, Password: rad123 (Dr. Smith)
• ID: rad002, Password: rad456 (Dr. Johnson)
• ID: rad003, Password: rad789 (Dr. Wilson)

PATIENTS (View Only):
• ID: pat001, Password: pat123 (John Doe - rad001)
• ID: pat002, Password: pat456 (Jane Smith - rad001)
• ID: pat003, Password: pat789 (Mike Wilson - rad002)
• ID: pat004, Password: pat321 (Sarah Brown - rad002)
• ID: pat005, Password: pat654 (David Lee - rad003)
        """
        info_label = Label(
            text=info_text, size_hint_y=None, height=200, 
            font_size=11, color=(0.5, 0.5, 0.5, 1), 
            halign="left", valign="top"
        )
        info_label.text_size = (None, None)
        self.add_widget(info_label)

    def select_role(self, role):
        """Handle role selection"""
        self.selected_role = role
        if role == "radiologist":
            self.radiologist_btn.background_color = (0.1, 0.9, 0.1, 1)
            self.patient_btn.background_color = (0.2, 0.6, 0.9, 1)
            self.selected_role_label.text = "Role: Radiologist (Upload Access)"
            self.selected_role_label.color = (0.1, 0.7, 0.1, 1)
        else:
            self.patient_btn.background_color = (0.1, 0.4, 0.9, 1)
            self.radiologist_btn.background_color = (0.2, 0.8, 0.2, 1)
            self.selected_role_label.text = "Role: Patient/Doctor (View Only)"
            self.selected_role_label.color = (0.1, 0.4, 0.9, 1)

    def attempt_login(self, instance):
        """Attempt user authentication"""
        if not self.selected_role:
            self.status_label.text = "Please select a role first"
            return
        
        user_id = self.userid_input.text.strip()
        password = self.password_input.text.strip()
        
        if not user_id or not password:
            self.status_label.text = "Please enter both User ID and Password"
            return
        
        if self.app.auth_manager.authenticate(user_id, password, self.selected_role):
            self.status_label.text = "Login successful!"
            self.status_label.color = (0.1, 0.7, 0.1, 1)
            Clock.schedule_once(lambda dt: self.app.show_main_interface(), 0.5)
        else:
            self.status_label.text = "Invalid credentials. Please try again."
            self.status_label.color = (0.8, 0.2, 0.2, 1)
            self.password_input.text = ""

class DataUploadInterface(BoxLayout):
    """Thread-safe upload interface for radiologists"""
    def __init__(self, app, **kwargs):
        super().__init__(**kwargs)
        self.app = app
        self.orientation = 'vertical'
        self.build_upload_interface()

    def build_upload_interface(self):
        # Header
        user_info = self.app.auth_manager.get_user_info()
        header = Label(
            text=f"📤 DICOM Data Upload\nRadiologist: {user_info.get('name', 'Unknown')} ({self.app.auth_manager.current_user})",
            size_hint_y=None, height=60, font_size=18, bold=True, color=(0.2, 0.7, 0.2, 1)
        )
        self.add_widget(header)

        # Patient ID input
        patient_layout = BoxLayout(size_hint_y=None, height=60, spacing=10, padding=20)
        patient_layout.add_widget(Label(text="Patient ID:", size_hint_x=None, width=100, font_size=16, bold=True))
        self.patient_input = TextInput(size_hint_y=None, height=40, font_size=16, multiline=False)
        patient_layout.add_widget(self.patient_input)
        self.add_widget(patient_layout)

        # Upload options
        upload_layout = GridLayout(cols=2, size_hint_y=None, height=120, spacing=20, padding=20)
        file_upload_btn = Button(
            text="📄 Upload DICOM Files", 
            background_color=(0.3, 0.7, 0.3, 1), 
            font_size=16, bold=True
        )
        file_upload_btn.bind(on_release=self.upload_files)
        folder_upload_btn = Button(
            text="📁 Upload DICOM Folder", 
            background_color=(0.2, 0.8, 0.2, 1), 
            font_size=16, bold=True
        )
        folder_upload_btn.bind(on_release=self.upload_folder)
        upload_layout.add_widget(file_upload_btn)
        upload_layout.add_widget(folder_upload_btn)
        self.add_widget(upload_layout)

        # Status and progress
        self.status_label = Label(
            text="Ready to upload DICOM data", 
            size_hint_y=None, height=40, 
            font_size=14, color=(0.5, 0.5, 0.5, 1)
        )
        self.add_widget(self.status_label)

        self.progress_bar = ProgressBar(size_hint_y=None, height=30)
        self.progress_bar.opacity = 0
        self.add_widget(self.progress_bar)

        # Back button
        back_btn = Button(
            text="← Back to Main", size_hint_y=None, height=40, 
            background_color=(0.6, 0.6, 0.6, 1)
        )
        back_btn.bind(on_release=lambda x: self.app.show_main_interface())
        self.add_widget(back_btn)

    def upload_files(self, instance):
        """Handle individual file uploads"""
        patient_id = self.patient_input.text.strip()
        if not patient_id:
            self.show_error("Please enter Patient ID")
            return

        content = BoxLayout(orientation='vertical', spacing=10)
        filechooser = FileChooserIconView(
            multiselect=True,
            filters=['*.dcm', '*.dicom', '*.ima', '*.dic'],
            show_hidden=False,
            dirselect=False,
            path=os.path.expanduser('~')
        )
        try:
            filechooser.rootpath = os.path.expanduser('~')
        except Exception:
            pass

        content.add_widget(filechooser)
        
        btn_layout = BoxLayout(size_hint=(1, 0.2), spacing=10)
        upload_btn = Button(text="Upload Selected", background_color=(0.3, 0.7, 0.3, 1))
        cancel_btn = Button(text="Cancel", background_color=(0.6, 0.6, 0.6, 1))
        btn_layout.add_widget(upload_btn)
        btn_layout.add_widget(cancel_btn)
        content.add_widget(btn_layout)

        popup = Popup(title=f"Select DICOM Files for Patient {patient_id}", content=content, size_hint=(0.9, 0.8))

        def upload_selected_files(btn):
            if filechooser.selection:
                selection = [p for p in filechooser.selection 
                           if safe_exists(p) and not is_windows_locked_or_system(p)]
                popup.dismiss()
                if selection:
                    self.process_file_upload_safe(selection, patient_id)
                else:
                    self.show_error("All selected files were skipped due to system restrictions")
            else:
                self.show_error("Please select files to upload")

        upload_btn.bind(on_release=upload_selected_files)
        cancel_btn.bind(on_release=lambda x: popup.dismiss())
        popup.open()

    def upload_folder(self, instance):
        """Handle folder uploads"""
        patient_id = self.patient_input.text.strip()
        if not patient_id:
            self.show_error("Please enter Patient ID")
            return

        content = BoxLayout(orientation='vertical', spacing=10)
        filechooser = FileChooserIconView(
            dirselect=True, show_hidden=False, path=os.path.expanduser('~')
        )
        try:
            filechooser.rootpath = os.path.expanduser('~')
        except Exception:
            pass

        content.add_widget(filechooser)
        
        btn_layout = BoxLayout(size_hint=(1, 0.2), spacing=10)
        upload_btn = Button(text="Upload Folder", background_color=(0.2, 0.8, 0.2, 1))
        cancel_btn = Button(text="Cancel", background_color=(0.6, 0.6, 0.6, 1))
        btn_layout.add_widget(upload_btn)
        btn_layout.add_widget(cancel_btn)
        content.add_widget(btn_layout)

        popup = Popup(title=f"Select DICOM Folder for Patient {patient_id}", content=content, size_hint=(0.9, 0.8))

        def upload_selected_folder(btn):
            if filechooser.selection:
                folder = filechooser.selection[0]
                if is_windows_locked_or_system(folder):
                    self.show_error("Selected folder is protected by the system")
                    return
                popup.dismiss()
                self.process_folder_upload_safe(folder, patient_id)
            else:
                self.show_error("Please select a folder to upload")

        upload_btn.bind(on_release=upload_selected_folder)
        cancel_btn.bind(on_release=lambda x: popup.dismiss())
        popup.open()

    def process_file_upload_safe(self, file_list, patient_id):
        """Thread-safe individual file upload processing"""
        def upload_worker():
            success_count = 0
            total_count = 0
            
            try:
                # Filter valid files
                valid_files = []
                for file_path in file_list:
                    if safe_exists(file_path) and not is_windows_locked_or_system(file_path):
                        valid_files.append(file_path)
                
                total_count = len(valid_files)
                
                # Show progress on main thread
                def show_progress():
                    self.progress_bar.opacity = 1
                    self.status_label.text = f"Uploading {total_count} files..."
                    self.status_label.color = (0.5, 0.5, 0.5, 1)
                
                Clock.schedule_once(lambda dt: show_progress())
                
                # Process each file
                for i, file_path in enumerate(valid_files):
                    try:
                        if self.app.data_manager.is_dicom_file(file_path):
                            study_type = "video" if self.app.data_manager.is_dicom_video(file_path) else "image"
                            stored_path = self.app.data_manager.store_dicom_file(
                                file_path, patient_id, self.app.auth_manager.current_user, study_type
                            )
                            if stored_path:
                                success_count += 1
                    except Exception as file_error:
                        print(f"Error processing file {file_path}: {file_error}")
                        continue
                    
                    # Update progress on main thread
                    progress = ((i + 1) / max(total_count, 1)) * 100
                    def update_progress(prog=progress, current=i+1, total=total_count):
                        self.progress_bar.value = prog
                        self.status_label.text = f"Processing file {current}/{total}..."
                    
                    Clock.schedule_once(lambda dt: update_progress())
                
                # Complete upload on main thread
                def complete_upload():
                    self.progress_bar.opacity = 0
                    self.progress_bar.value = 0
                    self.status_label.text = f"Upload complete: {success_count}/{total_count} files stored"
                    self.status_label.color = (0.1, 0.7, 0.1, 1) if success_count > 0 else (0.8, 0.2, 0.2, 1)
                    self.patient_input.text = ""
                
                Clock.schedule_once(lambda dt: complete_upload())
                
            except Exception as ex:
                # Handle errors on main thread
                error_msg = f"Upload failed: {str(ex)}"
                def show_error():
                    self.progress_bar.opacity = 0
                    self.progress_bar.value = 0
                    self.status_label.text = error_msg
                    self.status_label.color = (0.8, 0.2, 0.2, 1)
                
                Clock.schedule_once(lambda dt: show_error())
        
        # Start worker thread
        worker_thread = threading.Thread(target=upload_worker, daemon=True)
        worker_thread.start()

    def process_folder_upload_safe(self, folder_path, patient_id):
        """Thread-safe folder upload processing"""
        def upload_worker():
            try:
                # Show progress on main thread
                def show_progress():
                    self.progress_bar.opacity = 1
                    self.status_label.text = "Scanning and uploading folder..."
                    self.status_label.color = (0.5, 0.5, 0.5, 1)
                
                Clock.schedule_once(lambda dt: show_progress())
                
                # Store directory
                stored_files = self.app.data_manager.store_dicom_directory(
                    folder_path, patient_id, self.app.auth_manager.current_user
                )
                
                # Complete on main thread
                def complete_upload():
                    self.progress_bar.opacity = 0
                    self.progress_bar.value = 0
                    self.status_label.text = f"Folder upload complete: {len(stored_files)} files stored"
                    self.status_label.color = (0.1, 0.7, 0.1, 1) if stored_files else (0.8, 0.2, 0.2, 1)
                    self.patient_input.text = ""
                
                Clock.schedule_once(lambda dt: complete_upload())
                
            except Exception as ex:
                error_msg = f"Folder upload failed: {str(ex)}"
                def show_error():
                    self.progress_bar.opacity = 0
                    self.progress_bar.value = 0
                    self.status_label.text = error_msg
                    self.status_label.color = (0.8, 0.2, 0.2, 1)
                
                Clock.schedule_once(lambda dt: show_error())
        
        worker_thread = threading.Thread(target=upload_worker, daemon=True)
        worker_thread.start()

    def show_error(self, message):
        """Show error popup"""
        Popup(title="Upload Error", content=Label(text=str(message)), size_hint=(0.6, 0.4)).open()

# ============== Main Application ==============

class SecureDICOMViewer(App):
    def build(self):
        self.title = "🏥 Secure DICOM Viewer - Medical Data Management System"
        Window.clearcolor = (0.94, 0.94, 0.94, 1)

        # Initialize app data directory
        self.app_data_dir = os.path.join(os.path.expanduser("~"), "SecureDICOMViewer")
        os.makedirs(self.app_data_dir, exist_ok=True)

        # Initialize managers
        self.auth_manager = AuthenticationManager(self.app_data_dir)
        self.data_manager = DataManager(self.app_data_dir)

        # Navigation state
        self.series_groups = {}
        self.series_keys = []
        self.current_series_idx = 0
        self.current_instance_idx = 0

        # Create main container
        self.root_container = BoxLayout()
        self.show_login_interface()
        return self.root_container

    def show_login_interface(self):
        """Show login interface"""
        self.root_container.clear_widgets()
        self.login_interface = LoginInterface(self)
        self.root_container.add_widget(self.login_interface)

    def show_main_interface(self):
        """Show main interface based on user role"""
        self.root_container.clear_widgets()
        if self.auth_manager.current_role == "radiologist":
            self.build_radiologist_interface()
        else:
            self.build_patient_interface()

    def build_radiologist_interface(self):
        """Build interface for radiologists"""
        main_layout = BoxLayout(orientation='vertical')
        
        # Header
        user_info = self.auth_manager.get_user_info()
        header = ColoredLabel(
            text=f"🩺 Radiologist Dashboard - {user_info.get('name', 'Unknown')} ({self.auth_manager.current_user})",
            size_hint_y=None, height=50, font_size=18, bold=True, 
            bg_color=(0.2, 0.7, 0.2, 1), color=(1, 1, 1, 1)
        )
        main_layout.add_widget(header)

        # Action buttons
        actions_layout = GridLayout(cols=3, size_hint_y=None, height=100, spacing=10, padding=10)
        
        upload_btn = Button(text="📤 Upload Data", background_color=(0.3, 0.8, 0.3, 1), font_size=16, bold=True)
        upload_btn.bind(on_release=self.show_upload_interface)
        
        view_btn = Button(text="👁 View Patient Data", background_color=(0.2, 0.6, 0.9, 1), font_size=16, bold=True)
        view_btn.bind(on_release=self.show_patient_selector_for_radiologist)
        
        logout_btn = Button(text="🚪 Logout", background_color=(0.8, 0.3, 0.3, 1), font_size=16, bold=True)
        logout_btn.bind(on_release=self.logout)
        
        actions_layout.add_widget(upload_btn)
        actions_layout.add_widget(view_btn)
        actions_layout.add_widget(logout_btn)
        main_layout.add_widget(actions_layout)

        # Information panel
        info_label = ColoredLabel(
            text="🏥 RADIOLOGIST FEATURES:\n\n"
                 "📄 SINGLE FILE UPLOAD: Upload individual DICOM files\n"
                 "📁 FOLDER UPLOAD: Upload entire DICOM directories\n"
                 "👁 SERIES VIEWER: Browse patient studies with navigation\n"
                 "🔒 SECURE: Thread-safe, Windows-compatible uploads\n"
                 "⚡ FAST: Optimized for medical workflow",
            bg_color=(0.95, 0.98, 1.0, 1), color=(0.1, 0.3, 0.7, 1), 
            font_size=14, bold=True
        )
        main_layout.add_widget(info_label)

        self.root_container.add_widget(main_layout)

    def build_patient_interface(self):
        """Build interface for patients"""
        main_layout = BoxLayout(orientation='vertical')
        
        # Header
        user_info = self.auth_manager.get_user_info()
        header = ColoredLabel(
            text=f"👤 Patient Dashboard - {user_info.get('name', 'Unknown')} ({self.auth_manager.current_user})",
            size_hint_y=None, height=50, font_size=18, bold=True, 
            bg_color=(0.2, 0.6, 0.9, 1), color=(1, 1, 1, 1)
        )
        main_layout.add_widget(header)

        # Action buttons
        actions_layout = GridLayout(cols=2, size_hint_y=None, height=100, spacing=10, padding=10)
        
        view_btn = Button(text="👁 View My Medical Data", background_color=(0.2, 0.6, 0.9, 1), font_size=16, bold=True)
        view_btn.bind(on_release=self.show_my_patient_data)
        
        logout_btn = Button(text="🚪 Logout", background_color=(0.8, 0.3, 0.3, 1), font_size=16, bold=True)
        logout_btn.bind(on_release=self.logout)
        
        actions_layout.add_widget(view_btn)
        actions_layout.add_widget(logout_btn)
        main_layout.add_widget(actions_layout)

        # Information panel
        assigned_rad = self.auth_manager.get_patient_radiologist(self.auth_manager.current_user)
        info_text = (
            "🏥 PATIENT FEATURES:\n\n"
            f"👤 YOUR ASSIGNED RADIOLOGIST: {assigned_rad}\n"
            "👁 VIEW ONLY: Access your medical images and videos\n"
            "🔒 SECURE: Only your assigned data is visible\n"
            "⚡ FAST: Quick access to your medical records"
        )
        info_label = ColoredLabel(
            text=info_text, bg_color=(0.95, 0.98, 1.0, 1), 
            color=(0.1, 0.3, 0.7, 1), font_size=14, bold=True
        )
        main_layout.add_widget(info_label)

        self.root_container.add_widget(main_layout)

    def show_upload_interface(self, instance):
        """Show upload interface"""
        self.root_container.clear_widgets()
        self.upload_interface = DataUploadInterface(self)
        self.root_container.add_widget(self.upload_interface)

    def show_patient_selector_for_radiologist(self, instance):
        """Show patient selector for radiologists"""
        content = BoxLayout(orientation='vertical', spacing=10)
        
        label = Label(text="Enter Patient ID to view data:", size_hint_y=None, height=40, font_size=16, bold=True)
        content.add_widget(label)
        
        patient_input = TextInput(size_hint_y=None, height=40, font_size=16, multiline=False)
        content.add_widget(patient_input)

        btn_layout = BoxLayout(size_hint_y=None, height=50, spacing=10)
        view_btn = Button(text="Open Viewer", background_color=(0.3, 0.7, 0.3, 1))
        cancel_btn = Button(text="Cancel", background_color=(0.6, 0.6, 0.6, 1))
        btn_layout.add_widget(view_btn)
        btn_layout.add_widget(cancel_btn)
        content.add_widget(btn_layout)

        popup = Popup(title="Patient Data Viewer", content=content, size_hint=(0.6, 0.4))

        def open_view(btn):
            patient_id = patient_input.text.strip()
            if patient_id:
                popup.dismiss()
                self.open_viewer_for_patient(patient_id, self.auth_manager.current_user)
            else:
                self.show_error("Please enter Patient ID")

        view_btn.bind(on_release=open_view)
        cancel_btn.bind(on_release=lambda x: popup.dismiss())
        popup.open()

    def show_my_patient_data(self, instance):
        """Show patient's own data"""
        assigned_rad = self.auth_manager.get_patient_radiologist(self.auth_manager.current_user)
        self.open_viewer_for_patient(self.auth_manager.current_user, assigned_rad)

    def open_viewer_for_patient(self, patient_id, radiologist_id):
        """Open viewer for specific patient data"""
        grouped = self.data_manager.get_patient_files(patient_id, radiologist_id)
        if not grouped:
            self.show_info("No medical data found.")
            return

        self.series_groups = grouped
        self.series_keys = list(grouped.keys())
        self.current_series_idx = 0
        self.current_instance_idx = 0
        self.build_viewer_interface()

    def build_viewer_interface(self):
        """Build the DICOM viewer interface with navigation"""
        self.root_container.clear_widgets()
        main_layout = BoxLayout(orientation='vertical')

        # Header
        header = ColoredLabel(
            text="🏥 Medical Data Viewer - Series Navigation",
            size_hint_y=None, height=40, font_size=16, bold=True, 
            bg_color=(0.7, 0.8, 0.9, 1)
        )
        main_layout.add_widget(header)

        # Content area
        content_area = BoxLayout(orientation='horizontal')

        # Left panel - series list
        left_panel = BoxLayout(orientation='vertical', size_hint=(0.32, 1))
        files_header = ColoredLabel(
            text="Series", size_hint_y=None, height=30, 
            font_size=14, bold=True, bg_color=(0.75, 0.85, 0.75, 1)
        )
        left_panel.add_widget(files_header)
        
        self.series_scroll = ScrollView()
        self.series_layout = GridLayout(cols=1, size_hint_y=None, spacing=2)
        self.series_layout.bind(minimum_height=self.series_layout.setter('height'))

        for idx, key in enumerate(self.series_keys):
            series_uid, series_desc = key
            items = self.series_groups[key]
            first = items[0]
            icon = "🎥" if (first.get("number_of_frames", 1) or 1) > 1 or first.get("study_type") == "video" else "📷"
            
            btn = Button(
                text=f"{icon} {series_desc or 'Series'}\n{len(items)} images",
                size_hint_y=None, height=70, font_size=11, 
                background_color=(0.95, 0.98, 0.95, 1)
            )
            btn.bind(on_release=lambda x, i=idx: self.select_series(i))
            self.series_layout.add_widget(btn)

        self.series_scroll.add_widget(self.series_layout)
        left_panel.add_widget(self.series_scroll)

        # Center - image viewer
        self.center_area = BoxLayout(orientation='vertical')
        self.image = Image()
        self.center_area.add_widget(self.image)

        # Right panel - information
        right_panel = BoxLayout(orientation='vertical', size_hint=(0.32, 1))
        info_header = ColoredLabel(
            text="Information", size_hint_y=None, height=30, 
            font_size=14, bold=True, bg_color=(0.75, 0.8, 0.9, 1)
        )
        right_panel.add_widget(info_header)
        
        info_scroll = ScrollView()
        self.info_label = Label(
            text="Select a series and use navigation", 
            halign="left", valign="top", size_hint_y=None, 
            text_size=(200, None), font_size=10
        )
        self.info_label.bind(texture_size=self.info_label.setter("size"))
        info_scroll.add_widget(self.info_label)
        right_panel.add_widget(info_scroll)

        content_area.add_widget(left_panel)
        content_area.add_widget(self.center_area)
        content_area.add_widget(right_panel)
        main_layout.add_widget(content_area)

        # Navigation toolbar
        toolbar = BoxLayout(size_hint_y=None, height=50, spacing=10, padding=10)
        
        back_btn = Button(text="← Back", background_color=(0.6, 0.6, 0.6, 1))
        back_btn.bind(on_release=lambda x: self.show_main_interface())
        
        prev_series_btn = Button(text="⟨ Series", background_color=(0.5, 0.5, 0.5, 1))
        next_series_btn = Button(text="Series ⟩", background_color=(0.5, 0.5, 0.5, 1))
        prev_img_btn = Button(text="⟨ Prev", background_color=(0.5, 0.5, 0.5, 1))
        next_img_btn = Button(text="Next ⟩", background_color=(0.5, 0.5, 0.5, 1))

        prev_series_btn.bind(on_release=lambda x: self.change_series(-1))
        next_series_btn.bind(on_release=lambda x: self.change_series(1))
        prev_img_btn.bind(on_release=lambda x: self.change_instance(-1))
        next_img_btn.bind(on_release=lambda x: self.change_instance(1))

        toolbar.add_widget(back_btn)
        toolbar.add_widget(prev_series_btn)
        toolbar.add_widget(next_series_btn)
        toolbar.add_widget(Label())  # Spacer
        toolbar.add_widget(prev_img_btn)
        toolbar.add_widget(next_img_btn)

        main_layout.add_widget(toolbar)
        self.root_container.add_widget(main_layout)

        # Load initial image
        self.render_current()

    def select_series(self, idx):
        """Select a specific series"""
        self.current_series_idx = idx
        self.current_instance_idx = 0
        self.render_current()

    def change_series(self, delta):
        """Navigate between series"""
        if not self.series_keys:
            return
        self.current_series_idx = (self.current_series_idx + delta) % len(self.series_keys)
        self.current_instance_idx = 0
        self.render_current()

    def change_instance(self, delta):
        """Navigate between instances in current series"""
        if not self.series_keys:
            return
        key = self.series_keys[self.current_series_idx]
        items = self.series_groups[key]
        self.current_instance_idx = (self.current_instance_idx + delta) % len(items)
        self.render_current()

    def render_current(self):
        """Render currently selected image"""
        if not self.series_keys:
            return
        key = self.series_keys[self.current_series_idx]
        items = self.series_groups[key]
        entry = items[self.current_instance_idx]
        self.load_and_show(entry)
        self.update_info(entry, self.current_series_idx, self.current_instance_idx, len(items))

    def load_and_show(self, file_entry):
        """Load and display DICOM image"""
        file_path = file_entry['file_path']
        if not safe_exists(file_path):
            self.show_error("File not found")
            return
        
        try:
            dcm = pydicom.dcmread(file_path, force=True)
            if hasattr(dcm, 'pixel_array'):
                arr = dcm.pixel_array
                
                # Handle multi-frame images (show first frame)
                if arr.ndim == 3:
                    arr = arr[0]
                
                # Normalize to uint8
                img = self.normalize_to_uint8(arr)
                
                # Create texture
                if img.ndim == 3 and img.shape[2] == 3:
                    texture = Texture.create(size=(img.shape[1], img.shape[0]), colorfmt="rgb")
                    texture.blit_buffer(img.tobytes(), colorfmt="rgb", bufferfmt="ubyte")
                else:
                    texture = Texture.create(size=(img.shape[1], img.shape[0]), colorfmt="luminance")
                    texture.blit_buffer(img.tobytes(), colorfmt="luminance", bufferfmt="ubyte")
                
                texture.flip_vertical()
                self.image.texture = texture
        except Exception as e:
            self.show_error(f"Error loading file: {e}")

    def normalize_to_uint8(self, pixel_array):
        """Normalize pixel array to uint8 for display"""
        if pixel_array.dtype != np.uint8:
            pmin, pmax = np.min(pixel_array), np.max(pixel_array)
            if pmax > pmin:
                return ((pixel_array - pmin) / (pmax - pmin) * 255).astype(np.uint8)
            return np.full_like(pixel_array, 128, dtype=np.uint8)
        return pixel_array

    def update_info(self, entry, series_idx, instance_idx, series_len):
        """Update information panel"""
        info_text = f"""📋 SERIES/IMAGE INFORMATION

SERIES: {series_idx+1} / {len(self.series_keys)}
Description: {entry.get('series_description', 'Series')}
Series UID: {entry.get('series_uid', 'UID')[-20:]}...

IMAGE: {instance_idx+1} / {series_len}
Instance: {entry.get('instance_number', 'N/A')}
Type: {entry.get('study_type', 'Unknown')}
Modality: {entry.get('modality', 'Unknown')}
Frames: {entry.get('number_of_frames', 1)}

PATIENT:
Name: {entry.get('patient_name', 'Unknown')}
ID: {entry.get('patient_id', 'Unknown')}
Study: {entry.get('study_description', 'Unknown')}
Date: {entry.get('study_date', 'Unknown')}

UPLOAD:
Radiologist: {entry.get('radiologist_id', 'Unknown')}
Uploaded: {entry.get('upload_timestamp', '')[:19]}

FILE:
Name: {os.path.basename(entry.get('file_path',''))}
Size: {entry.get('file_size', 0)} bytes
Path: ...{entry.get('file_path','')[-30:]}
"""
        self.info_label.text = info_text

    def logout(self, instance):
        """Logout current user"""
        self.auth_manager.logout()
        self.show_login_interface()

    def show_error(self, message):
        """Show error popup"""
        Popup(title="Error", content=Label(text=str(message)), size_hint=(0.6, 0.4)).open()

    def show_info(self, message):
        """Show info popup"""
        Popup(title="Information", content=Label(text=str(message)), size_hint=(0.6, 0.4)).open()

# ============== Main Entry Point ==============

if __name__ == "__main__":
    print("=" * 80)
    print("🏥 🔒 SECURE DICOM VIEWER - COMPLETE MEDICAL DATA MANAGEMENT 🔒 🏥")
    print("=" * 80)
    print("✅ FEATURES:")
    print("   • Dual Role Authentication (Radiologist + Patient)")
    print("   • Thread-Safe File & Folder Uploads")
    print("   • Embedded Data Storage (No External Drives)")
    print("   • Series-Based Navigation (Prev/Next)")
    print("   • Windows-Safe File Handling")
    print("   • Role-Based Access Control")
    print("   • Professional Medical UI")
    print("   • Offline Operation")
    print("=" * 80)
    print("🔐 SAMPLE CREDENTIALS:")
    print("   Radiologists: rad001/rad123, rad002/rad456, rad003/rad789")
    print("   Patients: pat001/pat123, pat002/pat456, pat003/pat789, etc.")
    print("=" * 80)
    
    SecureDICOMViewer().run()
