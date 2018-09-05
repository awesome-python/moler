# -*- coding: utf-8 -*-
# Copyright (C) 2018 Nokia
"""
Runner abstraction goal is to hide concurrency machinery used
to make it exchangeable (threads, asyncio, twisted, curio)
"""

__author__ = 'Grzegorz Latuszek, Marcin Usielski'
__copyright__ = 'Copyright (C) 2018, Nokia'
__email__ = 'grzegorz.latuszek@nokia.com, marcin.usielski@nokia.com'

import atexit
import logging
import time
import threading
from abc import abstractmethod, ABCMeta
from concurrent.futures import ThreadPoolExecutor, wait
from six import add_metaclass

from moler.exceptions import ConnectionObserverTimeout
from moler.exceptions import CommandTimeout
from moler.exceptions import MolerException

# fix for concurrent.futures  v.3.0.3  to have API of v.3.1.1 or above
try:
    from multiprocessing import cpu_count
except ImportError:
    # some platforms don't have multiprocessing
    def cpu_count():
        """Workarround fix"""
        return None


@add_metaclass(ABCMeta)
class ConnectionObserverRunner(object):
    @abstractmethod
    def shutdown(self):
        """Cleanup used resources."""
        pass

    @abstractmethod
    def submit(self, connection_observer):
        """
        Submit connection observer to background execution.
        Returns Future that could be used to await for connection_observer done.
        """
        pass

    @abstractmethod
    def wait_for(self, connection_observer, connection_observer_future, timeout=10.0):
        """
        Await for connection_observer running in background or timeout.

        :param connection_observer: The one we are awaiting for.
        :param connection_observer_future: Future of connection-observer returned from submit().
        :param timeout: Max time (in float seconds) you want to await before you give up.
        :return:
        """
        pass

    @abstractmethod
    def wait_for_iterator(self, connection_observer, connection_observer_future):
        """
        Version of wait_for() intended to be used by Python3 to implement iterable/awaitable object.

        Note: we don't have timeout parameter here. If you want to await with timeout please do use timeout machinery
        of selected parallelism.

        :param connection_observer: The one we are awaiting for.
        :param connection_observer_future: Future of connection-observer returned from submit().
        :return: iterator
        """
        pass

    @abstractmethod
    def feed(self, connection_observer):
        """
        Feeds connection_observer with data to let it become done.
        This is a place where runner is a glue between words of connection and connection-observer.
        Should be called from background-processing of connection observer.
        """
        pass

    @abstractmethod
    def timeout_change(self, timedelta):
        """
        Call this method to notify runner that timeout has been changed in observer
        :param timedelta: delta timeout in float seconds
        :return: Nothing
        """
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()
        return False  # exceptions (if any) should be reraised


class ThreadPoolExecutorRunner(ConnectionObserverRunner):
    def __init__(self, executor=None):
        """Create instance of ThreadPoolExecutorRunner class"""
        self._in_shutdown = False
        self._i_own_executor = False
        self.executor = executor
        self.logger = logging.getLogger('moler.runner.thread-pool')
        self.logger.debug("created")
        atexit.register(self.shutdown)
        if executor is None:
            max_workers = (cpu_count() or 1) * 5  # fix for concurrent.futures  v.3.0.3  to have API of v.3.1.1 or above
            self.executor = ThreadPoolExecutor(max_workers=max_workers)
            self.logger.debug("created own executor {!r}".format(self.executor))
            self._i_own_executor = True
        else:
            self.logger.debug("reusing provided executor {!r}".format(self.executor))

    def shutdown(self):
        self.logger.debug("shutting down")
        self._in_shutdown = True  # will exit from feed() without stopping executor (since others may still use that executor)
        if self._i_own_executor:
            self.executor.shutdown()  # also stop executor since only I use it

    def submit(self, connection_observer):
        """
        Submit connection observer to background execution.
        Returns Future that could be used to await for connection_observer done.
        """
        self.logger.debug("go background: {!r}".format(connection_observer))

        # TODO: check dependency - connection_observer.connection

        feed_started = threading.Event()
        connection_observer_future = self.executor.submit(self.feed, connection_observer, feed_started)
        # await feed thread to be really started
        start_timeout = 0.5
        if not feed_started.wait(timeout=start_timeout):
            err_msg = "Failed to start observer feeding thread within {} sec".format(start_timeout)
            raise MolerException(err_msg)
        return connection_observer_future

    def wait_for(self, connection_observer, connection_observer_future, timeout=None):
        """
        Await for connection_observer running in background or timeout.

        :param connection_observer: The one we are awaiting for.
        :param connection_observer_future: Future of connection-observer returned from submit().
        :param timeout: Max time (in float seconds) you want to await before you give up. If None then taken from connection_observer
        :return:
        """
        self.logger.debug("go foreground: {!r} - await max. {} [sec]".format(connection_observer, timeout))
        start_time = time.time()
        remain_time = connection_observer.timeout
        check_timeout_from_observer = True
        wait_tick = 0.1
        if timeout:
            remain_time = timeout
            check_timeout_from_observer = False
            wait_tick = remain_time
        while remain_time > 0.0:
            done, not_done = wait([connection_observer_future], timeout=wait_tick)
            if connection_observer_future in done:
                self.shutdown()
                result = connection_observer_future.result()
                self.logger.debug("{} returned {}".format(connection_observer, result))
                return result
            if check_timeout_from_observer:
                timeout = connection_observer.timeout
            remain_time = timeout - (time.time() - start_time)
        moler_conn = connection_observer.connection
        moler_conn.unsubscribe(connection_observer.data_received)
        passed = time.time() - start_time
        self.logger.debug("timeouted {}".format(connection_observer))
        connection_observer.cancel()
        connection_observer_future.cancel()
        self.shutdown()
        connection_observer.on_timeout()
        if hasattr(connection_observer, "command_string"):
            raise CommandTimeout(connection_observer, timeout, kind="await_done", passed_time=passed)
        else:
            raise ConnectionObserverTimeout(connection_observer, timeout, kind="await_done", passed_time=passed)

    def wait_for_iterator(self, connection_observer, connection_observer_future):
        """
        Version of wait_for() intended to be used by Python3 to implement iterable/awaitable object.

        Note: we don't have timeout parameter here. If you want to await with timeout please do use timeout machinery
        of selected parallelism.

        :param connection_observer: The one we are awaiting for.
        :param connection_observer_future: Future of connection-observer returned from submit().
        :return: iterator
        """
        while not connection_observer_future.done():
            yield None
        # return connection_observer_future.result()  # May raise too.   # Python > 3.3
        res = connection_observer_future.result()
        raise StopIteration(res)  # Python 2 compatibility

    def feed(self, connection_observer, feed_started):
        """
        Feeds connection_observer by transferring data from connection and passing it to connection_observer.
        Should be called from background-processing of connection observer.
        """
        self.logger.debug("START OF feed({})".format(connection_observer))
        self.logger.debug("start feeding({})".format(connection_observer))
        moler_conn = connection_observer.connection
        # start feeding connection_observer by establishing data-channel from connection to observer
        self.logger.debug("feed subscribing for data {!r}".format(connection_observer))
        moler_conn.subscribe(connection_observer.data_received)
        self.logger.debug("feeding({}) started".format(connection_observer))
        feed_started.set()
        while True:
            if connection_observer.done():
                self.logger.debug("feed done & unsubscribing {!r}".format(connection_observer))
                moler_conn.unsubscribe(connection_observer.data_received)
                break
            if self._in_shutdown:
                self.logger.debug("feed: shutdown so cancelling {!r}".format(connection_observer))
                connection_observer.cancel()
            time.sleep(0.01)  # give moler_conn a chance to feed observer
        self.logger.debug("feed returning result {}".format(connection_observer))
        self.logger.debug("END   OF feed({})".format(connection_observer))
        return connection_observer.result()

    def timeout_change(self, timedelta):
        pass
