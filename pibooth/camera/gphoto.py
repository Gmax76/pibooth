# -*- coding: utf-8 -*-

import io
import time
import threading
import pygame
try:
    import gphoto2 as gp
except ImportError:
    gp = None  # gphoto2 is optional
from PIL import Image, ImageFilter
from pibooth.pictures import sizing
from pibooth.utils import LOGGER, PoolingTimer, pkill
from pibooth.language import get_translated_text
from pibooth.camera.base import BaseCamera


def get_gp_camera_proxy(port=None):
    """Return camera proxy if a gPhoto2 compatible camera is found
    else return None.

    .. note:: try to kill any process using gPhoto2 as it may block camera access.

    :param port: look on given port number
    :type port: str
    """
    if not gp:
        return None  # gPhoto2 is not installed

    pkill('*gphoto2*')
    if hasattr(gp, 'gp_camera_autodetect'):
        # gPhoto2 version 2.5+
        cameras = gp.check_result(gp.gp_camera_autodetect())
    else:
        port_info_list = gp.PortInfoList()
        port_info_list.load()
        abilities_list = gp.CameraAbilitiesList()
        abilities_list.load()
        cameras = abilities_list.detect(port_info_list)
    if cameras:
        LOGGER.debug("Found gPhoto2 cameras on ports: '%s'", "' / '".join([p for _, p in cameras]))
        # Initialize first camera proxy and return it
        camera = gp.Camera()
        if port is not None:
            port_info_list = gp.PortInfoList()
            port_info_list.load()
            idx = port_info_list.lookup_path(port)
            camera.set_port_info(port_info_list[idx])

        try:
            camera.init()
            return camera
        except gp.GPhoto2Error as ex:
            LOGGER.warning("Could not connect gPhoto2 camera: %s", ex)

    return None


def gp_log_callback(level, domain, string, data=None):
    """Logging callback for gphoto2.
    """
    LOGGER.getChild('gphoto2').debug(domain.decode("utf-8") + u': ' + string.decode("utf-8"))


class GpCamera(BaseCamera):

    """gPhoto2 camera management.
    """

    IMAGE_EFFECTS = [u'none',
                     u'blur',
                     u'contour',
                     u'detail',
                     u'edge_enhance',
                     u'edge_enhance_more',
                     u'emboss',
                     u'find_edges',
                     u'smooth',
                     u'smooth_more',
                     u'sharpen']

    def __init__(self, camera_proxy):
        super(GpCamera, self).__init__(camera_proxy)
        self._gp_logcb = None
        self._preview_compatible = True
        self._preview_viewfinder = False
        self._preview_autofocus = False
        self._eosremoterelease_choices = ()
        self._preview_image = None
        self._preview_image_lock = threading.Lock()
        self._preview_thread = None
        self._preview_stop = threading.Event()

    def _specific_initialization(self):
        """Camera initialization.
        """
        self._gp_logcb = gp.check_result(gp.gp_log_add_func(gp.GP_LOG_VERBOSE, gp_log_callback))
        abilities = self._cam.get_abilities()
        self._preview_compatible = gp.GP_OPERATION_CAPTURE_PREVIEW ==\
            abilities.operations & gp.GP_OPERATION_CAPTURE_PREVIEW
        if not self._preview_compatible:
            LOGGER.warning("The connected DSLR camera is not compatible with preview")
        else:
            try:
                self.get_config_value('actions', 'viewfinder')
                self._preview_viewfinder = True
            except ValueError:
                self._preview_viewfinder = False

            self._preview_autofocus = self._has_config_value('actions', 'autofocusdrive')
            if self._has_config_value('actions', 'eosremoterelease'):
                _, child = self._get_config_item('actions', 'eosremoterelease')
                self._eosremoterelease_choices = tuple(child.get_choices())

        self.set_config_value('imgsettings', 'iso', self.preview_iso)
        self.set_config_value('settings', 'capturetarget', 'Memory card')

    def _get_config_item(self, section, option):
        """Return configuration root and child widget.
        """
        try:
            config = self._cam.get_config()
            child = config.get_child_by_name(section).get_child_by_name(option)
            return config, child
        except gp.GPhoto2Error:
            raise ValueError('Unknown option {}/{}'.format(section, option))

    def _has_config_value(self, section, option):
        """Return True when the configuration option exists.
        """
        try:
            self._get_config_item(section, option)
            return True
        except ValueError:
            return False

    def _preview_is_running(self):
        """Return True when capture preview is active.
        """
        return self._preview_compatible and self._window is not None

    def _trigger_liveview_autofocus(self):
        """Trigger autofocus while liveview is still enabled.
        """
        if not self.liveview_autofocus or not self._preview_is_running():
            return

        try:
            if self._preview_autofocus:
                LOGGER.debug('Trigger DSLR autofocus using actions/autofocusdrive')
                self.set_config_value('actions', 'autofocusdrive', 1)
                time.sleep(0.3)
                return

            half_press = {'Press Half', 'Release Half'}
            if half_press.issubset(set(self._eosremoterelease_choices)):
                LOGGER.debug('Trigger DSLR autofocus using actions/eosremoterelease half-press')
                self.set_config_value('actions', 'eosremoterelease', 'Press Half')
                time.sleep(0.3)
                self.set_config_value('actions', 'eosremoterelease', 'Release Half')
        except (gp.GPhoto2Error, ValueError) as ex:
            LOGGER.warning('Liveview autofocus failed: %s', ex)

    def _show_overlay(self, text, alpha):
        """Add an image as an overlay.
        """
        if self._window:  # No window means no preview displayed
            rect = self.get_rect()
            self._overlay = self.build_overlay((rect.width, rect.height), str(text), alpha)

    def _rotate_image(self, image, rotation):
        """Rotate a PIL image, same direction than RpiCamera.
        """
        if rotation == 90:
            return image.transpose(Image.ROTATE_90)
        elif rotation == 180:
            return image.transpose(Image.ROTATE_180)
        elif rotation == 270:
            return image.transpose(Image.ROTATE_270)
        return image

    def _capture_preview_image(self):
        """Capture and process a new preview image.
        """
        rect = self.get_rect()
        if self._preview_compatible:
            cam_file = self._cam.capture_preview()
            image = Image.open(io.BytesIO(cam_file.get_data_and_size()))
            image = self._rotate_image(image, self.preview_rotation)
            # Crop to keep aspect ratio of the resolution
            image = image.crop(sizing.new_size_by_croping_ratio(image.size, self.resolution))
            # Resize to fit the available space in the window
            image = image.resize(sizing.new_size_keep_aspect_ratio(image.size, (rect.width, rect.height), 'outer'))

            if self.preview_flip:
                image = image.transpose(Image.FLIP_LEFT_RIGHT)
        else:
            image = Image.new('RGB', (rect.width, rect.height), color=(0, 0, 0))

        return image

    def _get_preview_image(self):
        """Return the latest available preview image.
        """
        rect = self.get_rect()
        with self._preview_image_lock:
            image = self._preview_image

        if image is None:
            image = Image.new('RGB', (rect.width, rect.height), color=(0, 0, 0))
        elif self._overlay:
            image = image.copy()

        if self._overlay:
            image.paste(self._overlay, (0, 0), self._overlay)
        return image

    def _preview_worker(self):
        """Continuously refresh the cached preview frame.
        """
        while not self._preview_stop.is_set():
            try:
                image = self._capture_preview_image()
                with self._preview_image_lock:
                    self._preview_image = image
            except gp.GPhoto2Error as ex:
                if self._preview_stop.is_set():
                    break
                LOGGER.warning('Preview refresh failed: %s', ex)
                break

    def _start_preview_stream(self):
        """Start the background preview refresh.
        """
        if not self._preview_compatible:
            return
        self._stop_preview_stream()
        self._preview_stop.clear()
        self._preview_thread = threading.Thread(target=self._preview_worker, name='pibooth-gphoto-preview')
        self._preview_thread.daemon = True
        self._preview_thread.start()

    def _stop_preview_stream(self):
        """Stop the background preview refresh.
        """
        self._preview_stop.set()
        if self._preview_thread and self._preview_thread.is_alive():
            self._preview_thread.join()
        self._preview_thread = None

    def _post_process_capture(self, capture_data):
        """Rework capture data.

        :param capture_data: couple (GPhotoPath, effect)
        :type capture_data: tuple
        """
        gp_path, effect = capture_data
        camera_file = self._cam.file_get(gp_path.folder, gp_path.name, gp.GP_FILE_TYPE_NORMAL)
        if self.delete_internal_memory:
            LOGGER.debug("Delete capture '%s' from internal memory", gp_path.name)
            self._cam.file_delete(gp_path.folder, gp_path.name)
        image = Image.open(io.BytesIO(camera_file.get_data_and_size()))
        image = self._rotate_image(image, self.capture_rotation)

        # Crop to keep aspect ratio of the resolution
        image = image.crop(sizing.new_size_by_croping_ratio(image.size, self.resolution))
        # Resize to fit the resolution
        image = image.resize(sizing.new_size_keep_aspect_ratio(image.size, self.resolution, 'outer'))

        if self.capture_flip:
            image = image.transpose(Image.FLIP_LEFT_RIGHT)

        if effect != 'none':
            image = image.filter(getattr(ImageFilter, effect.upper()))

        return image

    def set_config_value(self, section, option, value):
        """Set camera configuration.
        """
        try:
            LOGGER.debug('Setting option %s/%s=%s', section, option, value)
            config, child = self._get_config_item(section, option)
            if child.get_type() == gp.GP_WIDGET_RADIO:
                choices = [c for c in child.get_choices()]
            else:
                choices = None
            data_type = type(child.get_value())
            value = data_type(value)  # Cast value
            if choices and value not in choices:
                if value == 'Memory card' and 'card' in choices:
                    value = 'card'  # Fix for Sony ZV-1
                elif value == 'Memory card' and 'card+sdram' in choices:
                    value = 'card+sdram'  # Fix for Sony ILCE-6400
                else:
                    LOGGER.warning("Invalid value '%s' for option %s (possible choices: %s), trying to set it anyway",
                                   value, option, choices)
            child.set_value(value)
            self._cam.set_config(config)
        except gp.GPhoto2Error as ex:
            LOGGER.error('Unsupported option %s/%s=%s (%s), configure your DSLR manually', section, option, value, ex)

    def get_config_value(self, section, option):
        """Get camera configuration option.
        """
        try:
            _, child = self._get_config_item(section, option)
            value = child.get_value()
            LOGGER.debug('Getting option %s/%s=%s', section, option, value)
            return value
        except ValueError:
            raise ValueError('Unknown option {}/{}'.format(section, option))

    def preview(self, window, flip=True):
        """Setup the preview.
        """
        self._window = window
        self.preview_flip = flip

        if self._preview_compatible:
            if self._preview_viewfinder:
                self.set_config_value('actions', 'viewfinder', 1)
            with self._preview_image_lock:
                self._preview_image = self._capture_preview_image()
            self._start_preview_stream()
        else:
            with self._preview_image_lock:
                self._preview_image = None
        self._window.show_image(self._get_preview_image())

    def preview_countdown(self, timeout, alpha=80):
        """Show a countdown of `timeout` seconds on the preview.
        Returns when the countdown is finished.
        """
        timeout = int(timeout)
        if timeout < 1:
            raise ValueError("Start time shall be greater than 0")

        shown = False
        first_loop = True
        timer = PoolingTimer(timeout)
        while not timer.is_timeout():
            remaining = int(timer.remaining() + 1)
            if not self._overlay or remaining != timeout:
                # Rebluid overlay only if remaining number has changed
                self._show_overlay(str(remaining), alpha)
                timeout = remaining
                shown = False

            updated_rect = None
            if self._preview_compatible:
                updated_rect = self._window.show_image(self._get_preview_image())
            elif not shown:
                updated_rect = self._window.show_image(self._get_preview_image())
                shown = True  # Do not update dummy preview until next overlay update

            if first_loop:
                timer.start()  # Because first preview capture is longer than others
                first_loop = False

            pygame.event.pump()
            if updated_rect:
                pygame.display.update(updated_rect)

        self._show_overlay(get_translated_text('smile'), alpha)
        self._window.show_image(self._get_preview_image())

    def preview_wait(self, timeout, alpha=80):
        """Wait the given time.
        """
        timeout = int(timeout)
        if timeout < 1:
            raise ValueError("Start time shall be greater than 0")

        timer = PoolingTimer(timeout)
        if self._preview_compatible:
            while not timer.is_timeout():
                updated_rect = self._window.show_image(self._get_preview_image())
                pygame.event.pump()
                if updated_rect:
                    pygame.display.update(updated_rect)
        else:
            time.sleep(timer.remaining())

        self._show_overlay(get_translated_text('smile'), alpha)
        self._window.show_image(self._get_preview_image())

    def stop_preview(self):
        """Stop the preview.
        """
        self._stop_preview_stream()
        self._hide_overlay()
        with self._preview_image_lock:
            self._preview_image = None
        self._window = None

    def capture(self, effect=None):
        """Capture a new picture.
        """
        self._stop_preview_stream()

        effect = str(effect).lower()
        if effect not in self.IMAGE_EFFECTS:
            raise ValueError("Invalid capture effect '{}' (choose among {})".format(effect, self.IMAGE_EFFECTS))

        if self.capture_iso != self.preview_iso:
            self.set_config_value('imgsettings', 'iso', self.capture_iso)

        self._trigger_liveview_autofocus()

        if self._preview_viewfinder:
            self.set_config_value('actions', 'viewfinder', 0)

        self._captures.append((self._cam.capture(gp.GP_CAPTURE_IMAGE), effect))
        time.sleep(0.3)  # Necessary to let the time for the camera to save the image

        if self.capture_iso != self.preview_iso:
            self.set_config_value('imgsettings', 'iso', self.preview_iso)

        self._hide_overlay()  # If stop_preview() has not been called

    def quit(self):
        """Close the camera driver, it's definitive.
        """
        self._stop_preview_stream()
        if self._cam:
            del self._gp_logcb  # Uninstall log callback
            self._cam.exit()
