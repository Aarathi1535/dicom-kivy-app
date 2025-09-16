import os
import pydicom
import numpy as np
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.filechooser import FileChooserIconView
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.graphics.texture import Texture
from kivy.uix.label import Label
from kivy.core.window import Window
from kivy.uix.scrollview import ScrollView


class DICOMViewer(App):
    def build(self):
        self.title = "Offline DICOM Viewer"
        self.main_layout = BoxLayout(orientation="vertical", spacing=10, padding=10)
        self.build_filechooser_screen()
        return self.main_layout

    def build_filechooser_screen(self):
        """Initial screen with file chooser + upload button"""
        self.main_layout.clear_widgets()

        # File chooser
        self.filechooser = FileChooserIconView(filters=["*.dcm"], multiselect=True, size_hint=(1, 0.9))
        self.filechooser.path = os.getcwd()
        self.main_layout.add_widget(self.filechooser)

        # Upload button
        upload_btn = Button(
            text="Upload & View",
            size_hint=(1, 0.1),
            background_color=(0, 0.6, 0.8, 1)
        )
        upload_btn.bind(on_release=self.load_files)
        self.main_layout.add_widget(upload_btn)

    def build_viewer_screen(self):
        """Screen for showing DICOM image + metadata + back button"""
        self.main_layout.clear_widgets()

        # Image preview
        self.image = Image(size_hint=(1, 0.6), allow_stretch=True, keep_ratio=True)
        self.main_layout.add_widget(self.image)

        # Metadata display (scrollable)
        scroll = ScrollView(size_hint=(1, 0.3))
        self.meta_label = Label(
            halign="left",
            valign="top",
            size_hint_y=None,
            text="Loading metadata..."
        )
        self.meta_label.bind(texture_size=self.meta_label.setter("size"))
        scroll.add_widget(self.meta_label)
        self.main_layout.add_widget(scroll)

        # Back button
        back_btn = Button(
            text="🔄 Choose Another File",
            size_hint=(1, 0.1),
            background_color=(0.8, 0.2, 0.2, 1)
        )
        back_btn.bind(on_release=lambda x: self.build_filechooser_screen())
        self.main_layout.add_widget(back_btn)

    def load_files(self, instance):
        self.files = sorted(self.filechooser.selection)
        if not self.files:
            return
        self.index = 0
        self.build_viewer_screen()
        self.show_image()

        # Bind navigation keys only in viewer screen
        Window.bind(on_key_down=self.on_key_down)
        Window.bind(on_scroll=self.on_scroll)

    def show_image(self):
        try:
            dcm = pydicom.dcmread(self.files[self.index])
            pixel_array = dcm.pixel_array

            # Normalize
            img = (pixel_array - np.min(pixel_array)) / (np.max(pixel_array) - np.min(pixel_array))
            img = (img * 255).astype(np.uint8)

            # Convert to texture
            texture = Texture.create(size=(img.shape[1], img.shape[0]), colorfmt="luminance")
            texture.blit_buffer(img.tobytes(), colorfmt="luminance", bufferfmt="ubyte")
            texture.flip_vertical()
            self.image.texture = texture

            # Metadata
            study = getattr(dcm, "StudyDescription", "N/A")
            series = getattr(dcm, "SeriesDescription", "N/A")
            bodypart = getattr(dcm, "BodyPartExamined", "N/A")
            patient = getattr(dcm, "PatientName", "N/A")

            self.meta_label.text = f"""
[Study] {study}
[Series] {series}
[Body Part] {bodypart}
[Patient] {patient}
[File] {os.path.basename(self.files[self.index])}
Slice {self.index+1} / {len(self.files)}
            """

        except Exception as e:
            self.meta_label.text = f"⚠ Error loading file: {e}"

    def on_key_down(self, window, key, scancode, codepoint, modifier):
        if not self.files:
            return
        if key == 275:  # Right arrow
            self.index = (self.index + 1) % len(self.files)
            self.show_image()
        elif key == 276:  # Left arrow
            self.index = (self.index - 1) % len(self.files)
            self.show_image()

    def on_scroll(self, window, x, y, scroll_x, scroll_y):
        if not self.files:
            return
        if scroll_y > 0:  # Scroll up
            self.index = (self.index + 1) % len(self.files)
        else:  # Scroll down
            self.index = (self.index - 1) % len(self.files)
        self.show_image()


if __name__ == "__main__":
    DICOMViewer().run()
