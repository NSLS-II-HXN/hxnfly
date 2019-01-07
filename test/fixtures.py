import os
import logging

import pytest
import IPython

from hxnfly import ppmac_util

from .fly_mock import (MockIPython, MockPpmac, MockPositioner, MockLogbook,
                       AttrDict)
from .sim_detector import TestDetector


LOG_SETUP = False


@pytest.fixture(scope='function')
def ipython(monkeypatch):
    global LOG_SETUP

    def mock_ipython():
        return _ipython

    _ipython = MockIPython()
    monkeypatch.setattr(IPython, 'get_ipython', mock_ipython)

    import hxnfly.log

    if not LOG_SETUP:
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                'hxnfly.log')
        hxnfly.log.log_setup(log_path=log_path)
        LOG_SETUP = True

    _ipython.user_ns['logbook'] = MockLogbook()
    return _ipython


@pytest.fixture(scope='function')
def logbook(ipython):
    return ipython.user_ns['logbook']


@pytest.fixture(scope='function', autouse=True)
def ppmac(monkeypatch, ipython):
    def mock_connect(*args, **kwargs):
        return _ppmac

    _ppmac = MockPpmac()
    monkeypatch.setattr(ppmac_util, 'ppmac_connect', mock_connect)
    import hxnfly.fly
    monkeypatch.setattr(hxnfly.fly, 'ppmac_connect', mock_connect)
    return _ppmac


@pytest.fixture(scope='function')
def gpascii(ppmac):
    return ppmac.gpascii


def set_motor_status(gpascii, axis, home_pos, act_pos, in_position,
                     closed_loop):
    gpascii.set_variable('motor[{}].homepos'.format(axis), float(home_pos))
    gpascii.set_variable('motor[{}].actpos'.format(axis), float(act_pos))
    gpascii.set_variable('motor[{}].inpos'.format(axis), int(in_position))
    gpascii.set_variable('motor[{}].closedloop'.format(axis), int(closed_loop))


@pytest.fixture(scope='function')
def axes(gpascii):
    axes = dict(testx=30, testy=31, testz=32)
    for num in axes.values():
        set_motor_status(gpascii, num, home_pos=0.0, act_pos=1.0,
                         in_position=True, closed_loop=True)

    gpascii.positioners = {name: MockPositioner(name=name)
                           for name, num in axes.items()}
    gpascii.positioners_by_number = {num: gpascii.positioners[name]
                                     for name, num in axes.items()}
    return axes


@pytest.fixture(scope='function')
def positioners(gpascii, axes):
    return gpascii.positioners


@pytest.fixture(scope='module')
def sim_det():
    det = TestDetector('', name='test_det', image_name='sim_tiff')
    det.wait_for_connection()
    return det


@pytest.fixture(scope='function')
def xspress3(ipython):
    return ipython.user_ns['xspress3']


@pytest.fixture(scope='function')
def run_engine(ipython, monkeypatch):
    from bluesky.tests.utils import setup_test_run_engine

    run_engine = setup_test_run_engine()

    new_md = dict(run_engine.md)
    new_md.update(ipython.user_ns['gs'].RE.md)
    run_engine.md = new_md

    run_engine.ignore_callback_exceptions = False
    return run_engine


@pytest.fixture(scope='function')
def global_state(monkeypatch, run_engine):
    import hxntools.scans

    global_state = AttrDict(RE=run_engine, detectors=[])
    monkeypatch.setattr(hxntools.scans, 'get_gs', lambda: global_state)

    import hxntools.scans
    hxntools.scans.setup(debug_mode=True)
    return global_state


def setup_function(function):
    logger = logging.getLogger('hxnfly')
    logger.info('')
    logger.info('----------------------------------')
    logger.info('{}'.format(function))


def teardown_function(function):
    logger = logging.getLogger('hxnfly')
    logger.info('----------------------------------')
    logger.info('')


def setup_module(module):
    for name in ['hxnfly', 'hxntools', 'bluesky']:
        logging.getLogger(name).setLevel(logging.DEBUG)

    import filestore
    import filestore.handlers
    filestore.api.register_handler('AD_TIFF',
                                   filestore.handlers.AreaDetectorTiffHandler)
