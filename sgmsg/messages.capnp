@0x934efea7f017fff0;

struct Mode {
    enum CamMode {
        motion @0;
        smart @1;
    }

    type @0 :CamMode;
}

struct Shoot {
    enum ShotType {
        single @0;
        burst @1;
    }

    type @0 :ShotType;
}

struct ImagePath {
    path @0 :Text;
}
