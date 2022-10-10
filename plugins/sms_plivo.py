# !/usr/bin/env python
# -*- coding: utf-8 -*-

# Python 2/3 compatibility imports
from __future__ import print_function

# *********************************************************
#
#  Everything at the top of this program down to the plivo specific
#  code can be used as a template for other plugins developed
#  for other sms and voice providers
#
# *********************************************************

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

# Add new URLs to access classes in this plugin.
urls.extend([
    u"/sms-plivo-sp", u"plugins.sms_plivo.settings",
    u"/sms-plivo-save", u"plugins.sms_plivo.save_settings"

])

# Add this plugin to the PLUGINS menu ["Menu Name", "URL"], (Optional)
gv.plugin_menu.append([_(u"SMS Plivo Plugin"), u"/sms-plivo-sp"])


# ft = Thread(target=data_test)
# ft.daemon = True
# ft.start()
"""
Event Triggers
"""


def advertise_presence(name, **kw):
    """
    Respond to query looking for notification plugins
    When a "notify_checkin" message is received, this plugin will advertise its ability
    to accept sms and voice notifications by responding with a "notification presence" message.
    """
    notification_presence = signal("notification_presence")
    notification_presence.send(u"Plivo", txt=u"sms")
    notification_presence.send(u"Plivo", txt=u"voice")


notification_checkin = signal(u"notification_checkin")
notification_checkin.connect(advertise_presence)


def receive_sms(name, **kw):
    """
    Receive SMS message.  Send to SMS provider
    """
    print(u"SMS message received from {}: {}".format(name, kw[u"msg"]))
    sms.send_message(+18479519366, kw[u"msg"])


receive_sms_message = signal(u"sms_alert")
receive_sms_message.connect(receive_sms)


def receive_voice(name, **kw):
    """
    Receive voice message.  Send to voice provider
    """
    print(u"Voice message received from {}: {}".format(name, kw[u"msg"]))


receive_voice_message = signal(u"voice_alert")
receive_voice_message.connect(receive_voice)


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


# *********************************************************
#
#  Everything from here down is Plivo Specific
#  Plivo keys are stored in a configuration file and not exposed via settings
#  to reduce the risk of the info being disclosed to the public
#
# *********************************************************

# Imports required for Plivo
import requests
from os.path import exists

PLIVO_VERSION = "v1"
KEY_DATA = u"./data/plivo_keys.json"


class PlivoKeys(object):
    def __init__(self, _keyfile):
        self.key_file = _keyfile
        self._auth_keys = {}
        self.load_keyfile()

    def load_keyfile(self):
        # Load the keys from the keyfile
        if exists(self.key_file):
            with open(self.key_file, u"r") as f:
                self._auth_keys = json.load(f)
        else:
            self._auth_keys = {}

    def auth_id(self):
        if u"auth-id" in self._auth_keys.keys():
            return self._auth_keys["auth-id"]
        else:
            return ""

    def auth_token(self):
        if u"auth-token" in self._auth_keys.keys():
            return self._auth_keys["auth-token"]
        else:
            return ""

    def auth_phlo(self):
        if u"auth-phlo" in self._auth_keys.keys():
            return self._auth_keys["auth-phlo"]
        else:
            return ""

    def src(self):
        if u"src" in self._auth_keys.keys():
            return self._auth_keys["src"]
        else:
            return ""


class SMSAPI(object):
    def __init__(self, plivokeys, url='https://api.plivo.com', version="v1"):
        self.version = version
        self.url = url.rstrip('/') + '/' + self.version
        self.auth_id = plivokeys.auth_id()
        self.auth_token = plivokeys.auth_token()
        self.src = plivokeys.src()
        self._api = self.url + '/Account/%s' % self.auth_id
        self.headers = {'User-Agent': 'PythonPlivo'}

    def _request(self, method, path, data={}):
        path = path.rstrip('/') + '/'
        if method == 'POST':
            headers = {'content-type': 'application/json'}
            headers.update(self.headers)
            r = requests.post(self._api + path, headers=headers,
                              auth=(self.auth_id, self.auth_token),
                              data=json.dumps(data))
        elif method == 'GET':
            r = requests.get(self._api + path, headers=self.headers,
                             auth=(self.auth_id, self.auth_token),
                             params=data)
        elif method == 'DELETE':
            r = requests.delete(self._api + path, headers=self.headers,
                                auth=(self.auth_id, self.auth_token),
                                params=data)
        elif method == 'PUT':
            headers = {'content-type': 'application/json'}
            headers.update(self.headers)
            r = requests.put(self._api + path, headers=headers,
                             auth=(self.auth_id, self.auth_token),
                             data=json.dumps(data))
        content = r.content
        if content:
            try:
                response = json.loads(content.decode("utf-8"))
            except ValueError:
                response = content
        else:
            response = content

        return content

    def send_message(self, phone, text_message):
        try:
            params = {
                'src': self.src,  # Sender's phone number with country code
                'dst': phone,  # Receiver's phone Number with country code
                'text': text_message,  # Your SMS Text Message - English
                #   'url' : "http://example.com/report/", # The URL to which with the status of the message is sent
                'method': 'POST'  # The method used to call the url
            }

            print('Plivo sending SMS msg: ', text_message)
            response = self._request('POST', '/Message/', data=params)

            # print('Text message submitted.  Response: ', str(response))
            return response

        except Exception as inst:
            print('Unable to send SMS message')
            print(type(inst))  # the exception instance
            print(inst.args)  # arguments stored in .args
            print(inst)


class VoiceAPI(object):

    def __init__(self, plivokeys, url='https://phlorunner.plivo.com/v1', version="vi"):
        self.version = version
        self.url = url.rstrip('/') + '/'
        self.auth_id = plivokeys.auth_id()
        self.auth_token = plivokeys.auth_token()
        self.auth_phlo = plivokeys.auth_phlo()
        self._api = 'account/%s/phlo/%s' % (self.auth_id, self.auth_phlo)
        self.headers = {'User-Agent': 'PythonPlivo'}

    def _request(self, method, path, data={}):
        path = path.rstrip('/') + '/'
        if method == 'POST':
            headers = {'content-type': 'application/json'}
            headers.update(self.headers)
            r = requests.post(self.url + self._api, headers=headers,
                              auth=(self.auth_id, self.auth_token),
                              data=json.dumps(data))
        elif method == 'GET':
            r = requests.get(self._api + path, headers=self.headers,
                             auth=(self.auth_id, self.auth_token),
                             params=data)
        elif method == 'DELETE':
            r = requests.delete(self._api + path, headers=self.headers,
                                auth=(self.auth_id, self.auth_token),
                                params=data)
        elif method == 'PUT':
            headers = {'content-type': 'application/json'}
            headers.update(self.headers)
            r = requests.put(self._api, headers=headers,
                             auth=(self.auth_id, self.auth_token),
                             data=json.dumps(data))

        content = r.content
        if content:
            try:
                response = json.loads(content.decode("utf-8"))
            except ValueError:
                response = content
        else:
            response = content

        return content

    def send_message(self, params=None):
        if not params: params = {}
        return self._request('POST', '/Message/', data=params)


# def sendSMS(textmessage, phone):
#     try:
#         p = plivosms2.RestAPI()
#
#         params = {
#             'src': '+12242284700',  # Sender's phone number with country code
#             'dst': phone,  # Receiver's phone Number with country code
#             'text': textmessage,  # Your SMS Text Message - English
#             #   'url' : "http://example.com/report/", # The URL to which with the status of the message is sent
#             'method': 'POST'  # The method used to call the url
#         }
#
#         print('Sending SMS msg: ', textmessage)
#         response = p.send_message(params)
#         # print('Text message submitted.  Response: ', str(response))
#
#     except Exception as inst:
#         print('Unable to send SMS message')
#         print(type(inst))  # the exception instance
#         print(inst.args)  # arguments stored in .args
#         print(inst)


plivo_keys = PlivoKeys(KEY_DATA)
sms = SMSAPI(plivo_keys)
# voice = VoiceAPI(plivo_keys)

# sms.send_message(+18479519366, "Hello World from SIP plugin")
