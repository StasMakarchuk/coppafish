import numpy as np
cimport numpy as cnp
cimport cython

# numpy to Cython data type info:
# https://stackoverflow.com/questions/21851985/difference-between-np-int-np-int-int-and-np-int-t-in-cython

# https://stackoverflow.com/questions/29775700/image-convolution-at-specific-points
@cython.boundscheck(False)
def cy_convolve(cnp.ndarray[cnp.int8_t, ndim=3] im, cnp.ndarray[Py_ssize_t, ndim=3] kernel,
                Py_ssize_t[:, ::1] coords, cnp.ndarray[cnp.int8_t, ndim=3] im2 = None):
    """
    Finds result of convolution at specific locations indicated by `points`.
    I.e. instead of convolving whole `im`, just find result at these `points`.

    !!! note
        im needs to be padded before this function is called otherwise get an error when go out of bounds.

    Args:
        im: `np.int8 [image_szY x image_szX (x image_szZ)]`.
            Image to be filtered. Must be 2D or 3D.
            np.int8 as designed to use on np.sign of an image i.e. only contains -1, 0, 1.
        kernel: `int [kernel_szY x kernel_szX (x kernel_szZ)]`.
            Multidimensional filter. Must be odd in each dimension i.e. run ensure_odd_kernel before calling.
        coords: `int [n_points x image.ndims]`.
            Coordinates where result of filtering is desired.
        im2: `np.int8 [image_szY x image_szX (x image_szZ)]`.
            Can provide another image to find result of filtering with too.
            Must be same size as im.

    Returns:
        - `int [n_points]`.
            Result of filtering of `im` at each point in `coords`.
        - `int [n_points]`.
            Result of filtering of `im2` at each point in `coords`. Only returned if `im2` provided.
    """
    cdef Py_ssize_t j, i, k, y, x, z, n, ks_y, ks_x, ks_z
    cdef Py_ssize_t n_points = coords.shape[0]
    cdef Py_ssize_t[::1] responses = np.zeros(n_points, dtype=int)
    cdef Py_ssize_t[::1] responses2 = np.zeros(n_points, dtype=int)
    cdef Py_ssize_t[::1] x_steps, y_steps, z_steps

    # TODO: maybe modify ranges to avoid 0 values in kernel.
    ks_y = kernel.shape[0]
    # [::-1] inverts array so descending order to give same result as scipy convolution.
    y_steps = np.ascontiguousarray(np.arange(-(ks_y-1)/2, (ks_y-1)/2 + 1,
                                                    dtype=np.intp)[::-1])
    ks_x = kernel.shape[1]
    x_steps = np.ascontiguousarray(np.arange(-(ks_x-1)/2, (ks_x-1)/2 + 1,
                                                    dtype=np.intp)[::-1])
    ks_z = kernel.shape[2]
    z_steps = np.ascontiguousarray(np.arange(-(ks_z-1)/2, (ks_z-1)/2 + 1,
                                                    dtype=np.intp)[::-1])

    for n in range(n_points):
        y = coords[n, 0]
        x = coords[n, 1]
        z = coords[n, 2]
        for j in range(ks_y):
            for i in range(ks_x):
                for k in range(ks_z):
                    responses[n] += im[y+y_steps[j], x+x_steps[i], z+z_steps[k]] * kernel[j, i, k]
                    if im2 is not None:
                        responses2[n] += im2[y + y_steps[j], x + x_steps[i], z + z_steps[k]] * kernel[j, i, k]
    if im2 is not None:
        return np.asarray(responses), np.asarray(responses2)
    else:
        return np.asarray(responses)