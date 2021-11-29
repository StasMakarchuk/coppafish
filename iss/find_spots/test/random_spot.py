import numpy as np
from sklearn.neighbors import NearestNeighbors


def random_spot_yx(n_spots, max_y, max_x, max_z=None, min_y=0, min_x=0, min_z=0, min_spot_sep=0):
    """
    produces yx(z) location of n_spots random spots with coordinates in given range.

    :param n_spots: integer, approximate number of spots to create
    :param max_y: integer, max y coordinate.
    :param max_x: integer, max x coordinate.
    :param max_z: integer, max z coordinate, optional. default: None meaning no z dimension.
    :param min_y: integer, min y coordinate, optional. default: 0.
    :param min_x: integer, min x coordinate, optional. default: 0.
    :param min_z: integer, min z coordinate, optional. default: 0.
    :param min_spot_sep: float, optional. min separation of spots (negative means can have repeats). default: 0.
    :return: numpy array [n_spots, 2 or 3]
    """
    spot_y = np.random.choice(range(min_y, max_y+1), n_spots, replace=True)
    spot_x = np.random.choice(range(min_x, max_x+1), n_spots, replace=True)
    if max_z is not None:
        spot_z = np.random.choice(range(min_z, max_z+1), n_spots, replace=True)
        spot_yx = np.concatenate((spot_y.reshape(-1, 1), spot_x.reshape(-1, 1), spot_z.reshape(-1, 1)), axis=1)
    else:
        spot_yx = np.concatenate((spot_y.reshape(-1, 1), spot_x.reshape(-1, 1)), axis=1)
    keep = find_isolated_spots(spot_yx, spot_yx, min_spot_sep)
    return spot_yx[keep, :]


def find_isolated_spots(spot_yx, transformed_spot_yx, min_dist=3):
    """
    this determines, for each spot in transformed_spot_yx, if the second nearest neighbour in spot_yx is further
    away than min_dist.

    :param spot_yx: all spot locations [n_all_spots, 2 or 3]
    :param transformed_spot_yx: subset of spot_yx shifted by one of the transforms. [n_subset_spots, 2 or 3]
    :param min_dist: float, optional. default: 3
    :return: boolean numpy array [n_subset_spots,]. True if transformed_spot_yx further than min_dist pixels from
            second nearest spot in spot_yx.
    """
    nbrs = NearestNeighbors(n_neighbors=2).fit(spot_yx)
    distances, _ = nbrs.kneighbors(transformed_spot_yx)
    keep = distances[:, 1] > min_dist
    return keep


def remove_spots(spot_yx, n_remove):
    """
    removes n_remove spots at random from spot_yx

    :param spot_yx: numpy integer array [n_spots, 2 or 3]
    :param n_remove: integer
    :return: numpy integer array [n_spots-n_remove, 2 or 3]
    """
    remove = np.random.choice(range(spot_yx.shape[0]), n_remove, replace=False)
    return np.delete(spot_yx, remove, 0)


def add_noise(spot_yx, noise_amplitude=1, integer=False):
    """


    :param spot_yx: numpy integer array [n_spots, 2 or 3]
    :param noise_amplitude: float, optional. Max possible value of shift in each dimension. default: 1
    :param integer: boolean, optional. If True, noise added and thus returned array will be integer. default: False
    :return: numpy (float or integer) array [n_spots, 2 or 3]
    """
    if integer:
        noise = np.random.randint(-np.round(noise_amplitude), 1+np.round(noise_amplitude), spot_yx.shape)
    else:
        noise = ((np.random.random(spot_yx.shape))-0.5) * 2 * noise_amplitude
    return spot_yx + noise