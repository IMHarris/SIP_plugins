from __future__ import print_function
# !/usr/bin/env python
# -*- coding: utf-8 -*-
import gv
from os.path import exists
import json
import codecs
import time
import io
import ast
#import datetime

"""
**********************************************
Flow Plugin Helper functions
**********************************************
"""


class LocalSettings:
    
    def __init__(self):
        self.pulses_per_measure = 0
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
                self.pulses_per_measure = float(saved_settings["text-pulses-per-measure"])
            if u"enable-logging" in saved_settings.keys():
                self.enable_logging = True
            if u"text-volume-measure" in saved_settings.keys():
                self.volume_measure = saved_settings["text-volume-measure"]
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
            if u"text-volume-measure" in saved_settings.keys():
                self.volume_measure = saved_settings["text-volume-measure"]
        

class FlowWindow:
    def __init__(self,local_settings):
        self.ls = local_settings
        FlowWindow.clear(self)

    def clear(self):
        self.start_time = 0
        self.end_time = 0
        self.start_pulses = 0
        self.end_pulses = 0
        self.open_valves = []
        self.open_valves_names = []

    def usage(self):
        # Returns water usage in current flow window
        if self.ls.pulses_per_measure > 0:
            return round(((self.end_pulses-self.start_pulses)/self.ls.pulses_per_measure)*10)/10
        else:
            return 0
        
    def valves_status_str(self):
        # Returns string noting which valves are open
        if len(self.open_valves_names) == 0:
            status_str = "All valves closed"
        elif len(self.open_valves_names) == 1:
            status_str = self.open_valves_names[0] + " is open"
        else:
            status_str = self.open_valves_names[0]
            i = 1
            while i < len(self.open_valves_names):
                status_str = status_str + ", " + self.open_valves_names[i]
                i = i+1
        status = status_str + " are open"
        return status_str
                
    # def valves_str(self):
    #     # Returns list of open valves by name
    #     valve_list = []
    #     if len(self.open_valves_names) >= 1:
    #         valve_list.append(self.open_valves_names[0])
    #         if len(self.open_valves_names) > 1:
    #             i = 1
    #             while i < len(self.open_valves_names):
    #                 valve_list.append(self.open_valves_names[i])
    #                 i = i + 1

    def duration(self):
        delta = self.end_time - self.start_time
        return int(delta.total_seconds())

    def write_log(self):
        """
        Add flow window data to json log file - most recent first.
        If a record limit is specified (limit) the number of records is truncated.
        """
        print("writing flow log ", str(self.ls.enable_logging) )
        if self.ls.enable_logging:
            open_valves = ""
            open_valves_str = ""
            i = 0
            for valve in self.open_valves:
                # Create the string of valve numbers separated by commas
                open_valves = open_valves + str(valve)
                open_valves_str = open_valves_str + gv.snames[valve]
                i=i+1
                if i<len(self.open_valves):
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
                +'","'
                + u'start'
                + u'":"'
                + self.start_time.strftime(u'%H:%M:%S')
                + u'"}'
            )
            lines = []
            lines.append(logline + u"\n")
            log = read_log()
            for r in log:
                lines.append(json.dumps(r) + u"\n")
            with codecs.open(u"./data/flowlog.json", u"w", encoding=u"utf-8") as f:
                if self.ls.max_log_entries>0:
                    f.writelines(lines[: self.ls.max_log_entries])
                else:
                    f.writelines(lines)
                    
        self.clear()


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
