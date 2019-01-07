import re
import time
import logging

import numpy as np

import ophyd
from ophyd import (Signal, Component as Cpt)
from hxntools.detectors.trigger_mixins import HxnModalBase


class AttrDict(dict):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.__dict__ = self


class MockFastGather:
    def __init__(self, ppmac):
        self.ppmac = ppmac

        # state for the test:
        self.gathered = None
        self.n_addr = None
        self.n_samples = None

    def query_types(self):
        return 'type_placeholder'

    def query_raw_data(self):
        return 1, b'abcd'

    def _parse_raw_data(self, dtypes, raw_data):
        return self.gathered, self.n_addr, self.n_samples

    def __repr__(self):
        return 'MockFastGather()'


class MockGpascii:
    def __init__(self, ppmac):
        self.ppmac = ppmac
        self.servo_period = 1.0

        # for holdint test state:
        self.variables = {}
        self.positioners = {}
        self.positioners_by_number = {}

    def run_and_wait(self, coord_sys, prog_num, verbose=False, **kwargs):
        # NOTE: need enough time for areadetector to write out the frames:
        time.sleep(1.0)
        return 0  # success!

    def program(self, coord_sys, prog_num, stop=False, **kwargs):
        print('program kwargs', kwargs)

    def send_program(self, coord_sys, prog_num, filename=None, verbose=None,
                     macros=None, motors=None):
        print('send_program', coord_sys, prog_num, filename, verbose, macros,
              motors)

    def run_simple_script(self, script_fn):
        print('run_simple_script', script_fn)

    def get_variable(self, name, type_=float):
        return type_(self.variables[name.lower()])

    def set_variable(self, name, value):
        self.variables[name.lower()] = value

    def send_line(self, line):
        m = re.match('#(\d+)j=(.*)', line)
        if m:
            motor, position = m.groups()
            motor = int(motor)
            position = float(position)
            self.jog(motor, position, relative=False)

    def jog(self, motor, target, relative=False, wait=False):
        if relative:
            target += self.positioners_by_number[motor].position

        self.positioners_by_number[motor].position = target
        print('moved motor', motor, 'to position', target)

    def sync(self):
        pass

    def __repr__(self):
        return 'MockGpascii()'


class MockPpmac:
    def __init__(self, *args, **kwargs):
        self.fast_gather = MockFastGather(self)
        self.gpascii = MockGpascii(self)

    def __repr__(self):
        return 'MockPpmac()'


class MockDetector(HxnModalBase):
    def stage(self):
        print('staging', self, self.mode_settings.get())

    def unstage(self):
        print('unstaging', self)


class MockMca(ophyd.Device):
    spectrum = Cpt(Signal, value=np.array([1, 2, 3]))

    def __init__(self, ch, name):
        super().__init__('', name=name)
        self.ch = ch
        self.spectrum.pvname = 'fake_mca_pvname_{}'.format(ch)


class MockScaler(HxnModalBase):
    mca_by_index = {ch: MockMca(ch, name='mca{}'.format(ch))
                    for ch in range(32)}

    def stage(self):
        print('staging', self, self.mode_settings.get())

    def unstage(self):
        print('unstaging', self)


class MockPositioner:
    def __init__(self, name=''):
        self.name = name
        self.position = 0.0
        self.egu = 'um'

    def move(self, position, wait=False):
        raise ValueError()

    def __repr__(self):
        return 'MockPositioner(name={!r})'.format(self.name)


class MockSignal:
    def __init__(self, name, value=None):
        self.name = name
        self.value = value
        self._timestamp = 1

    def get(self, *, count=None, use_monitor=False):
        if count is not None:
            return self.value[:count]

        return self.value

    def put(self, value):
        self.value = value

    @property
    def timestamp(self):
        self._timestamp += 1
        return self._timestamp


class MockXspress3ROI:
    def __init__(self, name, value):
        self.name = name
        self.value = MockSignal(name, [1, 2, 3])
        self.value.put(value)

    channel_num = 1


class MockXspress3HDF5:
    _fn = '_fake_staged_filename_'
    capture = MockSignal('capture', 0)


class MockXspress3(MockDetector):
    def __init__(self, name):
        super().__init__(name, name=name)

    def setup_fake_rois(self, rois):
        self.enabled_rois = [MockXspress3ROI(name, spectrum)
                             for name, spectrum in rois]

    def read_hdf5(self, fn):
        for roi in self.enabled_rois:
            # yield roi name, namedtuple with info + spectrum
            yield roi.name, AttrDict(value=roi.value.get(),
                                     ev_low=5, ev_high=10,
                                     )

    enabled_rois = [MockXspress3ROI('Fe', [1, 2, 3]),
                    MockXspress3ROI('Mo', [3, 2, 1]),
                    ]
    acquire = MockSignal('acquire', 0)
    settings = AttrDict(array_counter=MockSignal('array_counter', 3))
    external_trig = MockSignal('external_trig', True)
    hdf5 = MockXspress3HDF5()
    spectra_per_point = MockSignal('spectra_per_point', 1)
    total_points = MockSignal('total_points', 3)


class MockIPython:
    # TODO: scan_id may be off by 1 with RE sync?
    user_ns = {'gs': AttrDict(RE=AttrDict(md={'scan_id': 99999})),
               'zebra': MockDetector('', name='zebra'),
               'sclr1': MockScaler('', name='sclr1'),
               'ssx': MockPositioner(name='ssx'),
               'ssy': MockPositioner(name='ssy'),
               'ssz': MockPositioner(name='ssz'),
               'zpssx': MockPositioner(name='zpssx'),
               'zpssy': MockPositioner(name='zpssy'),
               'zpssz': MockPositioner(name='zpssz'),
               'xspress3': MockXspress3(name='xspress3'),
               }

    class MockEvents:
        def register(self, event, callback):
            pass

    events = MockEvents()


class MockLogbook:
    def log(self, log_text, **kwargs):
        logger = logging.getLogger('hxnfly.fly')
        logger.info('[[LOGBOOK]] {}'.format(log_text))
