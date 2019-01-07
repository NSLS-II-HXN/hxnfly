import time

import pytest
import numpy as np
import pandas as pd

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

import filestore
import filestore.api
import filestore.handlers

import hxnfly.fly
import hxnfly.log
from hxnfly.callbacks import FlyLiveCrossSection
from hxnfly.fly2d import Fly2D
from hxnfly.bs import FlyPlan2D

from .fly_mock import (MockDetector, MockSignal)
from .sim_detector import TestDetector
from .fixtures import *


def test_scan_points():
    from hxnfly.fly2d import _get_scan_points
    point_args = (0.0, 1.0, 10,
                  1.0, 2.0, 10,
                  )
    points = list(_get_scan_points(*point_args, max_points=22))

    assert len(points) == 5
    assert sum(py for xi, xj, px, yi, yj, py in points) == 10

    xis = [xi for xi, xj, px, yi, yj, py in points]
    xjs = [xj for xi, xj, px, yi, yj, py in points]
    assert min(xis) == 0.0
    assert max(xjs) == 1.0

    yis = [yi for xi, xj, px, yi, yj, py in points]
    yjs = [yj for xi, xj, px, yi, yj, py in points]
    assert min(yis) == 1.0
    assert max(yjs) == 2.0


def make_2d_data(startx, endx, nptsx,
                 starty, endy, nptsy,
                 gathered_points=200,
                 gate_enable='low_to_high'):
    # this is not entirely accurate...
    time = np.linspace(0, 10.0, gathered_points)
    gather_y = gathered_points // nptsy
    px = np.array(np.linspace(startx, endx, gather_y).tolist() * nptsy)
    py = np.array(sum(([pt] * gather_y
                       for pt in np.linspace(starty, endy, nptsy)),
                      []))
    pz = np.random.rand(gathered_points) / 10.0

    enable = []
    npts = nptsx * nptsy
    exposed_count = (gathered_points // npts) - 1

    for i in range(npts):
        if gate_enable == 'low_to_high':
            enable.extend([0] + [1] * exposed_count)
        else:
            enable.extend([1] + [0] * exposed_count)

    if gate_enable == 'low_to_high':
        enable[-1] = 0
    else:
        enable[-1] = 1

    return [np.array(v) for v in (time, enable, px, py, pz)]


@pytest.fixture(scope='function',
                params=['with_mock_detector', 'with_sim_detector',
                        'relative'])
def fly2d(request, monkeypatch, ppmac, gpascii, axes, positioners,
          sim_det, ipython, global_state):
    import hxntools.scans
    hxntools.scans.setup(debug_mode=True)

    def run_and_wait(*args, **kwargs):
        print('run and wait!')
        change_callback = kwargs.pop('change_callback')
        time.sleep(0.1)
        change_callback('Q1', 0, 1)
        time.sleep(1.0)
        return 0

    monkeypatch.setattr(gpascii, 'run_and_wait', run_and_wait)

    if request.param == 'with_sim_detector':
        sim_det.count_time.put(0.01)
        detectors = [sim_det]
    else:
        detectors = [MockDetector('', name='det')]

    gpascii.set_variable('gather.samples', 100)
    gpascii.set_variable('gather.maxlines', 100)

    scan = Fly2D(axes=axes, positioners=positioners, detectors=detectors)
    startx, endx, nptsx = -1.0, 1.0, 2
    starty, endy, nptsy = -1.0, 1.0, 2
    exposure_time = 1.0
    relative = (request.param == 'relative')
    scan.configure(positioners['testx'], startx, endx, nptsx,
                   positioners['testy'], starty, endy, nptsy,
                   exposure_time=exposure_time, relative=relative)

    npts = nptsx * nptsy
    sclr1 = ipython.user_ns['sclr1']
    sclr1.mca_by_index[1].spectrum.put(np.array([exposure_time * 50e3] * npts))

    gather_client = scan.gather_client
    # fake data for parsing
    gather_client.gathered = make_2d_data(startx, endx, nptsx,
                                          starty, endy, nptsy,
                                          gathered_points=500,
                                          gate_enable=scan._gate_enable)

    def FakeClass(*args, **kwargs):
        print('initialized with', args, kwargs)
        scan.configure_defaults = dict(return_speed=5.0, dead_time=0.007,
                                       fly_type='soft', max_points=16384)
        return scan

    testx, testy = positioners['testx'], positioners['testy']
    FlyPlan2D.scans = {frozenset({testx, testy}): FakeClass,
                       }
    return scan


def test_fly2d(fly2d):
    # kickoff sends in the subscan number normally
    data = fly2d.run_subscan(0)
    df = pd.DataFrame(list(pd.DataFrame(data)['data']))
    print('acquired data:')
    print(df)

    has_test_det = any(isinstance(det, TestDetector)
                       for det in fly2d.detectors)

    if has_test_det:
        assert 'sim_tiff' in df

        for img_uid in df['sim_tiff']:
            print(img_uid, filestore.api.retrieve(img_uid).shape)

    print(fly2d.collect())
    print(fly2d.describe())


def test_failed_fly2d(fly2d, gpascii, monkeypatch):
    def run_and_wait(*args, **kwargs):
        time.sleep(1.0)
        return 1

    monkeypatch.setattr(gpascii, 'run_and_wait', run_and_wait)
    data = fly2d.run_subscan(0)
    assert data is None


def test_flyplan2d(monkeypatch, positioners, fly2d, run_engine):
    scan_fcn = hxnfly.bs.FlyPlan2D()
    gen = scan_fcn(positioners['testx'], -1.0, 1.0, 2,
                   positioners['testy'], -1.0, 1.0, 2,
                   1.0, dead_time=0.001,
                   )
    run_engine(gen)


def test_flyplan2d_liveimage(request, monkeypatch, positioners, run_engine,
                             fly2d, xspress3):
    fly2d.detectors.append(xspress3)

    scan_fcn = hxnfly.bs.FlyPlan2D()
    from hxnfly.callbacks import (FlyDataCallbacks, FlyLiveImage)

    monkeypatch.setattr(hxnfly.fly, 'Xspress3Detector', xspress3.__class__)

    xspress3.array_counter.put(4)

    # TODO is this done in configure_roi?
    xspress3.setup_fake_rois([('Fe', [1, 2, 3, 4]),
                              ('Mo', [4, 3, 2, 1])
                              ])
    liveimage = FlyLiveImage(['Fe', 'Mo'])

    scan_fcn.subs = [FlyDataCallbacks(), liveimage]
    gen = scan_fcn(positioners['testx'], -1.0, 1.0, 2,
                   positioners['testy'], -1.0, 1.0, 2,
                   1.0, dead_time=0.001,
                   )

    run_engine(gen)

    plt.savefig('liveimage-{}.png'.format(request.node.name))
    liveimage.disable()
    plt.clf()


# TODO crossection plot needs fixing
# @pytest.mark=
def test_flyplan2d_crossection(request, monkeypatch, positioners, run_engine,
                               fly2d, xspress3):
    fly2d.detectors.append(xspress3)

    scan_fcn = hxnfly.bs.FlyPlan2D()

    monkeypatch.setattr(hxnfly.fly, 'Xspress3Detector', xspress3.__class__)

    xspress3.array_counter.put(4)

    # TODO is this done in configure_roi?
    xspress3.setup_fake_rois([('Fe', [1, 2, 3, 4]),
                              ('Mo', [4, 3, 2, 1])
                              ])
    with pytest.raises(ValueError):
        # cross-section only does 1 at a time
        FlyLiveCrossSection(['Fe', 'Mo'])

    crossection = FlyLiveCrossSection(['Fe'])
    scan_fcn.subs = [crossection]
    gen = scan_fcn(positioners['testx'], -1.0, 1.0, 2,
                   positioners['testy'], -1.0, 1.0, 2,
                   1.0, dead_time=0.001,
                   )

    run_engine(gen)

    crossection.disable()
    from PyQt4.QtGui import QPixmap

    live_fn = 'crossection-live-{}.png'.format(request.node.name)
    QPixmap.grabWindow(crossection.live_window.winId()).save(live_fn, 'png')
    crossection.live_window.close()

    if crossection._final_window is not None:
        final_fn = 'crossection-final-{}.png'.format(request.node.name)
        QPixmap.grabWindow(crossection.final_window.winId()).save(final_fn,
                                                                  'png')
        crossection.final_window.close()
