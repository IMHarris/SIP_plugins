# !/usr/bin/env python
# -*- coding: utf-8 -*-

# Python 2/3 compatibility imports
from __future__ import print_function

# standard library imports
import json  # for working with data file
from threading import Thread
from time import sleep

# local module imports
from blinker import signal
import gv  # Get access to SIP's settings
from sip import template_render  # Needed for working with web.py templates
from urls import urls  # Get access to SIP's URLs
import web  # web.py framework
from webpages import ProtectedPage  # Needed for security
from webpages import showInFooter  # Enable plugin to display readings in UI footer
from webpages import showOnTimeline  # Enable plugin to display station data on timeline

# Add new URLs to access classes in this plugin.
urls.extend([
    u"/sms-plivo-sp", u"plugins.sms_plivo.settings",
    u"/sms-plivo-save", u"plugins.sms_plivo.save_settings"

])

# Add this plugin to the PLUGINS menu ["Menu Name", "URL"], (Optional)
gv.plugin_menu.append([_(u"SMS Plivo Plugin"), u"/sms-plivo-sp"])




ft = Thread(target=data_test)
ft.daemon = True
ft.start()


### Station Completed ###
def notify_station_completed(station, **kw):
    print(u"Station {} run completed".format(station))


complete = signal(u"station_completed")
complete.connect(notify_station_completed)


class settings(ProtectedPage):
    """
    Load an html page for entering plugin settings.
    """

    def GET(self):
        try:
            with open(
                    u"./data/sms_plivo.json", u"r"
            ) as f:  # Read settings from json file if it exists
                settings = json.load(f)
        except IOError:  # If file does not exist return empty value
            settings = {}  # Default settings. can be list, dictionary, etc.
        return template_render.sms_plivo(settings)  # open settings page


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
        with open(u"./data/sms_plivo.json", u"w") as f:  # Edit: change name of json file
            json.dump(qdict, f)  # save to file
        raise web.seeother(u"/")  # Return user to home page.


#  Run when plugin is loaded

