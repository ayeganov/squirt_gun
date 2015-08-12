import argparse
import asyncio
import itertools
import glob
import os

import libs.async_zmq as async_zmq

import sgmsg


class FileSystemCamera:
    '''
    Image server serving images from a provided directory. The default accepted
    formats are *.jpg.
    '''
    def __init__(self,
                 serve_directory,
                 cycle,
                 image_rate,
                 file_format,
                 loop=None):
        '''
        Initializes the instance of FileSystemCamera.

        @param serve_directory - directory containing images to serve 
        @param cycle - serve images infinitely
        @param image_rate - number of images to serve per second
        @param file_format - image format to serve
        @param loop - asyncio loop
        '''
        if not all(check(serve_directory) for check in (os.path.exists, os.path.isdir)):
            raise ValueError("Must provide an existing directory.")

        file_pattern = os.path.join(serve_directory, file_format)
        files = sorted(glob.iglob(file_pattern))

        self._serve_dir = serve_directory
        self._iterator = itertools.cycle(files)\
                         if cycle\
                         else iter(files)

        self._rate = 1 / image_rate
        self._loop = loop
        self._image_pub = async_zmq.SocketFactory.pub_socket(topic="/tmp/img_path",
                                                             loop=self._loop)

    @asyncio.coroutine
    def serve_images(self):
        '''
        Serves all images in the provided directory that match the file format.
        This routine will never finish if cycle is set to True.
        '''
        for path in self._iterator:
            msg = sgmsg.msgs.ImagePath.new_message(path=path)
            self._image_pub.send(msg.to_bytes())
            print(path)
            yield from asyncio.sleep(self._rate)


def start(args):
    '''
    This function creates the FileSystemCamera, and executes serve_images.
    '''
    loop = asyncio.get_event_loop()
    fs_cam = FileSystemCamera(args.directory,
                              args.cycle,
                              args.rate,
                              args.format,
                              loop=loop)

    loop.run_until_complete(fs_cam.serve_images())


if __name__ == "__main__":
    main()
