# -*- coding: utf-8 -*-
"""
Configure logging for Moler's needs
"""

__author__ = 'Grzegorz Latuszek, Marcin Usielski, Michal Ernst'
__copyright__ = 'Copyright (C) 2018, Nokia'
__email__ = 'grzegorz.latuszek@nokia.com, marcin.usielski@nokia.com, michal.ernst@nokia.com'

import codecs
import logging
import os
import sys

logging_path = os.getcwd()  # Logging path that is used as a prefix for log file paths
active_loggers = []  # TODO: use set()      # Active loggers created by Moler
date_format = "%d %H:%M:%S"

# new logging levels
RAW_DATA = 1  # should be used for logging data of external sources, like connection's data send/received
TRACE = 4  # may produce tons of logs, should be used for lib dev & troubleshooting
# (above ERROR = 40, below CRITICAL = 50)
TEST_CASE = 45

debug_level = None  # means: inactive
raw_logs_active = False
write_mode = "a"


def set_write_mode(mode):
    global write_mode
    if mode.lower() in ["a", "append"]:
        write_mode = "a"
    elif mode.lower() in ["w", "write"]:
        write_mode = "w"


def set_logging_path(path):
    global logging_path
    logging_path = path


def set_date_format(format):
    global date_format
    date_format = format


def configure_debug_level(level=None):
    """
    Configure debug_level based on environment variable MOLER_DEBUG_LEVEL
    We use additional env variable besides MOLER_CONFIG to allow for quick/temporary change
    since debug level is intended also for troubleshooting
    """
    global debug_level
    if level:
        level_name = level
    else:
        level_name = os.getenv('MOLER_DEBUG_LEVEL', 'not_found').upper()

    allowed = {'TRACE': TRACE, 'DEBUG': logging.DEBUG}

    if level_name in allowed:
        debug_level = allowed[level_name]
    else:
        debug_level = logging.INFO


def want_debug_details():
    """Check if we want to have debug details inside logs"""
    return debug_level is not None


def want_raw_logs():
    return raw_logs_active


def debug_level_or_info_level():
    """
    If debugging is active we want to have details inside logs
    otherwise we want to keep them small
    """
    if want_debug_details():
        level = debug_level
    else:
        level = logging.INFO
    return level


def setup_new_file_handler(logger_name, log_level, log_filename, formatter, filter=None):
    """
    Sets up new file handler for given logger
    :param logger_name: name of logger to which filelogger is added
    :param log_level: logging level
    :param log_filename: path to log file
    :param formatter: formatter for file logger
    :param filter: filter for file logger
    :return:  logging.FileHandler object
    """
    global write_mode
    logger = logging.getLogger(logger_name)
    cfh = logging.FileHandler(log_filename, write_mode)
    cfh.setLevel(log_level)
    cfh.setFormatter(formatter)
    if filter:
        cfh.addFilter(filter)
    logger.addHandler(cfh)
    return cfh


def _add_new_file_handler(logger_name,
                          log_file, formatter, log_level=TRACE, filter=None):
    """
    Add file writer into Logger
    :param logger_name: Logger name
    :param log_file: Path to logfile. Final logfile location is logging_path + log_file
    :param log_level: only log records with equal and greater level will be accepted for storage in log
    :param formatter: formatter for file logger
    :param filter: filter for file logger
    :return: None
    """

    logfile_full_path = os.path.join(logging_path, log_file)

    _prepare_logs_folder(logfile_full_path)
    setup_new_file_handler(logger_name=logger_name,
                           log_level=log_level,
                           log_filename=logfile_full_path,
                           formatter=formatter,
                           filter=filter)


def _add_raw_file_handler(logger_name, log_file):
    """
    Add raw/binary file writer into Logger
    :param logger_name: Logger name
    :param log_file: Path to logfile. Final logfile location is logging_path + log_file
    :return: None
    """
    global write_mode
    logfile_full_path = os.path.join(logging_path, log_file)
    _prepare_logs_folder(logfile_full_path)
    logger = logging.getLogger(logger_name)
    rfh = RawFileHandler(filename=logfile_full_path, mode='{}b'.format(write_mode))
    logger.addHandler(rfh)


def _add_raw_trace_file_handler(logger_name, log_file):
    """
    Add raw-info file writer into Logger
    :param logger_name: Logger name
    :param log_file: Path to logfile. Final logfile location is logging_path + log_file
    :return: None
    """
    global write_mode
    logfile_full_path = os.path.join(logging_path, log_file)
    _prepare_logs_folder(logfile_full_path)
    logger = logging.getLogger(logger_name)
    trace_rfh = RawFileHandler(filename=logfile_full_path, mode=write_mode)
    # exchange Formatter
    raw_trace_formatter = RawTraceFormatter()
    trace_rfh.setFormatter(raw_trace_formatter)
    logger.addHandler(trace_rfh)


def create_logger(name,
                  log_file=None, log_level=TRACE,
                  log_format="%(asctime)s %(levelname)-10s: |%(message)s",
                  datefmt=None):
    """
    Creates Logger with (optional) file writer
    :param name: Logger name
    :param log_file: Path to logfile. Final logfile location is logging_path + log_file
    :param log_level: only log records with equal and greater level will be accepted for storage in log
    :param log_format: layout of log file, default is "%(asctime)s %(levelname)-10s: |%(message)s"
    :param datefmt: format the creation time of the log record
    :return: None
    """
    logger = logging.getLogger(name)
    if name not in active_loggers:
        logger.setLevel(log_level)
        if log_file:  # if present means: "please add this file as logs storage for my logger"
            _add_new_file_handler(logger_name=name,
                                  log_file=log_file,
                                  log_level=log_level,
                                  formatter=logging.Formatter(fmt=log_format,
                                                              datefmt=datefmt))
        active_loggers.append(name)
    return logger


def configure_moler_main_logger():
    """Configure main logger of Moler"""
    # warning or above go to logfile
    if 'moler' not in active_loggers:
        logger = create_logger(name='moler', log_level=TRACE, datefmt=date_format)
        logger.propagate = True

        main_log_format = "%(asctime)s.%(msecs)03d %(levelname)-12s %(message)s"
        _add_new_file_handler(logger_name='moler',
                              log_file='moler.log',
                              log_level=logging.INFO,  # only hi-level info from library
                              formatter=MolerMainMultilineWithDirectionFormatter(fmt=main_log_format,
                                                                                 datefmt=date_format))

        if want_debug_details():
            debug_log_format = "%(asctime)s.%(msecs)03d %(levelname)-12s %(name)-30s %(threadName)22s %(filename)30s:#%(lineno)3s %(funcName)25s() %(transfer_direction)s|%(message)s"
            _add_new_file_handler(logger_name='moler',
                                  log_file='moler.debug.log',
                                  log_level=debug_level,
                                  # entries from different components go to single file, so we need to
                                  # differentiate them by logger name: "%(name)s"
                                  # do we need "%(threadName)-30s" ???
                                  formatter=MultilineWithDirectionFormatter(fmt=debug_log_format,
                                                                            datefmt=date_format))

        logger.info("More logs in: {}".format(logging_path))


def configure_runner_logger(runner_name):
    """Configure logger with file storing runner's log"""
    logger_name = 'moler.runner.{}'.format(runner_name)
    if logger_name not in active_loggers:
        create_logger(name=logger_name,
                      log_file='moler.runner.{}.log'.format(runner_name),
                      log_level=debug_level_or_info_level(),
                      log_format="%(asctime)s.%(msecs)03d %(levelname)-12s %(threadName)22s %(filename)30s:#%(lineno)3s %(funcName)25s() |%(message)s",
                      datefmt=date_format
                      # log_format="%(asctime)s %(levelname)-10s %(subarea)-30s: |%(message)s"
                      )


def configure_device_logger(connection_name, propagate=False):
    """Configure logger with file storing connection's log"""
    logger_name = 'moler.{}'.format(connection_name)
    if logger_name not in active_loggers:
        logger = create_logger(name=logger_name, log_level=TRACE)
        logger.propagate = propagate
        conn_formatter = MultilineWithDirectionFormatter(
            fmt="%(asctime)s.%(msecs)03d %(transfer_direction)s|%(message)s",
            datefmt=date_format)
        _add_new_file_handler(logger_name=logger_name,
                              log_file='{}.log'.format(logger_name),
                              log_level=logging.INFO,
                              formatter=conn_formatter)
        if want_raw_logs():
            # RAW_LOGS is lowest log-level so we need to change log-level of logger
            # to make it pass data into raw-log-handler
            logger.setLevel(min(RAW_DATA, TRACE))
            _add_raw_file_handler(logger_name=logger_name, log_file='{}.raw.log'.format(logger_name))
            if debug_level == TRACE:
                _add_raw_trace_file_handler(logger_name=logger_name, log_file='{}.raw.trace.log'.format(logger_name))
    else:
        logger = logging.getLogger(logger_name)
    return logger


def _prepare_logs_folder(logfile_full_path):
    """
    Checks that log folder exist and creates it if needed
    :param logfile_full_path: path to log folder
    :return: Nome
    """
    logdir = os.path.dirname(logfile_full_path)
    if not os.path.exists(logdir):
        os.makedirs(logdir)


class TracedIn(object):
    """
    Decorator to allow for tracing method/function invocation
    It sends function name and parameters into logger given as decorator parameter
    sends with loglevel=TRACE
    Decorator is active only when environment variable MOLER_DEBUG_LEVEL = TRACE
    ex.:
    @TracedIn('moler')
    def method(self, arg1, arg2):
    """

    def __init__(self, logger_name):  # decorator parameter
        self.logger = logging.getLogger(logger_name)
        self.trace_active = (debug_level == TRACE)

    def __call__(self, decorated_method):
        if not self.trace_active:
            return decorated_method

        method_name = decorated_method.__name__

        def _traced_method(*args,
                           **kwargs):  # parameters of decorated_method
            args_list = [str(arg) for arg in args]
            kwargs_list = ['{}={}'.format(arg, kwargs[arg]) for arg in
                           kwargs]
            param_str = ', '.join(args_list + kwargs_list)
            ret = decorated_method(*args, **kwargs)
            self.logger.log(TRACE, '{}({}) returned: {}'.format(method_name,
                                                                param_str,
                                                                ret))
            return ret

        return _traced_method


class RawDataFormatter(object):
    def format(self, record):
        """We want to take data from log_record.msg as bytes"""
        raw_bytes = record.msg
        if not isinstance(raw_bytes, (bytes, bytearray)):
            err_msg = "Log record directed for raw-logs must have encoder if record.msg is not bytes (it is {})".format(
                type(record.msg))
            assert hasattr(record, "encoder"), err_msg
            raw_bytes = record.encoder(record.msg)
        return raw_bytes


class RawTraceFormatter(RawDataFormatter):
    def __init__(self):
        self.date_formatter = logging.Formatter(fmt="%(asctime)s.%(msecs)03d", datefmt=date_format)
        self.total_bytesize = 0

    def format(self, record):
        """We want to see info about binary data log-record"""
        raw_bytes = super(RawTraceFormatter, self).format(record)
        bytesize = len(raw_bytes)
        timestamp = self.date_formatter.format(record)
        direction = record.transfer_direction if hasattr(record, 'transfer_direction') else '.'
        offset = self.total_bytesize
        self.total_bytesize += bytesize
        # make it look like YAML implicit document record:
        # - 1536862639.4494998: {time: '20:17:19.449', direction: <, bytesize: 17, offset: 17}
        # see:   https://pyyaml.org/wiki/PyYAMLDocumentation
        # but we don't use yaml library since we want predictable order
        raw_trace_record = "- %s: {time: '%s', direction: %s, bytesize: %s, offset: %s}\n" % (
            record.created, timestamp, direction, bytesize, offset)
        return raw_trace_record


class RawFileHandler(logging.FileHandler):
    def __init__(self, *args, **kwargs):
        """RawFileHandler must use RawDataFormatter and level == RAW_DATA only"""
        super(RawFileHandler, self).__init__(*args, **kwargs)
        raw_formatter = RawDataFormatter()
        self.setFormatter(raw_formatter)
        self.setLevel(RAW_DATA)
        raw_records_only_filter = SpecificLevelFilter(RAW_DATA)
        self.addFilter(raw_records_only_filter)

    def emit(self, record):
        """
        Emit a record.
        We don't want base class implementation since we don't want to do:
        stream.write(self.terminator)
        We are not adding any \n to bytes-message from record.
        """
        if self.stream is None:
            self.stream = self._open()
        try:
            msg = self.format(record)
            stream = self.stream
            stream.write(msg)
            self.flush()
        except Exception:
            self.handleError(record)


class MultilineWithDirectionFormatter(logging.Formatter):
    """
    We want logs to have non-overlapping areas
    timestamp area TTTTTTTTTTT
    transfer direction area >  (shows send '>' or receive '<')
    log message area MMMMMMMMMM
    It should look like:
    TTTTTTTTTTTTTTT D MMMMMMMMMMMMMMM
    01 00:36:09.581 >|cat my_file.txt
    01 00:36:09.585 <|This is
                     |multiline
                     |content
    This formatter allows to use %(transfer_direction)s inside format
    """

    def __init__(self, fmt=None, datefmt=None):
        if fmt is None:
            fmt = "%(asctime)s.%(msecs)03d %(transfer_direction)s|%(message)s"
        else:  # message should be last part of format
            assert fmt.endswith("|%(message)s")
        super(MultilineWithDirectionFormatter, self).__init__(fmt=fmt, datefmt=datefmt)

    def format(self, record):
        if not hasattr(record, 'transfer_direction'):
            record.transfer_direction = ' '
        if not hasattr(record, 'log_name'):
            record.log_name = ""

        msg_lines = record.getMessage().splitlines(True)
        base_output = super(MultilineWithDirectionFormatter, self).format(record)
        out_lines = base_output.splitlines(True)
        output = out_lines[0]

        if len(msg_lines) >= 1:
            empty_prefix = self._calculate_empty_prefix(msg_lines[0], out_lines[0])
            for line in out_lines[1:]:
                try:
                    output += u"{}|{}".format(empty_prefix, line)
                except UnicodeDecodeError as err:
                    if hasattr(err, "encoding"):
                        encoding = err.encoding
                    else:
                        encoding = sys.getdefaultencoding()
                    decoded_line = codecs.decode(line, encoding, 'replace')
                    output += u"{}|{}".format(empty_prefix, decoded_line)

                    # TODO: line completion for connection decoded data comming in chunks
        output = MolerMainMultilineWithDirectionFormatter._remove_duplicate_log_name(record, output)
        return output

    def _calculate_empty_prefix(self, message_first_line, output_first_line):
        prefix_len = output_first_line.rindex(u"|{}".format(message_first_line))
        empty_prefix = " " * prefix_len
        return empty_prefix

    @staticmethod
    def _remove_duplicate_log_name(record, output):
        if record.log_name and "|{}".format(record.log_name) in output:
            output = output.replace("|{:<20}".format(record.log_name), "")
        return output


class MolerMainMultilineWithDirectionFormatter(MultilineWithDirectionFormatter):
    def __init__(self, fmt, datefmt=None):
        if fmt is None:
            fmt = "%(asctime)s.%(msecs)03d %(transfer_direction)s|%(message)s"
        else:  # message should be last part of format
            assert fmt.endswith("%(message)s")
        super(MultilineWithDirectionFormatter, self).__init__(fmt=fmt, datefmt=datefmt)

    def format(self, record):
        if not hasattr(record, 'log_name'):
            record.log_name = record.name

        if hasattr(record, 'moler_error'):
            record.levelname = "MOLER_ERROR"

        record.msg = u"{:<20}|{}".format(record.log_name, record.msg)

        return super(MolerMainMultilineWithDirectionFormatter, self).format(record)

    def _calculate_empty_prefix(self, message_first_line, output_first_line):
        prefix_len = output_first_line.index("|")
        empty_prefix = " " * prefix_len
        return empty_prefix


class SpecificLevelFilter(object):
    def __init__(self, level):
        self.__level = level

    def filter(self, logRecord):
        return logRecord.levelno == self.__level


# actions during import:
logging.addLevelName(TRACE, "TRACE")
logging.addLevelName(RAW_DATA, "RAW_DATA")
logging.addLevelName(TEST_CASE, "TEST_CASE")
configure_debug_level()
