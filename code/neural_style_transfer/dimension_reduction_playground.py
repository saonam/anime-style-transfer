import numpy as np
import tensorflow as tf
import pandas as pd
import sys
import matplotlib as mpl

mpl.use('module://backend_interagg')
import matplotlib.pyplot as plt
import seaborn as sns
from keras.datasets import mnist
from keras.models import Sequential, Model
from keras.layers import Dense, Input
from keras.optimizers import Adam
from sklearn.decomposition import PCA, IncrementalPCA


def normalize(x, use_mean=True):
    x_normed = (x / 255) * 2 - 1
    if use_mean:
        means = x_normed.mean(axis=0)
    else:
        means = 0
    return x_normed - means, means


def denormalize(x, means):
    x += means
    x_denormed = (((x + 1) / 2) * 255).astype(np.int32)
    return x_denormed


def visualize_data(x_orig, y_orig, x_reconst, z, suffix, ims_limit=1000):
    show_data(x_orig[:ims_limit, :], 'x_orig_' + suffix)
    show_data(x_reconst[:ims_limit, :], 'x_reconst_' + suffix)

    plt.title('z_' + suffix)
    plt.axis('off')
    sc = plt.scatter(x=z[:, 0], y=z[:, 1], s=10, c=y_orig, cmap=plt.cm.Set1)
    plt.colorbar(sc)
    plt.clim(-4, 4)
    plt.show()

    # sns.jointplot(x=z_pca_train[:, 0], y=z_pca_train[:, 1])
    # plt.title('z_' + suffix)
    # plt.show()


def show_data(data, name):
    plt.figure(figsize=(20, 20))
    plt.axis('off')
    plt.title(name)
    size = data.shape[0]
    tile_width = int(round(np.sqrt(size)))
    while size % tile_width != 0:
        tile_width -= 1

    nw = size // tile_width
    # aligning images to one big
    h, w = 28, 28
    tiled = data.reshape(tile_width, nw, h, w).swapaxes(1, 2).reshape(tile_width * h, nw * w)

    plt.imshow(tiled, cmap="gray")
    # plt.draw()
    plt.show()


def plot_network_history(history):
    plt.plot(history.history['loss'])
    plt.plot(history.history['val_loss'])
    plt.title('model train vs validation loss - pca')
    plt.ylabel('loss')
    plt.xlabel('epoch')
    plt.legend(['train', 'validation'], loc='upper right')
    plt.show()


def extract_decoder(model: Model, latent_space_name='bottleneck'):
    latest_space_layer_idx = [i for i, v in enumerate(model.layers) if v.name == latent_space_name][0]
    latent_space_size = model.get_layer(latent_space_name).units
    decoder_layers = model.layers[latest_space_layer_idx + 1:]
    in_layer = Input(shape=(latent_space_size,))
    out_layer = in_layer
    for layer in decoder_layers:
        out_layer = layer(out_layer)
    return Model(in_layer, out_layer)


def show_factors(decoder, z_size):
    for i in range(z_size):
        latent_vector = np.zeros((1, z_size))
        latent_vector[:, i] = 1
        plt.imshow(decoder.predict(latent_vector).reshape(28, 28), cmap="gray")
        plt.show()


def main(_):
    z_size = 2
    (x_train, y_train), (x_test, y_test) = mnist.load_data()
    x_train = x_train.reshape(-1, 784)
    y_train = y_train
    x_test = x_test.reshape(-1, 784)
    x_train_normed, mu_train = normalize(x_train)
    x_test_normed, mu_test = normalize(x_test)

    # numpy pure pca
    #####################################################################
    # for PCA it is important to have 0 mean otherwise it does not work #
    #####################################################################
    u, s, v = np.linalg.svd(x_train_normed, full_matrices=False)
    z_pca_train = (x_train_normed @ v.T)[:, :z_size]
    z_pca_test = (x_test_normed @ v.T)[:, :z_size]

    r_pca_train = denormalize(z_pca_train @ v[:z_size, :], mu_train)  # reconstruction
    r_pca_test = denormalize(z_pca_test @ v[:z_size, :], mu_test)  # reconstruction
    err_train = np.sum((x_train - r_pca_train).astype(np.int64) ** 2) / r_pca_train.size
    err_test = np.sum((x_test - r_pca_test).astype(np.int64) ** 2) / r_pca_test.size
    print('PCA train reconstruction error with 2 PCs: ' + str(round(err_train, 3)))
    print('PCA test reconstruction error with 2 PCs: ' + str(round(err_test, 3)))

    for i in range(z_size):
        plt.imshow(v.reshape(-1, 28, 28)[i], cmap="gray")
        plt.show()

    visualize_data(x_train, y_train, r_pca_train, z_pca_train, 'train_pca')
    visualize_data(x_test, y_test, r_pca_test, z_pca_test, 'test_pca')

    # # scikit-learn pca
    # pca = PCA(n_components=z_size)
    # z_pca_train = pca.fit_transform(x_train)
    # z_pca_test = pca.transform(x_test)
    # r_pca_train = pca.inverse_transform(z_pca_train)
    # r_pca_test = pca.inverse_transform(z_pca_test)
    # err_train = np.sum((x_train - r_pca_train).astype(np.int64) ** 2) / r_pca_train.size
    # err_test = np.sum((x_test - r_pca_test).astype(np.int64) ** 2) / r_pca_test.size
    # print('scikit-learn PCA train reconstruction error with 2 PCs: ' + str(round(err_train, 3)))
    # print('scikit-learn PCA test reconstruction error with 2 PCs: ' + str(round(err_test, 3)))
    #
    # for i in range(z_size):
    #     plt.imshow(pca.components_.reshape(-1, 28, 28)[i], cmap="gray")
    #     plt.show()
    #
    # visualize_data(x_train, y_train, r_pca_train, z_pca_train, 'train_sklearn_pca')
    # visualize_data(x_test, y_test, r_pca_test, z_pca_test, 'test_sklearn_pca')

    # # scikit-learn incremental pca
    # pca = IncrementalPCA(n_components=z_size, batch_size=100)
    # z_pca_train = pca.fit_transform(x_train)
    # z_pca_test = pca.transform(x_test)
    # r_pca_train = pca.inverse_transform(z_pca_train)
    # r_pca_test = pca.inverse_transform(z_pca_test)
    # err_train = np.sum((x_train - r_pca_train).astype(np.int64) ** 2) / r_pca_train.size
    # err_test = np.sum((x_test - r_pca_test).astype(np.int64) ** 2) / r_pca_test.size
    # print('scikit-learn incremental PCA train reconstruction error with 2 PCs: ' + str(round(err_train, 3)))
    # print('scikit-learn incremental PCA test reconstruction error with 2 PCs: ' + str(round(err_test, 3)))
    #
    # for i in range(z_size):
    #     plt.imshow(pca.components_.reshape(-1, 28, 28)[i], cmap="gray")
    #     plt.show()
    #
    # visualize_data(x_train, y_train, r_pca_train, z_pca_train, 'train')
    # visualize_data(x_test, y_test, r_pca_test, z_pca_test, 'test')

    # keras pca using autoencoder
    m = Sequential()
    m.add(Dense(z_size, activation='linear', input_shape=(784,), name='bottleneck'))
    m.add(Dense(784, activation='linear', name='decoder'))
    m.compile(loss='mean_squared_error', optimizer=Adam())
    print(m.summary())
    history = m.fit(x_train_normed, x_train_normed, batch_size=256, epochs=10, verbose=1,
                    validation_data=(x_test_normed, x_test_normed))
    encoder = Model(m.input, m.get_layer('bottleneck').output)
    decoder = extract_decoder(m)
    z_pca_train = encoder.predict(x_train_normed)  # bottleneck representation
    z_pca_test = encoder.predict(x_test_normed)  # bottleneck representation
    r_pca_train = denormalize(m.predict(x_test_normed), mu_train)
    r_pca_test = denormalize(m.predict(x_test_normed), mu_test)

    show_factors(decoder, z_size)

    visualize_data(x_train, y_train, r_pca_train, z_pca_train, 'train_pca_ae')
    visualize_data(x_test, y_test, r_pca_test, z_pca_test, 'test_pca_ae')

    plot_network_history(history)

    # keras different autoencoders
    # todo: compare with no mean adjusting
    x_train_normed, mu_train = normalize(x_train)
    x_test_normed, mu_test = normalize(x_test)

    m = Sequential()
    m.add(Dense(512, activation='elu', input_shape=(784,)))
    m.add(Dense(128, activation='elu'))
    m.add(Dense(z_size, activation='linear', name='bottleneck'))
    m.add(Dense(128, activation='elu'))
    m.add(Dense(512, activation='elu'))
    m.add(Dense(784, activation='sigmoid', name='decoder'))
    # m.add(Dense(784, activation='linear', name='decoder'))
    m.compile(loss='mean_squared_error', optimizer=Adam())
    print(m.summary())
    history = m.fit(x_train_normed, x_train_normed, batch_size=256, epochs=30, verbose=1,
                    validation_data=(x_test_normed, x_test_normed))
    encoder = Model(m.input, m.get_layer('bottleneck').output)
    decoder = extract_decoder(m)
    z_pca_train = encoder.predict(x_train_normed)  # bottleneck representation
    z_pca_test = encoder.predict(x_test_normed)  # bottleneck representation
    r_pca_train = denormalize(m.predict(x_train_normed), mu_train)
    r_pca_test = denormalize(m.predict(x_test_normed), mu_test)

    show_factors(decoder, z_size)

    visualize_data(x_train, y_train, r_pca_train, z_pca_train, 'train_ae')
    visualize_data(x_test, y_test, r_pca_test, z_pca_test, 'test_ae')

    plot_network_history(history)

    print('done')


if __name__ == '__main__':
    tf.app.run()
