# -*- coding: utf-8 -*-

import os
import pytest

from pibooth.camera import GpCamera


@pytest.mark.skipif("CAM_VIDEODRIVER" in os.environ, reason="No camera")
def test_rpi_capture(camera_rpi):
    camera_rpi.capture()
    assert camera_rpi.get_captures()


@pytest.mark.skipif("CAM_VIDEODRIVER" in os.environ, reason="No camera")
def test_cv_capture(camera_cv):
    camera_cv.capture()
    assert camera_cv.get_captures()


@pytest.mark.skipif("CAM_VIDEODRIVER" in os.environ, reason="No camera")
def test_gp_capture(camera_gp):
    camera_gp.capture()
    assert camera_gp.get_captures()


@pytest.mark.skipif("CAM_VIDEODRIVER" in os.environ, reason="No camera")
def test_hybridr_capture(camera_rpi_gp):
    camera_rpi_gp.capture()
    assert camera_rpi_gp.get_captures()


@pytest.mark.skipif("CAM_VIDEODRIVER" in os.environ, reason="No camera")
def test_hybridc_capture(camera_cv_gp):
    camera_cv_gp.capture()
    assert camera_cv_gp.get_captures()


def test_gp_configure_exposure_keeps_camera_setting_by_default(monkeypatch):
    camera = GpCamera(None)
    calls = []
    monkeypatch.setattr(camera, 'set_config_value', lambda *args: calls.append(args))

    camera.configure_exposure('camera', 'camera')

    assert camera.aperture == 'camera'
    assert camera.shutter_speed == 'camera'
    assert calls == []


def test_gp_configure_exposure_sets_aperture(monkeypatch):
    camera = GpCamera(None)
    calls = []
    monkeypatch.setattr(camera, 'set_config_value', lambda *args: calls.append(args))

    camera.configure_exposure('8', '1/125')

    assert camera.aperture == '8'
    assert camera.shutter_speed == '1/125'
    assert calls == [('capturesettings', 'aperture', '8'),
                     ('capturesettings', 'shutterspeed', '1/125')]


def test_gp_initialization_keeps_camera_iso_setting(monkeypatch):
    camera = GpCamera(None)
    camera.preview_iso = 'camera'
    camera.capture_iso = 'camera'
    calls = []

    class FakeCamera(object):

        def get_abilities(self):
            return type('Abilities', (), {'operations': 0})()

    camera._cam = FakeCamera()
    monkeypatch.setattr(camera, 'set_config_value', lambda *args: calls.append(args))
    monkeypatch.setattr(camera, 'get_config_value', lambda *args: (_ for _ in ()).throw(ValueError()))
    monkeypatch.setattr(__import__('pibooth.camera.gphoto', fromlist=['gp']).gp, 'check_result', lambda value: value)
    monkeypatch.setattr(__import__('pibooth.camera.gphoto', fromlist=['gp']).gp, 'gp_log_add_func', lambda *args: object())
    monkeypatch.setattr(__import__('pibooth.camera.gphoto', fromlist=['gp']).gp, 'GP_LOG_VERBOSE', object())
    monkeypatch.setattr(__import__('pibooth.camera.gphoto', fromlist=['gp']).gp, 'GP_OPERATION_CAPTURE_PREVIEW', 1)

    camera._specific_initialization()

    assert calls == [('settings', 'capturetarget', 'Memory card')]


def test_gp_capture_keeps_camera_iso_setting(monkeypatch):
    camera = GpCamera(None)
    camera.preview_iso = 'camera'
    camera.capture_iso = 'camera'
    camera._preview_viewfinder = False
    camera._cam = type('FakeCamera', (), {'capture': lambda self, mode: 'image-path'})()
    calls = []
    monkeypatch.setattr(camera, '_stop_preview_stream', lambda: None)
    monkeypatch.setattr(camera, 'set_config_value', lambda *args: calls.append(args))
    monkeypatch.setattr(__import__('pibooth.camera.gphoto', fromlist=['gp']).gp, 'GP_CAPTURE_IMAGE', 'capture-image')
    monkeypatch.setattr(__import__('pibooth.camera.gphoto', fromlist=['time']).time, 'sleep', lambda _: None)

    camera.capture('none')

    assert calls == []
    assert camera._captures == [('image-path', 'none')]


def test_gp_get_calibration_options(monkeypatch):
    camera = GpCamera(None)
    gphoto_module = __import__('pibooth.camera.gphoto', fromlist=['gp'])

    class FakeChild(object):

        def __init__(self, value, choices):
            self._value = value
            self._choices = choices

        def get_type(self):
            return gphoto_module.gp.GP_WIDGET_RADIO

        def get_choices(self):
            return self._choices

        def get_value(self):
            return self._value

    children = {
        ('imgsettings', 'iso'): FakeChild('1600', ['800', '1600', '3200']),
        ('capturesettings', 'aperture'): FakeChild('8', ['5.6', '8', '11']),
        ('capturesettings', 'shutterspeed'): FakeChild('1/125', ['1/60', '1/100', '1/125']),
    }

    def fake_get_config_item(section, option):
        return None, children[(section, option)]

    monkeypatch.setattr(camera, '_get_config_item', fake_get_config_item)
    monkeypatch.setattr(camera, '_preview_compatible', True)

    options = camera.get_calibration_options()

    assert list(options) == ['iso', 'aperture', 'shutter_speed']
    assert options['iso']['current'] == '1600'
    assert options['aperture']['choices'] == ['5.6', '8', '11']
    assert options['shutter_speed']['current'] == '1/125'


def test_gp_set_calibration_value(monkeypatch):
    camera = GpCamera(None)
    calls = []
    monkeypatch.setattr(camera, 'set_config_value', lambda *args: calls.append(args))
    monkeypatch.setattr(camera, 'get_config_value', lambda section, option: '1/60')

    value = camera.set_calibration_value('shutter_speed', '1/60')

    assert value == '1/60'
    assert calls == [('capturesettings', 'shutterspeed', '1/60')]
