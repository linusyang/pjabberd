"""Contains various message processing queue stuff. events.py is the
primary intended user. This guarantees that for any connection only one
Message is being processed at a time.

The launcher should already be initialized and set in pjs.conf.conf in order
to import this.
"""

import pjs.conf.conf
import socket
import logging
from Queue import Queue, Empty
from pjs.handlers.write import prepareDataForSending

# Variables that the dispatchers share

# Currently executing Messages for connection ids. Used to make sure
# that we don't process Messages out of order.
# connID => Message
_runningMessages = {}

# The queue of messages waiting to be processed. A message is queued if
# there is another message for the same connection currently being
# processed.
# We're not using a deque here because we occasionally need to traverse
# the queue (worst case -- all but last connections already have messages
# being processed for them, till the end)
# [(connId, Message), ...]
_processingQ = []

# When messages finish running, they leave the result on this queue.
# out should be a string.
# [(connId, out), ...]
resultQ = Queue()

def _runMessages():
    """Runs all queued Messages that don't have an existing Message
    being processed for the same connection id.
    """
    # I don't care about the Pythonic Way, if it doesn't allow me to remove
    # items from a list I'm iterating on. We could iterate on a copy of the
    # list, but I'm afraid that the processingQ could get pretty large with
    # lots of connections.
    i = 0
    l = len(_processingQ)
    connId, msg = (None, None)
    while i < l:
        connId, msg = _processingQ[i]
        if connId not in _runningMessages:
            _runningMessages[connId] = msg
            # moved to runningMessages, so delete from processingQ
            del _processingQ[i]
            i -= 1
            l -= 1

            msg.process()
        i += 1

activeServers = pjs.conf.conf.launcher.servers

def pickupResults():
    """Picks up any available results on the result queue and calls
    runMessages() to continue processing the queue.
    """
    while 1:
        try:
            connId, out = resultQ.get_nowait()
            for server in activeServers:
                if connId in server.conns:
                    conn = server.conns[connId][1]
                    # FIXME: this should be prevented. test socket for writability
                    try:
                        conn.send(prepareDataForSending(out))
                    except socket.error, e:
                        logging.warning("[pickupResults] Socket error: %s", e)
                    break
            else:
                # message left on the queue for a connection that's no longer
                # there, so we log it and move on
                logging.debug("[pickupResults] Connection id %s has no corresponding" +\
                                " Connection object. Dropping result from queue.", connId)
            resultQ.task_done()
            del _runningMessages[connId]
        except Empty:
            break

    _runMessages()
