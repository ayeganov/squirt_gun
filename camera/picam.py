import argparse
import asyncio
import io
import os
import signal
import traceback

import sgmsg

import libs.async_zmq as async_zmq
import numpy
import picamera
import scipy.misc


JPEG_MAGIC_NUM = b'\xff\xd8'


class PiCamServer:
    '''
    PI camera image server, which acquires images from PI camera.
    '''
    IMAGE_LIMIT = 100
    def __init__(self, dest_dir, framerate, resolution, loop=None):
        '''
        Initializes the instance of PiCamServer.

        @param dest_dir - path to write images to
        @param framerate - number of images to serve per second
        @param resolution - (height, width) tuple representing image resolution
        @param loop - asyncio loop
        '''
        if not all(check(dest_dir) for check in (os.path.exists, os.path.isdir)):
            raise ValueError("Destination path must exist and be a directory: "
                             "{0}".format(dest_dir))

        if any(v <= 0 for v in resolution):
            raise ValueError("Resolution must contain only positive integers.")

        if framerate <= 0:
            raise ValueError("Framerate must be specified as a positive"
                             " integer: {0}".format(framerate))

        self._dest_dir = dest_dir
        self._camera = picamera.PiCamera()
        self._camera.framerate = framerate
        self._camera.resolution = resolution
        self._loop = loop if loop is not None else asyncio.get_event_loop()

        self._image_pub = async_zmq.SocketFactory.pub_socket(topic="/tmp/img_path",
                                                             loop=self._loop)
        self._image_count = 0
        self._write_buffer_handles = []

    def _make_image_name(self, image_count, dest_dir):
        '''
        Create a full path to image given the image_count and directory.
        '''
        image_name = "".join(("%07d" % image_count, ".jpg"))
        path_to_image = os.path.join(dest_dir, image_name)
        return path_to_image

    def _process_image(self, image_count, path_to_image):
        '''
        Processes the newly written image: broadcasts its path to subscribers,
        and cleans up old images.

        @param image_count - count of images written so far
        @param path_to_image - full path to the newly written image
        '''
        # Broadcast the image path
        print("Sending: {0}".format(path_to_image))
        msg = sgmsg.msgs.ImagePath.new_message(path=path_to_image)
        self._image_pub.send(msg.to_bytes())

        # Clean up old images
        if image_count >= PiCamServer.IMAGE_LIMIT:
            image_to_remove = self._make_image_name(image_count -
                                               PiCamServer.IMAGE_LIMIT,
                                               self._dest_dir)
            try:
                os.remove(image_to_remove)
            except IOError:
                pass

    def _write_image(self, img_path, img_buf):
        '''
        This method does the writing of the image buffer to disk.

        @param img_buf - image buffer in the form of bytes etc.
        @return True if written, False otherwise
        '''
        result = False
        try:
            if img_buf.startswith(JPEG_MAGIC_NUM):
                with io.open(img_path, 'wb') as output:
                    output.write(img_buf)
                result = True
            else:
                print("JPEG not found:", JPEG_MAGIC_NUM)
        except IOError as e:
            traceback.print_exc()
        return result

    def write(self, img_buf):
        '''
        This method is invoked from the picamera background image capturing
        thread. It writes out the image buffer to specified directory, and
        broadcasts its path.

        @param img_buf - image buffer in the form of bytes
        '''
        try:
            path_to_image = self._make_image_name(self._image_count, self._dest_dir)
            if self._write_image(path_to_image, img_buf):
                self._process_image(self._image_count,
                                    path_to_image)
                self._image_count += 1
        except Exception as e:
            print("Unexpected error while writing image.")
            traceback.print_exc()

    def start_camera(self):
        '''
        Starts camera recording.
        '''
        self._camera.start_recording(self, format='mjpeg')

    def stop_camera(self):
        '''
        Stop camera recording.
        '''
        self._camera.stop_recording()
        self._image_pub.close()


class MotionPiCam(PiCamServer):
    '''
    This camera records motion data in the video stream.
    '''
    def __init__(self, dest_dir, framerate, resolution, loop=None):
        '''
        Initializes the instance of MotionPiCam.

        @param dest_dir - path to write images to
        @param framerate - number of images to serve per second
        @param resolution - (height, width) tuple representing image resolution
        @param loop - asyncio loop
        '''
        super().__init__(dest_dir, framerate, resolution, loop)
        self._motion_dtype = numpy.dtype([
                        ('x', 'i1'),
                        ('y', 'i1'),
                        ('sad', 'u2'),
                    ])
        width, height = resolution
        self._cols = 1 + ((width + 15) // 16)
        self._rows = (height + 15) // 16

    def _write_image(self, image_path, motion_buf):
        '''
        Receive the motion vector buffer and write it out to a file.
        '''
        try:
            data = numpy.fromstring(motion_buf, dtype=self._motion_dtype)
            data = data.reshape((self._rows, self._cols))
            data = numpy.sqrt(
                numpy.square(data['x'].astype(numpy.float)) +
                numpy.square(data['y'].astype(numpy.float))
                ).clip(0, 255).astype(numpy.uint8)
            scipy.misc.imsave(image_path, data)
            return True
        except Exception as e:
            traceback.print_exc()
        return False

    def start_camera(self):
        '''
        Starts camera recording.
        '''
        self._camera.start_recording('/dev/null', format='h264', motion_output=self)


def ctrl_c(picamera, loop):
    '''
    Signal handler for SIGINT and SIGTERM.

    @param picamera - instance of picamera
    @param loop - instance of asyncio loop
    '''
    print("Received interrupt signal.")
    picamera.stop_camera()
    loop.stop()


def main():
    try:
        def resolution_tuple(value):
            if value.count(",") != 1:
                raise argparse.ArgumentTypeError("{0} is an invalid resolution "
                                                 "value.".format(value))
            h, w = [int(v) for v in value.split(",")]
            return (h, w)

        parser = argparse.ArgumentParser("PI camera image server")
        parser.add_argument("-p",
                            "--path",
                            help="Save path for images.",
                            required=True)

        parser.add_argument("-r",
                            "--resolution",
                            help="Image resolution in the form of H,W.",
                            default="1280,720",
                            type=resolution_tuple)

        parser.add_argument("-f",
                            "--framerate",
                            help="Camera framerate - number of images to take per second.",
                            type=int,
                            default=20)

        parser.add_argument("-t",
                            "--type",
                            help="Camera type - record pure image data, or motion.",
                            type=str,
                            choices=['image', 'motion'],
                            default="image")

        args = parser.parse_args()

        loop = asyncio.get_event_loop()

        if args.type == 'image':
            server = PiCamServer(dest_dir=args.path,
                                 framerate=args.framerate,
                                 resolution=args.resolution,
                                 loop=loop)
        elif args.type == 'motion':
            server = MotionPiCam(dest_dir=args.path,
                                 framerate=args.framerate,
                                 resolution=args.resolution,
                                 loop=loop)

        loop.add_signal_handler(signal.SIGINT, ctrl_c, server, loop)
        loop.add_signal_handler(signal.SIGTERM, ctrl_c, server, loop)

        print("Saving images to {0} with resolution of {1} at {2}"
              " fps".format(args.path, args.resolution, args.framerate))

        loop.call_soon(server.start_camera)
        print("Starting PI Camera server")

        loop.run_forever()
        loop.close()

        print("PI Camera stopped.")
    except (SystemExit, KeyboardInterrupt):
        print("Exiting due to interrupt...")
    except Exception as e:
        print("Error: {0}".format(e))


if __name__ == "__main__":
    main()
