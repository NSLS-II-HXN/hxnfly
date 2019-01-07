import os

from ophyd.areadetector.filestore_mixins import (FileStoreIterativeWrite,
                                                 FileStoreTIFF)

from ophyd import (Device, Component as Cpt)
from ophyd.areadetector import (SimDetectorCam, HDF5Plugin, TIFFPlugin,
                                DetectorBase)
from hxntools.detectors.trigger_mixins import (HxnModalTrigger,
                                               FileStoreBulkReadable)


DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         'test_data')


class SimTIFFPlugin(TIFFPlugin, FileStoreBulkReadable, FileStoreTIFF, Device):
    def __init__(self, prefix, **kwargs):
        print('tiff plugin', prefix, kwargs)
        super().__init__(prefix, **kwargs)

    def mode_external(self):
        print('tiff mode external')
        total_points = self.parent.mode_settings.total_points.get()
        self.stage_sigs[self.num_capture] = total_points

    def get_frames_per_point(self):
        mode = self.parent.mode_settings.mode.get()
        if mode == 'external':
            return 1
        else:
            return self.parent.cam.num_images.get()


class TestDetector(HxnModalTrigger, DetectorBase):
    tiff1 = Cpt(SimTIFFPlugin, 'XF:31IDA-BI{Cam:Tbl}TIFF1:',
                read_attrs=[],
                configuration_attrs=[],
                write_path_template=os.path.join(DATA_PATH, '%Y-%m-%d', ''),
                )

    cam = Cpt(SimDetectorCam, 'XF:31IDA-BI{Cam:Tbl}cam1:')
    # hdf5 = Cpt(SimDetectorCam, 'XF:31IDA-BI{Cam:Tbl}HDF5:')

    def mode_external(self):
        self.tiff1.stage_sigs[self.tiff1.blocking_callbacks] = 1
        self.cam.stage_sigs[self.cam.acquire_time] = 0.01
        self.cam.stage_sigs[self.cam.acquire_period] = 0.10
        super().mode_external()
