import json
import math
import os
from contextlib import redirect_stdout
from datetime import datetime

import numpy as np
import tensorflow as tf
import matplotlib as mpl
from sklearn.decomposition import PCA
from tensorflow.python.util.serialization import get_json_type

mpl.use('module://backend_interagg')
from keras.losses import mean_squared_error
from keras.models import Sequential, Model
from keras.layers import Dense, Input, Flatten, Reshape, Conv2D, Conv2DTranspose, ZeroPadding2D, MaxPooling2D, \
    Cropping2D
from keras.optimizers import Adam
from keras import backend as K
from keras.callbacks import TensorBoard, Callback, LearningRateScheduler, ReduceLROnPlateau
from keras.regularizers import l1
from PIL import Image
import io
import tensorflow.contrib.layers as layers
import tensorflow.contrib.slim as slim
from tensorflow.contrib.slim import arg_scope
import matplotlib.pyplot as plt
from cycle.models.anime._utils import normer, denormer
from keras.backend.tensorflow_backend import set_session

from cycle.utils import TFReader
from dimension_reduction_playground import extract_decoder


def norm_and_resize(data):
    data = normer(data)
    data = tf.image.resize_images(data, (432, 768))  # totally 331 776 pixels
    return data


def denormalize(x):
    x_denormed = (((x + 1) / 2) * 255).astype(np.uint8)
    return x_denormed


def create_dataset(tf_record, batch_size, seed=None):
    data = tf.data.TFRecordDataset(tf_record)
    data = data.map(TFReader._parse_example_encoded, num_parallel_calls=8)
    data = data.map(norm_and_resize, num_parallel_calls=8)
    data = tf.data.Dataset.zip((data, data))
    data = data.apply(tf.data.experimental.shuffle_and_repeat(buffer_size=100, seed=seed))
    data = data.batch(batch_size, drop_remainder=True)
    data = data.prefetch(batch_size * 5)
    return data


def tf_data_generator(iterator):
    next_batch = iterator.get_next()
    while True:
        yield K.get_session().run(next_batch)


def make_image(arr):
    arr = denormalize(arr)
    height, width, channel = arr.shape
    image = Image.fromarray(arr)
    output = io.BytesIO()
    image.save(output, format='PNG')
    image_string = output.getvalue()
    output.close()
    return tf.Summary.Image(height=height,
                            width=width,
                            colorspace=channel,
                            encoded_image_string=image_string)


class TensorBoardThings(Callback):
    def __init__(self, model: Model, data, log_dir):
        super().__init__()
        self.model = model
        self.data = data
        self.writer = tf.summary.FileWriter(log_dir)

    def on_epoch_end(self, epoch, logs={}):
        reconst_images = self.model.predict(self.data)
        for image_orig, image_reconst in zip(self.data, reconst_images):
            summary_orig = tf.Summary(value=[tf.Summary.Value(tag='orig_data', image=make_image(image_orig))])
            summary_reconst = tf.Summary(
                value=[tf.Summary.Value(tag='reconstructed_data', image=make_image(image_reconst))])
            self.writer.add_summary(summary_orig, epoch)
            self.writer.add_summary(summary_reconst, epoch)
            self.writer.flush()
        logs.update({'learning_rate': K.eval(self.model.optimizer.lr)})
        super().on_epoch_end(epoch, logs)


def show_data(data, name, dir_name):
    data = denormalize(data)
    size = data.shape[0]
    for i in range(size):
        plt.figure(figsize=(20, 10))
        plt.axis('off')
        plt.title(name, fontsize='50')
        plt.imshow(data[i])
        plt.savefig(f'figures/{dir_name}/{i}-{name}.png')
        plt.show()


def visualize_data(x_orig, x_reconst, z, dir_name):
    show_data(x_orig, 'x_orig', dir_name)
    show_data(x_reconst, 'x_reconst', dir_name)

    use_pca = z.shape[1] > 2
    if use_pca:
        plt.title(f'z pca from {z.shape[1]} dims to 2')
        pca = PCA(n_components=2)
        z_pca = pca.fit_transform(z)
        plt.scatter(x=z_pca[:, 0], y=z_pca[:, 1], s=10)
    else:
        plt.title('z')
        plt.scatter(x=z[:, 0], y=z[:, 1], s=10)
    plt.savefig(f'figures/{dir_name}/z.png')
    plt.show()

    # sns.jointplot(x=z_pca_train[:, 0], y=z_pca_train[:, 1])
    # plt.title('z_' + suffix)
    # plt.show()


def show_factors(decoder, z_size, dir_name):
    for i in range(z_size):
        latent_vector = np.zeros((1, z_size))
        latent_vector[:, i] = 1
        plt.imshow(denormalize(decoder.predict(latent_vector)[0]))
        plt.axis('off')
        plt.savefig(f'figures/{dir_name}/factor-{i}.png')
        plt.show()


def plot_network_history(history, dir_name):
    plt.plot(history.history['loss'])
    plt.plot(history.history['val_loss'])
    name = 'model train vs validation loss'
    plt.title(name)
    plt.ylabel('loss')
    plt.xlabel('epoch')
    plt.legend(['train', 'validation'], loc='upper right')
    plt.savefig(f'figures/{dir_name}/loss_history.png')
    plt.show()


def save_and_eval_model(m: Model, log_dir, validation_data, history, name):
    model_json = m.to_json()
    with open(log_dir + '/model.json', 'w') as json_file:
        json_file.write(model_json)
    m.save_weights(log_dir + '/model.h5')
    encoder = Model(m.input, m.get_layer('bottleneck').output)
    decoder = extract_decoder(m)
    latent_space = encoder.predict(validation_data[0])  # bottleneck representation
    reconst_data = m.predict(validation_data[0])

    show_factors(decoder, m.get_layer('bottleneck').units, name)
    plot_network_history(history, name)
    visualize_data(validation_data[0], reconst_data, latent_space, name)


def prepare_training(m, log_dir, validation_data):
    tensorboard = TensorBoard(
        log_dir=log_dir, histogram_freq=5, write_images=True, embeddings_freq=5,
        embeddings_layer_names=['bottleneck'], embeddings_data=validation_data[0]
    )
    tbi_callback = TensorBoardThings(model=m, data=validation_data[0], log_dir=log_dir)
    config = tf.ConfigProto()
    config.gpu_options.allow_growth = True
    set_session(tf.Session(config=config))
    return tbi_callback, tensorboard


# def step_decay(epoch):
#     initial_lrate = 5e-4
#     drop = 0.5
#     epochs_drop = 40.0
#     lrate = initial_lrate * math.pow(drop, math.floor((1 + epoch) / epochs_drop))
#     return lrate


def main(_):
    seed = seed = random.randrange(sys.maxsize)
    name = datetime.now().strftime('%Y-%m-%d--%H-%M')
    batch_size = 4
    dataset_name = '../../datasets/anime/no-game-no-life.tfrecord'
    data = create_dataset(dataset_name, batch_size, seed)
    iterator = data.make_one_shot_iterator()
    data_gen = tf_data_generator(iterator)

    K.set_image_data_format('channels_last')  # set format
    tf.set_random_seed(seed)

    # fuck it, I must create some validation data and keep it in memory, because fuck you
    validation_batches = 10
    validation_data = [next(data_gen) for _ in range(validation_batches)]
    validation_data = (np.array([i[0] for i in validation_data]).reshape(-1, 432, 768, 3),
                       np.array([i[1] for i in validation_data]).reshape(-1, 432, 768, 3))

    z_size = 30
    regul_const = 10e-7
    lr =5e-4
    decay = 0.
    # lrate = LearningRateScheduler(step_decay)
    reduce_lr = ReduceLROnPlateau(monitor='loss', patience=5)

    input_tensor = Input(shape=(432, 768, 3))
    out = Conv2D(16, kernel_size=3, strides=1, activation='elu', padding='same')(input_tensor)
    out = Conv2D(24, kernel_size=3, strides=1, activation='elu', padding='same')(out)
    out = Conv2D(32, kernel_size=5, strides=2, activation='elu', padding='same')(out)
    out = Conv2D(48, kernel_size=5, strides=2, activation='elu', padding='same')(out)
    out = Conv2D(64, kernel_size=5, strides=2, activation='elu', padding='same')(out)
    out = Conv2D(96, kernel_size=5, strides=2, activation='elu', padding='same')(out)
    out = Conv2D(128, kernel_size=5, strides=2, activation='elu', padding='same')(out)
    out = Conv2D(32, kernel_size=3, strides=1, activation='elu', padding='same')(out)
    out = Flatten()(out)
    out = Dense(z_size, activation='linear', name='bottleneck', activity_regularizer=l1(regul_const))(out)
    out = Dense(13 * 24 * 32, activation='elu')(out)
    out = Reshape((13, 24, 32))(out)
    out = Conv2DTranspose(128, kernel_size=3, strides=1, activation='elu', padding='same')(out)
    out = Conv2DTranspose(96, kernel_size=5, strides=2, activation='elu', padding='same')(out)
    out = ZeroPadding2D(padding=((1, 0), (0, 0)))(out)
    out = Conv2DTranspose(64, kernel_size=5, strides=2, activation='elu', padding='same')(out)
    out = Conv2DTranspose(18, kernel_size=5, strides=2, activation='elu', padding='same')(out)
    out = Conv2DTranspose(32, kernel_size=5, strides=2, activation='elu', padding='same')(out)
    out = Conv2DTranspose(24, kernel_size=5, strides=2, activation='elu', padding='same')(out)
    out = Conv2DTranspose(16, kernel_size=3, strides=1, activation='elu', padding='same')(out)
    out = Conv2DTranspose(3, kernel_size=1, activation='linear', padding='same')(out)
    m = Model(inputs=input_tensor, outputs=out)
    m.compile(loss=mean_squared_error, optimizer=Adam(lr=lr, beta_1=0.9, beta_2=0.999,
                                                      epsilon=None, decay=decay, amsgrad=False))

    m.summary()
    log_dir = f'logs/anime-{name}'
    os.makedirs(log_dir, exist_ok=True)
    os.makedirs(f'figures/{name}', exist_ok=True)
    # obtaining keras
    with open(f'{log_dir}/model-summary.txt', 'w') as f:
        with redirect_stdout(f):
            m.summary()
            print('dataset: ', dataset_name)
            print('seed: ', seed)
            print('training_config:', json.dumps({
                'optimizer_config': {
                    'class_name': m.optimizer.__class__.__name__,
                    # manual config for adam, because otherwise it can not be persisted before training
                    'config': {
                        'lr': lr,
                        'decay': decay,
                    }
                },
            }, default=get_json_type, indent=2).encode('utf8'))

    tbi_callback, tensorboard = prepare_training(m, log_dir, validation_data)

    history = m.fit_generator(data_gen, steps_per_epoch=500, epochs=200, verbose=1, validation_data=validation_data,
                              validation_steps=validation_batches * batch_size,
                              callbacks=[tensorboard, tbi_callback, reduce_lr])

    save_and_eval_model(m, log_dir, validation_data, history, name)


if __name__ == '__main__':
    tf.app.run()