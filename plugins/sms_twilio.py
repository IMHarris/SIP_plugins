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
TWILIO_FLOW_NAME = "SIP 1"

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


def send_sms(name, **kwargs):
    """
    Send message to SMS provider
    """
    print(u"SMS message request received from {}: {}".format(name, kwargs[u"msg"]))
    if "dest" in kwargs.keys():
        phone = kwargs["dest"]
    else:
        # todo send back an error message if phone number has not yet been saved.
        phone = save_settings.voice_numbers
    response = SMS().send_message(phone, kwargs["msg"], **kwargs)
    return response


sms_alert = signal(u"sms_alert")
sms_alert.connect(send_sms)


def send_voice(name, **kwargs):
    """
    Send message to voice provider
    """
    print(u"Voice message request received from {}: {}".format(name, kwargs[u"msg"]))
    if "dest" in kwargs.keys():
        phone = kwargs["dest"]
    else:
        phone = save_settings.voice_numbers

    kwargs["override"] = True
    print("kwargs;", kwargs)
    response = Voice().send_message(phone, kwargs[u"msg"], **kwargs)
    # response = Voice().send_message(phone, kwargs[u"msg"], kwargs)
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

    def __init__(self):
        web.header('Access-Control-Allow-Origin', '*')

    def GET(self):
        acct = ""
        auth = ""
        twilio_num = ""
        try:
            with open(
                    SETTINGS_FILENAME, u"r"
            ) as f:  # Read settings from json file if it exists
                settings = json.load(f)
                if "text-auth-token" in settings:
                    auth = settings["text-auth-token"]
                    settings["text-auth-token"] = "PLACEHOLDER"
                if "text-account-id" in settings:
                    acct = settings["text-account-id"]
                if "text-twilio-number" in settings:
                    twilio_num = settings["text-twilio-number"]

                success, _ = Voice.validate_credentials(acct, auth)

        except IOError:  # If file does not exist return empty value
            settings = {}  # Default settings. can be list, dictionary, etc.
            success = False

        # auth_validation = Voice().validate_credentials(acct,auth,twilio_num)
        runtime_values = {
            'sms-enabled': SMS_ENABLED,
            'voice-enabled': VOICE_ENABLED,
            'auth-valid': success
        }
        # passed_vars = json.dumps(runtime_values).encode("utf-8")
        # print("passed_vars", passed_vars)
        print(runtime_values)
        # return template_render.sms_twilio(settings, runtime_values, passed_vars)  # open settings page
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
        if "text-auth-token" in qdict.keys() and "text-account-id" in qdict.keys() and "text-twilio-number" in qdict.keys():
            phone_sid, qdict["text-flow-id"], err_msg = Voice().number_flow_sids(qdict["text-twilio-number"],
                                                                                 qdict["text-account-id"],
                                                                                 qdict["text-auth-token"])
        with open(SETTINGS_FILENAME, u"w") as f:
            json.dump(qdict, f)  # save to file
        raise web.seeother(u"sms-twilio-sp")  # Return user to home page.


class Test(ProtectedPage):

    # Receives messages to send test SMS or Voice messages
    def POST(self):
        qdict = (
            json.loads(str(web.data(), "utf-8"))
        )
        response = {}
        response["textbox"] = "1"
        if "type" in qdict.keys():
            if qdict["type"] == "SMS":
                auth_token = qdict["auth"]
                if auth_token == "PLACEHOLDER":
                    # we need to use the stored auth code
                    settings = load_settings()
                    if "text-auth-token" in settings:
                        auth_token = settings["text-auth-token"]
                # Voice().number_flow_sids(qdict["twilio-num"], qdict["acct"], auth_token)
                response["msg"] = (
                    send_sms(BROADCAST_NAME,
                             msg="This is a {} SMS test message from {}.  Congratulations, you have successfully"
                                 "configured the plugin for SMS messaging".format(BROADCAST_NAME, gv.sd["name"]),
                             dest=qdict["dest"],
                             account_sid=qdict["acct"],
                             auth_token=auth_token,
                             twilio_number=qdict["twilio-num"],
                             override=True
                             )
                )
                response["type"] = "SMS"
            elif qdict["type"] == "Voice":
                auth_token = qdict["auth"]
                if auth_token == "PLACEHOLDER":
                    # we need to use the stored auth code
                    settings = load_settings()
                    if "text-auth-token" in settings:
                        auth_token = settings["text-auth-token"]
                # Voice().number_flow_sids(qdict["twilio-num"], qdict["acct"], auth_token)
                response["msg"] = (send_voice(
                    BROADCAST_NAME,
                    msg="This is a {} voice test message from {}. Congratulations, you have successfully"
                        "configured the plugin for voice messaging".format(BROADCAST_NAME,
                                                                           gv.sd["name"]),
                    dest=qdict["dest"],
                    account_sid=qdict["acct"],
                    auth_token=auth_token,
                    twilio_number=qdict["twilio-num"],
                    override=True)
                )
                response["type"] = "Voice"

            elif qdict["type"] == "CreateFlowID":
                response["textbox"] = "2"
                account_sid = qdict["acct"]
                twilio_number = qdict["twilio-num"]
                auth_token = qdict["auth"]
                if auth_token == "PLACEHOLDER":
                    # we need to use the stored auth code
                    settings = load_settings()
                    if "text-auth-token" in settings:
                        auth_token = settings["text-auth-token"]

                response["msg"] = Voice().update_flow(account_sid, auth_token, twilio_number)
                response["type"] = "CreateFlowID"

            elif qdict["type"] == "ValidateCredentials":
                msg = ""
                # Load response coming in from web page
                response["textbox"] = "2"
                account_sid = qdict["acct"]
                twilio_number = qdict["twilio-num"]
                auth_token = qdict["auth"]

                if auth_token == "PLACEHOLDER":
                    # we need to use the stored auth code
                    settings = load_settings()
                    if "text-auth-token" in settings:
                        auth_token = settings["text-auth-token"]

                validate_response = Voice().validate_twilio_setup(account_sid, auth_token, twilio_number)
                if qdict["voice"]:
                    validate_str = validate_response["final_msg_voice"]
                elif qdict["sms"]:
                    validate_str = validate_response["final_msg_sms"]
                else:
                    validate_str = ""

                response["type"] = "ValidateCredentials"

                if validate_str:
                    response["msg"] = validate_str
                    response["auth_valid"] = validate_response["auth_valid"]
                    response["twilio_number_valid"] = validate_response["twilio_number_valid"]

            else:
                response["msg"] = ""
        else:
            response["msg"] = "There is an unidentified problem validating credentials"
            response["auth_valid"] = False
            response["twilio_number_valid"] = False

        web.header(u"Content-Type", u"text/csv")
        return json.dumps(response).encode()


# *********************************************************
# Twilio objects
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

    def send_message(self, phone, message, **kwargs):
        print("kwargs:", kwargs)
        if "override" in kwargs and kwargs["override"]:

            if "twilio_number" in kwargs:
                twilio_number = kwargs["twilio_number"]
            else:
                twilio_number = ""

            if "auth_token" in kwargs:
                auth_token = kwargs["auth_token"]
            else:
                auth_token = ""

            if "account_sid" in kwargs:
                account_sid = kwargs["account_sid"]
            else:
                account_sid = ""

            login_str = b64encode("{}:{}".format(account_sid, auth_token).encode("utf-8")).decode("ascii")
            headers = {
                'Authorization': 'Basic %s' % login_str,
                'Content-Type': 'application/x-www-form-urlencoded'
            }
        else:
            twilio_number = self.twilio_number
            auth_token = self.auth_token
            account_sid = self.account_sid
            headers = self.headers

        data = {
            'From': twilio_number,
            'To': phone,
            'Body': message
        }
        print('got to twilio send_message', message, phone)
        # Data must be bytes (we're url encoding it)
        data = urllib.parse.urlencode(data).encode('ascii')
        url = 'https://api.twilio.com/2010-04-01/Accounts/{}/Messages.json'.format(account_sid)

        # create Request object for POST
        request = urllib.request.Request(url, data=data, headers=headers, method="POST")

        # Send the request and get the response
        try:
            response = urllib.request.urlopen(request)
            response_str = response.read().decode('utf-8')
        except Exception as e:
            print("Credentials: ", account_sid, auth_token, twilio_number)
            response_str = ('An error occurred sending SMS request. '
                            'Please check your account id, auth code and Twilio number'
                            ': {}').format(e)
            print('an error occurred sending SMS', response_str)
            print('url: ', url)
            print('headers', str(headers))
            print('data', str(data))

        return response_str


class Voice(object):

    def __init__(self):

        self.auth_token = ""
        self.account_sid = ""
        self.twilio_number = ""
        self.url = None
        self.flow_sid = ""

        # Get settings
        saved_settings = load_settings()
        if "text-auth-token" in saved_settings.keys():
            self.auth_token = saved_settings["text-auth-token"]
        if "text-account-id" in saved_settings.keys():
            self.account_sid = saved_settings["text-account-id"]
        if "text-twilio-number" in saved_settings.keys():
            self.twilio_number = saved_settings["text-twilio-number"]
        if "text-flow-id" in saved_settings.keys():
            self.flow_sid = saved_settings["text-flow-id"]

        # self.login_str = b64encode(f"{account_sid}:{auth_token}".encode("utf-8")).decode("ascii")
        self.login_str = b64encode("{}:{}".format(self.account_sid, self.auth_token).encode("utf-8")).decode("ascii")
        self.headers = {
            'Authorization': 'Basic %s' % self.login_str,
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        self.flow_definition = (
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
        self.flow_definition_json = json.loads(self.flow_definition)

    def get_sip_sid(self, account_sid, auth_token):
        # Returns the flow SID associated with TWILIO_FLOW_NAME
        # Returns an empty string if there is no FLOW with TWILIO_FLOW_NAME
        # Will return a string starting with "ERROR:" if there is a problem
        url = "https://studio.twilio.com/v2/Flows"
        voice_sid = ""
        continue_loop = True
        method_failed = False
        response_str = ""
        login_str = b64encode("{}:{}".format(account_sid, auth_token).encode("utf-8")).decode("ascii")
        headers = {
            'Authorization': 'Basic %s' % login_str,
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        while continue_loop:
            req = urllib.request.Request(url, headers=headers)
            # Send the request and read the response
            try:
                with urllib.request.urlopen(req) as response:
                    data = response.read()
            except Exception as e:
                print("SIP SID Failed", e.reason)
                if e.reason == "Unauthorized":
                    response_str = "ERROR:Authentication Error.  Please check your Twilio account ID and auth token."
                else:
                    response_str = ('ERROR:An error occurred sending voice request. '
                                    'Please check your Twilio account ID, auth token, '
                                    'and Twilio phone number: {}').format(e)
                method_failed = True
                print(response_str)
                break
            # Decoding the response to string format
            data = data.decode('utf-8')
            json_response = json.loads(data)
            flows = json_response['flows']
            for flow in flows:
                # Iterate through the returned flows and look for the SIP flow
                if flow['friendly_name'] == TWILIO_FLOW_NAME:
                    voice_sid = flow['sid']
                    print('VoiceSID found: ', voice_sid)
                    break

            url = json_response['meta']['next_page_url']
            if voice_sid or str(url) == 'None':
                continue_loop = False

        if method_failed:
            return response_str
        else:
            return voice_sid

    def is_flow_config_current(self, flow_sid, account_sid, auth_token):
        login_str = b64encode("{}:{}".format(account_sid, auth_token).encode("utf-8")).decode("ascii")
        headers = {
            'Authorization': 'Basic %s' % login_str,
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        url = "https://studio.twilio.com/v2/Flows/%s" % flow_sid
        req = urllib.request.Request(url, headers=self.headers)
        # Send the request and read the response
        with urllib.request.urlopen(req) as response:
            data = response.read()

        twilio_data_json = json.loads(data.decode('utf-8'))
        if self.flow_definition_json == twilio_data_json['definition']:
            return True
        else:
            return False

    def number_flow_sids(self, twilio_number, account_sid, auth_token):
        """
        Get sids for twilio number and its attached flow
        Returns tuple: (number sid, flow sid, error message)
        """
        phone_sid = ""
        err_msg = ""

        login_str = b64encode("{}:{}".format(account_sid, auth_token).encode("utf-8")).decode("ascii")
        headers = {
            'Authorization': 'Basic %s' % login_str,
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        url = ("https://api.twilio.com/2010-04-01/Accounts/%s/IncomingPhoneNumbers.json?PhoneNumber=%s"
               % (account_sid, twilio_number))
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req) as response:
                data = response.read()
        except Exception as e:
            err_msg = str(e)
            return "", "", err_msg

        json_response = json.loads(data.decode('utf-8'))
        print("number response: ", data.decode('utf-8'))
        if "incoming_phone_numbers" in json_response.keys() and "sid" in json_response["incoming_phone_numbers"][0]:
            phone_sid = json_response["incoming_phone_numbers"][0]['sid']
        if phone_sid == "":
            err_msg = ("Unable to find twilio phone number %s configured to twilio account" % twilio_number)
            return "", "", err_msg

        # Now check the flow attached to the number
        if (not ("voice_url" in json_response["incoming_phone_numbers"][0].keys()) or
                len(json_response["incoming_phone_numbers"][0]['voice_url']) == 0 or
                len(json_response["incoming_phone_numbers"][0]["voice_url"].split("Flows/")) == 0):
            err_msg = "No voice flow is attached to the twilio phone number."
            return phone_sid, "", err_msg

        parsed_url = json_response["incoming_phone_numbers"][0]["voice_url"].split("Flows/")
        flow_sid = parsed_url[1]
        print("Number SID:", phone_sid, "Flow SID: ", flow_sid)
        return phone_sid, flow_sid, err_msg

    @staticmethod
    def validate_credentials(account_sid, auth_token):
        success = False
        login_str = b64encode("{}:{}".format(account_sid, auth_token).encode("utf-8")).decode("ascii")
        headers = {
            'Authorization': 'Basic %s' % login_str,
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        # Query for the phone numbers.  If we get a valid response, we know
        # The login credentials are good
        url = "https://api.twilio.com/2010-04-01/Accounts/%s/IncomingPhoneNumbers.json" % account_sid
        req = urllib.request.Request(url, headers=headers)
        # Send the request and read the response
        try:
            with urllib.request.urlopen(req) as response:
                data = response.read()
                success = True
                response_str = data.decode('utf-8')
        except Exception as e:
            response_str = str(e)

        return success, response_str

    def validate_twilio_setup(self, account_sid, auth_token, twilio_number):
        # Create headers with the passed credentials
        response_dict = {}
        response_dict["auth_valid"] = False
        response_dict["auth_token"] = ""
        response_dict["twilio_number_valid"] = False
        response_dict["twilio_number_msg"] = ""
        response_dict["flow_attached"] = False
        response_dict["flow_attached_msg"] = ""
        response_dict["flow_current"] = False
        response_dict["final_msg_voice"] = ""
        response_dict["final_msg_sms"] = ""

        success, error_msg = self.validate_credentials(account_sid, auth_token)
        if not success:
            response_dict["auth_message"] = error_msg
            response_dict["final_msg_voice"] = ("Unable to log in to your Twilio account.  "
                                                "Please check your Twilio account ID and auth token. / %s") % error_msg
            response_dict["final_msg_sms"] = response_dict["final_msg_voice"]
            return response_dict

        # If we've gotten this far, credentials are valid.  Need to check the phone number next

        phone_sid, flow_sid, err_msg = self.number_flow_sids(twilio_number, account_sid, auth_token)

        if phone_sid == "":
            response_dict["twilio_number_msg"] = (
                "Unable to find twilio phone number %s configured in your twilio account. Error: " % twilio_number,
                err_msg)
            response_dict["final_msg_voice"] = ("Credentials validated but unable to find twilio phone number %s "
                                                "configured in your twilio account" % twilio_number)
            response_dict["final_msg_sms"] = response_dict["final_msg_voice"]
            print("number fetch blew up")
            return response_dict
        else:
            response_dict["final_msg_voice"] = "Twilio credentials and phone number validated successfully."
            response_dict["final_msg_sms"] = response_dict["final_msg_voice"]
            response_dict["twilio_number_valid"] = True

        # Now check the flow attached to the number
        if flow_sid == "":
            response_dict["flow_attached_msg"] = "No voice flow is attached to the twilio phone number."
            response_dict["final_msg_voice"] = (
                    "There is no voice flow attached to the twilio phone number %s, use the "
                    "create/ update button to create a new flow in your Twilio account and"
                    " attach it to your phone number." % twilio_number)
            return response_dict

        response_dict["flow_attached"] = True

        # Check that the attached flow matches current flow
        url = "https://studio.twilio.com/v2/Flows/%s" % flow_sid
        # print("flow fetch url", url)
        login_str = b64encode("{}:{}".format(account_sid, auth_token).encode("utf-8")).decode("ascii")
        headers = {
            'Authorization': 'Basic %s' % login_str,
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req) as response:
                data = response.read()
        except Exception as e:
            response_str = str(e)
            response_dict["flow_attached_msg"] = ("An unexpected error occurred fetching the Twilio flow information."
                                                  " / " % response_str)
            response_dict["final_msg_voice"] = response_dict["flow_attached_msg"]
            return response_dict

        print("flow found:", data.decode('utf-8'))
        json_response = json.loads(data.decode('utf-8'))
        flow_name = json_response.get('friendly_name')
        if flow_name != TWILIO_FLOW_NAME:
            response_dict["flow_attached_msg"] = "Attached flow name does not match Twilio flow"
            response_dict["final_msg_voice"] = ("Credentials and phone validated, however the flow attached to your "
                                                "Twilio phone number was not created by the "
                                                "SIP Twilio plug-in and may not work properly with this app. "
                                                "Use the create/update button to create a new flow and attach it to "
                                                "your Twilio phone number. This operation will not delete the current "
                                                "flow. It will create a new flow and attach it to your Twilio phone "
                                                "number. If another application is using this phone number as well, "
                                                "the SIP flow may not work properly for that application once "
                                                "attached to your Twilio phone number.")
            return response_dict

        response_dict["flow_attached_msg"] = "Flow was created by SIP plug-in"
        response_dict["final_msg_voice"] = "Flow was created by SIP plug-in"

        # Flow is found and was created by SIP.  Check to see if it is current
        if json_response["definition"] != self.flow_definition_json:
            response_dict["flow_attached_msg"] = "Flow was created by SIP plug-in and does not match current flow"
            response_dict["final_msg_voice"] = ("Your flow was created by the SIP plug-in, but isn't current.  Use the "
                                                "create/update button to update the %s flow configuration on your Twilio "
                                                "account") % TWILIO_FLOW_NAME
            response_dict["flow_current"] = False
            return response_dict
        else:
            response_dict["flow_current"] = True

        response_dict["final_msg_voice"] = "Credentials validated, phone number validated, flow is up to date."
        return response_dict

    def update_flow(self, account_sid, auth_token, twilio_number):

        login_str = b64encode("{}:{}".format(account_sid, auth_token).encode("utf-8")).decode("ascii")
        headers = {
            'Authorization': 'Basic %s' % login_str,
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        error_msg = ""
        flow_created = False
        flow_updated = False
        sip_sid = self.get_sip_sid(account_sid, auth_token)

        if sip_sid.startswith("ERROR:"):
            response_str = ("An error was encountered creating/updating the voice flow: %s" %
                            sip_sid.split("ERROR:", 1)[1])
        elif sip_sid:
            # Flow exists.  Fetching the flow resource to compare against current configuration
            if self.is_flow_config_current(sip_sid, account_sid, auth_token):
                print('Uploaded Twilio flow is current')
                response_str = "Flow configured on Twilio is current"
            else:
                print('Current flow does not match uploaded value. Will update')
                url = 'https://studio.twilio.com/v2/Flows/%s' % sip_sid
                data = {
                    'Status': 'published',
                    'Definition': self.flow_definition,
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
                    flow_updated = True
                    response_str = "Twilio flow configuration updated successfully"
                else:
                    response_str = "There was a problem updating the Twilio flow. " + response_str
                print("Response flow update request made:", response_str)

        else:
            # flow doesn't exist, need to create it and read back the flow id
            url = "https://studio.twilio.com/v2/Flows"
            data = {
                'FriendlyName': TWILIO_FLOW_NAME,
                'Status': 'published',
                'Definition': self.flow_definition,
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
                flow_created = True
                saved_settings = load_settings()
                # Todo: I don't think we need to save back the flow_sid anymore
                saved_settings['text-flow-id'] = response_json["sid"]
                sip_sid = response_json["sid"]
                with open(SETTINGS_FILENAME, u"w") as f:
                    json.dump(saved_settings, f)  # save to file
                response_str = ("Twilio flow configuration created successfully. Next, you need to update your "
                                "phone number configuration on your Twilio account and tie it to the "
                                "flow we just created:'%s'" % TWILIO_FLOW_NAME)
            else:
                response_str = "There was a problem updating the Twilio flow. " + response_str

            print("Create flow request made.:", response_str)

            # Ensure the phone number is tied to the sip_sid
        # todo: start here
        # We've created/updated the SIP flow, now we need to ensure it is connected to the phone number
        url = ("https://api.twilio.com/2010-04-01/Accounts/%s/IncomingPhoneNumbers.json?PhoneNumber=%s"
               % (account_sid, twilio_number))
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req) as response:
                response_str = response.read().decode('utf-8')
        except Exception as e:
            response_str = str(e)
            print("number fetch blew up")
            return response_str

        response_json = json.loads(response_str)
        voice_url = response_json["incoming_phone_numbers"][0]['voice_url']
        twilio_number_sid = response_json["incoming_phone_numbers"][0]['sid']
        split_string = voice_url.split("/Flows/")
        if len(split_string) > 1:
            attached_flow_sid = split_string[1]
            print("flow attached to number:", attached_flow_sid)
        else:
            attached_flow_sid = None
            print("'/Flows/' not found in the voice_url")

        if attached_flow_sid:
            if attached_flow_sid == sip_sid:
                if flow_updated:
                    # Flow has been updated and is attached to the Twilio number
                    response_str = "Flow has been updated and confirmed connected to your Twilio phone number."
                    return response_str
            else:
                # A different flow is attached to the phone number.  Need to replace it.
                # First need to get the friendly name of the attached flow
                url = "https://studio.twilio.com/v2/Flows/%s" % attached_flow_sid
                req = urllib.request.Request(url, headers=self.headers)
                with urllib.request.urlopen(req) as response:
                    data = response.read()
                attached_flow_friendly = json.loads(data.decode('utf-8'))["friendly_name"]
                print("Friendly name of currently attached Twilio flow:", attached_flow_friendly)
                url = ("https://api.twilio.com/2010-04-01/Accounts/%s/IncomingPhoneNumbers/%s.json"
                       % (account_sid, twilio_number_sid))
                voice_url = ("https://webhooks.twilio.com/v1/Accounts/%s/Flows/%s"
                             % (account_sid, sip_sid))
                data = {
                    'VoiceUrl': voice_url
                }
                print("url", url)
                print("voice_url", voice_url)
                print("data", data)

                data = urllib.parse.urlencode(data).encode('ascii')

                # create Request object for POST
                request = urllib.request.Request(url, data=data, headers=self.headers, method="POST")
                response = urllib.request.urlopen(request)
                response_str = response.read().decode('utf-8')
                if flow_updated:
                    response_str = ("Flow updated and attached to Twilio phone number, replacing the %s "
                                    "flow previously attached" % attached_flow_friendly)
                elif flow_created:
                    response_str = ("A new flow was created and attached to Twilio phone number, replacing the %s flow."
                                    "previously attached." % attached_flow_friendly)
                else:
                    response_str = ("SIP flow attached to Twilio phone number, replacing the %s flow "
                                    "previously attached." % attached_flow_friendly)
                # response_str = response.read().decode('utf-8')

        print("number fetch response string:", response_str)

        return response_str

    def send_message(self, phone, message, **kwargs):

        if "override" in kwargs and kwargs["override"]:

            if "twilio_number" in kwargs:
                twilio_number = kwargs["twilio_number"]
            else:
                twilio_number = ""

            if "auth_token" in kwargs:
                auth_token = kwargs["auth_token"]
            else:
                auth_token = ""

            if "account_sid" in kwargs:
                account_sid = kwargs["account_sid"]
                phone_sid, flow_sid, err_msg = self.number_flow_sids(twilio_number, account_sid, auth_token)
            else:
                account_sid = ""
                flow_sid = ""

            login_str = b64encode("{}:{}".format(account_sid, auth_token).encode("utf-8")).decode("ascii")
            headers = {
                'Authorization': 'Basic %s' % login_str,
                'Content-Type': 'application/x-www-form-urlencoded'
            }
        else:
            flow_sid = self.flow_sid
            twilio_number = self.twilio_number
            headers = self.headers
            flow_sid = self.flow_sid

        data = {
            'To': phone,
            'From': twilio_number,
            'Parameters': json.dumps(
                {'my_message': message})
        }

        data = urllib.parse.urlencode(data).encode('ascii')
        url = 'https://studio.twilio.com/v2/Flows/{}/Executions'.format(flow_sid)

        request = urllib.request.Request(url, data=data, headers=headers)
        try:
            with urllib.request.urlopen(request) as response:
                response_body = response.read().decode()
                response_str = str(response_body)
        except Exception as e:
            response_str = ('An error occurred sending voice request. '
                            'Please check your Twilio account ID, auth token, '
                            'and Twilio phone number: {}'.format(e))

        return response_str
