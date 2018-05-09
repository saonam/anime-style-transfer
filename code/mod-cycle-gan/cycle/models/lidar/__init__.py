__all__ = ['X_normer', 'X_denormer', 'Y_normer', 'Y_denormer', 'X_DATA_SHAPE', 'Y_DATA_SHAPE', 'XY_Generator', 'YX_Generator', 'X_Discriminator', 'Y_Discriminator', 'visualise', 'X_name', 'Y_name']

import cycle
from . import _utils as utils

X_normer = utils.normer
Y_normer = utils.normer
X_denormer = utils.denormer
Y_denormer = utils.denormer
XY_Generator = cycle.nets.BaseNet
YX_Generator = cycle.nets.BaseNet
X_Discriminator = cycle.nets.BaseNet
Y_Discriminator = cycle.nets.BaseNet
X_name = 'valeo'
Y_name = 'gta'
visualise = utils.visualise

X_DATA_SHAPE = (64, 2084, 3)
Y_DATA_SHAPE = (64, 2084, 3)