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

# local module imports
from blinker import signal
import gv  # Get access to SIP's settings
from sip import template_render  # Needed for working with web.py templates
from urls import urls  # Get access to SIP's URLs
import web  # web.py framework
from webpages import ProtectedPage  # Needed for security

SMS_ENABLED = True
VOICE_ENABLED = True

sms_numbers = ""
voice_numbers = ""

# Add new URLs to access classes in this plugin.
urls.extend([
    u"/sms-plivo-sp", u"plugins.sms_plivo.settings",
    u"/sms-plivo-save", u"plugins.sms_plivo.save_settings",
    u"/sms-plivo-test", u"plugins.sms_plivo.Test"

])

# Add this plugin to the PLUGINS menu ["Menu Name", "URL"], (Optional)
gv.plugin_menu.append([_(u"SMS Plivo Plugin"), u"/sms-plivo-sp"])

"""
Event Triggers
"""


def advertise_presence(name, **kw):
    """
    Respond to query looking for notification plugins
    When a "notification_checkin" message is received, this plugin will advertise its ability
    to accept sms and voice notifications by responding with a "notification presence" message.
    """
    notification_presence = signal("notification_presence")

    # Notify that plivo_sms is listening for sms messages
    if SMS_ENABLED:
        notification_presence.send(u"Plivo", txt=u"sms")

    # Notify that plivo_sms is listening for voice messages
    if VOICE_ENABLED:
        notification_presence.send(u"Plivo", txt=u"voice")


notification_checkin = signal(u"notification_checkin")
notification_checkin.connect(advertise_presence)


def send_sms(name, **kw):
    """
    Send message to SMS provider
    """
    print(u"SMS message received from {}: {}".format(name, kw[u"msg"]))
    sms.send_message(save_settings.sms_numbers, kw[u"msg"])


sms_alert = signal(u"sms_alert")
sms_alert.connect(send_sms)


def send_voice(name, **kw):
    """
    Send message to voice provider
    """
    print(u"Voice message received from {}: {}".format(name, kw[u"msg"]))
    voice.send_message(save_settings.voice_numbers, kw[u"msg"])


voice_alert = signal(u"voice_alert")
voice_alert.connect(send_voice)


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

        runtime_values = {
            'sms-enabled': SMS_ENABLED,
            'voice-enabled': VOICE_ENABLED,
        }

        return template_render.sms_plivo(settings, runtime_values)  # open settings page


class save_settings(ProtectedPage):
    """
    Save user input to json file.
    Will create or update file when SUBMIT button is clicked
    CheckBoxes only appear in qdict if they are checked.
    """
    sms_numbers = ""
    voice_numbers = ""

    def GET(self):
        qdict = (
            web.input()
        )  # Dictionary of values returned as query string from settings page.

        # Save the phone numbers to local variables and reformat for plivo
        if "text-sms" in qdict.keys():
            save_settings.sms_numbers = qdict["text-sms"].replace(",", "<")
        if "text-voice" in qdict.keys():
            save_settings.voice_numbers = qdict["text-voice"].replace(",", "p")
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


class Test(ProtectedPage):
    def GET(self):
        qdict = (
            web.input()
        )  # Dictionary of values returned as query string .
        print("hi", qdict)


class PlivoKeys(object):
    # Loads the authentication keys from the KEY_DATA file
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
        self.src = plivokeys.src()
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

    def send_message(self, phone, voicemessage,params=None):

        try:
            params = {
                'from': self.src,  # Sender's phone number with country code
                'to': phone,  # Receiver's phone Number with country code
                'items': voicemessage,  # Your SMS Text Message - English
            }

            print('Plivo sending SMS msg: ', voicemessage)
            response = self._request('POST', '/Message/', data=params)

            # Prints the complete response
            print('Voice message submitted.  Response: ', str(response))
            return response

        except Exception as inst:
            print('Unable to send voice message')
            print(type(inst))  # the exception instance
            print(inst.args)  # arguments stored in .args
            print(inst)


plivo_keys = PlivoKeys(KEY_DATA)
sms = SMSAPI(plivo_keys)
voice = VoiceAPI(plivo_keys)
