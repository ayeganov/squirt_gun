import argparse
import asyncio
import os

import camera


class VirtualServer(camera.ImageServer):
    '''
    Concrete implementation of image server, which generates images from thin
    air.
    '''
    def __init__(self, loop=None):
        '''
        Initializes the instance of VirtualServer.

        @param loop - asyncio loop
        '''
        self._loop = loop if loop is not None else asyncio.get_event_loop()

    @asyncio.coroutine
    def serve_image(self):
        '''
        Creates a random image.
        '''
        yield from asyncio.sleep(1)
        return "blabla"


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
        self._dest_dir = dest_dir

    @asyncio.coroutine
    def write_image(self, image_data, image_name):
        '''
        Writes image to the destination directory

        @param image_data - actual image data
        @param image_name - name to be given to the image in destination
                            directory
        '''
        path_to_image = os.path.join(self._dest_dir, image_name)
        #blabla save image
        return path_to_image


class DiskCleaner(camera.ImageCleaner):
    '''
    Deletes images from the disk once the limit of images stored is exceeded.
    '''
    IMAGE_LIMIT = 1000

    @asyncio.coroutine
    def clean_image(self, image, image_path, image_cnt):
        '''
        Removes the images from disk once the count exceeds the IMAGE_LIMIT.

        @param image - actual image data in the form of the numpy array
        @param image_path - path to the image
        @param image_cnt - count of the current image
        '''
        if image_cnt >= DiskCleaner.IMAGE_LIMIT:
            try:
                os.remove(image_path)
            except IOError:
                pass


def main():
    try:
        parser = argparse.ArgumentParser("Virtual camera image server")
    #    parser.add_argument()

        server = VirtualServer()
        writer = DiskWriter(dest_dir="/run")
        cleaner = DiskCleaner()
        loop = asyncio.get_event_loop()

        sgcamera = camera.Camera(server, writer, cleaner, loop=loop)

        loop.run_until_complete(sgcamera.serve_images())
    except (SystemExit, KeyboardInterrupt):
        print("Exiting due to interrupt...")


if __name__ == "__main__":
    main()
