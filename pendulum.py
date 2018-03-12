#!/usr/bin/env python

import time
import sys
import json
from math import cos, sin, pi, radians, sqrt, pow, degrees
from Adafruit_BNO055 import BNO055
from player import WhatTheHellIsThisNoize
import numpy as np
from pykalman import KalmanFilter

def unit_vector(vector):
    """ Returns the unit vector of the vector.  """
    return vector / np.linalg.norm(vector)

def angle_between(v1, v2):
    v1_u = unit_vector(v1)
    v2_u = unit_vector(v2)
    return np.arccos(np.clip(np.dot(v1_u, v2_u), -1.0, 1.0))

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

CALIBRATION_THRESHOLD = .5 # degrees
CALIBRATION_DURATION  = 3 
LENGTH_CALC_PASSES = 7

class Calibration(object):

    def __init__(self, pendulum):
        self.pend = pend
        self.pend_length = 0.0
        self.cal = []

    @property
    def calibration(self):
        return self.cal

    @property
    def length(self):
        return self.pend_length

    def calibrate(self):

        # read and ignore a couple of readings.
        try:
            self.pend.sensor.read_euler()
            self.pend.sensor.read_euler()
        except RuntimeError:
            pass

        print "\nstarting calibration. hold the pendulim still for fuck sake!"
        while True:
            try:
                last_value = self.pend.sensor.read_euler()
            except RuntimeError as e:
                continue

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

    def calculate_length(self):

        print "Calculate length"
        index = 0
        start = time.time()
        last_value = pend.sensor.read_euler()
        last_crossing = 0
        durations = []
        while len(durations) < LENGTH_CALC_PASSES:
            value = list(pend.sensor.read_euler())
            for i in range(3):
                value[i] = self.calibration[i] - value[i]

            if last_value[1] >= 0 and value[1] < 0.0:
                if last_crossing and time.time() - last_crossing > .1:
                    durations.append(time.time() - last_crossing)
                    print "falling zero crossing: %.2f (%.2f)" % (time.time() - start, time.time() - last_crossing)
                else:
                    print "falling zero crossing: %.2f" % (time.time() - start)
                last_crossing = time.time()
                index += 1
            last_value = value

        print "done"

        durations = durations[2:]
        plen = 0.0
        for l in durations:
            plen += l 

        t = plen / len(durations)
        self.pend_length = t * t / 4.0

    def save(self):
        if not self.cal:
            return

        with open(".calibration", "w") as f:
            f.write(json.dumps({ 'calibration' : self.cal, 'length' : self.length }))

    def load(self):
        try:
            with open(".calibration", "r") as f:
                c = f.read()
                data = json.loads(c)
                self.cal = data['calibration']
                self.pend_length = data['length']
        except IOError:
            return False
            
        return True

MAX_SENSOR_BEGIN_COUNT = 3
MAX_SENSOR_ERROR_COUNT = 3
class Pendulum(object):

    WINDOW_SIZE = 100 

    STATE_START   = 0
    STATE_IDLE    = 1
    STATE_PULL_UP = 2
    STATE_DROP    = 3
    STATE_WOBBLE  = 4

    EVENT_IDLE    = 0
    EVENT_PULL_UP = 1
    EVENT_DROP    = 2
    EVENT_WOBBLE  = 3

    gravity = (0.0, 0.0, -9.81)

    table = (
        (STATE_START,    EVENT_IDLE,    STATE_IDLE),
        (STATE_IDLE,     EVENT_PULL_UP, STATE_PULL_UP),
        (STATE_PULL_UP,  EVENT_DROP,    STATE_DROP),
        (STATE_PULL_UP,  EVENT_IDLE,    STATE_IDLE),
        (STATE_DROP,     EVENT_WOBBLE,  STATE_WOBBLE),
        (STATE_WOBBLE,   EVENT_IDLE,    STATE_IDLE),
        (STATE_WOBBLE,   EVENT_PULL_UP, STATE_PULL_UP),
    )

    def __init__(self):
        self.bno = None
        self.cur_state = self.STATE_START
        self.window = []
        self.last_angle = None

        self.kf = KalmanFilter(initial_state_mean=0, n_dim_obs=1)
        self.point = None
        self.covariance = [ [0.0], [0.0], [0.0] ]

    @property
    def sensor(self):
        return self.bno

    @property
    def status(self):
        if not self.bno:
            return None

        return self.bno.get_system_status()

    def open(self, serial_port='/dev/serial0', rst=18):
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

        print "Sensor setup complete."

        return True

    def is_idle(self):
        MIN_ANGLE_FOR_IDLE = 5
        IDLE_SAMPLES = 50
        if len(self.window) < IDLE_SAMPLES:
            return False

        for value in self.window[-IDLE_SAMPLES:]:
            #print "i %.3f %.3f" % (value[1], value[2])
            if abs(value[1]) > MIN_ANGLE_FOR_IDLE or abs(value[2]) > MIN_ANGLE_FOR_IDLE:
                return False

        return True

    def is_pull_up(self):
        MAX_CHANGE_PER_SAMPLE = .2
        MIN_ANGLE_FOR_PULL_UP = 5
        PULL_UP_SAMPLES = 50
        if len(self.window) < PULL_UP_SAMPLES:
            return False

        samples = self.window[-PULL_UP_SAMPLES:]
        for i, value in enumerate(samples):
            #print "%.3f %.3f" % (value[1], value[2])
            if not i:
                continue

            if abs(value[1]) < MIN_ANGLE_FOR_PULL_UP and abs(value[2]) < MIN_ANGLE_FOR_PULL_UP:
                return False

            if abs(value[1] - samples[i-1][1]) > MAX_CHANGE_PER_SAMPLE or abs(value[2] - samples[i-1][2]) > MAX_CHANGE_PER_SAMPLE:
                return False

        return True

    def is_drop(self):

        return False

        MAX_CHANGE_PER_SAMPLE = .2
        MIN_ANGLE_FOR_PULL_UP = 5
        PULL_UP_SAMPLES = 50
        if len(self.window) < PULL_UP_SAMPLES:
            return False

        samples = self.window[-PULL_UP_SAMPLES:]
        for i, value in enumerate(samples):
            print "%.3f %.3f" % (value[1], value[2])
            if not i:
                continue

            if abs(value[1]) < MIN_ANGLE_FOR_PULL_UP and abs(value[2]) < MIN_ANGLE_FOR_PULL_UP:
                return False

            if abs(value[1] - samples[i-1][1]) > MAX_CHANGE_PER_SAMPLE or abs(value[2] - samples[i-1][2]) > MAX_CHANGE_PER_SAMPLE:
                return False

        return True
 
    def loop(self):
        # read value and normalize according to calibration
        value = list(pend.sensor.read_accelerometer())
        t = time.time()

        (self.point[0], self.covariance[0]) = self.kf.filter_update(self.point[0], self.covariance[0], value[0])
        (self.point[1], self.covariance[1]) = self.kf.filter_update(self.point[1], self.covariance[1], value[1])
        (self.point[2], self.covariance[2]) = self.kf.filter_update(self.point[2], self.covariance[2], value[2])

        angle = degrees(angle_between(self.point, self.gravity))

        if len(self.window) == self.WINDOW_SIZE:
            self.window = self.window[1:]
        self.window.append((angle,t))

        time_diff = self.window[len(self.window) - 1][1] - self.window[0][1]
        if time_diff:
            self.a_accel = (self.window[0][0] - self.window[len(self.window) - 1][0]) / time_diff
        else:
            self.a_accel = 0.0

        self.angle = angle

#        print "%f,%f,%f" % (t, angle, self.a_accel)


    def state_start(self):
        print "STATE start. waiting for idle."
        while not self.is_idle():
            self.loop()

        return self.EVENT_IDLE

    def state_idle(self):
        print "STATE idle. waiting for pull-up."
        while not self.is_pull_up():
            self.loop()

        return self.EVENT_PULL_UP

    def state_pull_up(self):
        print "STATE pull up. waiting for drop or idle."
        while True:
            if self.is_drop():
                return self.EVENT_DROP
            if self.is_idle():
                return self.EVENT_IDLE
            self.loop()

    def state_drop(self):
        print "state drop, not implemented"
        sys.exit(-1)

    def state_wobble(self):
        print "state wobble, not implemented"
        sys.exit(-1)

    def run(self):
        next_event = self.state_start()
        while True:
            done = False
            for from_state, event, next_state in self.table:
                if from_state == self.cur_state and next_event == event:
                    print "Cur: %d Event: %d Next: %d" % (self.cur_state, event, next_state)
                    if next_state == self.STATE_IDLE:
                        self.cur_state = self.STATE_IDLE
                        next_event = self.state_idle()
                        done = True
                    elif next_state == self.STATE_PULL_UP:
                        self.cur_state = self.STATE_PULL_UP
                        next_event = self.state_pull_up()
                        done = True
                    elif next_state == self.STATE_DROP:
                        self.cur_state = self.STATE_DROP
                        next_event = self.state_drop()
                        done = True
                    elif next_state == self.STATE_WOBBLE:
                        self.cur_state = self.STATE_WOBBLE
                        next_event = self.state_wobble()
                        done = True
                    else:
                        print "oops. Unknown event %d from state %d" % (next_event, self.cur_state)

                    break

            if not done:
                print "Unknown event %d from state %d" % (next_event, self.cur_state)
                return

    def close(self):
        self.bno.close()
        self.bno = None

sound_sources = [ 
    dict(x = 20, y = 20, r = 10.0, mp3="music/dubstep-bass-1.mp3"),
    dict(x = -20, y = 20, r = 10.0, mp3="dubstep-track-2.mp3"),
    dict(x = -20, y = -20, r = 10.0, mp3="music/dubstep-bass-2.mp3"),
#    dict(x = 20, y = -20, r = 10.0, mp3="dubstep-track-4.mp3"),
]

if len(sys.argv) > 1:
    for i, arg in enumerate(sys.argv):
        if not i:
            continue
        if i >= len(sound_sources):
            break

        sound_sources[i - 1]['mp3'] = sys.argv[i]
        

#print "Create noize pipeline"
#noize = WhatTheHellIsThisNoize()
#if not noize.setup(sound_sources):
#    print "Cannot create noise making setup."
#    sys.exit(-1)

#print "Create pendulum object"
pend = Pendulum()
if not pend.open():
    status, self_test, error = pend.status
    print('System error: {0}'.format(error))
    print('See datasheet section 4.3.59 for the meaning.')
    sys.exit(-1)

print "load calibration"
cal = Calibration(Pendulum)
if not cal.load():
    print "Could not load calibration data. Forcing calibration."
    cal.calibrate()
    cal.calculate_length()
    cal.save()

print "pendulum length: %.2fm" % cal.length
#if not noize.start():
#    print "Could not start noize pipeline."
#    sys.exit(-1)

index = 0
start = time.time()

while True:
    try:
        last_value = pend.sensor.read_accelerometer()
        break
    except RuntimeError as e:
        pass

print "t,a,acc"
pend.run()
sys.exit(0)

