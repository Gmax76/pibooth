DSLR first configuration
^^^^^^^^^^^^^^^^^^^^^^^^

- Disable "auto-sleep" or "auto-off" to prevent errors while running pibooth.
- Disable Wifi feature to solve gphoto2 troubles to detect hardware.
- Disable the autofocus to avoid gphoto2 troubles to take a picture.
- Put a SD card on the camera (the captures will be kept also on the camera side)

DSLR settings
^^^^^^^^^^^^^

If your DSLR exposes remote aperture and shutter controls through gphoto2, pibooth
can also set the `CAMERA` `aperture` and `shutter_speed` options. Keep the mode dial
on `M`, `Av`, `Tv` or `P`, otherwise the camera may refuse the requested value and
keep its current setting.

Most common settings for DSLR::

    Shutter speed: 1/60
    Focal Opening: F10
    ISO: 3200

    Shutter speed: 1/125
    Focal Opening: F8
    ISO: 3200

Credits goes to https://fotomax.fr/canon-camera-settings-with-a-magic-mirror-photobooth/, alternative settings are also available, mainly depending on natural light conditions.

DSLR Troubleshooting
^^^^^^^^^^^^^^^^^^^^

If the DLSR don't manage to take the photo Pibooth will show the "Oops something went wrong" screen. Most of the issues that our users encountered are either linked to:

- Not enough light (or no light at all when the lens cap has not been removed)
- Camera didn't manage to focus (that's why we advise to disable the autofocus and manually set it at the beginning)
- Camera rejected a requested ISO, aperture or shutter speed value because the mode dial is in a fully automatic mode
- No SD card in the camera (as all the captures are downloaded in the processing stage)