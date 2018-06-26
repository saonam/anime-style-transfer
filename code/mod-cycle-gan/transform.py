#!/usr/bin/env python3

"""
Script for neural network inference. Transforms real images into anime.
Inference from anime into real world is possible, but not implemented, because no one cares about real world.

Params:
    includein   includes original images into output data
    random=number   how many random images from ade20k dataset will be taken
    indir=path  path to dir with input images
    outdir=path    dir for output, where dir with network name is created with images in it
    rundir=path     dir with model checkpoint. If not specified, last network is taken
Examples:
    python transform.py --random=20    # takes 20 random images from ade20k dataset and transforms them
    python transform.py --indir=../images    # takes all images from specified dir and transforms them
    python transform.py --indir=../images --includein    # takes all images from specified dir and transforms them, including input images
"""
import glob
import os
import os.path as osp
import logging
import random
import numpy as np
import tensorflow as tf
from PIL import Image
from scipy.misc import imsave

import cycle
from cycle.models.anime import X_DATA_SHAPE
from train import initialize_networks
from data_preparation.images_to_tfrecord import process_sample, get_real_images_ade20k

FLAGS = tf.flags.FLAGS

tf.flags.DEFINE_string('in_dir', None, 'Name of dir with input images')
tf.flags.DEFINE_integer('random', 20, 'If not none, random images are taken')
tf.flags.DEFINE_string('out_dir', '../../data/images', 'Name of output dir')
tf.flags.DEFINE_bool('includein', True,
                     'Whether to include input data in the output file. If on, output file will be larger, but self-contained.')


def load_and_export(checkpoint_dir, export_dir):
    modellib, xfeed, xy, yfeed, yx = initialize_networks()

    XtoY = xy
    YtoX = yx

    X_normer = xfeed.normalize
    Y_normer = yfeed.normalize
    X_denormer = xfeed.denormalize
    Y_denormer = yfeed.denormalize

    cycle.CycleGAN.export_from_checkpoint(XtoY, YtoX, X_normer, X_denormer, Y_normer, Y_denormer,
                                          checkpoint_dir, export_dir, FLAGS.Xname, FLAGS.Yname)


def images_to_numpy(im_paths):
    one_img_size = X_DATA_SHAPE
    data = np.zeros((len(im_paths), one_img_size[0], one_img_size[1], one_img_size[2]), dtype=np.float32)
    for i, f in enumerate(im_paths):
        image = process_sample(np.array(Image.open(f)))
        data[i, :, :, :] = image
    return data


def numpy_to_images(data, out_dir, suffix='-out'):
    if not osp.exists(out_dir):
        os.makedirs(out_dir)
    for i, im in enumerate(data):
        # im = data[i, :, :, :]
        imsave(osp.join(out_dir, '{}{}.png'.format(i, suffix)), im)


def main(_):
    # just as test, but with loading from checkpoint
    if FLAGS.random is not None:
        num_images = FLAGS.random
        im_paths = random.sample(get_real_images_ade20k(), num_images)
        in_data = images_to_numpy(im_paths)
    elif FLAGS.indir is not None:
        im_paths = list(glob.glob(osp.join(FLAGS.indir, '*.png')))
        im_paths += list(glob.glob(osp.join(FLAGS.indir, '*.jpg')))
        in_data = images_to_numpy(im_paths)
    else:
        raise Exception("No data source specified")

    logging.getLogger().setLevel(logging.INFO)

    if FLAGS.rundir is None:
        FLAGS.rundir = sorted([d for d in os.listdir(FLAGS.cpdir)
                               if osp.isdir(osp.join(FLAGS.cpdir, d))])[-1]
    fulldir = osp.join(FLAGS.cpdir, FLAGS.rundir)

    print('rundir: ', FLAGS.rundir)
    pb_dir = osp.join(FLAGS.cpdir, '..', 'export', FLAGS.rundir)
    if not osp.exists(pb_dir):
        os.makedirs(pb_dir)
    load_and_export(fulldir, pb_dir)

    d_inputs, d_outputs, outputs = cycle.CycleGAN.test_one_part(osp.join(pb_dir, '{}2{}.pb'.format(FLAGS.Xname, FLAGS.Yname)),
                                 in_data)

    if FLAGS.includein:
        numpy_to_images(in_data, osp.join(FLAGS.XYout, FLAGS.rundir), suffix='-in')
    numpy_to_images(outputs, osp.join(FLAGS.XYout, FLAGS.rundir), suffix='-out')
    print('all done')


if __name__ == '__main__':
    tf.app.run()
