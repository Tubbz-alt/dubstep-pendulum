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
        self.sources = []

    def create_source(self, mp3):
        index = len(self.sources)
        filesrc = Gst.ElementFactory.make("multifilesrc", "filesrc%d" % index)
        decode = Gst.ElementFactory.make("decodebin", "decode%d" % index)
        convert = Gst.ElementFactory.make("audioconvert", "convert%d" % index)
        resample = Gst.ElementFactory.make("audioresample", "resample%d" % index)

        if not filesrc:
            print "failed to create filesrc"
            return False
        if not decode:
            print "failed to create decoder"
            return False
        if not convert:
            print "failed to create convert"
            return False
        if not resample:
            print "failed to create resample"
            return False

        filesrc.set_property("location", mp3)
        filesrc.set_property("loop", "true")

        self.pipeline.add(filesrc)
        self.pipeline.add(decode)
        decode.connect("pad-added", self.decode_src_created) 
        self.pipeline.add(convert)
        self.pipeline.add(resample)

        filesrc.link(decode)
        convert.link(resample)

        self.sources.append(dict(filesrc=filesrc, decode=decode, convert=convert, resample = resample))

        return True

    def decode_src_created(self, element, pad):
        index = int(element.get_name()[-1:])
        pad.link(self.sources[index]['convert'].get_static_pad("sink"))
        
    def setup(self, sources):

        self.mainloop = GObject.MainLoop()
        self.pipeline = Gst.Pipeline.new("pipeline")

        for source in sources:
            self.create_source(source['mp3'])

        self.mixer = Gst.ElementFactory.make("audiomixer", "mixer")
        self.sink = Gst.ElementFactory.make("alsasink", "sink")

        if not self.mixer or not self.sink:
            print "failed to create something"
            return False

        self.pipeline.add(self.mixer)
        self.pipeline.add(self.sink)

        for source in self.sources:
            source['resample'].link(self.mixer)

        self.mixer.link(self.sink)
        
        return True


    def start(self):
        self.pipeline.set_state(Gst.State.PLAYING)
        return self.loop()

    def set_volumes(self, volumes):
        assert(len(volumes) == len(self.sources))

        for i, volume in enumerate(volumes):
            mixer_pad = self.mixer.get_static_pad("sink_%d" % i)
            mixer_pad.set_property("volume", min(volumes[i] * 10.0, 10.0))

    def loop(self):
        bus = self.pipeline.get_bus()
        msg = bus.timed_pop_filtered(10000,Gst.MessageType.ERROR | Gst.MessageType.EOS)
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
