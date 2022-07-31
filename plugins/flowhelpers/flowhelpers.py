from __future__ import print_function
# !/usr/bin/env python
# -*- coding: utf-8 -*-
import gv
from os.path import exists
import json
import codecs
import io
import ast
import threading
import datetime

"""
**********************************************
Flow Plugin Helper functions
**********************************************
"""

class LocalSettings:
    
    def __init__(self):
        self.pulses_per_measure = 0
        self.enable_logging = False
        self.volume_measure = ""
        self.max_log_entries = 0
        LocalSettings.load_settings(self)

    def load_settings(self):
        self.pulses_per_measure = 0
        self.enable_logging = False
        self.max_log_entries = 0
        self.volume_measure = ""
        print("loading flow settings")
        if exists(u"./data/flow.json"):
            with open(u"./data/flow.json", u"r") as f:
                saved_settings = json.load(f)
            if u"text-pulses-per-measure" in saved_settings.keys():
                pulses_per_measure = saved_settings["text-pulses-per-measure"]
                if pulses_per_measure.replace(".","").isnumeric():
                    self.pulses_per_measure = float(saved_settings["text-pulses-per-measure"])
            if u"enable-logging" in saved_settings.keys():
                self.enable_logging = True
            if u"text-volume-measure" in saved_settings.keys():
                vm = saved_settings["text-volume-measure"]
                if len(vm.strip()) != 0:
                    self.volume_measure = saved_settings["text-volume-measure"]
                else:
                    self.volume_measure = "?"
            else:
                self.volume_measure = "?"
            if u"chk-enable-logging" in saved_settings.keys():
                self.enable_logging = True
            if u"text-max-log-entries" in saved_settings.keys():
                textmax = saved_settings["text-max-log-entries"]
                if textmax.isnumeric():
                    self.max_log_entries = int(textmax)
                else:
                    self.max_log_entries = 0
            else:
                self.max_log_entries = 0


class Notice:
    #  0: SIP flow sensor is reporting water movement, but all valves should be off
    #  1: SIP has stations on, but sensor is not reporting water movement

    def __init__(self):
        msg_email = ""
        msg_sms = ""
        msg_voice = ""

    def send_notice(self):
        pass


class FlowWindow:
    # Flow window class holds data about the current open valves
    def __init__(self, local_settings):
        self.ls = local_settings
        self._lock = threading.Lock()
        self._start_time = datetime.datetime.now()
        self.end_time = datetime.datetime.now()
        self.start_pulses = 0
        self.end_pulses = 0
        self._pulse_rate = 0
        self._open_valves = []
        self._open_valves_names = []
        self._valve_states = []
        self._valve_open = False
        self.load_valve_states()
        self._flow_warning1_given = False
        self._flow_warning2_given = False

    def load_valve_states(self):
        i = 0
        self._valve_open = False
        while i < len(gv.srvals):
            self._valve_states.append(gv.srvals[i])
            if i != gv.sd["mas"] - 1:
                # Ignore status of or changes in the master valve
                if gv.srvals[i] == 1:
                    # Determine open valves
                    self._open_valves.append(i)
                    self._open_valves_names.append(gv.snames[i])
                    self._valve_open = True
            i = i + 1

    def valve_states(self):
        return self._valve_states

    def open_valves(self):
        return self._open_valves

    def open_valves_names(self):
        return self._open_valves_names

    def valve_open(self):
        # Returns True if a valve is open, else False
        return self._valve_open

    def add_open_valve(self, valve_number):
        self._open_valves.append(valve_number)

    def master_station(self):
        return gv.sd[u"mas"]

    @property
    def start_time(self):
        return self._start_time

    @start_time.setter
    def start_time(self,val):
        self._start_time = val
        self.clear_warning_flags()

    @property
    def pulse_rate(self):
        return self._pulse_rate

    @pulse_rate.setter
    def pulse_rate(self, val):
        delta = datetime.datetime.now() - self.start_time
        duration = delta.total_seconds()
        print("got the pulse rate", duration, self.valve_open(), val)
        if not self._flow_warning1_given:
            if duration > 3 and self.valve_open() and val == 0:
                print("Flow error 1 encountered")
                self._flow_warning1_given = True
        if not self._flow_warning2_given:
            if duration > 3 and not self.valve_open() and val > 3:
                print("Flow error 2 encountered")
                self._flow_warning2_given = True
        self._pulse_rate = val

    def usage(self):
        # Returns water usage in current flow window
        if self.ls.pulses_per_measure > 0:
            return round(((self.end_pulses-self.start_pulses)/self.ls.pulses_per_measure)*10)/10
        else:
            return 0

    def valves_status_str(self):
        # Returns string noting which valves are open
        if len(self._open_valves_names) == 0:
            status_str = "All valves closed"
        else:
            status_str = self._open_valves_names[0]
            i = 1
            while i < len(self._open_valves_names):
                status_str = status_str + ", " + self._open_valves_names[i]
                i = i + 1
        return status_str

    def duration(self):
        delta = self.end_time - self._start_time
        return int(delta.total_seconds())

    def write_log(self):
        """
        Add flow window data to json log file - most recent first.
        If a record limit is specified (limit) the number of records is truncated.
        """
        if not self._lock.locked():
            # if locked, then this write_log request came right on the heels of the last one.  Valve changes come
            # in one at a time, even if they are shut off simultaneously.  The flow window needs to
            # collect these in a group. To make this work, the program puts write_log actions on a
            # short delay ignoring requests that come in quickly on the heels of the last one.  All changes
            # are then collected at the end of the delay
            with self._lock:
                print("writing flow log ", str(self.ls.enable_logging))
                if self.ls.enable_logging:
                    open_valves = ""
                    open_valves_str = ""
                    i = 0
                    for valve in self._open_valves:
                        # Create the string of valve numbers separated by commas
                        open_valves = open_valves + str(valve)
                        open_valves_str = open_valves_str + gv.snames[valve]
                        i = i+1
                        if i < len(self._open_valves):
                            open_valves = open_valves + ","
                            open_valves_str = open_valves_str + ","
                    
                    logline = (
                        u'{"'
                        + u"valves"
                        + u'":"'
                        + open_valves
                        + u'","'
                        + u'stations'
                        + u'":"'
                        + open_valves_str
                        + u'","'
                        + "usage"
                        + u'":'
                        + str(FlowWindow.usage(self))
                        + u',"'
                        + u'measure'
                        + u'":"'
                        + self.ls.volume_measure
                        + u'","'
                        + u'duration'
                        + u'":"'
                        + timestr(FlowWindow.duration(self))
                        + u'","'
                        + u'date'
                        + u'":"'
                        + self.start_time.strftime(u'%Y-%m-%d')
                        + '","'
                        + u'start'
                        + u'":"'
                        + self.start_time.strftime(u'%H:%M:%S')
                        + u'"}'
                    )
                    lines = [logline + u"\n"]
                    log = read_log()
                    for r in log:
                        lines.append(json.dumps(r) + u"\n")
                    with codecs.open(u"./data/flowlog.json", u"w", encoding=u"utf-8") as f:
                        if self.ls.max_log_entries > 0:
                            f.writelines(lines[: self.ls.max_log_entries])
                        else:
                            f.writelines(lines)

    def clear_warning_flags(self):
        self._flow_warning1_given = False
        self._flow_warning2_given = False
                            

class ValveNotice:
    def __init__(self, switchtime, counter):
        self.switch_time = switchtime
        self.counter = counter
        

class FlowSmoother:
    # Averages the flow readings for a smoother readout
    def __init__(self, average_period):
        self._average_period = average_period
        self._readings = [0] * average_period
        self._last_reading = float(0)
        self._i = 0

    def add_reading(self, reading):
        self._last_reading = reading
        self._readings[self._i % self._average_period] = reading
        self._i = self._i + 1

    def last_reading(self):
        return self._last_reading

    def ave_reading(self):
        reading_sum = 0
        i = 0
        while i < self._average_period:
            reading_sum = reading_sum + self._readings[i]
            i = i + 1
        return reading_sum/self._average_period


def timestr(t):
    """
    Convert duration in seconds to string in the form mm:ss.
    """
    return (
        str((t // 60 >> 0) // 10 >> 0)
        + str((t // 60 >> 0) % 10)
        + u":"
        + str((t % 60 >> 0) // 10 >> 0)
        + str((t % 60 >> 0) % 10)
    )  


def read_log():
    """
    Read data from irrigation log file.
    """
    result = []
    try:
        with io.open(u"./data/flowlog.json") as logf:
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
