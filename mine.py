#!/usr/bin/python
# Copyright (C) 2011 by fpgaminer <fpgaminer@bitcoin-mining.com>
#                       fizzisist <fizzisist@fpgamining.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import sys
from ft232r import FT232R, FT232R_PortList
from jtag import JTAG
from ConsoleLogger import ConsoleLogger
from rpcClient import RPCClient
from fpga import FPGA
import time
from optparse import OptionParser
import traceback
from threading import Thread, Lock
from Queue import Queue, Empty, Full
from struct import pack, unpack
from hashlib import sha256
import os

BASE_TARGET = 'ffffffffffffffffffffffffffffffffffffffffffffffffffffffff00000000'.decode('hex')

# Option parsing:
parser = OptionParser(usage="%prog [-d <devicenum>] [-c <chain>] -u <pool-url> -w <user:pass>")
parser.add_option("-d", "--devicenum", type="int", dest="devicenum", default=None,
                  help="Device number, optional. Opens the first available device by default")
parser.add_option("-c", "--chain", type="int", dest="chain", default=2,
                  help="JTAG chain number, can be 0, 1, or 2 for both FPGAs on the board (default 2)")
parser.add_option("-i", "--interval", type="int", dest="getwork_interval", default=20,
                  help="Getwork interval in seconds (default 20)")
parser.add_option("-v", "--verbose", action="store_true", dest="verbose", default=False,
                  help="Verbose logging")
parser.add_option("-u", "--url", type="str", dest="url",
                  help="URL for the pool or bitcoind server, e.g. pool.com:8337")
parser.add_option("-w", "--worker", type="str", dest="worker",
                  help="Worker username and password for the pool, e.g. user:pass")
parser.add_option("-s", "--sleep", action="store_true", dest="sleep", default=False,
                  help="Put FPGAs to sleep upon exit [EXPERIMENTAL]")
parser.add_option("--overclock", type="int", dest="overclock", default=None,
		  help="Set the FPGA's clocking speed (in MHz) [WARNING: Use with Extreme Caution]")
settings, args = parser.parse_args()

# Special error to make sure the user doesn't do something terrible
if settings.overclock is not None and (settings.overclock > 300 or settings.overclock < 4):
	print "ERROR: Overclock set too high!!! Please be careful with this setting, it could DAMAGE your Miner!!!"
	parser.print_usage()
	sys.exit()


class Object(object):
	pass
	
def checkTarget(target, hashOutput):
	for t,h in zip(target[::-1], hashOutput[::-1]):
		if ord(t) > ord(h):
			return True
		elif ord(t) < ord(h):
			return False
	return True

def checkNonce(gold):
	staticDataUnpacked = unpack('<' + 'I'*19, gold.job.data.decode('hex')[:76])
	staticData = pack('>' + 'I'*19, *staticDataUnpacked)
	hashInput = pack('>76sI', staticData, gold.nonce)
	# hashOutput = sha256(sha256(hashInput).digest()).digest()

	# blakecoin: This is a bit beyond my python skills, so just report the hash for now
	gnhex = "{0:08x}".format(gold.nonce)
	gnhexrev = gnhex[6:8]+gnhex[4:6]+gnhex[2:4]+gnhex[0:2]
	# hrnonce = gnhex	# TODO check which order is needed
	hrnonce = gnhexrev
	print "hrnonce=",hrnonce	# DEBUG
	chkdata = gold.job.data[:152] + hrnonce + gold.job.data[160:]
	if (os.name == "nt"):
		os.system ("echo checkblake " + chkdata + ">>logmine-ms.log")		# Log file is runnable (rename .BAT)
		os.system ("checkblake " + chkdata)
	else:
		os.system ("echo ./checkblake " + chkdata + ">>logmine-ms.log")	# Log file is runnable as a shell script
		os.system ("./checkblake " + chkdata)
	
	return True	# Just assume its OK
	
	if checkTarget(BASE_TARGET, hashOutput):
		logger.reportValid(gold.fpgaID)
	else:
		logger.reportError(hex(gold.nonce)[2:], gold.fpgaID)
		return False
	
	if checkTarget(gold.job.target.decode('hex'), hashOutput):
		return True
	
	return False
	
def handleNonce(job, nonce, fpgaID):
	logger.reportNonce(fpgaID)
	gold = Object()
	gold.fpgaID = fpgaID
	gold.job = job
	gold.nonce = nonce & 0xFFFFFFFF
	try:
		noncequeue.put(gold, block=True, timeout=10)
	except Full:
		logger.log("%d: Queue full! Lost a nonce!" % fpgaID)

def nonceLoop():
	while True:
		gold = noncequeue.get(block=True)
		if checkNonce(gold):
			try:
				goldqueue.put(gold, block=True, timeout=10)
				#logger.reportDebug("%d: goldqueue loaded (%d)" % (chain, goldqueue[chain].qsize()))
			except Full:
				logger.log("%d: Golden nonce queue full! Lost a golden nonce!" % gold.fpgaID)

def mineLoop(fpga_list):
	for fpga in fpga_list:
		fpga.clearQueue()
	
	while True:
		if stop: return
		
		time.sleep(0.1)
		
		for fpga in fpga_list:
			nonce = None
			job = fpga.getJob()
			
			if job is not None:
				#logger.reportDebug("%d: Loading new job..." % fpga.id)
				if fpga.current_job is not None:
					#logger.reportDebug("%d: Checking for nonce*..." % fpga.id)
					nonce = fpga.readNonce()
				#logger.reportDebug("%d: Writing job..." % fpga.id)
				fpga.writeJob(job)
				if nonce is not None:
					handleNonce(fpga.current_job, nonce, fpga.id)
				fpga.current_job = job
			
			if fpga.current_job is not None:
				#logger.reportDebug("%d: Checking for nonce..." % fpga.id)
				nonce = fpga.readNonce()
				if nonce is not None:
					handleNonce(fpga.current_job, nonce, fpga.id)

if settings.url is None:
	print "ERROR: URL not specified!"
	parser.print_usage()
	sys.exit()
if settings.worker is None:
	print "ERROR: Worker not specified!"
	parser.print_usage()
	sys.exit()

fpga_list = []

goldqueue = Queue()

logger = ConsoleLogger(settings.verbose)
rpcclient = RPCClient(settings, logger, goldqueue)

try:
	# open FT232R
	ft232r = FT232R()
	portlist = FT232R_PortList(7, 6, 5, 4, 3, 2, 1, 0)
	if ft232r.open(settings.devicenum, portlist):
		logger.reportOpened(ft232r.devicenum, ft232r.serial)
	else:
		logger.log("ERROR: FT232R device not opened!", False)
		sys.exit()
	
	if settings.chain == 0 or settings.chain == 1:
		fpga_list.append(FPGA(ft232r, settings.chain, logger))
	elif settings.chain == 2:
		fpga_list.append(FPGA(ft232r, 0, logger))
		fpga_list.append(FPGA(ft232r, 1, logger))
	else:
		logger.log("ERROR: Invalid chain option!", False)
		parser.print_usage()
		sys.exit()
	
	logger.fpga_list = fpga_list
	rpcclient.fpga_list = fpga_list
	
	for id, fpga in enumerate(fpga_list):
		fpga.id = id
		logger.reportDebug("Discovering FPGA %d..." % id, False)
		fpga.detect()
		
		logger.reportDebug("Found %i device%s:" % (fpga.jtag.deviceCount,
			's' if fpga.jtag.deviceCount != 1 else ''), False)

		if len(fpga.jtag.idcodes) > 0:
			idcode = fpga.jtag.idcodes[-1]
			msg = " FPGA" + str(id) + ": "
			msg += JTAG.decodeIdcode(idcode)
			msg += " - Firmware: rev " + str(fpga.firmware_rev)
			msg += ", build " + str(fpga.firmware_build)
			logger.reportDebug(msg, False)
	
	logger.log("Connected to %d FPGAs" % len(fpga_list), False)

	if settings.overclock is not None:
		for fpga in fpga_list:
			fpga.setClockSpeed(settings.overclock)

	
	for fpga in fpga_list:
		clock_speed = fpga.readClockSpeed()

		clock_speed = "???" if clock_speed is None else str(clock_speed)

		logger.log("FPGA %d is running at %sMHz" % (fpga.id, clock_speed), False)
	
	logger.start()
	rpcclient.start()
	
	noncequeue = Queue()
	nonceThread = Thread(target=nonceLoop)
	nonceThread.daemon = True
	nonceThread.start()
	
	stop = False
	
	mineThread = Thread(target=mineLoop, args=(fpga_list,))
	mineThread.daemon = True
	mineThread.start()
	
	while True:
		time.sleep(1)
		logger.updateStatus()
		if mineThread is None or not mineThread.isAlive():
			logger.log("Restarting minethread")
			mineThread = Thread(target=mineLoop, args=(fpga_list,))
			mineThread.daemon = True
			mineThread.start()

except KeyboardInterrupt:
	stop = True
	logger.lineLength += 2
	pass

finally:
	logger.log("Exiting...")
	if settings.sleep:
		for fpga in fpga_list:
			fpga.sleep()
	ft232r.close()
	logger.printSummary(settings)
