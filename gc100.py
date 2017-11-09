"""A TCP socket client for communication with GC100 devices."""

from threading import Thread
import queue
import socket
import uuid
from datetime import datetime
from time import sleep
import logging


# class PingThread(Thread):
#     def __init__(self, scrolls_client):
#         self.scrolls_client = scrolls_client
#         self.stopped = False
#         Thread.__init__(self)
#
#     def run(self):
#         while not self.stopped:
#             self.scrolls_client.send({'msg': 'Ping'})
#             time.sleep(10)

_LOGGER = logging.getLogger(__name__)


class MessageThread(Thread):
    """Process responses & notifications and pipe data to callback(s)."""

    def __init__(self, gc100_client):
        """Initialize message thread."""
        self.gc100_client = gc100_client
        self.stopped = False
        super(MessageThread, self).__init__()

    def run(self):
        """Run message thread."""
        while not self.stopped:
            try:
                # grab a message from queue
                message = self.gc100_client.queue.get(True, 5)
            except queue.Empty:
                _LOGGER.debug("message thread: no messages")
                continue

            _LOGGER.debug("message thread: " + str(message))

            # parse message
            split_message = str(message).split(',')
            if len(split_message) != 3:
                _LOGGER.error("can't parse server response")
                continue
            event, module_address, value = str(message).split(',')
            value = int(value)

            # make a copy of the current subscribers to keep this thread-safe
            current_subscribers = dict(self.gc100_client.subscribers)

            # send message to subscribers
            for subscriber_id in current_subscribers:
                # msg or op should match what we asked for
                subscriber = current_subscribers[subscriber_id]

                if event + "," + module_address == subscriber['event']:
                    subscriber['callback'](value)
                    if subscriber['permanent'] is False:
                        self.gc100_client.unsubscribe(subscriber_id)

            # signals to queue job is done
            self.gc100_client.queue.task_done()


class ReceiveThread(Thread):
    """Receive data and push it to the queue."""

    def __init__(self, gc100_client):
        """Initialize receive thread."""
        self.gc100_client = gc100_client
        self.stopped = False
        Thread.__init__(self)

    def run(self):
        """Run receive thread."""
        while not self.stopped:
            self.gc100_client.receive()


class GC100SocketClient(object):
    """A Python client for the GC100 socket server."""

    queue = queue.Queue()
    subscribers = {}
    _socket_recv = 1024

    def __init__(self, host, port):
        """Initialize the socket client."""
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.settimeout(5)
        # self.socket.setblocking(False)
        self.socket.connect((self.host, self.port))

        # self.ping_thread = PingThread(self)
        self.message_thread = MessageThread(self)
        self.receive_thread = ReceiveThread(self)

        # self.ping_thread.start()
        self.receive_thread.start()
        self.message_thread.start()

    def subscribe(self, event, callback, permanent=False):
        """Subscribe a callback to any event."""
        # add subscribers
        subscriber_id = uuid.uuid4()
        self.subscribers[subscriber_id] = {'event': event,
                                           'callback': callback,
                                           'permanent': permanent,
                                           'time_created': datetime.now()}

    def subscribe_notify(self, module_address, callback):
        """Subscribe a callback to a notification event."""
        self.subscribe('statechange,' + module_address, callback, True)

    def unsubscribe(self, subscriber_id):
        """Unsubscribe a callback from an event."""
        self.subscribers.pop(subscriber_id)

    def send(self, data):
        """Send data to socket."""
        # send message
        _LOGGER.debug("send: " + data)
        self.socket.send(data.encode('ascii'))

    def receive(self):
        """Receive data from socket."""
        while True:
            try:
                # read data from the buffer
                data = self.socket.recv(self._socket_recv)
            except socket.timeout as e:
                _LOGGER.debug(e)
                sleep(1)
                return
            except socket.error as e:
                # Something else happened
                _LOGGER.error(e)
                return

            else:
                if len(data) == 0:
                    # no more data being transmitted
                    _LOGGER.info('orderly shutdown on server end')
                    return

                # remove trailing carriage return, then split
                # on carriage return (for multi-line replies)
                results = data.decode('ascii').rstrip('\r').split('\r')
                if len(results) > 1:
                    _LOGGER.debug("multi-line reply")
                for result in results:
                    _LOGGER.debug("receive thread: " + result)
                    self.queue.put(result)

    def quit(self):
        """Close threads and socket."""
        # stop all threads and close the socket
        self.receive_thread.stopped = True
        # self.receive_thread._Thread__stop()

        self.message_thread.stopped = True
        # self.message_thread._Thread__stop()

        # self.ping_thread.stopped = True
        # self.ping_thread._Thread__stop()

        self.receive_thread.join()
        _LOGGER.info('receive_thread exited')
        self.message_thread.join()
        _LOGGER.info('message_thread exited')

        self.socket.close()

    def read_sensor(self, module_address, callback_fn):
        """Read state from digital input."""
        _LOGGER.info("read_sensor: getstate,{}{}"
                     .format(module_address, chr(13)))
        self.subscribe("state," + module_address, callback_fn)
        self.send("getstate,{}{}".format(module_address, chr(13)))

    def write_switch(self, module_address, state, callback_fn):
        """Set relay state."""
        _LOGGER.info("write_switch: setstate,{},{}{}"
                     .format(module_address, str(state), chr(13)))
        self.subscribe("state," + module_address, callback_fn)
        self.send("setstate,{},{}{}"
                  .format(module_address, str(state), chr(13)))
