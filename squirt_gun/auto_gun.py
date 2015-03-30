import abc
import asyncio
import random
import signal

import sgmsg

import libs.async_zmq as async_zmq
import numpy
import scipy.misc


class Gun(metaclass=abc.ABCMeta):
    '''
    Gun interface expected by the GunController.
    '''
    @abc.abstractmethod
    def shoot(self):
        '''
        Issues a single shot.
        '''

    @abc.abstractmethod
    def analyze_image(self, image):
        '''
        Accepts the image from controller to analyze.
        '''


class MotionGun(Gun):
    '''
    This class is responsible for detecting motion in pictures being fed to it.
    If motion is detected it will issue the shoot command. This class relies on
    the pictures from MotionPiCam, which generates images of motion vectors.
    Using regular images with this class won't work.
    '''
    def __init__(self, controller, loop=None):
        '''
        Initialize instance of MotionGun.

        @param controller - class to which all actions being performed(shoot
                            etc) are delegated.
        @param loop - asyncio loop
        '''
        self._controller = controller
        self._loop = loop if loop is not None else asyncio.get_event_loop()

    def shoot(self):
        '''
        Issue the shoot command to gun controller.
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


class GunController:
    '''
    GunController class abstracts away all communications from Gun classes.
    '''
    def __init__(self, loop=None):
        self._loop = loop if loop is not None else asyncio.get_event_loop()
        self._image_pub = async_zmq.SocketFactory.sub_socket(topic="/tmp/img_path",
                                                             on_recv=self.process_img_path,
                                                             loop=loop)
        self._gun = MotionGun(self, loop)

    def process_img_path(self, img_path_msg):
        '''
        Process the received image path.
        '''
        data = img_path_msg[-1]
        img_path = sgmsg.msgs.ImagePath.from_bytes(data)
        img = scipy.misc.imread(img_path.path)
        self._gun.analyze_image(img)

    def shoot(self):
        '''
        Sends a message to all physical guns to shoot.
        '''
        choices = ("Poof poof!", "Пиф паф ой ой!", "Прямо в яблочко!")
        print(random.choice(choices))

    def shutdown(self):
        '''
        Shut down the gun controller: release all resources etc.
        '''
        self._image_pub.close()


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
        print("Starting the gun AI.")
        gun_control = GunController(loop)

        loop.add_signal_handler(signal.SIGINT, ctrl_c, gun_control, loop)
        loop.add_signal_handler(signal.SIGTERM, ctrl_c, gun_control, loop)

        loop.run_forever()
        loop.close()
        print("Gun AI shut down.")
    except (SystemExit, KeyboardInterrupt):
        print("Exiting due to interrupt...")


if __name__ == "__main__":
    main()
