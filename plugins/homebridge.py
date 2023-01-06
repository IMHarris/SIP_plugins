from __future__ import print_function
# !/usr/bin/env python
# -*- coding: utf-8 -*-

# Flow SIP addin
from plugins import mqtt
import sys
from blinker import signal
import datetime
import gv  # Get access to SIP's settings
import io
import queue
import json  # for working with data file
from sip import template_render  # Needed for working with web.py templates
import threading
import time
from urls import urls  # Get access to SIP's URLs
import web  # web.py framework
from webpages import ProtectedPage, WebPage  # Needed for security

# from webpages import showOnTimeline  # Enable plugin to display station data on timeline

# Global variables
plugin_initiated = False
valve_loop_running = False
valve_message_received = False
prior_valve_state = []
settings_b4 = {}
homebridge_loop_running = False

# Variables for the flow controller client

# Initiate notifications object

# Add new URLs to access classes in this plugin.
# fmt: off
urls.extend([
    u"/homebridge-sp", u"plugins.homebridge.settings",
    u"/homebridge-save", u"plugins.homebridge.save_settings",
])

# Add this plugin to the PLUGINS menu ["Menu Name", "URL"], (Optional)
gv.plugin_menu.append([_(u"Homebridge Plugin"), u"/homebridge-sp"])


def save_prior_settings():
    """
    Save prior settings dictionary to local variable settings_b4
    """
    global settings_b4

    try:
        with open(
                u"./data/homebridge.json", u"r"
        ) as f:  # Read settings from json file if it exists
            prior_settings = json.load(f)
    except IOError:
        prior_settings = {}
    finally:
        settings_b4 = prior_settings


def changed_valves_loop():
    """
    Monitors valve_messages queue for notices that the valve state has changed and takes appropriate action
    This loop runs on its own thread.  Valves changing at the same time sometimes are sent in separate messages.
    By initiating a delay, we can cut down on the number of outgoing messages
    """
    global prior_valve_state
    global valve_loop_running
    global valve_message_received
    global all_data_request_received

    valve_loop_running = True
    while True:

        if valve_message_received:
            # sleep here to ensure that if multiple valves are closed at the same time,
            # the main program has time to update all the valves in gv.sd
            valve_message_received = False
            time.sleep(0.25)
            valves = []
            if len(prior_valve_state) != len(gv.srvals):
                all_data_request_received = True 
            i = 0
            SIP_in_use = False
            for valve in gv.srvals:
                if all_data_request_received  or valve != prior_valve_state[i]:
                    # Valve state has changed, send updated valve info to Homebridge
                    if valve == 1: SIP_in_use = True
                    valve_info = getValveInfo(i)
                    valves.append(valve_info)      
                i += 1
            SIP_info = getSIPInfo()
            SIP_info["InUse"] = SIP_in_use
            
            prior_valve_state = gv.srvals
            SIP_info['valves'] = valves
            print("SIP Info:", SIP_info)
            print("sbits", gv.sbits)
            
            payload = json.dumps(SIP_info).encode('utf-8')
            client = mqtt.get_client()
            if client:
                client.publish(
                "SIP-Homebridge/valves", payload, qos=1, retain=True
                )
        
        time.sleep(0.25)

def getValveInfo(valve_index):
    valve_info = {}
    valve_info["Name"] = gv.snames[valve_index]
    valve_info["InUse"] = ""
    if gv.srvals[valve_index] == 1:
        valve_info["InUse"] = True
    else:
        valve_info["InUse"] = False
    if gv.sd["mas"] - 1 == valve_index:
        valve_info['master'] = True
    else:
        valve_info['master'] = False
    return valve_info
    
def getSIPInfo():
    global gv
    SIP_info = {}
    SIP_info["DisplayName"] = gv.sd["name"]
    SIP_info["ProgramMode"] = ""
    return SIP_info


class settings(ProtectedPage):
    """
    Load an html page for entering plugin settings.
    """

    def GET(self):
        try:
            with open(
                u"./data/homebridge.json", u"r"
            ) as f:  # Read settings from json file if it exists
                settings = json.load(f)
        except IOError:  # If file does not exist return empty value
            settings = {}  # Default settings. can be list, dictionary, etc.
        return template_render.homebridge(settings)  # open settings page


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
        #        print qdict  # for testing
        with open(u"./data/homebridge.json", u"w") as f:  # Edit: change name of json file
            json.dump(qdict, f)  # save to file
        raise web.seeother(u"/")  # Return user to home page.


def on_message(client, msg):
    # "Callback when MQTT message is received."
    if msg.topic == "SIP-Homebridge/valves":
        print("valve message received", json.loads(msg.payload.decode('utf-8')))
    else:
        print("other mqtt message received:", msg.topic, "payload:", str(msg.payload.decode("utf-8")))

class LoopThread(threading.Thread):
    def __init__(self, fn, thread_id, name, counter):
        threading.Thread.__init__(self)
        self.fn = fn
        self.threadID = thread_id
        self.name = name
        self.counter = counter

    def run(self):
        self.fn()


def main_loop():
    """
    **********************************************
    PROGRAM MAIN LOOP
    runs on separate thread
    **********************************************
    """
    global homebridge_loop_running
    homebridge_loop_running = True
    print(u"Homebridge plugin main loop initiated.")
    start_time = datetime.datetime.now()

    while True:
        # Loop code goes here - listening for incoming mqtt commands
        time.sleep(1)


homebridge_loop = LoopThread(main_loop, 1, "HomebridgeLoop", 1)
valve_loop = LoopThread(changed_valves_loop, 2, "ValveLoop", 2)


#class ValveNotice:
#    def __init__(self, switchtime):
#        self.switch_time = switchtime


"""
Event Triggers
"""


def notify_zone_change(name, **kw):
    global valve_message_received
    """
    This event tells us a valve was turned on or off
    """
    valve_message_received = True


zones = signal(u"zone_change")
zones.connect(notify_zone_change)


### valves ###


def notify_new_day(name, **kw):
    """
    App sends a new_day message after plugins are loaded.
    We'll use this as a trigger to start the threaded loops
    and run any code that has to run after other plugins are loaded
    """
    global valve_message_received
    global plugin_initiated

    if not homebridge_loop_running:
        # This loop watches the flow
        homebridge_loop.start()

    # send out current valve statuses
    valve_message_received = True

    if not valve_loop_running:
        # This loop watches for changed valves
        valve_loop.start()
        
    if not plugin_initiated:
        # Code below here runs once all other plugins are initiated    
        subscribe()
    
        # Send a test message
        client = mqtt.get_client()
        #if client:
        #    client.publish(
        #        "SIP-Homebridge", "Hello World", qos=1, retain=True
        #    )
        plugin_initiated = True


new_day = signal(u"new_day")
new_day.connect(notify_new_day)

"""
Run when plugin is loaded
"""


def subscribe():
    "Subscribe to messages"
    # topic = "$SYS/#"
    # if topic:
    #    mqtt.subscribe(topic, on_message, 2)
    #    print('subscribed to sys messages')
    topic = "SIP-Homebridge/#"
    if topic:
        mqtt.subscribe(topic, on_message, 2)
        print('subscribed to SIP to Homebridge messages')
   # topic = "Homebridge-SIP"
   # if topic:
   #     mqtt.subscribe(topic, on_message, 2)
   #     print('subscribed to Homebridge to SIP messages')


