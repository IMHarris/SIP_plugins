from __future__ import print_function
# !/usr/bin/env python
# -*- coding: utf-8 -*-

# Flow SIP addins

import web  # web.py framework
import gv  # Get access to SIP's settings
from os.path import exists
from urls import urls  # Get access to SIP's URLs
from sip import template_render  #  Needed for working with web.py templates
from webpages import ProtectedPage, WebPage  # Needed for security
import json  # for working with data file
# from .kazoofiles import plivosms3
from blinker import signal
import time
import random
import datetime
import threading
from smbus import SMBus


"""
TODO may be possible for a valve to be on when program starts
Need to test for this and add code if necessary
"""

# Global variables
sensor_register = 0x01 # 0x00 for sensor readings, 0x01 to have the sensor send random numbers to use for testing
settings_b4 = {}
saved_settings = {}
valve_states = []
changed_valves = {}
flow_start_time = 0  # Holds start time 
flow_pulses = 0  #Calculated pulses since the start time
all_pulses = 0 # Calculated pulses since beginning of time
master_sensor_addr = 0
pulse_rate = 0 # holds last captured flow rate
loop_running = False # Notes if the main loop has started
valve_open = False # Shows as true if any valve is open
master_station = 0 # Master station number 0 = no master
fw_start_time = 0 # Start time of current flow window
fw_start_flow_counter = 0 # Flow counter at start of flow window

# Variables for the flow controller client
client_addr = 0x44
bus = SMBus(1)

# Add new URLs to access classes in this plugin.
# fmt: off
urls.extend([
    u"/flow-sp", u"plugins.flow.settings",
    u"/flow-save", u"plugins.flow.save_settings",
    u"/flow-data", u"plugins.flow.flowdata"
    ])

# Add this plugin to the PLUGINS menu ["Menu Name", "URL"], (Optional)
gv.plugin_menu.append([_(u"Flow Plugin"), u"/flow-sp"])


def save_prior_settings(prior_settings):
    """
    Save prior settings dictionary to local variable settings_b4
    """
    global settings_b4
    settings_b4 = prior_settings


def actions_on_change_settings():
    """ 
    Execute any actions required from plugin settings changes
    """
    pass
    #if u"check-sms-enabled" in settings_b4.keys():
    #    value = settings_b4[u"check-sms-enabled"]
    #else:
    #    value = u""


def update_settings():
    """
    Load settings from flow.json file to local variables
    """
    global master_sensor_addr
    global saved_settings
    
    if exists(u"./data/flow.json"):
        with open(u"./data/flow.json", u"r") as f:
            saved_settings = json.load(f)    

    actions_on_change_settings() # Take action on any changes in settings


def print_settings(lpad=2):
    """
    Prints the flow settings
    """
    print(u"{}Master flow sensor address: {}".format(" " * lpad, u"0x%02X" % client_addr))
   
        
def update_options():
    """
    Read key main program options into local variables
    """
    print(gv.sd["mas"])
      

def initialize_valve_states():
    """
    Puts valve states into local variable valve_states[]
    """
    global valve_states
    valve_states = []
    i=0
    while (i<len(gv.srvals)):
        valve_states.append(gv.srvals[i])
        i = i + 1
        
    master_station = gv.sd[u"mas"]


def determine_changed_valves():
    """
    Outputs a dictionary of the valves with changed states
    by comparing new gv.srvals[] with values saved to local variable valve_state[]
    """
    global changed_valves
    global valve_open
    capture_time=datetime.datetime.now()
    capture_flow_counter = all_pulses
    valve_now_open = False
    i = 0
    while (i<len(valve_states)):
        if (i != gv.sd["mas"] - 1):
            # Ignore changes in the master valve
            if valve_states[i] != gv.srvals[i]:
                if gv.srvals[i] == 1:
                    changed_valves[i] = u"on"
                    valve_now_open = True
                else:
                    changed_valves[i] = u"off"
            i = i + 1
    
    """if (valve_open and not valve_now_open):
        # All valves are now closed end current flow window
        pass
        
    elif (not valve_open and valve_now_open):
        #Flow has started.  Start a new flow window
        pass
        
    else:
        # Flow is still running but through different valve(s)
        # End current flow window, start the next
        fw_start_time = capture_time # Start time of current flow window
        fw_start_flow_counter = capture_flow_counter # Flow counter at start of flow window
    """
    
    print("valves changed: ", changed_valves)
    
    
    stop_time=datetime.datetime.now()
     #       time_elapsed = stop_time - start_time
    
    
    
    
    
    return changed_valves

def publish_flow_entry():
    pass
    """
    Add a flow entry to the log
    """


def create_flow_log():
    pass
    """
    Create the flow log if it doesn't already exist 
    """
    #with open(u"./data/flow.json", u"w") as f:
    

def action_on_valve_change(changed_valves):
    pass
    """
    Take action on a change in valve state
    """
    

"""
Log pages

class view_log(ProtectedPage):
    View Log

    def GET(self):
        records = read_log()
        return template_render.log(records)


class clear_log(ProtectedPage):
    Delete all log records

    def GET(self):
        with io.open(u"./data/log.json", u"w") as f:
            f.write(u"")
        raise web.seeother(u"/vl")
        
"""



class settings(ProtectedPage):
    """
    Load an html page for entering plugin settings.
    """ 
    global master_sensor_addr
    settings_b4 = {}
    def GET(self):
        
        try:
            
            runtime_values = {"sensor-addr":u"0x%02X" % client_addr}
            if pulse_rate >=0:
                runtime_values.update({"sensor-connected":"no"})
            else:
                runtime_values.update({"sensor-connected":"no"})
            
            with open(
                u"./data/flow.json", u"r"
            ) as f:  # Read settings from json file if it exists
                settings = json.load(f)
        except IOError:  # If file does not exist return empty value
            settings = {}
              # Default settings. can be list, dictionary, etc.
        finally:
            save_prior_settings(settings)
        return template_render.flow(settings,runtime_values)  # open settings page


class save_settings(ProtectedPage):
    """
    Save user input to json file.
    Will create or update file when SUBMIT button is clicked
    CheckBoxes only appear in qdict if they are checked.
    """

    def GET(self):
        qdict = (
            web.input()
        )  # Dictionary of values returned as query string from settings page.
        
        # print(u"SMS settings before update")
        # print_settings()
        with open(u"./data/flow.json", u"w") as f:  # Edit: change name of json file
            json.dump(qdict, f)  # save to file
        update_settings()
        print(u"Flow settings after update")
        print_settings()
        # actions_on_change_settings()
        raise web.seeother(u"/")  # Return user to home page.
 
   
class flowdata(ProtectedPage):
    """
    Return flow values to the web page in JSON form
    """
    global pulse_rate
    global saved_settings
    
    def GET(self):
        web.header(b"Access-Control-Allow-Origin", b"*")
        web.header(b"Content-Type", b"application/json")
        web.header(b"Cache-Control", b"no-cache")
        qdict = {u"pulse_rate":pulse_rate}
        qdict.update({u"total_pulses":all_pulses})
        
        if u"text-pulses-per-measure" in saved_settings.keys():
            pulses_per_measure = float(saved_settings[u"text-pulses-per-measure"])
            if pulses_per_measure > 0:
                if pulse_rate >= 0:
                    flow_rate = round(pulse_rate * 60 / pulses_per_measure,3)
                else:
                    flow_rate = -1
                qdict.update({u"flow_rate": flow_rate})
            else:
                qdict.update({u"flow_rate": 0})          
        else:
            qdict.update({u"flow_rate": 0})
            
        if u"text-volume-measure" in saved_settings.keys():
            qdict.update({u"volume_measure": saved_settings[u"text-volume-measure"] + "/hr"})
        else:
            qdict.update({u"volume_measure": "?/hr"})
        
        return json.dumps(qdict)


def read_log():
    """
    Read data from irrigation log file.
    """
    result = []
    try:
        with io.open(u"./data/log.json") as logf:
            records = logf.readlines()
            for i in records:
                try:
                    rec = ast.literal_eval(json.loads(i))
                except ValueError:
                    rec = json.loads(i)
                result.append(rec)
        return result
    except IOError:
        return result


class flowlog(ProtectedPage):
    """
    Renders the flow log page
    """
    
    def GET(self):
        web.header(b"Access-Control-Allow-Origin", b"*")
        web.header(b"Content-Type", b"application/json")
        web.header(b"Cache-Control", b"no-cache")

        log = read_log()
        return template_render.flow.flowlog(log)  # open settings page



class loopThread (threading.Thread):
   def __init__(self, threadID, name, counter):
      threading.Thread.__init__(self)
      self.threadID = threadID
      self.name = name
      self.counter = counter
   def run(self):
      main_loop()

loop_thread = loopThread(1, "LoopThread", 1) 

def main_loop():
    """
    **********************************************
    PROGRAM MAIN LOOP
    runs on separate thread
    **********************************************
    """
    global loop_running
    global pulse_rate
    global valve_open
    global all_pulses
    loop_running = True
    print(u"Flow plugin main loop initiated.")
    start_time = datetime.datetime.now()
    while True:
        try:
            bytes = bus.read_i2c_block_data(client_addr, sensor_register, 4)
            pulse_rate = int.from_bytes(bytes,u"little")
        except IOError:
            pulse_rate = -1
        
        if not pulse_rate == -1:
            stop_time=datetime.datetime.now()
            time_elapsed = stop_time - start_time
            # Todo does total_seconds include a fraction?
            all_pulses = all_pulses + time_elapsed.total_seconds() * pulse_rate
            start_time = stop_time        
            
        time.sleep(1)
        #print("looped")

"""
Event Triggers
"""

### valves ###
def notify_zone_change(name, **kw):
    """
    This event tells us a valve was turned on or off
    """
    print("Valves changing - kazoo")
    changed_valves = determine_changed_valves()
    if len(changed_valves) > 0:
        for num, val in changed_valves.items():
            print(u"Valve {} switched {}".format(str(num), val))
    initialize_valve_states()


zones = signal(u"zone_change")
zones.connect(notify_zone_change)

def notify_new_day(name, **kw):
    """
    App sends a new_day message after plugins are loaded.
    We'll use this as a trigger to start the main loop
    """
    if not loop_running:
        print("hihi")
        loop_thread.start()

new_day = signal(u"new_day")
new_day.connect(notify_new_day)


# Function to be run when sigal is recieved.
def notify_alarm_toggled(name, **kw):
    pass

# instance of named signal
alarm = signal(u"alarm_toggled")  
# Connect signal to function to be run.
alarm.connect(notify_alarm_toggled)


### Option settings ###
def notify_option_change(name, **kw):
    """
    TODO: Refresh valve state when number of stations changes
    """
    update_options()
    
    
    #print(u"kz Option settings changed in gv.sd Name:{}".format("hi"))
    #for x in kw:
    #    print(x)
    
    #  gv.sd is a dictionary containing the setting that changed.
    #  See "from options" in gv_reference.txt


option_change = signal(u"option_change")
option_change.connect(notify_option_change)


#  Run when plugin is loaded
update_settings()
initialize_valve_states()
print(u"Flow Settings")
print_settings()

    


