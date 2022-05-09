from .. import utils, setup
from .. import find_spots as fs
from tqdm import tqdm
import numpy as np
import numpy_indexed
from ..setup.notebook import NotebookPage
from ..extract import scale
from ..spot_colors import get_all_pixel_colors, get_spot_colors
from ..call_spots import get_spot_intensity, fit_background
from .. import omp
from sklearn.neighbors import NearestNeighbors
import os
from scipy import sparse


def call_spots_omp(config: dict, nbp_file: NotebookPage, nbp_basic: NotebookPage,
                   nbp_call_spots: NotebookPage, tile_origin: np.ndarray,
                   transform: np.ndarray, ref_spots_intensity_thresh: float) -> NotebookPage:
    nbp = setup.NotebookPage("omp")

    # use bled_codes with gene efficiency incorporated and only use_rounds/channels
    rc_ind = np.ix_(nbp_basic.use_rounds, nbp_basic.use_channels)
    bled_codes = np.moveaxis(np.moveaxis(nbp_call_spots.bled_codes_ge, 0, -1)[rc_ind], -1, 0)
    norm_bled_codes = np.linalg.norm(bled_codes, axis=(1, 2))
    if np.abs(norm_bled_codes-1).max() > 1e-6:
        raise ValueError("nbp_call_spots.bled_codes_ge don't all have an L2 norm of 1 over "
                         "use_rounds and use_channels.")
    n_genes, n_rounds_use, n_channels_use = bled_codes.shape
    dp_norm_shift = nbp_call_spots.dp_norm_shift * np.sqrt(n_rounds_use)

    if nbp_basic.is_3d:
        detect_radius_z = config['radius_z']
        n_z = nbp_basic.nz
    else:
        detect_radius_z = None
        n_z = 1

    # determine initial_intensity_thresh from average intensity over all pixels on central z-plane.
    if config['initial_intensity_thresh'] is None:
        config['initial_intensity_thresh'] = \
            utils.round_any(nbp_call_spots.median_abs_intensity * config['initial_intensity_thresh_auto_param'],
                            config['initial_intensity_precision'])
    nbp.initial_intensity_thresh = \
        float(np.clip(config['initial_intensity_thresh'], config['initial_intensity_thresh_min'],
                      config['initial_intensity_thresh_max']))

    use_tiles = nbp_basic.use_tiles.copy()
    if not os.path.isfile(nbp_file.omp_spot_shape):
        # Set tile order so do central tile first because better to compute spot_shape from central tile.
        t_centre = scale.select_tile(nbp_basic.tilepos_yx, nbp_basic.use_tiles)
        t_centre_ind = np.where(np.array(nbp_basic.use_tiles) == t_centre)[0][0]
        use_tiles[0], use_tiles[t_centre_ind] = use_tiles[t_centre_ind], use_tiles[0]
        spot_shape = None
    else:
        nbp.shape_tile = None
        nbp.shape_spot_local_yxz = None
        nbp.shape_spot_gene_no = None
        nbp.spot_shape_float = None
        # -1 because saved as uint16 so convert 0, 1, 2 to -1, 0, 1.
        spot_shape = utils.tiff.load(nbp_file.omp_spot_shape).astype(int) - 1

    spot_info = np.zeros((0, 7), dtype=np.int16)
    spot_coefs = sparse.csr_matrix(np.zeros((0, n_genes)))
    for t in use_tiles:
        # TODO: Maybe detect spots on each z-plane then convolution at end.
        pixel_yxz_t = np.zeros((0, 3), dtype=np.int16)
        pixel_coefs_t = sparse.csr_matrix(np.zeros((0, n_genes)))
        for z in range(n_z):
            # While iterating through tiles, only save info for rounds/channels using - add all rounds/channels back in later
            # this returns colors in use_rounds/channels only and no nan.
            pixel_colors_tz, pixel_yxz_tz = get_all_pixel_colors(t, transform, nbp_file, nbp_basic, z)
            # save memory - colors max possible value is around 80000. yxz max possible value is around 2048.
            pixel_colors_tz = pixel_colors_tz.astype(np.int32)
            pixel_yxz_tz = pixel_yxz_tz.astype(np.int16)

            # Only keep pixels with significant absolute intensity to save memory.
            # absolute because important to find negative coefficients as well.
            pixel_intensity_tz = get_spot_intensity(np.abs(pixel_colors_tz / nbp_call_spots.color_norm_factor[rc_ind]))
            keep = pixel_intensity_tz > nbp.initial_intensity_thresh
            pixel_colors_tz = pixel_colors_tz[keep]
            pixel_yxz_tz = pixel_yxz_tz[keep]
            del pixel_intensity_tz, keep

            pixel_coefs_tz = sparse.csr_matrix(
                omp.get_all_coefs(pixel_colors_tz / nbp_call_spots.color_norm_factor[rc_ind], bled_codes,
                                  nbp_call_spots.background_weight_shift,  dp_norm_shift, config['dp_thresh'],
                                  config['alpha'], config['beta'],  config['max_genes'], config['weight_coef_fit'])[0])
            del pixel_colors_tz
            # Only keep pixels for which at least one gene has non-zero coefficient.
            keep = (np.abs(pixel_coefs_tz).max(axis=1) > 0).nonzero()[0]  # nonzero as is sparse matrix.
            pixel_yxz_t = np.append(pixel_yxz_t, pixel_yxz_tz[keep].astype(np.int16), axis=0)
            del pixel_yxz_tz
            pixel_coefs_t = sparse.vstack((pixel_coefs_t, pixel_coefs_tz[keep]))
            del pixel_coefs_tz, keep

        if spot_shape is None:
            nbp.shape_tile = t
            spot_yxz, spot_gene_no = omp.get_spots(pixel_coefs_t, pixel_yxz_t, config['radius_xy'], detect_radius_z)
            z_scale = nbp_basic.pixel_size_z / nbp_basic.pixel_size_xy
            spot_shape, spots_used, nbp.spot_shape_float = \
                omp.spot_neighbourhood(pixel_coefs_t, pixel_yxz_t, spot_yxz, spot_gene_no, config['shape_max_size'],
                                       config['shape_pos_neighbour_thresh'], config['shape_isolation_dist'], z_scale,
                                       config['shape_sign_thresh'])

            nbp.shape_spot_local_yxz = spot_yxz[spots_used]
            nbp.shape_spot_gene_no = spot_gene_no[spots_used]
            utils.tiff.save(spot_shape + 1, nbp_file.omp_spot_shape)  # add 1 so can be saved as uint16.
            del spot_yxz, spot_gene_no, spots_used

        spot_info_t = \
            omp.get_spots(pixel_coefs_t, pixel_yxz_t, config['radius_xy'], detect_radius_z, 0, spot_shape,
                          config['initial_pos_neighbour_thresh'])
        n_spots = spot_info_t[0].shape[0]
        spot_info_t = np.concatenate([spot_var.reshape(n_spots, -1).astype(np.int16) for spot_var in spot_info_t],
                                     axis=1)
        spot_info_t = np.append(spot_info_t, np.ones((n_spots, 1), dtype=np.int16) * t, axis=1)

        # find index of each spot in pixel array to add colors and coefs
        pixel_index = numpy_indexed.indices(pixel_yxz_t, spot_info_t[:, :3])

        # append this tile info to all tile info
        spot_coefs = sparse.vstack((spot_coefs, pixel_coefs_t[pixel_index]))
        del pixel_coefs_t, pixel_index
        spot_info = np.append(spot_info, spot_info_t, axis=0)
        del spot_info_t

    nbp.spot_shape = spot_shape

    # find duplicate spots as those detected on a tile which is not tile centre they are closest to
    # Do this in 2d as overlap is only 2d
    tile_centres = tile_origin + nbp_basic.tile_centre
    tree_tiles = NearestNeighbors(n_neighbors=1).fit(tile_centres[:, :2])
    spot_global_yxz = spot_info[:, :3] + tile_origin[spot_info[:, 6]]
    _, all_nearest_tile = tree_tiles.kneighbors(spot_global_yxz[:, :2])
    not_duplicate = all_nearest_tile.flatten() == spot_info[:, 6]

    # Add spot info to notebook page
    nbp.local_yxz = spot_info[not_duplicate, :3]
    nbp.tile = spot_info[not_duplicate, 6]

    # Get colors, background_coef and intensity of final spots.
    n_spots = np.sum(not_duplicate)
    nan_value = -nbp_basic.tile_pixel_value_shift - 1
    nd_spot_colors = np.ones((n_spots, nbp_basic.n_rounds, nbp_basic.n_channels), dtype=int) * nan_value
    for t in tqdm(use_tiles, desc='Current Tile'):
        in_tile = nbp.tile == t
        if np.sum(in_tile) > 0:
            nd_spot_colors[in_tile] = get_spot_colors(nbp.local_yxz[in_tile], t, transform, nbp_file, nbp_basic)
    utils.errors.check_spot_color_nan(nd_spot_colors, nbp_basic)
    nbp.colors = nd_spot_colors

    nd_background_coefs = np.ones((n_spots, nbp_basic.n_channels)) * np.nan
    spot_colors_norm = nd_spot_colors[np.ix_(np.arange(n_spots), nbp_basic.use_rounds, nbp_basic.use_channels)
                       ] / nbp_call_spots.color_norm_factor[rc_ind]
    nd_background_coefs[np.ix_(np.arange(n_spots), nbp_basic.use_channels)] = \
        fit_background(spot_colors_norm, nbp_call_spots.background_weight_shift)[1]
    nbp.background_coef = nd_background_coefs
    nbp.intensity = get_spot_intensity(spot_colors_norm)
    del spot_colors_norm

    nbp.coef = spot_coefs[not_duplicate].toarray()
    nbp.gene_no = spot_info[not_duplicate, 3]
    nbp.n_neighbours_pos = spot_info[not_duplicate, 4]
    nbp.n_neighbours_neg = spot_info[not_duplicate, 5]

    # Add quality thresholds to notebook page
    nbp.score_multiplier = config['score_multiplier']
    nbp.score_thresh = config['score_thresh']
    if config['intensity_thresh'] is None:
        nbp.intensity_thresh = ref_spots_intensity_thresh
    else:
        nbp.intensity_thresh = config['intensity_thresh']

    return nbp