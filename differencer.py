#!/usr/bin/env python

import argparse
import os

import numpy
import scipy.misc


def verify_image(img_path):
    '''
    Verifies the image_path points to a regular existing file.

    @param img_path - path to image to check
    @returns boolean
    '''
    return all(check(img_path) for check in (os.path.exists,
                                             os.path.isfile))

def verify_folder(dir_path):
    '''
    Verifies the dir_path points to an existing directory.

    @param dir_path - path to directory
    @returns boolean
    '''
    return all(check(dir_path) for check in (os.path.exists,
                                             os.path.isdir))

def compute_differences(image_paths, flat):
    '''
    Given a list of paths to images computer difference between them
    iteratively.

    @param image_paths - list of image paths
    @returns a list of image differences as numpy arrays
    '''
    diffs = []
    if not image_paths:
        return diffs

    prev_img = scipy.misc.imread(image_paths[0], flatten=flat).astype(numpy.int16)
    for path in image_paths[1:]:
        current_img = scipy.misc.imread(path, flatten=flat).astype(numpy.int16)
        diffs.append(numpy.clip(current_img - prev_img, 0, 255))
        prev_img = current_img

    return diffs


def main():
    parser = argparse.ArgumentParser("Computes image differences in a given list of images.")

    parser.add_argument("-i",
                        "--images",
                        help="List of images to compute differences.",
                        nargs="+",
                        required=True)

    parser.add_argument("-o",
                        "--output",
                        help="Output folder to save diff images to.",
                        required=True)

    parser.add_argument("-f",
                        "--flat",
                        help="Compute differences of images as grayscale.",
                        action="store_true")

    args = parser.parse_args()

    if verify_folder(args.output):
        existing_images = [img for img in args.images if verify_image(img)]

        diffs = compute_differences(existing_images, args.flat)
        for i, diff_img in enumerate(diffs):
            img_name = os.path.join(args.output, "%04d.jpg" % i)
            print("Saving {0}...".format(img_name))
            scipy.misc.imsave(img_name, diff_img)
    else:
        print("Output folder must exist: {0}".format(args.output))

if __name__ == "__main__":
    main()
