import struct
import board
import logger
import logging
import time
from equations import bytes_to_pressure
from adafruit_bus_device.i2c_device import I2CDevice

try:
    from busio import I2C  # pylint: disable=unused-import
    from typing import Optional, List
except ImportError:
    pass

sensor_logger = logging.getLogger(__name__)

SGP40_ADDR = None
SCD40_ADDR = 0x62
BMP_SEA_LEVEL_PRESSURE = 2971155.4124


class Sensor():
    def __init__(self, i2cbus: I2C, addr):
        self.retries = 0
        self.addr = addr
        self.i2cbus = i2cbus
        self.i2c_device = None
        self._buffer = None
        self._connected = self.open_connection()
        if self.logger is None:
            self.logger = logger.getLogger("envmon.sensor")

    def open_connection(self):
        if self.retries > 5:
            # sensor probably not hooked up
            return

        try:
            self.i2c_device = I2CDevice(self.i2cbus, self.addr)
        except ValueError:
            logger.debug("Failed to connect")
            self.retries = self.retries + 1
            return False
        else:
            self.logger.debug("Connected")
            return True

    @property
    def connected(self):
        return self._connected

    def reset(self):
        raise NotImplementedError("Reset not supported by this sensor")

    def _read_raw(self, buffer: bytearray = None) -> None:
        if self._buffer is None:
            raise NotImplementedError("Need to give this a bytearray buffer")
        if self._connected:
            with self.i2c_device as device:
                try:
                    if buffer is None:
                        device.readinto(self._buffer)
                    else:
                        device.readinto(buffer, end=len(buffer))

                except OSError as err:
                    self.logger.error(err)
                    self._connected = False
        else:
            self.open_connection()

    def _send_cmd(self, cmd: bytearray = None, **kwargs):
        if self._connected:
            with self.i2c_device as device:
                if cmd is None:
                    if self._send_buffer is None:
                        raise NotImplementedError(
                            "Class needs to implement a send buffer"
                        )
                    cmd = self._send_buffer
                self.logger.debug("Sending command: {}".format(cmd.hex()))
                device.write(cmd)
        time.sleep(kwargs.get("delay_ms", 0)/1000.0)

    def _read_reply(
            self, delay_ms: int = 30,
            length: int = 1,
            **kwargs
    ):
        ''' Send command and read back whats recieved '''
        word_len = 2
        cmd = kwargs.get("cmd")
        self._send_cmd(cmd)

        time.sleep(round(delay_ms * 0.001, 3))

        reply_buffer = bytearray(length * (word_len + 1))
        self._read_raw(reply_buffer)
        data_buffer = []
        if not kwargs.get("raw", None):
            for i in range(0, length * (word_len + 1), 3):
                data_buffer.append(struct.unpack_from(
                    ">H", reply_buffer[i:i+2])[0])
        return data_buffer

    def _read_register(self, register: int, length: int) -> bytearray:
        self.logger.debug("Reading register {:02x}".format(register))
        register_value = bytearray(length)
        self._send_cmd(bytes([register & 0xFF]))
        self._read_raw(register_value)
        self.logger.debug("Register content: {}".format(register_value.hex()))
        return register_value

    def _read_byte(self, register):
        return self._read_register(register, 1)[0]

    @staticmethod
    def _crc8(buffer: bytearray) -> int:
        crc = 0xFF
        for byte in buffer:
            crc ^= byte
            for _ in range(8):
                if crc & 0x80:
                    crc = (crc << 1) ^ 0x31
                else:
                    crc = crc << 1
        return crc & 0xFF  # return the bottom 8 bits




