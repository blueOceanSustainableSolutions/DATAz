"""
dataset.py — AcousticDataset, ScaledDatasetWrapper, scale_data

Pipeline
--------
AcousticDataset   → raw tensors (ais, bathy_rays, spl_rays, t_max)
scale_data()      → wraps each split in ScaledDatasetWrapper and
                    returns (train_ds, val_ds, test_ds, stats)
custom_collate    → merges variable-length ship lists across a batch
"""

import os
import glob

import numpy as np
import pandas as pd
import torch
import torch.nn
import xarray as xr
import geopandas as gpd
import scipy.ndimage as ndimage
from scipy.interpolate import LinearNDInterpolator, NearestNDInterpolator
from shapely.geometry import Point
from torch.utils.data import Dataset



# 1.  Base Dataset


class AcousticDataset(Dataset):
    """
    Loads paired AIS / SPL pickle files and the static bathymetry grid,
    then extracts per-ship radial profiles (bathy rays, SPL rays, t_max).

    Parameters
    ----------
    ais_dir : str
        Directory containing ``AIS_<timestamp>.pickle`` files.
    spl_dir : str
        Directory containing ``SPL_<timestamp>.pickle`` files.
    example_nc_path : str
        NetCDF file used to infer the spatial grid (lat/lon).
    bathy_csv : str
        CSV with columns lat/latitude, lon/longitude, z/depth.
    coastline_shp : str
        Shapefile used to build the land mask.
    cache_dir : str
        Folder for pre-computed bathy / land-mask arrays.
    crop_size : int
        Square spatial crop applied to the centre of the grid.
    use_63hz : bool
        Whether to load the 63 Hz SPL files (True) or 125 Hz (False).
    use_pascal : bool
        If True, convert SPL from dB re 1 µPa to linear Pa before
        returning.
    num_rays : int
        Number of angular rays sampled around each ship position.
    ray_points : int
        Number of equidistant samples along each ray.
    """

    def __init__(
        self,
        ais_dir: str,
        spl_dir: str,
        example_nc_path: str,
        bathy_csv: str,
        coastline_shp: str,
        cache_dir: str = "cache",
        crop_size: int = 250,
        use_63hz: bool = True,
        use_pascal: bool = False,
        num_rays: int = 360,
        ray_points: int = 125,
    ):
        self.cache_dir  = cache_dir
        self.crop_size  = crop_size
        self.use_63hz   = use_63hz
        self.use_pascal = use_pascal
        self.num_rays   = num_rays
        self.ray_points = ray_points
        os.makedirs(self.cache_dir, exist_ok=True)

        # Infer spatial grid from example NetCDF 
        with xr.open_dataset(example_nc_path) as ds_nc:
            orig_lats = np.sort(ds_nc["lat"].values)
            orig_lons = np.sort(ds_nc["lon"].values)

            self.lat_start = (len(orig_lats) - crop_size) // 2
            self.lon_start = (len(orig_lons) - crop_size) // 2

            self.target_lats = orig_lats[self.lat_start: self.lat_start + crop_size]
            self.target_lons = orig_lons[self.lon_start: self.lon_start + crop_size]

            self.lat_min = self.target_lats.min()
            self.lat_max = self.target_lats.max()
            self.lon_min = self.target_lons.min()
            self.lon_max = self.target_lons.max()

        self.ais_files, self.spl_files = self._match_files(ais_dir, spl_dir)
        self.bathy_csv    = bathy_csv
        self.coastline_shp = coastline_shp

        # Pre-compute static arrays (cached to disk)
        self._static_bathy     = self.get_bathymetry()
        self._static_land_mask = self.get_land()

    # Static grid helpers

    def get_land(self) -> torch.Tensor:
        """Build (or load cached) binary land mask. Water=1, Land=0."""
        cache_path = os.path.join(self.cache_dir, f"land_mask_{self.crop_size}.npy")
        if os.path.exists(cache_path):
            return torch.from_numpy(np.load(cache_path)).float()

        gdf      = gpd.read_file(self.coastline_shp)
        land_geom = gdf.unary_union
        mask     = np.ones((self.crop_size, self.crop_size), dtype=np.float32)
        for i, lat in enumerate(self.target_lats):
            for j, lon in enumerate(self.target_lons):
                if land_geom.contains(Point(lon, lat)):
                    mask[i, j] = 0.0

        np.save(cache_path, mask)
        return torch.from_numpy(mask).float()

    def get_bathymetry(self) -> torch.Tensor:
        """Interpolate bathymetry CSV onto the target grid (cached)."""
        cache_path = os.path.join(
            self.cache_dir, f"bathy_aligned_{self.crop_size}.npy"
        )
        if os.path.exists(cache_path):
            return torch.from_numpy(np.load(cache_path)).float()

        df    = pd.read_csv(self.bathy_csv)
        lat_c = self._get_best_col(df, ["lat", "latitude"])
        lon_c = self._get_best_col(df, ["lon", "longitude"])
        z_c   = self._get_best_col(df, ["z", "depth"])

        points     = df[[lat_c, lon_c]].values
        values     = df[z_c].values
        lat_grid, lon_grid = np.meshgrid(
            self.target_lats, self.target_lons, indexing="ij"
        )
        bathy_grid = LinearNDInterpolator(points, values)(lat_grid, lon_grid)

        # Fill NaNs with nearest neighbour
        if np.isnan(bathy_grid).any():
            fill = NearestNDInterpolator(points, values)
            nan_mask = np.isnan(bathy_grid)
            bathy_grid[nan_mask] = fill(lat_grid[nan_mask], lon_grid[nan_mask])

        np.save(cache_path, bathy_grid)
        return torch.from_numpy(bathy_grid).float()

    # Internal helpers

    def _get_best_col(self, df: pd.DataFrame, options: list) -> str:
        col_map = {c.lower(): c for c in df.columns}
        for opt in options:
            if opt.lower() in col_map:
                return col_map[opt.lower()]
        raise KeyError(f"None of {options} found in DataFrame columns.")

    def _match_files(self, ais_dir: str, spl_dir: str):
        ais_paths  = sorted(glob.glob(os.path.join(ais_dir, "AIS_*.pickle")))
        all_spl    = sorted(glob.glob(os.path.join(spl_dir, "SPL_*.pickle")))
        spl_paths  = [
            f for f in all_spl
            if ("_63.0" in os.path.basename(f)) == self.use_63hz
        ]
        ais_map = {
            os.path.basename(f).split("_")[1].split(".")[0]: f
            for f in ais_paths
        }
        m_ais, m_spl = [], []
        for s in spl_paths:
            ts = os.path.basename(s).split("_")[1].split(".")[0]
            if ts in ais_map:
                m_ais.append(ais_map[ts])
                m_spl.append(s)
        return m_ais, m_spl

    # Radial extraction 

    def extract_radials(
        self,
        ship_lat: float,
        ship_lon: float,
        bathy_grid: np.ndarray,
        spl_grid: np.ndarray,
    ):
        """Sample bathy and SPL along ``num_rays`` radials from a ship.

        Returns
        -------
        bathy_rays : ndarray (num_rays, ray_points)
        spl_rays   : ndarray (num_rays, ray_points)
        t_max      : ndarray (num_rays,)  — pixel distance to grid edge
        """
        lat_idx = np.interp(ship_lat, self.target_lats, np.arange(self.crop_size))
        lon_idx = np.interp(ship_lon, self.target_lons, np.arange(self.crop_size))
        H, W    = self.crop_size, self.crop_size

        angles  = np.deg2rad(np.arange(self.num_rays))
        cos_a, sin_a = np.cos(angles), np.sin(angles)

        with np.errstate(divide="ignore", invalid="ignore"):
            t_x = np.where(
                cos_a > 0, (W - 1 - lon_idx) / cos_a,
                np.where(cos_a < 0, -lon_idx / cos_a, np.inf),
            )
            t_y = np.where(
                sin_a > 0, (H - 1 - lat_idx) / sin_a,
                np.where(sin_a < 0, -lat_idx / sin_a, np.inf),
            )

        t_max = np.minimum(t_x, t_y)
        r     = np.linspace(0, 1, self.ray_points)
        x_pts = lon_idx + np.outer(t_max, r) * cos_a[:, None]
        y_pts = lat_idx + np.outer(t_max, r) * sin_a[:, None]

        coords     = np.vstack(
            (np.clip(y_pts, 0, H - 1).ravel(), np.clip(x_pts, 0, W - 1).ravel())
        )
        bathy_rays = ndimage.map_coordinates(bathy_grid, coords, order=1).reshape(
            self.num_rays, self.ray_points
        )
        spl_rays   = ndimage.map_coordinates(spl_grid, coords, order=1).reshape(
            self.num_rays, self.ray_points
        )
        return bathy_rays, spl_rays, t_max.astype(np.float32)

    # Dataset interface

    def __len__(self) -> int:
        return len(self.ais_files)

    def __getitem__(self, idx: int):
        """Return (ais, bathy_rays, spl_rays, t_max) for sample ``idx``."""
        ais_df = pd.read_pickle(self.ais_files[idx])
        lat_c  = self._get_best_col(ais_df, ["lat", "latitude"])
        lon_c  = self._get_best_col(ais_df, ["lon", "longitude"])

        if not ais_df.empty:
            mask   = (
                (ais_df[lat_c] >= self.lat_min) & (ais_df[lat_c] <= self.lat_max)
                & (ais_df[lon_c] >= self.lon_min) & (ais_df[lon_c] <= self.lon_max)
            )
            ais_df = ais_df[mask]

        spl_data  = pd.read_pickle(self.spl_files[idx])
        spl_array = spl_data.values if hasattr(spl_data, "values") else np.array(spl_data)
        if spl_array.shape != (self.crop_size, self.crop_size):
            spl_array = spl_array[
                self.lat_start: self.lat_start + self.crop_size,
                self.lon_start: self.lon_start + self.crop_size,
            ]

        spl_tensor = torch.from_numpy(spl_array).float()
        if self.use_pascal:
            spl_tensor = 1e-6 * torch.pow(10.0, spl_tensor / 20.0)

        spl_np   = (spl_tensor * self._static_land_mask).numpy()
        bathy_np = self._static_bathy.numpy()

        all_bathy, all_spl, all_ais, all_tmax = [], [], [], []

        if ais_df.empty:
            all_ais.append(np.zeros(5))
            all_bathy.append(np.zeros((self.num_rays, self.ray_points)))
            all_spl.append(np.zeros((self.num_rays, self.ray_points)))
            all_tmax.append(np.zeros(self.num_rays))
        else:
            ordered_cols = [lat_c, lon_c] + [
                c for c in ais_df.columns if c not in [lat_c, lon_c, "Name", "Time"]
            ]
            ship_data = ais_df[ordered_cols].values.astype(np.float32)
            for i, (_, row) in enumerate(ais_df.iterrows()):
                b, s, t = self.extract_radials(row[lat_c], row[lon_c], bathy_np, spl_np)
                all_bathy.append(b)
                all_spl.append(s)
                all_ais.append(ship_data[i])
                all_tmax.append(t)

        return (
            torch.tensor(np.stack(all_ais)),
            torch.from_numpy(np.stack(all_bathy)).float(),
            torch.from_numpy(np.stack(all_spl)).float(),
            torch.from_numpy(np.stack(all_tmax)).float(),
        )

    def get_with_metadata(self, idx: int) -> dict:
        """Like ``__getitem__`` but also returns the 2-D ground-truth SPL
        map, ship pixel indices, and the static land mask — useful for
        visualisation."""
        ais, b_rays, s_rays, t_max = self[idx]

        spl_data  = pd.read_pickle(self.spl_files[idx])
        spl_array = spl_data.values if hasattr(spl_data, "values") else np.array(spl_data)
        if spl_array.shape != (self.crop_size, self.crop_size):
            spl_array = spl_array[
                self.lat_start: self.lat_start + self.crop_size,
                self.lon_start: self.lon_start + self.crop_size,
            ]
        gt_2d = torch.from_numpy(spl_array).float()

        ais_df = pd.read_pickle(self.ais_files[idx])
        lat_c  = self._get_best_col(ais_df, ["lat", "latitude"])
        lon_c  = self._get_best_col(ais_df, ["lon", "longitude"])
        ship_indices = []
        if not ais_df.empty:
            for _, row in ais_df.iterrows():
                y_idx = np.interp(row[lat_c], self.target_lats, np.arange(self.crop_size))
                x_idx = np.interp(row[lon_c], self.target_lons, np.arange(self.crop_size))
                ship_indices.append((y_idx, x_idx))
        else:
            ship_indices.append((self.crop_size // 2, self.crop_size // 2))

        return {
            "ais":          ais,
            "bathy_rays":   b_rays,
            "spl_rays":     s_rays,
            "t_max":        t_max,
            "ship_indices": ship_indices,
            "gt_2d":        gt_2d,
            "land_mask":    self._static_land_mask,
            "crop_size":    self.crop_size,
        }



# 2.  Scaling wrapper


class ScaledDatasetWrapper(Dataset):
    """
    Wraps a dataset split and applies normalisation on-the-fly.

    Normalisation strategy
    ~~~~~~~~~~~~~~~~~~~~~~
    * **AIS lat/lon**  — min-max to [0, 1] using the grid extent.
    * **AIS speed / length** (columns 2 & 4) — z-score using training stats.
    * **Bathymetry rays** — min-max to [0, 1], zeroed over land (depth ≤ 0).
    * **SPL rays**     — min-max to [0, 1], zeroed over land.

    Parameters
    ----------
    subset : Dataset
        A ``torch.utils.data.Subset`` or compatible object.
    stats  : dict
        Statistics dict as returned by :func:`scale_data`.
    """

    def __init__(self, subset, stats: dict):
        self.subset = subset
        self.stats  = stats

        # Traverse nested wrappers to reach AcousticDataset
        curr = subset
        while hasattr(curr, "dataset"):
            curr = curr.dataset
        self.base_dataset = curr

    def __len__(self) -> int:
        return len(self.subset)

    def _scale_tensors(self, ais, bathy, spl, tmax):
        if ais.shape[0] > 0 and not torch.all(ais == 0):
            ais = ais.clone()
            m   = self.stats["ais"]["means"].to(ais.device)
            s   = self.stats["ais"]["stds"].to(ais.device)
            ais[:, [2, 4]] = (ais[:, [2, 4]] - m) / s

            bd  = self.base_dataset
            ais[:, 0] = (ais[:, 0] - bd.lat_min) / (bd.lat_max - bd.lat_min)
            ais[:, 1] = (ais[:, 1] - bd.lon_min) / (bd.lon_max - bd.lon_min)

        b_min, b_max = self.stats["bathy"]["min"], self.stats["bathy"]["max"]
        s_min, s_max = self.stats["spl"]["min"],   self.stats["spl"]["max"]

        water_mask   = (bathy > 0).float()
        scaled_bathy = torch.clamp((bathy - b_min) / (b_max - b_min + 1e-8), 0, 1) * water_mask
        scaled_spl   = torch.clamp((spl   - s_min) / (s_max - s_min + 1e-8), 0, 1) * water_mask

        return ais, scaled_bathy, scaled_spl, tmax

    def __getitem__(self, idx: int):
        return self._scale_tensors(*self.subset[idx])

    def get_with_metadata(self, idx: int) -> dict:
        """Returns scaled tensors merged with the raw metadata dict."""
        meta = self.base_dataset.get_with_metadata(self.subset.indices[idx])
        ais, b, s, t = self._scale_tensors(
            meta["ais"], meta["bathy_rays"], meta["spl_rays"], meta["t_max"]
        )
        meta.update({"ais": ais, "bathy_rays": b, "spl_rays": s, "t_max": t})
        return meta



# 3.  Collate & scaling entry-point


def custom_collate(batch):
    """Collate variable-length ship lists by concatenating along dim 0."""
    return (
        torch.cat([item[0] for item in batch], dim=0),
        torch.cat([item[1] for item in batch], dim=0),
        torch.cat([item[2] for item in batch], dim=0),
        torch.cat([item[3] for item in batch], dim=0),
    )


def scale_data(train_ds, val_ds, test_ds):
    """
    Compute scaling statistics from the training split only (no leakage)
    and return wrapped datasets together with the statistics dictionary.

    Parameters
    ----------
    train_ds, val_ds, test_ds : Dataset subsets

    Returns
    -------
    sc_train, sc_val, sc_test : ScaledDatasetWrapper
    stats : dict
        Keys: ``spl``, ``ais``, ``bathy`` — each a sub-dict of scalars
        and tensors needed to invert normalisation.
    """
    print("Computing dataset statistics from training set …")

    # Navigate to AcousticDataset base
    curr = train_ds
    while hasattr(curr, "dataset"):
        curr = curr.dataset
    base = curr

    # Bathymetry stats (static grid) 
    static_bathy = base._static_bathy
    water_mask   = static_bathy > 0
    if water_mask.any():
        bathy_min = static_bathy[water_mask].min().item()
        bathy_max = static_bathy[water_mask].max().item()
    else:
        bathy_min, bathy_max = 0.0, 500.0

    # AIS + SPL stats (accumulated from training subset)
    all_ais_features = []
    spl_min =  float("inf")
    spl_max =  float("-inf")

    for idx in range(len(train_ds)):
        ais, _, spl, _ = train_ds[idx]

        if ais.shape[0] > 0 and not torch.all(ais == 0):
            all_ais_features.append(ais[:, [2, 4]])

        if (spl > 0).any():
            cur_min = spl[spl > 0].min().item()
            cur_max = spl.max().item()
            spl_min = min(spl_min, cur_min)
            spl_max = max(spl_max, cur_max)

    if spl_min == float("inf"):  spl_min = 40.0
    if spl_max == float("-inf"): spl_max = 120.0

    if all_ais_features:
        cat  = torch.cat(all_ais_features, dim=0)
        ais_means = cat.mean(dim=0)
        ais_stds  = torch.clamp(cat.std(dim=0), min=1e-6)
    else:
        ais_means = torch.tensor([10.0, 150.0])
        ais_stds  = torch.tensor([ 5.0,  50.0])

    stats = {
        "spl":   {"min": spl_min,   "max": spl_max},
        "ais":   {"means": ais_means, "stds": ais_stds},
        "bathy": {"min": bathy_min,  "max": bathy_max},
    }

    print(f"  Bathy  range : {bathy_min:.1f} m → {bathy_max:.1f} m")
    print(f"  SPL    range : {spl_min:.1f}   → {spl_max:.1f}")
    print(f"  AIS    means : {ais_means.tolist()}")
    print(f"  AIS    stds  : {ais_stds.tolist()}")

    return (
        ScaledDatasetWrapper(train_ds, stats),
        ScaledDatasetWrapper(val_ds,   stats),
        ScaledDatasetWrapper(test_ds,  stats),
        stats,
    )
