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

# Get initial location
if len(sys.argv) > 1:
    option = sys.argv[1]
    if option == "-p":
        latitude = float(sys.argv[2])
        longitude = float(sys.argv[3])
    elif option == "-r":
        if not os.path.isfile("./" + CACHE_FILE_NAME):
            print "Cannot find file \"" + CACHE_FILE_NAME + "\""
            exit(1)
        with open(CACHE_FILE_NAME) as f:
            line = f.read()
        point = line.split()
        latitude = float(point[0])
        longitude = float(point[1])
    else:
        print "Unrecognized option:", option
        exit(1)
else:
    print "Use current location ..."
    resp = requests.get(FREE_GEO_IP_URL)
    resp_json = json.loads(resp.text)
    latitude = resp_json['latitude']
    longitude = resp_json['longitude']

if latitude > 90.0:
    latitude = 90.0
if latitude < -90.0:
    latitude = -90.0
if longitude > 180.0:
    longitude = 180.0
if longitude < -180.0:
    longitude = -180.0

print "Initial location: "
print "Latitude:", latitude, "Longitude:", longitude

angle = INIT_ANGLE

# Run geny motion shell
print "Starting geny motion shell from", GENY_MOTION_SHELL
geny_motion = subprocess.Popen(GENY_MOTION_SHELL, stdin=subprocess.PIPE, stdout=subprocess.PIPE)

lock = threading.Lock()
exit_gps_thread = False
def update_gps_thread_run():
    prev_latitude = latitude
    prev_longitude = longitude
    while not exit_gps_thread:
        time.sleep(MIN_UPDATE_INTERVAL/1000.0) 
        lock.acquire()
        if prev_latitude == latitude and prev_longitude == longitude:
            lock.release()
            continue
        prev_latitude = latitude
        prev_longitude = longitude
        set_location(latitude, longitude)
        lock.release()
        wait_until_match(r".*GPS Latitude set to.*")
        wait_until_match(r".*GPS Longitude set to.*")

gps_thread = threading.Thread(target = update_gps_thread_run)


def terminate(exit_code=0):
    global exit_gps_thread 
    exit_gps_thread = True
    gps_thread.join()
    geny_motion.terminate()
    exit(exit_code)

def run_geny_motion_command(cmd):
    geny_motion.stdin.write(cmd)
    geny_motion.stdin.flush()

def set_location(lat, log):
    run_geny_motion_command("gps setlatitude " + str(latitude) + "\n")
    run_geny_motion_command("gps setlongitude " + str(longitude) + "\n")
    with open(CACHE_FILE_NAME, 'w') as f:
        f.write(str(lat) + " " + str(log))

def wait_until_match(regex):
    line = geny_motion.stdout.readline()
    while re.match(regex, line) == None:
        line = geny_motion.stdout.readline()
    return line

signal.signal(signal.SIGTERM, lambda x, y: terminate())
signal.signal(signal.SIGINT, lambda x, y: terminate())
signal.signal(signal.SIGTSTP, lambda x, y: terminate())

# wait until geny motion shell connects a device or fails
print "Waiting for geny motion shell..."
res = wait_until_match(r".*(?:No Genymotion virtual device running found)|(?:Genymotion virtual device selected).*")
if re.match(r".*(?:No Genymotion virtual device running found).*", res):
    print "No Genymotion virtual device running found!"
    terminate()

# set initial location
print "Set initial location..."
set_location(latitude, longitude)


print "Starting gps updating thread.."
gps_thread.start()

KEY_UP = 1
KEY_DOWN = 2
KEY_LEFT = 3
KEY_RIGHT = 4
KEY_EXIT = 5
KEY_OTHER = 6

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
            return key_code_map[key]
    return KEY_OTHER
            


print "Ready to use."
while True:
    move_step = 0
    
    key = read_key_board()
    if key == KEY_EXIT:
        break
    elif key == KEY_UP:
        move_step = MOVE_STEP
    elif key == KEY_DOWN:
        move_step = -MOVE_STEP
    elif key == KEY_LEFT:
        angle = (angle + ROTATE_STEP) % 360
    elif key == KEY_RIGHT:
        angle = (360 + angle - ROTATE_STEP) % 360
    else:
        continue

    print "Current angle is ", angle
    if move_step == 0:
        continue
    lock.acquire()
    longitude = longitude + move_step * math.cos(angle*math.pi/180)
    latitude = latitude + move_step * math.sin(angle*math.pi/180) 
    print "Set latitude to", latitude, ", set longitude to", longitude
    lock.release()
    
# terminate process, clean everything up
print "Pokemon Not Go is terminating..."
terminate()
