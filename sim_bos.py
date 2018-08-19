#!/usr/bin/env python
""" PTC-Sim's Back Office Server (BOS). 
    Publishes the PTC-Sim web interface via Flask and watches the message
    broker (via TCP/IP) for device and locomotive status msgs. The web display 
    is then updated to reflect these statuses, including Google Earth location
    mapping. 
    The BOS may also also send outgoing computer-aided-dispatch (CAD) msgs to
    each device.

    Author: Dustin Fast, 2018
"""

from time import sleep
from threading import Thread
from subprocess import check_output

from lib_app import bos_log
from lib_msging import Client, Queue
from lib_track import Track, Loco, Milepost

from lib_app import APP_NAME, REFRESH_TIME
from lib_msging import BROKER, SEND_PORT, FETCH_PORT, BOS_EMP

# Attempt to import flask and prompt for install on fail
while True:
    try:
        from flask import Flask, render_template, jsonify
        break
    except:
        prompt = 'Flask is required, install it? (Y/n): '
        install_pip = raw_input(prompt)

        if install_pip == 'Y':
            print('Installing... Please wait.')
            result = check_output('pip install flask')
            print('Success!')
        else:
            print('Exiting.')
            exit()


# Web state vars
locos_table = ''
loco_status = {}
current_loco_sel = ''


# Flask Web Handlers 
web = Flask(__name__)

@web.route('/' + APP_NAME)
def home():
    return render_template('home.html')


@web.route('/_home_content', methods=['GET'])
def update_home():
    global locos_table
    return jsonify(locos_table=locos_table, loco_status=loco_status)


class BOS(object):
    """ The Back Office Server. Consists of a messaging client and status
        watcher thread that fetches messages from the broker over TCP/IP, in
        addition to the web interface.
    """
    def __init__(self):
        self.track = Track()  # Track object instance

        # Messaging client
        self.msg_client = Client(BROKER, SEND_PORT, FETCH_PORT)

        # Threads
        self.running = False  # Thread kill flag
        self.status_watcher_thread = Thread(target=self._statuswatcher)
        self.webupdate_thread = Thread(target=self._webupdater)

    def start(self, debug=False):
        """ Start the BOS. I.e., the status watcher thread and web interface.
        """
        bos_log.info('BOS Starting.')
        
        self.running = True
        self.status_watcher_thread.start()
        self.webupdate_thread.start()
        global locos_table
        locos_table = 'teststatus1'
        web.run(debug=debug)  # Web interface, blocks until killed from console

        # Do shutdown
        print('\nBOS Stopping... Please wait.')
        self.running = False
        self.status_watcher_thread.join(timeout=REFRESH_TIME)
        self.webupdate_thread.join(timeout=REFRESH_TIME)
        bos_log.info('BOS stopped.')

    def _statuswatcher(self):
        """ The status message watcher thread - watches the broker for msgs
            addressed to it and processes them. See 
        """
        while self.running:
            # Fetch the next available msg, if any
            msg = None
            try:
                msg = self.msg_client.fetch_next_msg(BOS_EMP)
            except Queue.Empty:
                bos_log.info('Msg queue empty.')
            except Exception:
                bos_log.warn('Could not connect to broker.')

            # Process loco status msg. Msg should be of form given in 
            # docs/app_messaging_spec.md, Msg ID 6000.
            if msg:
                try:
                    locoID = msg.payload['loco']
                    milepost = Milepost(msg.payload['milepost'],
                                        msg.payload['lat'],
                                        msg.payload['long'])

                    active_conns = eval(msg.payload['conns'])  # evals to dict

                    # Update the loco object
                    loco = self.track.locos.get(locoID)
                    if not loco:
                        loco = Loco(locoID, self.track)

                    loco.update(msg.payload['speed'],
                                msg.payload['heading'],
                                msg.payload['direction'],
                                milepost,
                                active_conns)

                    bos_log.info('Processed status msg for loco ' + loco.ID)
                except KeyError:
                    bos_log.error('Malformed status msg: ' + str(msg.payload))

            sleep(REFRESH_TIME)
        
    def _webupdater(self):
        """ The web updater thread. Parses the BOS's local track object
            devices and updates the web output (Google Earth/KMLs,
            DataTables, etc.)
            accordingly.
        """

        # Update loco display
        global locos_table
        for i in range(100):
            locos_table = str(i)
            sleep(2)


if __name__ == '__main__':
    # Start the Back Office Server
    print('-- ' + APP_NAME + ': Back Office Server - CTRL + C quits --\n')
    sleep(.2)  # Ensure print statment occurs before flask output
    bos = BOS().start(debug=True)  # Blocks until CTRL+C
    # TODO: BOS REPL
