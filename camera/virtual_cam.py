import argparse
import asyncio
import glob
import os
import traceback

import camera

import numpy
import scipy.misc


class VirtualServer(camera.ImageServer):
    '''
    Concrete implementation of image server, which generates images from thin
    air. The images contain random noise.
    '''
    def __init__(self, resolution, image_per_second, loop=None):
        '''
        Initializes the instance of VirtualServer.

        @param resolution - resolution of generated images
        @param image_per_second - number of images to serve per second
        @param loop - asyncio loop
        '''
        self._loop = loop if loop is not None else asyncio.get_event_loop()
        self._resolution = resolution
        self._img_per_sec = image_per_second

    @asyncio.coroutine
    def serve_image(self):
        '''
        Creates a random image.
        '''
        yield from asyncio.sleep(1 / self._img_per_sec)
        img = numpy.random.random(self._resolution)
        return img


class DiskWriter(camera.ImageWriter):
    '''
    Writes images to disk.
    '''
    def __init__(self, dest_dir):
        '''
        Initialize instance of DiskWriter.

        @param dest_dir - destination directory to which all images will be
                          written
        '''
        if not all(check(dest_dir) for check in (os.path.exists, os.path.isdir)):
            raise ValueError("Destination path must exist and be a directory: "
                             "{0}".format(dest_dir))

        self._dest_dir = dest_dir

    @asyncio.coroutine
    def write_image(self, image_data, image_name):
        '''
        Writes image to the destination directory

        @param image_data - actual image data
        @param image_name - name to be given to the image in destination
                            directory
        '''
        path_to_image = os.path.join(self._dest_dir, image_name + ".png")
        try:
            scipy.misc.imsave(path_to_image, image_data)
        except IOError as e:
            print("Failed to save image: {0}".format(e))
        return path_to_image


class DiskCleaner(camera.ImageCleaner):
    '''
    Deletes images from the disk once the limit of images stored is exceeded.
    '''
    IMAGE_LIMIT = 100

    @asyncio.coroutine
    def clean_image(self, image, image_path, image_cnt):
        '''
        Removes the images from disk once the count exceeds the IMAGE_LIMIT.

        @param image - actual image data in the form of the numpy array, bytes,
                       etc.
        @param image_path - path to the image
        @param image_cnt - count of the current image
        '''
        if image_cnt >= DiskCleaner.IMAGE_LIMIT:
            image_to_remove = os.path.join(os.path.dirname(image_path),
                                           "%06d.png" % (image_cnt - DiskCleaner.IMAGE_LIMIT))
            try:
                os.remove(image_to_remove)
            except FileNotFoundError:
                pass
            except IOError as e:
                print(e)


def start(args):
    '''
    This method starts the Random Noise Image Camera.
    '''
    loop = asyncio.get_event_loop()
    server = VirtualServer(resolution=args.resolution,
                           image_per_second=args.framerate)
    writer = DiskWriter(dest_dir=args.path)
    cleaner = DiskCleaner()

    loop = asyncio.get_event_loop()

    sgcamera = camera.Camera(server, writer, cleaner, loop=loop)

    loop.run_until_complete(sgcamera.serve_images())
