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
# import json  # for working with data file

# local module imports
from blinker import signal
import gv  # Get access to SIP's settings
from sip import template_render  # Needed for working with web.py templates
from urls import urls  # Get access to SIP's URLs
import web  # web.py framework
from webpages import ProtectedPage  # Needed for security

# *****
# Twilio Specific imports
from base64 import b64encode
import urllib.request, urllib.parse
import datetime
import json
# *****

SMS_ENABLED = True  # Toggles SMS option display to user
VOICE_ENABLED = True  # Toggles voice option display to user
BROADCAST_NAME = u"Twilio"  # App name broadcast to other plugins
SETTINGS_FILENAME = u"./data/sms_twilio.json"
TWILIO_FLOW_NAME = "SIP 10"

# Add new URLs to access classes in this plugin.
urls.extend([
    u"/sms-twilio-sp", u"plugins.sms_twilio.settings",
    u"/sms-twilio-save", u"plugins.sms_twilio.save_settings",
    u"/sms-twilio-test", u"plugins.sms_twilio.Test"
])

# Add this plugin to the PLUGINS menu
gv.plugin_menu.append([_(u"SMS Twilio"), u"/sms-twilio-sp"])

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

    # Notify that the plugin is listening for sms messages
    if SMS_ENABLED:
        notification_presence.send(BROADCAST_NAME, txt=u"sms")

    # Notify that plugin is listening for voice messages
    if VOICE_ENABLED:
        notification_presence.send(BROADCAST_NAME, txt=u"voice")


notification_checkin = signal(u"notification_checkin")
notification_checkin.connect(advertise_presence)


def load_settings():
    try:
        with open(
                SETTINGS_FILENAME, u"r"
        ) as f:  # Read settings from json file if it exists
            saved_settings = json.load(f)
    except IOError:  # If file does not exist return empty value
        saved_settings = {}  # Default settings. can be list, dictionary, etc.
    return saved_settings


def send_sms(name, **kw):
    """
    Send message to SMS provider
    """
    print(u"SMS message request received from {}: {}".format(name, kw[u"msg"]))
    if "dest" in kw.keys():
        phone = kw["dest"]
    else:
        # todo send back an error message if phone number has not yet been saved.
        phone = save_settings.voice_numbers
    response = SMS().send_message(kw[u"msg"], phone)
    return response


# Todo: what is this????
sms_alert = signal(u"sms_alert")
sms_alert.connect(send_sms)


def send_voice(name, **kw):
    """
    Send message to voice provider
    """
    print(u"Voice message request received from {}: {}".format(name, kw[u"msg"]))
    if "dest" in kw.keys():
        phone = kw["dest"]
    else:
        phone = save_settings.voice_numbers
    response = Voice().send_message(kw[u"msg"], phone)
    print("voice response", response)
    return response


voice_alert = signal(u"voice_alert")
voice_alert.connect(send_voice)

"""
Web page classes
"""


class settings(ProtectedPage):
    """
    Load an html page for entering plugin settings.
    """

    def GET(self):
        try:
            with open(
                    SETTINGS_FILENAME, u"r"
            ) as f:  # Read settings from json file if it exists
                settings = json.load(f)
                if "text-auth-token" in settings:
                    settings["text-auth-token"] = "PLACEHOLDER"
        except IOError:  # If file does not exist return empty value
            settings = {}  # Default settings. can be list, dictionary, etc.

        runtime_values = {
            'sms-enabled': SMS_ENABLED,
            'voice-enabled': VOICE_ENABLED,
        }

        return template_render.sms_twilio(settings, runtime_values)  # open settings page


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

        saved_settings = load_settings()
        # Save the phone numbers to local variables and reformat for twilio
        if "text-sms-phone" in qdict.keys():
            qdict["text-sms-phone"] = qdict["text-sms-phone"].replace(" ", "")
        if "text-voice-phone" in qdict.keys():
            qdict["text-voice-phone"] = qdict["text-voice-phone"].replace(" ", "")
        if "text-auth-token" in qdict.keys() and (not qdict["text-auth-token"].strip() or qdict["text-auth-token"] ==
                                                  "PLACEHOLDER") and "text-auth-token" in saved_settings.keys():
            qdict["text-auth-token"] = saved_settings["text-auth-token"]
        if "text-flow-id" in saved_settings.keys():
           qdict["text-flow-id"] = saved_settings["text-flow-id"]
        with open(SETTINGS_FILENAME, u"w") as f:
            json.dump(qdict, f)  # save to file
        raise web.seeother(u"/")  # Return user to home page.


class Test(ProtectedPage):

    # Receives messages to send test SMS or Voice messages
    def POST(self):
        qdict = (
            json.loads(str(web.data(), "utf-8"))
        )
        if "type" in qdict.keys():
            if qdict["type"] == "SMS":
                response = (
                    send_sms(BROADCAST_NAME,
                             msg="This is a {} SMS test message from {}.".format(BROADCAST_NAME, gv.sd["name"]),
                             dest=qdict["dest"])
                )
            elif qdict["type"] == "Voice":
                response = (
                    send_voice(BROADCAST_NAME,
                               msg="This is a {} voice test message from {}.".format(BROADCAST_NAME, gv.sd["name"]),
                               dest=qdict["dest"])
                )
            elif qdict["type"] == "CreateFlowID":
                response = (
                        '2' +
                        Voice().update_flow(TWILIO_FLOW_NAME)
                )
            else:
                response = ""
        else:
            response = ""

        web.header(u"Content-Type", u"text/csv")
        return response

# *********************************************************
#
#  Everything from here down is mostly Twilio Specific
#
# *********************************************************




class SMS(object):
    def __init__(self):

        # Get settings
        saved_settings = load_settings()
        if "text-auth-token" in saved_settings.keys():
            self.auth_token = saved_settings["text-auth-token"]
        else:
            self.auth_token = ""
        if "text-account-id" in saved_settings.keys():
            self.account_sid = saved_settings["text-account-id"]
        else:
            self.account_sid = ""
        if "text-twilio-number" in saved_settings.keys():
            self.twilio_number = saved_settings["text-twilio-number"]
        else:
            self.twilio_number = ""

        self.login_str = b64encode("{}:{}".format(self.account_sid, self.auth_token).encode("utf-8")).decode("ascii")
        self.headers = {
            'Authorization': 'Basic %s' % self.login_str,
            'Content-Type': 'application/x-www-form-urlencoded'
        }

    def send_message(self, text_msg, phone):

        data = {
            'From': self.twilio_number,
            'To': phone,
            'Body': text_msg
        }
        print('got to twilio send_message', text_msg, phone)
        # Data must be bytes (we're url encoding it)
        data = urllib.parse.urlencode(data).encode('ascii')
        url = 'https://api.twilio.com/2010-04-01/Accounts/{}/Messages.json'.format(self.account_sid)

        # create Request object for POST
        request = urllib.request.Request(url, data=data, headers=self.headers, method="POST")

        # Send the request and get the response
        try:
            response = urllib.request.urlopen(request)
            response_str = response.read().decode('utf-8')
        except Exception as e:
            response_str = 'An error occurred sending SMS request: {}'.format(e)
            print('an error occurred sending SMS', response_str)
            print('url: ', self.url)
            print('headers', str(self.headers))
            print('data', str(data))

        return response_str


class Voice(object):

    def __init__(self):

        # Get settings
        saved_settings = load_settings()
        if "text-auth-token" in saved_settings.keys():
            self.auth_token = saved_settings["text-auth-token"]
        else:
            self.auth_token = ""
        if "text-account-id" in saved_settings.keys():
            self.account_sid = saved_settings["text-account-id"]
        else:
            self.account_sid = ""
        if "text-twilio-number" in saved_settings.keys():
            self.twilio_number = saved_settings["text-twilio-number"]
        else:
            self.twilio_number = ""
        if "text-flow-id" in saved_settings.keys():
            self.flow_id = saved_settings["text-flow-id"]
        else:
            self.flow_id = ""

        # self.login_str = b64encode(f"{account_sid}:{auth_token}".encode("utf-8")).decode("ascii")
        self.login_str = b64encode("{}:{}".format(self.account_sid, self.auth_token).encode("utf-8")).decode("ascii")
        self.headers = {
            'Authorization': 'Basic %s' % self.login_str,
            'Content-Type': 'application/x-www-form-urlencoded'
        }

    def update_flow(self, twilio_flow_name):
        # If flow already exists, we will update it.  If not, we will create it.
        method_failed = False
        flow_definition = (
            '{"states": [{"transitions": [{"event": "incomingMessage"}, {"event": "incomingCall"}, {"event": '
            '"incomingConversationMessage"}, {"event": "incomingRequest", "next": "make_the_call"}, '
            '{"event": "incomingParent"}], "type": "trigger", "name": "Trigger", "properties": {"offset": {'
            '"y": 0, "x": 0}}}, {"transitions": [{"event": "audioComplete"}], "type": "say-play", '
            '"name": "play_the_message", "properties": {"say": "{{flow.data.my_message}}", '
            '"voice": "Polly.Nicole", "language": "en-AU", "loop": 1, "offset": {"y": 480, "x": 10}}}, '
            '{"transitions": [{"event": "answered", "next": "play_the_message"}, {"event": "busy"}, '
            '{"event": "noAnswer"}, {"event": "failed"}], "type": "make-outgoing-call-v2", '
            '"name": "make_the_call", "properties": {"trim": "do-not-trim", '
            '"machine_detection_silence_timeout": "5000", "from": "{{flow.channel.address}}", '
            '"recording_status_callback": "", "record": false, "machine_detection_speech_threshold": "2400", '
            '"to": "{{contact.channel.address}}", "detect_answering_machine": false, "sip_auth_username": "", '
            '"machine_detection": "Enable", "send_digits": "", "machine_detection_timeout": "30", "timeout": '
            '60, "offset": {"y": 220, "x": -10}, "machine_detection_speech_end_threshold": "1200", '
            '"sip_auth_password": "", "recording_channels": "mono"}}], "initial_state": "Trigger", '
            '"flags": {"allow_concurrent_calls": true}, "description": "A New Flow"}')
        flow_definition_json = json.loads(flow_definition)
        url = "https://studio.twilio.com/v2/Flows"
        voice_sid = ""
        continue_loop = True
        while continue_loop:
            req = urllib.request.Request(url, headers=self.headers)
            # Send the request and read the response
            try:
                with urllib.request.urlopen(req) as response:
                    data = response.read()
            except Exception as e:
                if e.reason == "Unauthorized":
                    response_str = "Authentication Error.  Please check your Twilio account ID and auth token."
                else:
                    response_str = 'An error occurred sending voice request: {}'.format(e)
                method_failed = True
                print(response_str)
                break
            # Decoding the response to string format
            data = data.decode('utf-8')
            json_response = json.loads(data)

            flows = json_response['flows']
            for flow in flows:
                if flow['friendly_name'] == twilio_flow_name:
                    voice_sid = flow['sid']
                    print('VoiceSID found: ', voice_sid)
                    break

            url = json_response['meta']['next_page_url']
            if voice_sid or str(url) == 'None':
                continue_loop = False

        if method_failed:
            pass
        elif voice_sid and not method_failed:
            # Flow exists.  Fetching the flow resource to compare against current configuration
            url = "https://studio.twilio.com/v2/Flows/%s" % voice_sid
            req = urllib.request.Request(url, headers=self.headers)
            # Send the request and read the response
            with urllib.request.urlopen(req) as response:
                data = response.read()

            twilio_data_json = json.loads(data.decode('utf-8'))
            if flow_definition_json == twilio_data_json['definition']:
                print('Uploaded  Twilio flow is current')
                response_str = "Flow configured on Twilio is current. No action necessary"
            else:
                print('Current flow does not match uploaded value. Will update')
                url = 'https://studio.twilio.com/v2/Flows/%s' % voice_sid
                data = {
                    'Status': 'published',
                    'Definition': flow_definition,
                    'CommitMessage': 'Updated by SIP Twilio_SMS plugin'
                }

                # Data must be bytes (we're url encoding it)
                data = urllib.parse.urlencode(data).encode('ascii')

                # create Request object for POST
                request = urllib.request.Request(url, data=data, headers=self.headers, method="POST")
                response = urllib.request.urlopen(request)
                response_str = response.read().decode('utf-8')
                response_json = json.loads(response_str)
                if "status" in response_json.keys() and response_json['status'] == 'published':
                    response_str = "Twilio flow configuration updated successfully"
                else:
                    response_str = "There was a problem updating the Twilio flow. " + response_str
                print("Response flow update request made:", response_str)

        else:
            # flow doesn't exist, need to create it and read back the flow id
            url = "https://studio.twilio.com/v2/Flows"
            data = {
                'FriendlyName': twilio_flow_name,
                'Status': 'published',
                'Definition': flow_definition,
                'CommitMessage': 'Set up by SIP Twilio_SMS plugin on %s' % datetime.datetime.now().strftime(
                        "%m/%d/%Y, %I:%M:%S %p")
            }

            # Data must be bytes (we're url encoding it)
            data = urllib.parse.urlencode(data).encode('ascii')

            # create Request object for POST
            request = urllib.request.Request(url, data=data, headers=self.headers, method="POST")
            response = urllib.request.urlopen(request)
            response_str = response.read().decode('utf-8')
            print("Flow creation response string:", response_str)
            response_json = json.loads(response_str)
            if "status" in response_json.keys() and response_json['status'] == 'published':
                # A flow configuration has been created.  Need to save the flow ID to our settings:
                saved_settings = load_settings()
                saved_settings['text-flow-id'] = response_json["sid"]
                with open(SETTINGS_FILENAME, u"w") as f:
                    json.dump(saved_settings, f)  # save to file
                response_str = ("Twilio flow configuration created successfully. Next, you need to update your "
                                "phone number configuration on your Twilio account and tie it to the "
                                "flow we just created:'%s'" % twilio_flow_name)
            else:
                response_str = "There was a problem updating the Twilio flow. " + response_str

            print("Create flow request made.:", response_str)
        return response_str

    def send_message(self, voice_msg, phone):

        data = {
            'To': phone,
            'From': self.twilio_number,
            'Parameters': json.dumps(
                {'my_message': voice_msg})
        }

        data = urllib.parse.urlencode(data).encode('ascii')
        url = 'https://studio.twilio.com/v2/Flows/{}/Executions'.format(self.flow_id)

        request = urllib.request.Request(url, data=data, headers=self.headers)
        try:
            with urllib.request.urlopen(request) as response:
                response_body = response.read().decode()
                response_str = str(response_body)
        except Exception as e:
            response_str = 'An error occurred sending voice request: {}'.format(e)

        return response_str