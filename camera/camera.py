import abc
import asyncio

import sgmsg

import libs.async_zmq as async_zmq


class ImageServer(metaclass=abc.ABCMeta):
    '''
    This is an image server interface, it allows its users to receive images
    from it. Implementers must implement serve_image method, which is suppose
    to return an image in the form of a numpy array.
    '''
    @abc.abstractmethod
    def serve_image(self):
        '''
        This method returns a numpy array representation of an image.
        '''


class ImageWriter(metaclass=abc.ABCMeta):
    '''
    This is an image writer interface. Implementers must implement write_image
    method.
    '''
    @abc.abstractmethod
    def write_image(self, image, image_name):
        '''
        Writes image to some destination, disk, network etc.

        @param image - image in the form of the numpy array
        @param image_name - name of the image at the destination
        '''


class ImageCleaner(metaclass=abc.ABCMeta):
    '''
    This is an image cleaner interface. Implementers must implement clean_image
    method. That method accepts current image, its path, and image count from
    the camera.
    '''
    @abc.abstractmethod
    def clean_image(self, image, image_path, img_count):
        '''
        Clean up resources taken up by the image, if any.
        '''


class Camera:
    '''
    This is the camera class that produces images to be consumed by the gun
    controllers.
    '''
    def __init__(self, image_server, image_writer, image_cleaner, loop=None):
        '''
        Initializes instance of the Camera.

        @param image_server - image server, from which camera gets its images.
        @param image_writer - writes images to wherever it wants to
        @param image_cleaner - cleans up resources taken up by the image
        @parma loop - asyncio loop
        '''
        self._server = image_server
        self._writer = image_writer
        self._cleaner = image_cleaner
        self._loop = loop if loop is not None else asyncio.get_event_loop()
        self._image_pub = async_zmq.SocketFactory.pub_socket(topic="img_path",
                                                             loop=self._loop)

        self._img_count = 0

    @asyncio.coroutine
    def serve_images(self):
        '''
        Camera starts serving images on the img_path topic indefinitely.
        '''
        while True:
            image = yield from self._server.serve_image()
            image_name = "%06d" % self._img_count
            path_to_image = yield from self._writer.write_image(image, image_name)
            msg = sgmsg.msgs.ImagePath.new_message(path=path_to_image)

            self._image_pub.send(msg.to_bytes_packed())
            yield from self._cleaner.clean_image(image, path_to_image, self._img_count)
            self._img_count += 1
            print("Serving: {0}".format(path_to_image))

