"""
Random Instructions, by Adrian Velicu
"""

from XPLMDefs import *
from XPLMProcessing import *
from XPLMDataAccess import *
from XPLMUtilities import *
from XPLMMenus import *

import datetime
import time
import os
import random
from collections import OrderedDict

CHECK_INTERVAL_SECS = 1
GEN_TIME_INTERVAL = (20, 70)

# (probability of a change, lower bound for change, upper bound for change, precision (given value will be divisible by this), minimum value, maximum value)
GEN_HDG = (.4, -181, 181, 10, None, None)
GEN_ALT = (.3, -2001, 2001, 500, 5000, 13000)
GEN_IAS = (.1, -21, 21, 10, 100, 140)


# returns value rounded to the nearest multiple of precision.
# Example: (132, 100) -> 100; (132, 10) -> 130
def deprecisify(value, precision):
	return int(precision * round(float(value) / precision))

class PythonInterface:
	def XPluginStart(self):
		self.IsOperating = False
		self.InitDatarefs()
		self.MenuSetup()
		return (
			"Random Instructions",
			"Adi.RandomInstructions",
			"Gives random instructions for attitude instrument flying practice.")

	def XPluginStop(self):
		self.MenuDestroy()
		self.StopOperating()

	def XPluginEnable(self):
		return 1

	def XPluginDisable(self):
		pass
	
	def XPluginReceiveMessage(self, inFromWho, inMessage, inParam):
		pass
	
	def MenuSetup(self):
		idx = XPLMAppendMenuItem(XPLMFindPluginsMenu(), "Random Instructions", 0, 0)
		self.ourMenuHandlerCb = self.MenuHandlerCB
		self.ourMenu = XPLMCreateMenu(self, "Random Instructions", XPLMFindPluginsMenu(), idx, self.ourMenuHandlerCb, 0)
		XPLMAppendMenuItem(self.ourMenu, "Start giving random instructions", 0, 1)
		XPLMAppendMenuItem(self.ourMenu, "Stop giving random instructions", 1, 1)
	
	def MenuDestroy(self):
		XPLMDestroyMenu(self.ourMenu)
	
	def MenuHandlerCB(self, inMenuRef, inItemRef):
		if inItemRef == 0:
			self.StartOperating()
		elif inItemRef == 1:
			self.StopOperating()

	def InitDatarefs(self):
		self.elapsed_time_dataref = XPLMFindDataRef("sim/time/total_flight_time_sec")
		self.ias_dataref = XPLMFindDataRef("sim/flightmodel/position/indicated_airspeed2")
		self.gps_alt_dataref = XPLMFindDataRef("sim/flightmodel/position/elevation")
		self.hdg_dataref = XPLMFindDataRef("sim/flightmodel/position/mag_psi")

	def StartOperating(self):
		if self.IsOperating:
			return
		
		self.IsOperating = True
		self.NextInstructionTime = None
		self.FLCB = self.FlightLoopCallback
		XPLMSpeakString("Random Instructions: starting")
		XPLMRegisterFlightLoopCallback(self, self.FLCB, CHECK_INTERVAL_SECS, 0)
		
	def StopOperating(self):
		if not self.IsOperating:
			return
		
		XPLMUnregisterFlightLoopCallback(self, self.FLCB, 0)
		XPLMSpeakString("Random Instructions: stopping")

	def WriteMetadata(self):
		self.OutputFile.write("Metadata,CA_CSV.3\n")
		self.OutputFile.write("GMT,%s\n" % int(time.time()))
		self.OutputFile.write("TAIL,X56433\n") # todo: ui to set tail number
		self.OutputFile.write("GPS,XPlane\n")
		self.OutputFile.write("ISSIM,1\n")
		self.OutputFile.write("DATA,\n")
		self.OutputFile.write("%s\n" % ",".join([column_name for (column_name, (_, _)) in DATAREF_MAP.items()]))

	def FlightLoopCallback(self, elapsedMe, elapsedSim, counter, refcon):
		elapsed = XPLMGetDataf(self.elapsed_time_dataref)
		ias = XPLMGetDataf(self.ias_dataref)
		alt = XPLMGetDataf(self.gps_alt_dataref) * 3.2 #dataref is in meters
		hdg = XPLMGetDataf(self.hdg_dataref)
		
		if self.NextInstructionTime is None:
			self.NextInstructionTime = elapsed + random.randrange(GEN_TIME_INTERVAL[0], GEN_TIME_INTERVAL[1])
		
		if elapsed > self.NextInstructionTime:
			self.GenerateInstruction(ias, alt, hdg)
			self.NextInstructionTime = None			
		
		return CHECK_INTERVAL_SECS
	
	def GenerateInstruction(self, ias, alt, hdg):
		instructions = []
		if random.random() > GEN_IAS[0]:
			next_ias = deprecisify(ias + random.randrange(GEN_IAS[1], GEN_IAS[2], GEN_IAS[3]), GEN_IAS[3])
			if GEN_IAS[4] is not None and next_ias < GEN_IAS[4]:
				next_ias = GEN_IAS[4]
			if GEN_IAS[5] is not None and next_ias > GEN_IAS[5]:
				next_ias = GEN_IAS[5]
			
			instructions.append("maintain %s knots" % next_ias)
		
		if random.random() > GEN_ALT[0]:
			next_alt = deprecisify(alt + random.randrange(GEN_ALT[1], GEN_ALT[2], GEN_ALT[3]), GEN_ALT[3])
			if GEN_ALT[4] is not None and next_alt < GEN_ALT[4]:
				next_alt = GEN_ALT[4]
			if GEN_ALT[5] is not None and next_alt > GEN_ALT[5]:
				next_alt = GEN_ALT[5]

			alt_change_verb = "climb and maintain" if next_alt > alt else "descend and maintain" if next_alt < alt else "maintain"
			instructions.append("%s %s" % (alt_change_verb, next_alt))
		
		if random.random() > GEN_HDG[0]:
			hdgdiff = int(random.randrange(GEN_HDG[1], GEN_HDG[2], GEN_HDG[3]))
			next_hdg = deprecisify((hdg + hdgdiff) % 360, GEN_HDG[3])
			if GEN_HDG[4] is not None and next_hdg < GEN_HDG[4]:
				next_hdg = GEN_HDG[4]
			if GEN_HDG[5] is not None and next_hdg > GEN_HDG[5]:
				next_hdg = GEN_HDG[5]

			if hdgdiff < 0:
				instructions.append("turn left heading %s" % next_hdg)
			elif hdgdiff > hdg:
				instructions.append("turn right heading %s" % next_hdg)
			else:
				instructions.append("maintain present heading")
			
		XPLMSpeakString("N56433, %s" % ", ".join(instructions))