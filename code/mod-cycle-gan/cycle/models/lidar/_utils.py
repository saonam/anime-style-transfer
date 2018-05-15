import tensorflow as tf
import cycle

MAX_RAYDIST = 131.0

def normer(data, name='normer'):
    tmp_data = data[:, :, 0] / MAX_RAYDIST
    ndata = tf.concat((tmp_data[:, :, None], data[:, :, 1:]), axis=-1)
    ndata = (ndata * 2) - 1
    return tf.identity(ndata, name=name)

def denormer(data, name='denormer'):
    ndata = (data + 1)/2
    tmp_data = ndata[:, :, 0] * MAX_RAYDIST
    return tf.concat((tmp_data[:, :, None], ndata[:, :, 1:]), axis=-1, name=name)

def _conv_visual(batch):
    depth = tf.image.convert_image_dtype((batch[:, :, :, 0] + 1.0)/2.0, tf.uint8)
    intensity = tf.image.convert_image_dtype((batch[:, :, :, 1] + 1.0)/2.0, tf.uint8)
    zeros = tf.zeros_like(depth)
    return (tf.where(batch[:, :, :, 2] > 0, x=depth, y=zeros),
            tf.where(batch[:, :, :, 2] > 0, x=intensity, y=zeros))

def visualize(data_orig, data_conv, data_conv_conv):
    d1, i1 = _conv_visual(data_orig)
    d2, i2 = _conv_visual(data_conv)
    d3, i3 = _conv_visual(data_conv_conv)
    stripe = tf.ones_like(d1) * 255
    img = tf.concat((d1, d2, d3, stripe[:, :20], i1, i2, i3), axis=1)
    return img[:, :, :, None]

def feature_map(orig, conv):
    odepth = orig[:, :, :, 0]
    ointensity = orig[:, :, :, 1]
    omask = orig[:, :, :, 2]
    cdepth = conv[:, :, :, 0]
    cintensity = conv[:, :, :, 1]
    cmask = conv[:, :, :, 2]
    zeros = tf.zeros_like(odepth)
    torig = tf.concat((tf.where((omask > 0) & (cmask > 0), odepth, zeros),
                       tf.where((omask > 0) & (cmask > 0), ointensity, zeros)), axis=-1)
    tconv = tf.concat((tf.where((omask > 0) & (cmask > 0), cdepth, zeros),
                       tf.where((omask > 0) & (cmask > 0), cintensity, zeros)), axis=-1)
    return torig, tconv
