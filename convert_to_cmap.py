from __future__ import print_function
import logging


def spacing(s):
    try:
        x, y, z = map(int, s.split(','))
        return x, y, z
    except:
        raise argparse.ArgumentTypeError("Spacing must be x,y,z")


class MorphParser(object):
    def __init__(self):
        self.count = 0

    def parse_op(self, arg):
        self.count += 1
        if self.count == 1:
            return self.morphological_operation(arg)
        elif self.count == 2:
            return self.radius(arg)
        else:
            argparse.ArgumentTypeError("morphological argument has one or two arguments")

    @staticmethod
    def radius(radius):
        try:
            radius = int(radius)
        except ValueError:
            argparse.ArgumentTypeError("Second argument of morphological operation should be int")
        if radius < 1:
            argparse.ArgumentTypeError("Second argument of morphological operation should be positive int")
        return radius

    @staticmethod
    def morphological_operation(name):
        """
        :type name: str
        :return:
        """
        print("Morph op parse \"{}\"".format(name))
        import backend
        if name == backend.MorphChange.no_morph:
            return name
        if name.lower() in ["open", "opening"]:
            return backend.MorphChange.opening_morph
        elif name.lower() in ["close", "closing"]:
            return backend.MorphChange.closing_morph
        else:
            raise argparse.ArgumentTypeError("morphological operation should be open[ing] or close|closing")

if __name__ == '__main__':
    import argparse
    import glob
    import os
    import sys
    import backend
    import numpy as np
    mpr = MorphParser()
    parser = argparse.ArgumentParser("Convert project to chimera cmap")
    parser.add_argument("source_folder", type=str, nargs=1, help="Folder with project files to proceed or one file")
    parser.add_argument("destination_folder", type=str, nargs=1, help="Destination folder")
    parser.add_argument("--base_folder", dest="base_folder", type=str, nargs=1, default=None,
                        help="TBD")
    parser.add_argument("-s", "--spacing", dest="spacing", default=None, type=spacing,
                        help="Spacing between pixels saved to cmap")
    parser.add_argument("-g", "--use_2d_gauss", dest="use_2d_gauss", default=backend.GaussUse.no_gauss,
                        const=backend.GaussUse.gauss_2d, action="store_const",
                        help="Apply 2d (x,y) gauss blur data to image before put in cmap")
    parser.add_argument("-g3", "--use_gauss_3d", dest="use_3d_gauss", default=backend.GaussUse.no_gauss,
                        const=backend.GaussUse.gauss_3d, action="store_const",
                        help="Apply 3d gauss blur data to image before put in cmap")
    parser.add_argument("-ns", "--no_statistics", dest="no_statistics", default=False, const=True,
                        action="store_const",
                        help="Off saving statistics in 'Chimera/image1/Statistics' group")
    parser.add_argument("-nc", "--no_center_data", dest="no_center_data", default=False, const=True,
                        action="store_const",
                        help="Off centering and rotating volumetric data")
    parser.add_argument("-morph", "--morphological_operation", dest="morph", default=backend.MorphChange.no_morph,
                        nargs='+', type=mpr.parse_op)
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)
    files_to_proceed = glob.glob(os.path.join(args.source_folder[0], "*.gz"))
    if len(files_to_proceed) == 0:
        files_to_proceed = glob.glob(os.path.join(args.source_folder[0], "*.bz2"))
        if len(files_to_proceed) == 0:
            files_to_proceed = args.source_folder

    if args.base_folder is not None:
        if not os.path.isdir(args.base_folder[0]):
            logging.error("Folder {} does not exists".format(args.base_folder[0]))
            sys.exit(-1)
        else:
            base_folder = args.base_folder[0]
    else:
        base_folder = None

    settings = backend.Settings("settings.json")
    segment = backend.Segment(settings)

    def canvas_update(image):
        segment.draw_canvas = np.zeros(image.shape, dtype=np.uint8)
        segment.set_image(image)

    settings.add_image_callback(canvas_update)
    num = len(files_to_proceed)
    gauss_type = args.use_2d_gauss
    if args.use_3d_gauss == backend.GaussUse.gauss_3d:
        gauss_type = backend.GaussUse.gauss_3d
    logging.info("Gauss type {}".format(gauss_type))
    logging.info("Morph op type {}".format(args.morph))

    for i, file_path in enumerate(files_to_proceed):
        if base_folder is not None:
            rel_path = os.path.dirname(os.path.relpath(file_path, base_folder))
        else:
            rel_path = ""
        file_name = os.path.basename(file_path)
        print("file: {}; {} from {}".format(file_name, i+1, num))
        backend.load_project(file_path, settings, segment)
        segment.threshold_updated()
        file_name = os.path.splitext(file_name)[0]
        file_name += ".cmap"
        if args.spacing is not None:
            settings.spacing = args.spacing
        if not os.path.isdir(os.path.join(args.destination_folder[0], rel_path)):
            os.makedirs(os.path.join(args.destination_folder[0], rel_path))

        backend.save_to_cmap(os.path.join(args.destination_folder[0], rel_path, file_name), settings, segment,
                             gauss_type=gauss_type, with_statistics=not args.no_statistics,
                             centered_data=not args.no_center_data, morph_op=args.morph)