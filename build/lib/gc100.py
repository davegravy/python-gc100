from threading import Thread
from queue import Queue
import socket
import uuid
from datetime import datetime


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


class MessageThread(Thread):
    def __init__(self, gc100_client):
        self.gc100_client = gc100_client
        self.stopped = False
        super(MessageThread, self).__init__()

    def run(self):
        while not self.stopped:
            # grab a message from queue
            message = self.gc100_client.queue.get()

            # parse message
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


            print("message thread: " + message)

            # signals to queue job is done
            self.gc100_client.queue.task_done()


class ReceiveThread(Thread):
    def __init__(self, gc100_client):
        self.gc100_client = gc100_client
        self.stopped = False
        Thread.__init__(self)

    def run(self):
        while not self.stopped:
            self.gc100_client.receive()


class GC100SocketClient(object):
    """
    A Python client for the GC100 socket server.


    """

    queue = Queue()
    subscribers = {}
    _socket_recv = 1024

    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.host, self.port))

        # self.ping_thread = PingThread(self)
        self.message_thread = MessageThread(self)
        self.receive_thread = ReceiveThread(self)

        # self.ping_thread.start()
        self.receive_thread.start()
        self.message_thread.start()

    def subscribe(self, event, callback, permanent=False):
        # add subscribers
        subscriber_id = uuid.uuid4()
        self.subscribers[subscriber_id] = {'event': event,
                                           'callback': callback,
                                           'permanent': permanent,
                                           'time_created': datetime.now()}

    def subscribe_notify(self, module_address, callback):
        self.subscribe('statechange,' + module_address, callback, True)

    def unsubscribe(self, subscriber_id):
        # rm subscribers
        self.subscribers.pop(subscriber_id)

    def send(self, data):
        # send message
        self.socket.send(data.encode('ascii'))

    def receive(self):

        while (True):
            # read data from the buffer
            data = self.socket.recv(self._socket_recv)

            if not data:
                # no more data being transmitted
                return

            print("receive thread: " + data.decode('ascii'))
            result = data.decode('ascii').strip(' \r')
            self.queue.put(result)

            # try:
            #     # line breaks means we are handling multiple responses
            #     if "\n\n" in stream_data:
            #         # split and parse each response
            #         for stream_data_line in stream_data.split("\n\n"):
            #             # try to load as JSON
            #             data_json = json.loads(stream_data_line)
            #
            #             # we have a response, add it to the queue
            #             self.queue.put(data_json)
            # except ValueError:
            #     # invalid json, incomplete data
            #     pass

    def quit(self):
        # stop all threads and close the socket
        self.receive_thread.stopped = True
        self.receive_thread._Thread__stop()

        self.message_thread.stopped = True
        self.message_thread._Thread__stop()

        # self.ping_thread.stopped = True
        # self.ping_thread._Thread__stop()

        self.socket.close()

    def read_sensor(self, module_address, callback_fn):
        self.subscribe("state," + module_address, callback_fn)
        self.send("getstate,{}{}".format(module_address, chr(13)))

    def write_switch(self, module_address, state, callback_fn):
        self.subscribe("state," + module_address, callback_fn)
        self.send("setstate,{},{}{}".format(module_address, str(state), chr(13)))
