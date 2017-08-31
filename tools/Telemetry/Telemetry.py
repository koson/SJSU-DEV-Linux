from __future__ import division
from flask import Flask, request, render_template, jsonify, send_from_directory
import threading
import serial
import time
import glob
import json
import re
import os
import logging
import webbrowser
from enum import Enum

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

class State(Enum):
    OFFLINE = 0
    SYSTEM_BOOTING = 1
    ONLINE_SYS_PROMPT = 2

# INITIAL STATE
state                           = State.OFFLINE
previous_prompt                 = -1
# CONSTANTS
SERIAL_READ_CONSTANT_LENGTH     = 100000
BAUDRATE                        = 38400
# BAUDRATE                        = 115200
MILLIS_RATIO                    = (1/1000)
SUCCESS                         = "SUCCESS"
FAILURE                         = "FAILURE"
PARTIAL_TELEMETETRY_PATTERN     = re.compile('(?s)LPC: telemetry ascii(.*)')
FULL_TELEMETRY_PATTERN          = re.compile('(?s)LPC: telemetry ascii(.*?)[\x03][\x03][\x04][\x04][ ]{3}Finished in [0-9]+ us\n')

# SETUP FLASK APPLICATION
app                             = Flask(__name__)
app.debug                       = True

# SETUP SERIAL PORT
ser                             = serial.Serial()
ser.baudrate                    = 38400
ser.rts                         = False
ser.dtr                         = False
ser.timeout                     = 0

# SERIAL DATA STORAGE
serial_output                   = ""
telemetry                       = ""
new_serial                      = ""

# THREAD VARIABLES
lock = threading.Lock()

def read_serial():
    global MILLIS_RATIO
    global PARTIAL_TELEMETETRY_PATTERN
    global FULL_TELEMETRY_PATTERN
    global telemetry
    global serial_output
    global new_serial
    global previous_prompt
    global state

    while True:
        time.sleep(100 * MILLIS_RATIO)

        ser.baudrate = BAUDRATE
        ser.rts = False
        ser.dtr = False

        if state == State.OFFLINE:
            found_prompt = serial_output.rfind("LPC:")
            if found_prompt > previous_prompt:
                previous_prompt = found_prompt
                state = State.ONLINE_SYS_PROMPT

        if ser.is_open == True:

            global serial_output
            global telemetry
            global MILLIS_RATIO

            if ser.is_open == False:
                break

            ser.write("telemetry ascii\n")
            time.sleep(100 * MILLIS_RATIO)

            serial_output   += ser.read(SERIAL_READ_CONSTANT_LENGTH)
            end_array       = FULL_TELEMETRY_PATTERN.findall(serial_output)

            if len(end_array) > 0:
                telemetry = end_array[-1]
                # If telemetry is found, trim it from the serial_output
                serial_tmp = FULL_TELEMETRY_PATTERN.sub('', serial_output)
                serial_tmp = PARTIAL_TELEMETETRY_PATTERN.sub('', serial_tmp)
                serial_output = serial_tmp

# SERVER ROUTES
@app.route('/js/<path:path>')
def send_js(path):
    return send_from_directory('js', path)

@app.route('/css/<path:path>')
def send_css(path):
    return send_from_directory('css', path)

@app.route('/lib/<path:path>')
def send_lib(path):
    return send_from_directory('lib', path)

@app.route('/')
def index():
    return render_template("index.html", version="version 0.0.2")

@app.route('/server-is-alive')
def server_is_alive():
    return SUCCESS

@app.route('/telemetry')
def return_telemetry():
    payload = ""

    if state == State.ONLINE_SYS_PROMPT:
        payload = telemetry

    return payload

@app.route('/list')
def list():
    ttyUSB_list = glob.glob("/dev/ttyUSB*")
    ttyACM_list = glob.glob("/dev/ttyACM*")
    tty_list = ttyUSB_list + ttyACM_list
    sorted_tty_list = sorted(tty_list)
    return json.dumps(sorted_tty_list)

@app.route('/connect')
@app.route('/connect/<int:device>')
def connect(device=0):
    ser.close()
    ser.port = "/dev/ttyUSB%d" % (device)
    state = State.OFFLINE
    ser.open()
    return SUCCESS

@app.route('/disconnect', methods=['GET'])
def disconnect():
    ser.close()
    state = State.OFFLINE
    return SUCCESS

@app.route('/serial')
def serial():
    # print(serial_output)
    serial_return   = serial_output
    serial_return   = FULL_TELEMETRY_PATTERN.sub('', serial_return)
    serial_return   = PARTIAL_TELEMETETRY_PATTERN.sub('', serial_return)
    return serial_return

@app.route('/write/<string:payload>')
def write(payload=""):
    lock.acquire()
    payload += "\n"
    # print(payload)
    ser.write(payload.encode('utf-8'))
    lock.release()
    return SUCCESS


@app.route('/set/<string:component_name>/<string:variable_name>/<value>')
def set(component_name, variable_name, value):
    lock.acquire()
    payload = "telemetry %s %s %g\n" % (component_name, variable_name, float(value))
    ser.write(payload.encode('utf-8'))
    lock.release()
    return SUCCESS


webbrowser.open('http://localhost:5001')
thread = threading.Thread(target=read_serial)
thread.daemon = True
thread.start()