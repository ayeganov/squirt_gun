import abc
import argparse
import asyncio
import random
import signal
import traceback

import sgmsg

import libs.async_zmq as async_zmq
import netifaces
import numpy
import scipy.ndimage
import scipy.misc


class AI(metaclass=abc.ABCMeta):
    '''
    AI interface expected by the AIController.
    '''
    @abc.abstractmethod
    def analyze_image(self, image):
        '''
        Accepts the image from controller to analyze.
        '''


class MotionAI(AI):
    '''
    This class is responsible for detecting motion in pictures being fed to it.
    If motion is detected it will issue the shoot command. This class relies on
    the pictures from MotionPiCam, which generates images of motion vectors.
    Using regular images with this class won't work.
    '''
    def __init__(self, controller):
        '''
        Initialize instance of MotionAI.

        @param controller - class to which all actions being performed(shoot
                            etc) are delegated.
        '''
        self._controller = controller

    def shoot(self):
        '''
        Issue the shoot command to ai controller.
        '''
        self._controller.shoot()

    def analyze_image(self, image):
        '''
        Analyze the given image to determine whether anything is moving in
        front of the camera.

        @param image - latest image from camera in the form of the numpy array
        '''
        # If there are more than 10 pixels with a magnitude greater than 60 lets
        # call that motion.
        motion = (image > 60).sum() > 10
        if motion:
            self.shoot()


class MotionAIDiff(AI):
    '''
    Motion detection based on the difference between two consecutive images.
    The images this class expects must be regular images not images of motion
    vectors.
    '''
    def __init__(self, controller, loop):
        '''
        Initialize instance of MotionAIDiff.

        @param controller - class to which all actions being performed(shoot
                            etc) are delegated.
        @param loop - asyncio loop
        '''
        self._controller = controller
        self._loop = loop
        self._previous = None
        self._future = None

    def shoot(self):
        '''
        Issue the shoot command to ai controller.
        '''
        self._controller.shoot()

    def _reset_state(self):
        '''
        Resets the processing state of this analyzer.
        '''
        self._future = None
        self._previous = None


    @asyncio.coroutine
    def analyze_image(self, image):
        '''
        Analyze the given image to determine whether anything is moving in
        front of the camera.

        @param image - latest image from camera in the form of the numpy array
        '''
        if self._previous is None:
            self._previous = image
            return

        if self._future is not None:
            print("Skipping image...")
            if self._future.cancelled():
                self._reset_state()
            return

        def is_motion_detected():
            smooth_prev = scipy.ndimage.gaussian_filter(self._previous, sigma=3)
            smooth_cur = scipy.ndimage.gaussian_filter(image, sigma=3)
            diff = numpy.abs(smooth_cur - smooth_prev)

            # If there are more than 10 pixels with a magnitude greater than 60 lets
            # call that motion.
            motion = (diff > 60).sum() > 10
            return motion

        self._future = self._loop.run_in_executor(None, is_motion_detected)
        try:
            motion = yield from self._future
        except:
            traceback.print_exc()
            self._reset_state()

        # Once we receive the result, drop the future AND previous image
        # because it is too old
        self._reset_state()

        print("Motion detected: {0}".format(motion))
        if motion:
            self.shoot()


class AIController:
    '''
    AIController class abstracts away all communications from AI classes.
    '''
    def __init__(self, ai, net_iface, port, loop=None):
        '''
        Initializes instance of AIController.

        @param ai - type of ai determining when to shoot
        @param net_iface - network interface to broadcast commands on
        @param port - socket port number
        @param loop - asyncio loop
        '''
        self._net_iface = net_iface
        self._port = port
        self._loop = loop if loop is not None else asyncio.get_event_loop()
        self._image_sub = async_zmq.SocketFactory.sub_socket(topic="/tmp/img_path",
                                                             on_recv=self.process_img_path,
                                                             loop=self._loop)
        self._shoot_pub_ipc = async_zmq.SocketFactory.pub_socket(topic="/tmp/shoot",
                                                                 loop=self._loop)
        self._shoot_pub = async_zmq.SocketFactory.pub_socket(host=net_iface,
                                                             port=port,
                                                             transport="tcp",
                                                             loop=self._loop)

        if ai == "motion_fast":
            self._ai = MotionAI(self)
        elif ai == "motion_slow":
            self._ai = MotionAIDiff(self, loop=self._loop)

    @asyncio.coroutine
    def process_img_path(self, img_path_msg):
        '''
        Process the received image path.
        '''
        data = img_path_msg[-1]
        img_path = sgmsg.msgs.ImagePath.from_bytes(data)
        print("Analyzing {0}".format(img_path.path))
        img = scipy.misc.imread(img_path.path, flatten=True)
        yield from self._ai.analyze_image(img)

    def shoot(self):
        '''
        Sends a message to all physical guns to shoot.
        '''
        msg = sgmsg.msgs.Shoot.new_message(type="single")
        msg_bytes = msg.to_bytes()
        self._shoot_pub.send(msg_bytes)
        self._shoot_pub_ipc.send(msg_bytes)

    def shutdown(self):
        '''
        Shut down the ai controller: release all resources etc.
        '''
        self._image_sub.close()


def ctrl_c(ai_control, loop):
    '''
    Signal handler for SIGINT and SIGTERM.

    @param ai_control - instance of ai controller
    @param loop - instance of asyncio loop
    '''
    print("Received interrupt signal.")
    ai_control.shutdown()
    loop.stop()


def main():
    loop = asyncio.get_event_loop()
    try:
        print("Starting the AI.")

        def port_num(value):
            ivalue = int(value)
            min_val = 1024
            max_val = 2**16
            if not (min_val <= ivalue <= max_val):
                raise argparse.ArgumentTypeError("{0} is an invalid port "
                                                 "number.".format(value))
            return ivalue

        parser = argparse.ArgumentParser(description="Gun AI Controller.")
        parser.add_argument("-n",
                            "--niface",
                            help="Network interface on which to serve the AI commands.",
                            choices=netifaces.interfaces(),
                            type=str)

        parser.add_argument("-p",
                            "--port",
                            help="Port number to listen on for brain commands.",
                            type=port_num,
                            default=9000)

        parser.add_argument("-i",
                            "--intelligence",
                            help="Intelligence that determines when shots will "
                                 "be fired.",
                            choices=['motion_fast', 'motion_slow'],
                            default='motion_slow',
                            type=str)

        args = parser.parse_args()

        ai_control = AIController(ai=args.intelligence,
                                  net_iface=args.niface,
                                  port=args.port,
                                  loop=loop)

        loop.add_signal_handler(signal.SIGINT, ctrl_c, ai_control, loop)
        loop.add_signal_handler(signal.SIGTERM, ctrl_c, ai_control, loop)

        loop.run_forever()
        print("AI shut down.")
    except (SystemExit, KeyboardInterrupt):
        print("Exiting due to interrupt...")


if __name__ == "__main__":
    main()
