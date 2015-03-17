import sys

import capnp

modes_capnp = capnp.load("modes.capnp")


if __name__ == "__main__":
    def main():
        while True:
            mode = modes_capnp.Mode.new_message(type="motion")
#            print("Current mode: {0}".format(mode.to_bytes_packed()))

    main()
