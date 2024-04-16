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

# Global variables
plugin_initiated = False
valve_loop_running = False
valve_message_received = False
all_data_request_received = False
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


def main_loop():
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
            # Request has been made to send valve information to Homebridge
            valve_message_received = False
            # sleep here to ensure that if multiple valves are closed at the same time,
            # the main program has time to update all the valves in gv.sd
            time.sleep(0.25)
            if all_data_request_received:
                sip_info = getSIPInfo(0)
            else:
                sip_info = getSIPInfo(1)
            print("SIP Info:", sip_info)
            payload = json.dumps(sip_info).encode('utf-8')
            publishMQTT("SIP-Homebridge/valves", payload, 1, True)
            # if client:
            #     client.publish(
            #         "SIP-Homebridge/valves", payload, qos=1, retain=True
            #     )
            # valves = []
            # if len(prior_valve_state) != len(gv.srvals):
            #     all_data_request_received = True
            # i = 0
            # sip_in_use = False
            # enabled_valves = gv.sd["show"]  # enabled valves stored as bits
            # #
            # enabled_valves = 7
            # for valve in gv.srvals:
            #     if (all_data_request_received or valve != prior_valve_state[i]) and enabled_valves & 1 << i != 0:
            #         # Valve state has changed, send updated valve info to Homebridge
            #         if valve == 1: sip_in_use = True
            #         valve_info = getValveInfo(i)
            #         valves.append(valve_info)
            #     i += 1
            # sip_info["InUse"] = sip_in_use
            #
            # prior_valve_state = gv.srvals
            # sip_info['valves'] = valves

        time.sleep(0.25)


def getSIPInfo(valve_option):
    # Returns a dictionary with SIP information and a valve info collection
    # valve_option = 0, return all valves
    # valve_option = 1, return changed valves only
    global prior_valve_state

    # Get SIP Properties
    global gv
    sip_info = {"Name": gv.sd["name"], "ProgramMode": 0, "Active": 1, "InUse": 1 in gv.srvals}

    valves = []
    enabled_valves = gv.sd["show"]  # enabled valves stored as bits
    # todo remove next line and test for more than 8 valves
    enabled_valves = 7
    i = 0
    for valve in gv.srvals:
        if (valve_option == 0 or valve != prior_valve_state[i]) and enabled_valves & 1 << i != 0:
            if valve == 1: sip_in_use = True
            valve_info = getValveInfo(i)
            valves.append(valve_info)
        i += 1
        prior_valve_state = gv.srvals

    sip_info["valves"] = valves
    # sip_info["valves"] = []
    return sip_info


def getValveInfo(valve_index):
    # Returns a dictionary with valve information based on valve index
    valve_info = {"Name": gv.snames[valve_index]}
    if gv.srvals[valve_index] == 1:
        valve_info["InUse"] = 1
    else:
        valve_info["InUse"] = 0
    if gv.sd["mas"] - 1 == valve_index:
        valve_info['Master'] = True
    else:
        valve_info['Master'] = False
    valve_info['Active'] = 1
    valve_info['ValveType'] = 1
    return valve_info



def publishMQTT(topic, payload, qos=1, retain=True):
    client = mqtt.get_client()
    if client:
        client.publish(
            topic="SIP-Homebridge/valves", payload=payload, qos=qos, retain=retain
        )


# def getSIPInfo():
#     global gv
#     sip_info = {"Name": gv.sd["name"], "ProgramMode": ""}
#     return sip_info


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


class LoopThread(threading.Thread):
    def __init__(self, fn, thread_id, name, counter):
        threading.Thread.__init__(self)
        self.fn = fn
        self.threadID = thread_id
        self.name = name
        self.counter = counter

    def run(self):
        self.fn()


homebridge_loop = LoopThread(main_loop, 1, "HomebridgeLoop", 1)

"""
Event Triggers
"""


def on_message(client, msg):
    # "Callback when MQTT message is received."
    if msg.topic == "Homebridge-SIP/changed-valve":
        #  Request received to change valve state
        payload = json.loads(msg.payload.decode('utf-8'))
        print("Valve state change requested:", payload)
        # todo work here to take action on valve state change requests
        valve_index = gv.snames.index(payload["Name"])
        print("gv.snames: ", str(gv.snames), "valve index: ", str(valve_index))

        # gv.srvals = [0, 0, 0, 0, 0, 0, 0, 0]
    elif msg.topic == "SIP-Homebridge/valves":
        print("valve message received", json.loads(msg.payload.decode('utf-8')))
    elif msg.topic == "Homebridge/SIP/common":
        # This is a request from Homebridge for information
        pass
    else:
        print("unrecognized mqtt message received:", msg.topic, "payload:", str(msg.payload.decode("utf-8")))


def notify_zone_change(name, **kw):
    global valve_message_received
    """
    This event tells us a valve was turned on or off
    """
    print("zone change notified")
    if plugin_initiated:
        valve_message_received = True


zones = signal(u"zone_change")
zones.connect(notify_zone_change)


### Option settings ###
def notify_option_change(name, **kw):
    print(u"Option settings changed in gv.sd", "name:", name, "kw:", kw)
    #  gv.sd is a dictionary containing the setting that changed.
    #  See "from options" in gv_reference.txt


option_change = signal(u"option_change")
option_change.connect(notify_option_change)


### Station Names ###
def notify_station_names(name, **kw):
    print(u"Station names changed")
    # Station names are in gv.snames and /data/snames.json


station_names = signal(u"station_names")
station_names.connect(notify_station_names)


### System settings ###
def notify_value_change(name, **kw):
    print(u"Controller values changed in gv.sd")
    #  gv.sd is a dictionary containing the setting that changed.
    #  See "from controller values (cvalues)" gv_reference.txt


value_change = signal(u"value_change")
value_change.connect(notify_value_change)


def notify_new_day(name, **kw):
    """
    App sends a new_day message after plugins are loaded.
    We'll use this as a trigger to start the threaded loops
    and run any code that has to run after other plugins are loaded
    """
    global valve_message_received
    global plugin_initiated
    global all_data_request_received
    print("NEW DAY")
    if not homebridge_loop_running:
        # This loop watches the flow
        homebridge_loop.start()

    if not plugin_initiated:
        # Code below here runs once all other plugins are initiated    
        subscribe()

        # set indicator to send out current valve statuses
        all_data_request_received = True
        valve_message_received = True
        plugin_initiated = True


new_day = signal(u"new_day")
new_day.connect(notify_new_day)

"""
Run when plugin is loaded
"""


def subscribe():
    # Subscribe to messages
    # topic = "$SYS/#"
    # if topic:
    #    mqtt.subscribe(topic, on_message, 2)
    #    print('subscribed to sys messages')
    topic = "SIP-Homebridge/#"
    if topic:
        mqtt.subscribe(topic, on_message, 2)
        mqtt.subscribe("Homebridge-SIP/#", on_message, 2)
        print('subscribed to SIP to Homebridge messages')
