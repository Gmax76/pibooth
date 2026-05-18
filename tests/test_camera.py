# -*- coding: utf-8 -*-

import os
import pytest
from types import SimpleNamespace

import pibooth.camera.gphoto as gphoto_module
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


def test_gp_liveview_autofocus_uses_autofocusdrive(monkeypatch):
    camera = GpCamera(None)
    camera.set_liveview_autofocus(True)
    camera._preview_compatible = True
    camera._window = object()
    camera._preview_autofocus = True
    camera._eosremoterelease_choices = ()

    calls = []
    monkeypatch.setattr(camera, 'set_config_value', lambda section, option, value: calls.append((section, option, value)))
    monkeypatch.setattr(gphoto_module.time, 'sleep', lambda _: None)

    camera._trigger_liveview_autofocus()

    assert calls == [('actions', 'autofocusdrive', 1)]


def test_gp_liveview_autofocus_falls_back_to_half_press(monkeypatch):
    camera = GpCamera(None)
    camera.set_liveview_autofocus(True)
    camera._preview_compatible = True
    camera._window = object()
    camera._preview_autofocus = False
    camera._eosremoterelease_choices = ('None', 'Press Half', 'Release Half')

    calls = []
    monkeypatch.setattr(camera, 'set_config_value', lambda section, option, value: calls.append((section, option, value)))
    monkeypatch.setattr(gphoto_module.time, 'sleep', lambda _: None)

    camera._trigger_liveview_autofocus()

    assert calls == [
        ('actions', 'eosremoterelease', 'Press Half'),
        ('actions', 'eosremoterelease', 'Release Half'),
    ]


def test_gp_capture_triggers_liveview_autofocus_before_capture(monkeypatch):
    camera = GpCamera(None)
    camera.set_liveview_autofocus(True)
    camera._preview_compatible = True
    camera._preview_viewfinder = True
    camera._window = object()
    camera.preview_iso = 100
    camera.capture_iso = 100

    calls = []

    class FakeProxy(object):

        def capture(self, mode):
            calls.append(('capture', mode))
            return 'image-path'

    camera._cam = FakeProxy()
    monkeypatch.setattr(gphoto_module, 'gp', SimpleNamespace(GP_CAPTURE_IMAGE='capture-image'))
    monkeypatch.setattr(gphoto_module.time, 'sleep', lambda _: None)
    monkeypatch.setattr(camera, '_stop_preview_stream', lambda: calls.append('stop-preview-stream'))
    monkeypatch.setattr(camera, '_trigger_liveview_autofocus', lambda: calls.append('autofocus'))
    monkeypatch.setattr(camera, 'set_config_value', lambda section, option, value: calls.append((section, option, value)))

    camera.capture('none')

    assert calls == [
        'stop-preview-stream',
        'autofocus',
        ('actions', 'viewfinder', 0),
        ('capture', 'capture-image'),
    ]
    assert camera._captures == [('image-path', 'none')]
