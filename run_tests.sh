rm -rf test/hxnfly.log

py.test -vv test --cov=hxnfly $@
# py.test -vv test/test_fly2d.py --cov=hxnfly $@
