import time
import sys
import json
from Adafruit_BNO055 import BNO055

# pendulum axis defined:
# looking down on top of the pendulum, the support holes at the top of the 
# pendulum come out left and right:
#
# axis:
# x - from left to right
# y - up/down 
# z - rotate (about y)
#
# angles:
# heading - rotation about z
# roll    - rotation about x
# pitch   - rotation about y

BNO_AXIS_REMAP = { 
    'x': BNO055.AXIS_REMAP_X,
    'y': BNO055.AXIS_REMAP_Z,
    'z': BNO055.AXIS_REMAP_Y,
    'x_sign': BNO055.AXIS_REMAP_POSITIVE,
    'y_sign': BNO055.AXIS_REMAP_POSITIVE,
    'z_sign': BNO055.AXIS_REMAP_NEGATIVE 
}

CALIBRATION_THRESHOLD = .5 # degrees
CALIBRATION_DURATION  = 3 

class Calibration(object):

    def __init__(self, pendulum):
        self.pend = pend
        self.cal = []

    @property
    def calibration(self):
        return self.cal

    def calibrate(self):

        # read and ignore a couple of readings.
        try:
            self.pend.sensor.read_euler()
            self.pend.sensor.read_euler()
        except RuntimeError:
            pass

        print "\nstarting calibration. hold the pendulim still for fuck sake!"
        while True:
            last_value = self.pend.sensor.read_euler()
            values = [0.0, 0.0, 0.0];
            count = 0
            start_t = time.time()
            tilt = False
            while time.time() < start_t + CALIBRATION_DURATION:
                value = self.pend.sensor.read_euler()
                if len(last_value) and (abs(last_value[0] - value[0]) > CALIBRATION_THRESHOLD or \
                    abs(last_value[1] - value[1]) > CALIBRATION_THRESHOLD or \
                    abs(last_value[2] - value[2]) > CALIBRATION_THRESHOLD):
                    tilt = True
                    break

                last_value = value
                count += 1
                for i in range(3):
                    values[i] += value[i]

                sys.stdout.write("%5d\b\b\b\b\b" % count)
                sys.stdout.flush()

            if not tilt:
                break
           
        self.cal = []
        for i in range(3):
            self.cal.append(values[i] / count)

        print

    def save(self):
        if not self.cal:
            return

        with open(".calibration", "w") as f:
            f.write(json.dumps(self.cal))

    def load(self):
        try:
            with open(".calibration", "r") as f:
                c = f.read()
                self.cal= json.loads(c)
        except IOError:
            return False
            
        return True

MAX_SENSOR_BEGIN_COUNT = 3
MAX_SENSOR_ERROR_COUNT = 3
class Pendulum(object):

    def __init__(self):
        self.bno = None

    @property
    def sensor(self):
        return self.bno

    @property
    def status(self):
        if not self.bno:
            return None

        return self.bno.get_system_status()

    def open(self, serial_port='/dev/ttyAMA0', rst=18):
        self.bno = BNO055.BNO055(serial_port=serial_port, rst=rst)

        count = 0
        while True:
            try:
                if not self.bno.begin():
                    count += 1
                    print "Sensor begin failed."
                    continue
                break
            except RuntimeError as e:
                count += 1
                if count == MAX_SENSOR_BEGIN_COUNT:
                    print "Cannot start sensor: " + str(e)
                    return False

        count = 0
        status = -1
        while True:
            try:
                self.bno.set_axis_remap(**BNO_AXIS_REMAP)
                status, self_test, error = self.bno.get_system_status()
                if self_test != 0x0F:
                    print('Self test result (0x0F is normal): 0x{0:02X}'.format(self_test))
                    count += 1
                    continue

                break

            except RuntimeError as e:
                count += 1
                if count == MAX_SENSOR_ERROR_COUNT:
                    print "Got error reading status, retrying: %s" % str(e)
                    continue

                break

        if status == 0x01:
            return False

        return True

    def close(self):
        self.bno.close()
        self.bno = None


pend = Pendulum()
if not pend.open():
    status, self_test, error = pend.status
    print('System error: {0}'.format(error))
    print('See datasheet section 4.3.59 for the meaning.')
    sys.exit(-1)

cal = Calibration(Pendulum)
if not cal.load():
    print "Could not load calibration data. Forcing calibration."
    cal.calibrate()
    cal.save()

index = 0
start = time.time()
last_value = pend.sensor.read_euler()
last_crossing = 0
print "t,x,y"
while True:

    # read value and normalize according to calibration
    value = list(pend.sensor.read_euler())
    for i in range(3):
        value[i] = cal.calibration[i] - value[i]

    if last_value[1] >= 0 and value[1] < 0.0:
        if last_crossing:
            print "falling zero crossing: %.2f (%.2f)" % (time.time() - start, time.time() - last_crossing)
        else:
            print "falling zero crossing: %.2f" % (time.time() - start)
        last_crossing = time.time()
        print "%d,%.3f,%.3f" % (index, value[1] - cal.calibration[1], value[2] - cal.calibration[2])
        index += 1

    last_value = value

