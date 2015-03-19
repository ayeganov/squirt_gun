import os

import capnp

this_script_dir = os.path.dirname(os.path.abspath(__file__))
capnp_defs = os.path.join(this_script_dir, "messages.capnp")

msgs = capnp.load(capnp_defs)


if __name__ == "__main__":
    def main():
        for p in dir(msgs):
            print("Dir: {0}".format(type(getattr(msgs, p))))

    main()
