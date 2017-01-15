import gi
gi.require_version('Gst', '1.0')
from gi.repository import GObject, Gst

# Initializing threads used by the Gst various elements
GObject.threads_init()
#Initializes the GStreamer library, setting up internal path lists, registering built-in elements, and loading standard plugins.
Gst.init(None)

class Main:
    def __init__(self):
        self.mainloop = GObject.MainLoop()
        self.pipeline = Gst.Pipeline.new("pipeline")

        self.filesrc0 = Gst.ElementFactory.make("filesrc", "filesrc0")
        self.filesrc0.set_property("location", "test-1.mp3")
        self.pipeline.add(self.filesrc0)

        
        self.decode = Gst.ElementFactory.make("decodebin", "decode")
        self.pipeline.add(self.decode)
        #connecting the decoder's "pad-added" event to a handler: the decoder doesn't yet have an output pad (a source), it's created at runtime when the decoders starts receiving some data
        self.decode.connect("pad-added", self.decode_src_created) 
        
        self.sink = Gst.ElementFactory.make("alsasink", "sink")
        self.pipeline.add(self.sink)

        self.filesrc0.link(self.decode)
            
#        self.filesrc1 = Gst.ElementFactory.make("filesrc", "filesrc1")
#        self.filesrc1.set_property("location", "test-2.mp3")
#        self.pipeline.add(self.filesrc1)

    #handler taking care of linking the decoder's newly created source pad to the sink
    def decode_src_created(self, element, pad):
        pad.link(self.sink.get_static_pad("sink"))
        
    #running the shit
    def run(self):
        self.pipeline.set_state(Gst.State.PLAYING)
        self.mainloop.run()

start=Main()
start.run()
