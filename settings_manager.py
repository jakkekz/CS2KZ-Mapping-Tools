import json
import os
import tempfile

class SettingsManager:
    def __init__(self):
        self.temp_dir = tempfile.gettempdir()
        self.app_dir = os.path.join(self.temp_dir, '.CS2KZ-mapping-tools')
        os.makedirs(self.app_dir, exist_ok=True)
        self.settings_file = os.path.join(self.app_dir, 'settings.json')
        self.default_settings = {
            'theme': 'system',  # 'light', 'dark', or 'system'
            'visible_buttons': {
                'dedicated_server': True,
                'insecure': True,
                'listen': True,
                'mapping': True,
                'source2viewer': True
            },
            'button_order': ['dedicated_server', 'insecure', 'listen', 'mapping', 'source2viewer'],  # Custom button order
            'window_position': None,  # Will store as [x, y]
            'appearance_mode': 'system',  # For CustomTkinter
            'color_theme': 'blue',  # For CustomTkinter
            'source2viewer_path': None,  # Path to Source2Viewer.exe
            'show_move_icons': False,  # Show move icons on buttons
            'auto_update_source2viewer': True  # Auto update Source2Viewer via S2V-AUL.py
        }
        self.settings = self.load_settings()

    def load_settings(self):
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    return {**self.default_settings, **json.load(f)}
            return self.default_settings.copy()
        except Exception as e:
            print(f"Error loading settings: {e}")
            return self.default_settings.copy()

    def save_settings(self):
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def get(self, key, default=None):
        return self.settings.get(key, default)

    def set(self, key, value):
        self.settings[key] = value
        self.save_settings()

    def get_window_position(self):
        pos = self.get('window_position')
        return pos if pos else None

    def set_window_position(self, x, y):
        self.set('window_position', [x, y])

    def get_visible_buttons(self):
        return self.get('visible_buttons', self.default_settings['visible_buttons'])

    def set_button_visibility(self, button_name, is_visible):
        visible_buttons = self.get_visible_buttons()
        visible_buttons[button_name] = is_visible
        self.set('visible_buttons', visible_buttons)

    def get_theme(self):
        return self.get('theme', 'system')

    def set_theme(self, theme):
        self.set('theme', theme)

    def get_button_order(self):
        return self.get('button_order', self.default_settings['button_order'])

    def set_button_order(self, order):
        self.set('button_order', order)