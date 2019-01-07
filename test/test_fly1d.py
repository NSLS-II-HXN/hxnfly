import pytest

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

import filestore
import filestore.api
import filestore.handlers

from hxnfly.fly1d import Fly1D
from hxnfly.bs import FlyPlan1D
from .fly_mock import (MockDetector, MockSignal)
from .sim_detector import TestDetector
from .fixtures import *


def make_1d_data(startx, endx, npts, gathered_points=100,
                 gate_enable='low_to_high'):
    time = np.linspace(0, 10.0, gathered_points)
    px = np.linspace(startx, endx, gathered_points)
    py = np.random.rand(gathered_points) / 10.0
    pz = np.random.rand(gathered_points) / 10.0

    enable = []
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

    return [time, enable, px, py, pz]


@pytest.fixture(scope='function',
                params=['with_mock_detector', 'with_sim_detector',
                        'relative'])
def fly1d(request, monkeypatch, ppmac, axes, positioners, sim_det,
          ipython, global_state):
    if request.param == 'with_sim_detector':
        sim_det.count_time.put(0.01)
        detectors = [sim_det]
    else:
        detectors = [MockDetector('', name='det')]

    scan = Fly1D(axes=axes, positioners=positioners, detectors=detectors)
    scan.relative = (request.param == 'relative')

    def FakeClass(*args, **kwargs):
        print('initialized with', args, kwargs)
        scan.configure_defaults = dict(return_speed=5.0, dead_time=0.007,
                                       fly_type='soft', max_points=16384)
        return scan

    testx = positioners['testx']
    FlyPlan1D.scans = {frozenset({testx}): FakeClass,
                       }
    return scan


def setup_scan(fly1d, ipython, positioners, *, configure=True):
    startx, endx, npts = -1.0, 1.0, 2
    exposure_time = 1.0

    if configure:
        fly1d.configure(positioners['testx'], startx, endx, npts,
                        exposure_time=exposure_time, relative=fly1d.relative)

    sclr1 = ipython.user_ns['sclr1']
    sclr1.mca_by_index[1].spectrum.put(np.array([exposure_time * 50e3] * npts))

    # fake data for parsing
    gather_client = fly1d.gather_client
    gather_client.gathered = make_1d_data(startx, endx, npts,
                                          gathered_points=100,
                                          gate_enable=fly1d._gate_enable)


def test_fly1d(fly1d, sim_det, ipython, positioners):
    setup_scan(fly1d, ipython, positioners, configure=True)
    data = fly1d.run_subscan(0)
    df = pd.DataFrame(list(pd.DataFrame(data)['data']))
    print('acquired data:')
    print(df)

    for sig, value in sim_det.stage_sigs.items():
        print('det', sig.name, value, sig.setpoint_pvname)
    for sig, value in sim_det.cam.stage_sigs.items():
        print('cam', sig.name, value)
    for sig, value in sim_det.tiff1.stage_sigs.items():
        print('tiff1', sig.name, value)

    has_test_det = any(isinstance(det, TestDetector)
                       for det in fly1d.detectors)

    if has_test_det:
        assert 'sim_tiff' in df

        for img_uid in df['sim_tiff']:
            print(img_uid, filestore.api.retrieve(img_uid).shape)

    print(fly1d.collect())
    print(fly1d.describe())


def test_flyplan1d(positioners, fly1d, run_engine):
    import hxnfly.bs
    plan = hxnfly.bs.FlyPlan1D()
    gen = plan(positioners['testx'], -1.0, 1.0, 2, 1.0, dead_time=0.001)
    run_engine(gen)


def test_flyplan1d_with_callbacks(request, positioners, fly1d, run_engine):
    import hxnfly.bs
    from hxnfly.callbacks import FlyLivePlot
    #    , FlyRoiPlot, FlyLiveImage)
    from hxnfly.callbacks import FlyDataCallbacks
    plan = hxnfly.bs.FlyPlan1D()

    # flyplot = FlyRoiPlot(['Pt'], channels=[1, 2, 3], use_sum=True)
    # fly2dplot = FlyLiveImage(['As','Ba','S','Cs','Ti'], channels=[1, 2, 3],
    #                          use_sum=True)
    # fly2dplot1 = FlyLiveCrossSection(['Ba'], channels=[1, 2, 3],
    #                                  use_sum=True)
    point_signal = MockSignal('point_signal', 3)
    data_signal1 = MockSignal('data_signal1', [1, 0.5, 2])
    data_signal2 = MockSignal('data_signal2', [2, 1.5, 1])
    liveplot = FlyLivePlot({'sig1': [data_signal1],
                            'sig2': [data_signal2]},
                           point_signal=point_signal)
    plan.subs = [FlyDataCallbacks(), liveplot]
    gen = plan(positioners['testx'], -1.0, 1.0, 2, 1.0, dead_time=0.001)
    run_engine(gen)

    plt.savefig('liveplot-{}.png'.format(request.node.name))
    liveplot.disable()
    plt.clf()


def test_fly1d_plot_position(request, fly1d, sim_det, ipython, positioners):
    setup_scan(fly1d, ipython, positioners, configure=True)
    fly1d.run_subscan(0)

    from hxnfly.plot import plot_position
    plot_position(fly1d.scan_id, fly1d.data[fly1d.scan_id], fly1d._debug_data,
                  left='testx', right='testy')
    plt.savefig('plot_position-{}.png'.format(request.node.name))
    plt.clf()


def test_mll_imports(ipython):
    import hxnfly.fly_mll


def test_zp_imports(ipython):
    import hxnfly.fly_zp


def test_mllzp_imports(ipython):
    import hxnfly.hxn_fly
