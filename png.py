#!/usr/bin/env python

import sys
import json
import requests
import os
import subprocess
import signal
import re
import math
import time
import threading
from getch import getch

CACHE_FILE_NAME = "cache.txt"
GENY_MOTION_SHELL = "/Applications/Genymotion Shell.app/Contents/MacOS/genyshell"
FREE_GEO_IP_URL = "http://freegeoip.net/json"
MOVE_STEP = 0.000015
INIT_ANGLE = 90
ROTATE_STEP = 5
MIN_UPDATE_INTERVAL = 100
SHOW_GENY_MOTION_SHELL_STD_OUT = False

class Location:
    
    def __init__(self, latitude, longitude):
        latitude = min(max(latitude, -89.9), 89.9)
        longitude = min(max(longitude, -179.9), 179.9)
        self.latitude = latitude
        self.longitude = longitude

    def __eq__(self, location):
        return self.latitude == location.latitude and self.longitude == location.longitude
    
    def __str__(self):
        return "Latitude: " + str(self.latitude) + ", Longitude: " + str(self.longitude)


class GenyMotion:

    def __init__(self, geny_motion_shell_location, cache_file_path=None, show_stdout=False):
        self.shell = subprocess.Popen(geny_motion_shell_location, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        self.cache_file_path = cache_file_path
        self.show_stdout = show_stdout
        # wait until geny motion shell connects a device or fails
        res = self.__wait_until_match__(r".*(?:No Genymotion virtual device running found)|(?:Genymotion virtual device selected).*")
        if re.match(r".*(?:No Genymotion virtual device running found).*", res):
            self.terminate()
            raise Exception("No Genymotion virtual device running found")

    def terminate(self):
        self.shell.terminate()

    def set_location(self, location):
        self.__run_command__("gps setlatitude " + str(location.latitude) + "\n")
        self.__run_command__("gps setlongitude " + str(location.longitude) + "\n")
        if self.cache_file_path:
            with open(self.cache_file_path, 'w') as f:
                f.write(str(location.latitude) + " " + str(location.longitude))
        self.__wait_until_match__(r".*GPS Latitude set to.*")
        self.__wait_until_match__(r".*GPS Longitude set to.*")
  
    def __run_command__(self, cmd):
        self.shell.stdin.write(cmd)
        self.shell.stdin.flush()

    def __wait_until_match__(self, regex):
        line = self.shell.stdout.readline()
        if self.show_stdout:
            print line
        while re.match(regex, line) == None:
            line = self.shell.stdout.readline()
            if self.show_stdout:
                print line
        return line
   

# Get initial location
if len(sys.argv) > 1:
    option = sys.argv[1]
    if option == "-p":
        location = Location(float(sys.argv[2]), float(sys.argv[3]))
    elif option == "-r":
        if not os.path.isfile("./" + CACHE_FILE_NAME):
            print "Cannot find file \"" + CACHE_FILE_NAME + "\""
            exit(1)
        with open(CACHE_FILE_NAME) as f:
            line = f.read()
        point = line.split()
        location = Location(float(point[0]), float(point[1]))
    else:
        print "Unrecognized option:", option
        exit(1)
else:
    print "Use current location ..."
    resp = requests.get(FREE_GEO_IP_URL).json()
    location = Location(resp['latitude'], resp['longitude'])

angle = INIT_ANGLE
print "Initial location: "
print location
print "Initial angle: "
print angle


# register signal handlers, make sure resources are released when terminate
geny_motion = None
gps_thread = None
exit_gps_thread = False

def terminate(exit_code=0):
    global exit_gps_thread
    if geny_motion:
        geny_motion.terminate()
    if gps_thread:
        exit_gps_thread = True
        gps_thread.join()
    exit(exit_code)


signal.signal(signal.SIGTERM, lambda x, y: terminate())
signal.signal(signal.SIGINT, lambda x, y: terminate())
signal.signal(signal.SIGTSTP, lambda x, y: terminate())



# Start geny motion shell
print "Starting geny motion shell from " + GENY_MOTION_SHELL + ", cache file is \"" + CACHE_FILE_NAME + "\"."
try:
    geny_motion = GenyMotion(GENY_MOTION_SHELL, CACHE_FILE_NAME, SHOW_GENY_MOTION_SHELL_STD_OUT)
except Exception as e:
    print "Unable to open geny motion shell because:", e.message
    exit()


# set initial location
print "Set initial location..."
geny_motion.set_location(location)


# start gps thread
print "Starting gps updating thread.."
def update_gps_thread_run():
    prev_location = location
    while not exit_gps_thread:
        time.sleep(MIN_UPDATE_INTERVAL/1000.0) 
        cur_location = location
        if cur_location == prev_location:
            continue
        prev_location = cur_location
        geny_motion.set_location(cur_location)
        
gps_thread = threading.Thread(target = update_gps_thread_run)
gps_thread.start()


# define keyboard operations:
KEY_UP = 1
KEY_DOWN = 2
KEY_LEFT = 3
KEY_RIGHT = 4
KEY_SMALLER = 5
KEY_LARGER = 6
KEY_EXIT = 7
KEY_OTHER = 8

def read_key_board():
    key = ord(getch())
    if key == 27:
        key = ord(getch())
        if key == 27:
            return KEY_EXIT
        elif key == 91:
            key = ord(getch())
            key_code_map = {
                65: KEY_UP,
                66: KEY_DOWN,
                67: KEY_RIGHT,
                68: KEY_LEFT
            }
            res = key_code_map[key]
            if res != None:
                return res
    else:
        key_code_map = {
            119: KEY_UP,
            97: KEY_LEFT,
            115: KEY_DOWN,
            100: KEY_RIGHT,
            44: KEY_SMALLER,
            46: KEY_LARGER
        }
        res = key_code_map[key]
        if res != None:
            return res
    return KEY_OTHER

def move(move_step):
    global location
    cur_location = location
    longitude = cur_location.longitude + move_step * math.cos(angle*math.pi/180)
    latitude = cur_location.latitude + move_step * math.sin(angle*math.pi/180) 
    location = Location(latitude, longitude)
    print "Set location to", location
    print "Current angle is", angle

def turn(degree):
    global angle
    angle = (angle + degree + 360) % 360 
    print "Current angle is ", angle



def on_key_up():
    move(MOVE_STEP)

def on_key_down():
    move(-MOVE_STEP)

def on_key_left():
    turn(ROTATE_STEP)

def on_key_right(): 
    turn(-ROTATE_STEP)

def on_key_smaller():
    turn(90)

def on_key_larger():
    turn(-90)

def on_key_exit():
    print "Pokemon Not Go is terminating..."
    terminate()

def on_key_other():
    pass

key_handler_map = {
    KEY_UP: on_key_up,
    KEY_DOWN: on_key_down,
    KEY_LEFT: on_key_left,
    KEY_RIGHT: on_key_right,
    KEY_SMALLER: on_key_smaller,
    KEY_LARGER: on_key_larger,
    KEY_EXIT: on_key_exit,
    KEY_OTHER: on_key_other
}

# listen to keyboard
print "Ready to use."
while True:
    key = read_key_board()
    key_handler_map[key]()

