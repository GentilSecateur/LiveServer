"""Bridges Midi from Voicelive to OSC RASPI, and to Local midi PC sampler. bridges notes from Raspi/LH to sampler"""

import logging
import sys
import time

import rtmidi
from rtmidi.midiutil import open_midiinput


from pythonosc import udp_client
from pythonosc import osc_server
from pythonosc import dispatcher


import os
import socket 

from threading import Timer

#==========================================================
# Constant definitions
hostname = socket.gethostname()
LOCALHOST_IP   = socket.gethostbyname(hostname)


LIVESERVER_PORT     = 8000
LH_PORT = 8010

INPUT_PORT  = 'Springbeats vMIDI2'
OUTPUT_PORT = 'Springbeats vMIDI4'

DEBOUNCE_PRESET_DELAY = 3.0

#==========================================================


class MidiInputHandler(object):
    def __init__(self, port):
        self.port = port
        self._wallclock = time.time()
        self.scheduled_timer = None


    def debounced_func(self, wait, func, *args, **kwargs):
            
        if self.scheduled_timer and not self.scheduled_timer.finished.is_set():
            print("cancelling Timer")
            self.scheduled_timer.cancel()
            
        self.scheduled_timer = Timer(wait, func, args=args, kwargs=kwargs)
        self.scheduled_timer.start()

    def debounce(self, wait, func, *args, **kwargs):
        """Returns a debounced version of a function.

        The debounced function delays invoking `func` until after `wait`
        seconds have elapsed since the last time the debounced function
        was invoked.
        """
        print("Debouncing")  
        return self.debounced_func(wait, func, *args)


    def forwardProgramChange(self, value):
        print("Forwarding Program change : " + str(value))
        client.send_message("/midi/voicelive", [0xC0, value, 0])
        
        if(value == 1): #We don't receive the preset 1(index 0...), so let's use the number 2(index 1).
            #shutdown
            print("Shuting down immediately")
            client.send_message("/midi/shutdown", 1)
            cmd = "Shutdown -s -f -t 0"
            os.system(cmd)
              
    def __call__(self, event, data=None):
        message, deltatime = event
        self._wallclock += deltatime
        print("[%s] @%0.6f %r" % (self.port, self._wallclock, message))
        #Forward program changes received from Voicelive
        if(message[0] == 0xC0):
           #send program change thru OSC
           programVal = message[1]
           self.debounce(DEBOUNCE_PRESET_DELAY, self.forwardProgramChange, programVal)

        else:
           #Forward Control change received from Voicelive
           #print("Forwarding Control change" + str(message[1]))
           client.send_message("/midi/voicelive", [message[0], message[1], message[2]])
       

#Receives note on and off coming from LaserHarp
def print_laserharp_handler(osc_address, args, velocity):
  print("received OSC message from laser harp")
  print("address" + osc_address)
  print(velocity)

  temp = osc_address.split("/")
  note = int(temp[4])
  print (note);
  if(velocity != 0):
    note = [0x90, note, velocity]    # Note ON
  else:
    note = [0x80, note, 0]           #note OFF
  midiout.send_message(note)

#==========================================================
#Main code


#Open output port
midiout = rtmidi.MidiOut()
ports = midiout.get_ports()
for port, name in enumerate(ports):
    print("[%i] #%s#" % (port, name))
    if(OUTPUT_PORT in name):
       print("Opening output port [%i] #%s#" % (port, name))
       midiout.open_port(port)

log = logging.getLogger('midiin_callback')
logging.basicConfig(level=logging.DEBUG)

#Open input port
midiin = rtmidi.MidiIn()
ports = midiin.get_ports()
for port, name in enumerate(ports):
    print("[%i] #%s#" % (port, name))
    if(INPUT_PORT in name):
       print("Opening input port [%i] #%s#" % (port, name))
       midiin.open_port(port)
       port_name = name


client = udp_client.SimpleUDPClient(LOCALHOST_IP, LIVESERVER_PORT)

dispatcher = dispatcher.Dispatcher()
dispatcher.map("/vkb_midi/0/*", print_laserharp_handler, "midi_laserharp")

server = osc_server.ThreadingOSCUDPServer(
    (LOCALHOST_IP, LH_PORT), dispatcher)

print("Attaching MIDI input callback handler.")
midiin.set_callback(MidiInputHandler(port_name))

try:
    print("Entering main loop. Press Control-C to exit.")
    server.serve_forever()
except KeyboardInterrupt:

    exit()

