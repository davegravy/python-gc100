# python-gc100
A Python-based socket client for Global Cache GC100 digital I/O interface

The global cache GC100 features an array of digital inputs / IR outputs (switchable),
serial ports, and solid state relays, accessible via a TCP interface.

python-gc100 provides a TCP client to interface with a GC100.

Currently serial port communication and IR functions are not supported. 
Digital input (including notification mode) and changing relay state are supported.



Usage
-----

Given a callback function

    >>> def callback_fn(state):
    >>>   print(state)

Initialize the connection to the socket server

    >>> hostname = 'myserver'
    >>> port = 4998
    >>> gc = gc100.GC100SocketClient(hostname,port)

Example, if you want to read and print the state of module address '4:1':

    >>> gc.read_input('4:1', callback_fn)

Or turn the relay on at address '3:2', and confirm its new state:

    >>> gc.write_switch('3:2', 1, callback_fn)

Turn it off again:

    >>> gc.write_switch('3:2', 0, callback_fn)

If you want to subscribe to be notified (push) of state changes to digital input '4:3':
   
    >>> gc.notify_subscribe('4:3', callback_fn)
 
Compatibility
------------

This module is only tested with Python 3.5.2, and will definitely not be compatible with python 2.x

Author and License
------------------

This software is (c) 2017 David Grant <davegravy@gmail.com>

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version.

GC100 is a trademark of Global Cache, with whom the author of this software is not
affiliated in any way other than using some of the their hardware
