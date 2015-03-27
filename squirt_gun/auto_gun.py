import asyncio

import sgmsg

import libs.async_zmq as async_zmq


def got_image(msg_bytes):
    data = msg_bytes[-1]
    msg = sgmsg.msgs.ImagePath.from_bytes(data)
    print("Received:", msg)

def main():
    loop = asyncio.get_event_loop()
    image_pub = async_zmq.SocketFactory.sub_socket(topic="/tmp/img_path",
                                                   on_recv=got_image,
                                                   loop=loop)
    try:
        print("Lets listen to data.")
        loop.run_forever()
    except (SystemExit, KeyboardInterrupt):
        print("Exiting due to interrupt...")


if __name__ == "__main__":
    main()
