import abc
import argparse
import asyncio
import ipaddress
import random
import signal
import traceback

import libs.async_zmq as async_zmq

import sgmsg

try:
    import RPi.GPIO as GPIO
except ImportError:
    VIRTUAL_ONLY = True

class Gun(metaclass=abc.ABCMeta):
    '''
    Interface that is expected from every gun.
    '''
    @abc.abstractproperty
    def is_active(self):
        '''
        Is this gun currently shooting?
        '''

    @abc.abstractmethod
    def process_shot(self, shot_type):
        '''
        Process request for shooting.

        @param shot_type - requested shooting behavior
        '''


class VirtualGun(Gun):
    '''
    This is a virtual gun made for testing the code without relying on the
    hardware.
    '''
    def __init__(self, gun_pin, loop=None):
        '''
        Initializes the instance of VirtualGun.

        @param gun_pin - pin number for controlling the gun
        @param loop - asyncio loop
        '''
        self._gun_pin = gun_pin
        self._loop = loop if loop is not None else asyncio.get_event_loop()

    @property
    def is_active(self):
        '''
        Is this gun currently shooting?
        '''
        return False

    @asyncio.coroutine
    def process_shot(self, shot_type):
        '''
        This gun only has one behavior - print out that it is shooting.
        '''
        choices = ("Poof poof!", "Пиф паф ой ой!", "Прямо в яблочко!")
        print(random.choice(choices))


class PinGun(Gun):
    '''
    Hardware layer for controlling the gun. It relies on knowing the PIN
    number, which turns on the gun.
    '''
    def __init__(self, gun_pin, loop=None):
        '''
        Initializes the instance of PinGun.

        @param gun_pin - pin number for controlling the gun
        @param loop - asyncio loop
        '''
        self._gun_pin = gun_pin
        self._loop = loop if loop is not None else asyncio.get_event_loop()
        self._shooting = False

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self._gun_pin, GPIO.OUT)

    @property
    def is_active(self):
        '''
        Is this gun currently shooting?
        '''
        return self._shooting

    @asyncio.coroutine
    def process_shot(self, shot_type):
        '''
        Given a specific shot type, invokes appropriate gun behavior.

        @param shot_type - type of requested gun behavior
        '''
        # ignore requests to shoot when shooting
        if self.is_active:
            return

        if shot_type == sgmsg.msgs.Shoot.ShotType.single:
            print("Single shot")
            yield from self._single_shot()
        elif shot_type == sgmsg.msgs.Shoot.ShotType.burst:
            print("Burst shot!")
            yield from self._burst_shot()
        else:
            print("Don't know how to do: {0}".format(shot_type))

    @asyncio.coroutine
    def _single_shot(self):
        '''
        Shoot the gun once.
        '''
        self._shooting = True
        GPIO.output(self._gun_pin, True)
        yield from asyncio.sleep(0.1)
        GPIO.output(self._gun_pin, False)
        self._shooting = False

    @asyncio.coroutine
    def _burst_shot(self):
        '''
        Shoot the gun in a burst of "bullets."
        '''
        self._shooting = True
        for _ in range(3):
            GPIO.output(self._gun_pin, True)
            yield from asyncio.sleep(0.08)
            GPIO.output(self._gun_pin, False)
            yield from asyncio.sleep(0.03)

        self._shooting = False


class GunController:
    '''
    GunController class abstracts away all communications from Gun classes.
    '''
    def __init__(self, gun, ai_host, port, loop=None):
        '''
        Initializes the instance of GunController.

        @param gun - gun to be controlled by this controller
        @param ai_host - ip address of the gun AI, which will broadcast commands.
        @param port - socket port number
        @param loop - asyncio loop
        '''
        self._gun = gun
        self._ai_host = ai_host
        self._port = port
        self._loop = loop if loop is not None else asyncio.get_event_loop()
        self._shoot_sub = async_zmq.SocketFactory.sub_socket(host=ai_host,
                                                             port=port,
                                                             transport="tcp",
                                                             on_recv=self._handle_command,
                                                             loop=loop)

    @asyncio.coroutine
    def _handle_command(self, shoot_msg):
        '''
        Process the received image path.
        '''
        data = shoot_msg[-1]
        shot_msg = sgmsg.msgs.Shoot.from_bytes(data)
        yield from self._gun.process_shot(shot_msg.type)

    def shutdown(self):
        '''
        Shut down the gun controller: release all resources etc.
        '''
        self._shoot_sub.close()


def ctrl_c(gun_control, loop):
    '''
    Signal handler for SIGINT and SIGTERM.

    @param gun_control - instance of gun controller
    @param loop - instance of asyncio loop
    '''
    print("Received interrupt signal.")
    gun_control.shutdown()
    loop.stop()


def main():
    loop = asyncio.get_event_loop()
    try:
        print("Starting the Gun.")

        def positive_int(value):
            ivalue = int(value)
            if ivalue <= 1:
                raise argparse.ArgumentTypeError("{0} is an invalid pin number "
                                                 "value.".format(value))
            return ivalue

        def port_num(value):
            ivalue = int(value)
            min_val = 1024
            max_val = 2**16
            if not (min_val <= ivalue <= max_val):
                raise argparse.ArgumentTypeError("{0} is an invalid port "
                                                 "number.".format(value))
            return ivalue

        parser = argparse.ArgumentParser("Gun Hardware Controller.")
        parser.add_argument("-t",
                            "--type",
                            help="Gun type - virtual, or real. Use virtual for "
                            "testing with no hardware, use real when using "
                            "RPi.",
                            type=str,
                            choices=['virtual'] + [] if VIRTUAL_ONLY else ['real'],
                            default="virtual")

        parser.add_argument("-b",
                            "--brain",
                            help="Address of the host serving as the guns brain.",
                            type=ipaddress.ip_address,
                            required=True)

        parser.add_argument("-p",
                            "--port",
                            help="Port number to listen on for brain commands.",
                            type=port_num,
                            default=9000)

        parser.add_argument("-i",
                            "--pin",
                            help="Pin number for controlling the gun. Must be > 0.",
                            type=positive_int,
                            default=18)

        args = parser.parse_args()

        if args.type == "virtual":
            gun = VirtualGun(gun_pin=args.pin, loop=loop)
        else:
            gun = PinGun(gun_pin=args.pin, loop=loop)

        gun_control = GunController(gun=gun,
                                    ai_host=str(args.brain),
                                    port=args.port,
                                    loop=loop)

        loop.add_signal_handler(signal.SIGINT, ctrl_c, gun_control, loop)
        loop.add_signal_handler(signal.SIGTERM, ctrl_c, gun_control, loop)

        loop.run_forever()
        print("Gun shut down.")
    except (SystemExit, KeyboardInterrupt):
        print("Exiting due to interrupt...")
    except Exception:
        traceback.print_exc()


if __name__ == "__main__":
    main()
