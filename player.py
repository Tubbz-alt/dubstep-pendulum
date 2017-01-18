import gi
from math import sin, pi, cos
gi.require_version('Gst', '1.0')
from gi.repository import GObject, Gst

# Initializing threads used by the Gst various elements
GObject.threads_init()
#Initializes the GStreamer library, setting up internal path lists, registering built-in elements, and loading standard plugins.
Gst.init(None)

class WhatTheHellIsThisNoize(object):

    def __init__(self):
        self.done = False
        self.mainloop = None
        self.pipeline = None

    def setup(self):

        self.mainloop = GObject.MainLoop()
        self.pipeline = Gst.Pipeline.new("pipeline")

        self.filesrc0 = Gst.ElementFactory.make("filesrc", "filesrc0")
        self.decode0 = Gst.ElementFactory.make("decodebin", "decode0")
        self.convert0 = Gst.ElementFactory.make("audioconvert", "convert0")
        self.resample0 = Gst.ElementFactory.make("audioresample", "resample0")
        self.mixer = Gst.ElementFactory.make("audiomixer", "mixer")
        self.sink = Gst.ElementFactory.make("alsasink", "sink")

        if not self.mixer or not self.filesrc0 or not self.decode0:
            print "failed to create something"
            return False

        self.filesrc0.set_property("location", "dubstep-track-1.mp3")
        self.pipeline.add(self.filesrc0)
        self.pipeline.add(self.decode0)
        self.decode0.connect("pad-added", self.decode_src_created) 
        self.pipeline.add(self.convert0)
        self.pipeline.add(self.resample0)
        self.pipeline.add(self.mixer)
        self.pipeline.add(self.sink)

        self.filesrc0.link(self.decode0)
        self.convert0.link(self.resample0)
        self.resample0.link(self.mixer)
        self.mixer.link(self.sink)
        
        self.filesrc1 = Gst.ElementFactory.make("filesrc", "filesrc1")
        self.decode1 = Gst.ElementFactory.make("decodebin", "decode1")
        self.convert1 = Gst.ElementFactory.make("audioconvert", "convert1")
        self.resample1 = Gst.ElementFactory.make("audioresample", "resample1")

        self.filesrc1.set_property("location", "dubstep-track-2.mp3")
        self.pipeline.add(self.filesrc1)
        self.pipeline.add(self.decode1)
        self.decode1.connect("pad-added", self.decode_src_created) 
        self.pipeline.add(self.convert1)
        self.pipeline.add(self.resample1)

        self.filesrc1.link(self.decode1)
        self.convert1.link(self.resample1)
        self.resample1.link(self.mixer)

        return True


    def decode_src_created(self, element, pad):
        index = element.get_name()[-1:]
        if index == '0':
            pad.link(self.convert0.get_static_pad("sink"))
        else:
            pad.link(self.convert1.get_static_pad("sink"))
        
    def start(self):
        self.pipeline.set_state(Gst.State.PLAYING)
        return self.loop()

    def set_volumes(self, volumes):

        assert(len(volumes) == 2)

        mixer_pad0 = self.mixer.get_static_pad("sink_0")
        mixer_pad1 = self.mixer.get_static_pad("sink_1")
        mixer_pad0.set_property("volume", volumes[0] * 10.0)
        mixer_pad1.set_property("volume", volumes[1] * 10.0)

    def loop(self):
        bus = self.pipeline.get_bus()
        msg = bus.timed_pop_filtered(10000000,Gst.MessageType.ERROR | Gst.MessageType.EOS)
        if not msg:
            return True
            
        if msg.type == Gst.MessageType.EOS:
            self.done = True
            return True

        if msg.type == Gst.MessageType.ERROR:
            Gst.debug_bin_to_dot_file(self.pipeline, Gst.DebugGraphDetails.ALL, "pipeline")
            err, debug = msg.parse_error()
            print "Got error ", err, debug
            return False


if __name__ == "__main__":
    noize = WhatTheHellIsThisNoize()
    noize.start()
    while not noise.done():
        sleep(.1)
