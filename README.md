# README
x6500-miner is a set of code designed for working with the X6500 FPGA Miner boards, which are used for bitcoin mining. Portions of the code are borrowed or inspired by poclbm and phoenix-miner, and some direct contribution has been made by m0mchil.

## KRAMBLE WARNING
This is a quick, nasty hack to support blakecoin, do not use for bitcoin as it will not work

## Dependencies
The main dependencies are python 2.7 and the PyUSB module created by Pablo Bleyer. PyUSB is available as source or an installer for Windows from: http://bleyer.org/pyusb.

For Linux, you will need to build and install my modified version of the PyUSB module. This is available from http://fpgamining.com/software.

## Usage
There are two python scripts that are needed to mine with an X6500. The first is _program.py_, which will program the FPGA and prepare it for bitcoin mining. This needs to be run every time power is removed from the board or if you want to load a different bitstream. The second script is _mine.py_, which handles the communication between the pool and the X6500.

### program.py
```
Usage: program.py [-d <devicenum>] [-c <chain>] <path-to-bitstream-file>

Options:
  -h, --help            show this help message and exit
  -d DEVICENUM, --devicenum=DEVICENUM
                        Device number, optional. If left out, the first available 
						device will be opened.
  -c CHAIN, --chain=CHAIN
                        JTAG chain number, can be 0, 1, or 2 for both FPGAs on
                        the board (default 2)
  -v, --verbose         Verbose logging
```

### mine.py
```
Usage: mine.py [-d <devicenum>] [-c <chain>] -u <pool-url> -w <user:pass>

Options:
  -h, --help            show this help message and exit
  -d DEVICENUM, --devicenum=DEVICENUM
                        Device number, optional. If left out, the first available 
						device will be opened.
  -c CHAIN, --chain=CHAIN
                        JTAG chain number, can be 0, 1, or 2 for both FPGAs on
                        the board (default 2)
  -i GETWORK_INTERVAL, --interval=GETWORK_INTERVAL
                        Getwork interval in seconds (default 20)
  -v, --verbose         Verbose logging
  -u URL, --url=URL     URL for the pool or bitcoind server, e.g. pool.com:8337
  -w WORKER, --worker=WORKER
                        Worker username and password for the pool, e.g. user:pass
```

