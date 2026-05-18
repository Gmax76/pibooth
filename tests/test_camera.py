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
