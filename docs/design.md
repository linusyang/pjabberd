
Pjabberd Design Doc
===================

Introduction
------------

[XMPP](http://www.xmpp.org/), previously known as Jabber, is an open protocol for messaging and presence. It's designed for push-style data distribution between network entities in near real-time. The core protocol is described in two RFCs, although many [extensions](http://www.xmpp.org/extensions/) are listed on the XMPP web site. [RFC 3920](http://www.xmpp.org/rfcs/rfc3920.html) and [3921](http://www.xmpp.org/rfcs/rfc3921.html) describe concepts like streams, stanzas, authentication procedures, resource binding, the Instant Messaging (IM) aspect of XMPP, and others. XMPP is based on clients and servers—both are required. Clients connect to servers and send messages to other clients through them.

The adoption of the protocol has been steadily increasing. Many commercial entities, such as TiVo and Jive Software, use it in their products. Google's XMPP-based Talk application has thousands of users world-wide.

[Python](http://python.org/) is a dynamic object-oriented programming language with extensive support of Internet protocols. It's fairly popular, easy to learn, very appropriate for prototyping, yet lacks a usable XMPP server implementation.

Goal
----

The goal of this project is to create a framework for XMPP servers. It would provide the basic components and some helpful tools for creating concrete implementations. The goal is not to create a single monolithic server (like Openfire, for example).

Design Choices
--------------

The specific design choices are documented below.

### XML Representation ###

[ElementTree](http://effbot.org/zone/element-index.htm) is the XML library used throughout the framework. We needed XPath support, so we bundled the 1.3alpha3 version with pjabberd. Handlers are passed the parsed messages via the `tree` parameter as an instance of the `Element` class. ElementTree's parser (expat) strips the `xmlns` attributes on XML elements and changes &lt;elementname&gt; to &lt;{namespace}elementname&gt;. In order to send out uniform XML, all handlers should use `tostring()` found in `pjs.utils`, and not ElementTree's `tostring()`, since the latter produces incorrect namespaces.

### Asynchronous Connections ###

Pjabberd uses asynchronous connections. There is only a single process that accepts and processes connections. This was done for the following reasons:

1. It has worked well for [DJabberd](http://www.danga.com/djabberd/). It's written in Perl, which is interpreted like Python and comparable in terms of performance.

2. Unlike HTTP, Jabber connections persist for a long time, so it is beneficial to have low per-connection memory overhead. The asynchronous design allows for it, because new threads aren't being spawned for every connection.

3. Python's threading performance is limited by the GIL (global interpreter lock), which allows only one thread to run inside a single interpreter at a time. Therefore, adding more threads to the server would only decrease performance due to thread-switching overhead.

4. The [Twisted](http://twistedmatrix.com/trac/) framework developers have been successful in implementing a similar concept.

This design implies that only one connection/message is being processed at a time. However, many tasks that an XMPP server must perform (such as authentication) require some form of blocking I/O, such as accessing a database. With asynchronous connections, all code running in the main thread cannot block for any reason. If it does, it will hold up the entire server. Pjabberd solves this problem by allowing individual handlers (see [chained handlers](#chained-handlers)) to run outside the main thread.

![Asynchronous connections](async.png)

<a name="chained-handlers"></a>

### Phases ###

Every message that comes in is assigned a "phase", a sequence of handlers. The phases are configured in `pjs.conf.phases` and `pjs.conf.handlers`. Each phase distinguishes itself from others by its XPath expression. The current version of ElementTree only support basic operations, such as matching on tag name and attributes. The phases are checked in random order, because in Python dictionaries have no order. However, if there are two or more conflicting phases, higher priorities can be assigned to create an artificial ordering. An example of this is 'c2s-presence' and 'subscription' phases for the c2s server. 'c2s-presence' matches on '{jabber:client}presence' and 'subscription' matches on '{jabber:client}presence[@type]'. If there were no priorities in phase lists, a subscription could be interpreted as a simple presence stanza.

Phases define the regular and error handlers (see below) associated with phase. The list can be queried and modified at runtime by handlers to queue others (via `Message`'s `setNextHandler()` and `setLastHandler()`).

### Chained Handlers ###

When an XMPP stanza is taken off the wire, it can be handled by any class that subclasses either `Handler` or `ThreadedHandler` from `pjs.handlers.base`. If a class subclasses `Handler` then its `handle()` method is executed. If a class subclasses `ThreadedHandler` then its `handle()` method is executed, but it needs to return a tuple of `FunctionCall` objects (from `pjs.utils`) that specify how a thread should be started and how it can be checked for completion. When the thread-checking function returns `True`, the handler's `resume()` function is called, so that it may collect the result or do some cleanup. The `ThreadedHandler` classes are responsible for launching their own threads and cleaning up after themselves. The framework only knows that a `ThreadedHandler` needs to do some work that might take a while, so it lets it do whatever it needs until the checking function returns `True`. As a convenience, each server in the framework has a threadpool associated with it that handlers can drop jobs onto and retrieve results. Many classes in `pjs.handlers` use this approach. See `SASLResponseHandler` in `pjs.handlers.auth` for an example.

The handlers are chained. This means that for any type of message (as defined below) there can be a sequence of handlers that run on that message. Only one handler per message runs at a time even if the current handler is executing in another thread. The same message is passed to each handler in the chain. It can be modified by handlers, but this should probably be avoided as it will result in hard-to-debug code. If a handler needs to modify a message, it should `deepcopy()` it.

Each handler can pass the next handler in the chain some data through the `lastRetVal` parameter in `handle()` by returning a value from `handle()`. If it doesn't return anything, the `lastRetVal` is preserved and passed to the next handler. However, if a handler returns a value it will overwrite the `lastRetVal` for future handlers. Most handlers will probably want to attach a value to `lastRetVal` -- such handlers should use the `chainOutput()` function from `pjs.handlers.base`. This is how a roster push currently occurs: the handler that accepts an "iq get" message chains the roster stanza that should be sent to all of the client's connected resources. A handler can stop the chain by setting `stopChain` in the `Message` object to `True`.

The chained handlers design also allows for handling unexpected exceptions. Each handler can be paired with an "error handler" in the same phase. The error handler's `handle()` method will be executed with the exception being the last element in `lastRetVal`. If the error handler (A) throws another exception, the next handler is skipped and its error handler (B) is run. If A does not throw and exception then B's regular handler will run next.

![](handlers.png)

Data Persistence
----------------

Internal Data
-------------


<div style="display:none">:wrap=soft:maxLineLen=100:noTabs=false:</div>

