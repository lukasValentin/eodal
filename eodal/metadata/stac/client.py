"""
Querying datasets from a Spatio-Temporal Asset Catalog (STAC).
"""

import geopandas as gpd
import pandas as pd
import planetary_computer

from datetime import date, datetime
from pathlib import Path
from pystac_client import Client
from pystac.item_collection import ItemCollection
from shapely.geometry import Polygon
from typing import Any, Dict, List

from eodal.config import get_settings, STAC_Providers
from eodal.utils.decorators import prepare_bbox
from eodal.utils.sentinel2 import ProcessingLevels

Settings = get_settings()

def query_stac(
    date_start: date,
    date_end: date,
    collection: str,
    bounding_box: Polygon,
) -> List[Dict[str, Any]]:
    """
    Queries a STAC (Spatio-Temporal Asset Catalog) by bounding box and
    time period to get items from a user-defined collection.

    This is a sensor-agnostic function called by sensor-specific ones.

    :param date_start:
        start date of the time period
    :param date_end:
        end date of the time period
    :param collection:
        name of the collection
        (e.g., sentinel-2-l2a for Sentinel-2 L2A data)
    :param bounding_box:
        bounding box either as extended well-known text in geographic coordinates
        or as shapely ``Polygon`` in geographic coordinates (WGS84)
    :returns:
        list of dictionary items returned from the STAC query
    """
    # open connection to STAC server
    cat = Client.open(Settings.STAC_BACKEND.URL)
    # transform dates into the required format (%Y-%m-%d)
    datestr = f'{date_start.strftime("%Y-%m-%d")}/{date_end.strftime("%Y-%m-%d")}'
    # search datasets on catalog
    search = cat.search(
        collections=collection,
        intersects=bounding_box,
        datetime=datestr,
        max_items=Settings.MAX_ITEMS,
        limit=Settings.LIMIT_ITEMS,
    )
    # fetch items and convert them to GeoDataFrame, drop all records with
    # too many clouds
    items = search.get_all_items()
    item_json = items.to_dict()
    scenes = item_json["features"]
    return scenes

@prepare_bbox
def sentinel2(
    cloud_cover_threshold: float, processing_level: ProcessingLevels, **kwargs
) -> pd.DataFrame:
    """
    Sentinel-2 specific STAC query allows filtering by scene-wide cloudy pixel
    percentage.

    :param cloud_cover_threshold:
        optional cloud cover threshold to filter datasets by scene cloud coverage.
        Must be provided as number between 0 and 100%.
    :param processing_level:
        Sentinel-2 processing level
    :param kwargs:
        keyword arguments to pass to `query_stac` function
    :returns:
        dataframe with references to found Sentinel-2 scenes
    """
    # check for processing level of the data and set the collection accordingly
    processing_level_stac = eval(f"Settings.STAC_BACKEND.S2{processing_level.name}")
    kwargs.update({"collection": processing_level_stac})

    # query STAC catalog
    scenes = query_stac(**kwargs)
    # get STAC provider specific naming conventions
    s2 = Settings.STAC_BACKEND.Sentinel2
    # loop over found scenes and check their cloud cover
    metadata_list = []
    for scene in scenes:
        # extract scene metadata required for Sentinel-2
        # map the STAC keys to eodal's naming convention
        props = scene["properties"]
        # tile-id requires some string handling in case of AWS
        if isinstance(s2.tile_id, list):
            tile_id = "".join(
                [str(props[x]) for x in Settings.STAC_BACKEND.Sentinel2.tile_id]
            )
        else:
            tile_id = props[Settings.STAC_BACKEND.Sentinel2.tile_id]
        # the product_uri is also not handled the same way by the different
        # STAC providers
        try:
            product_uri = scene[s2.product_uri]
        except KeyError:
            product_uri = props[s2.product_uri]
        # same for the scene_id
        try:
            scene_id = props[s2.scene_id]
        except KeyError:
            scene_id = scene[s2.scene_id]
        meta_dict = {
            "product_uri": product_uri,
            "scene_id": scene_id,
            "spacecraft_name": props[s2.platform],
            "tile_id": tile_id,
            "sensing_date": datetime.strptime(
                props[s2.sensing_time].split("T")[0], "%Y-%m-%d"
            ).date(),
            "cloudy_pixel_percentage": props[s2.cloud_cover],
            "epsg": props[s2.epsg],
            "sensing_time": datetime.strptime(
                props[s2.sensing_time], s2.sensing_time_fmt
            ),
            "sun_azimuth_angle": props[s2.sun_azimuth_angle],
            "sun_zenith_angle": props[s2.sun_zenith_angle]
        }
        # get links to actual Sentinel-2 bands
        meta_dict["assets"] = scene["assets"]
        # only keep scene if the cloudy pixel percentage is not above
        # the user-defined threshold (in theory, this could also be directly
        # passed to the STAC API but then the function is less generic
        if meta_dict["cloudy_pixel_percentage"] <= cloud_cover_threshold:
            metadata_list.append(meta_dict)

    # create pandas DataFrame out of scene metadata records
    return pd.DataFrame(metadata_list)

@prepare_bbox
def sentinel1_rtc(**kwargs) -> pd.DataFrame:
    """
    Sentinel-1 RTC (radiometry and terrain corrected) querying using data
    from Microsoft Planetary Computer.

    :param kwargs:
        :param kwargs:
        keyword arguments to pass to `query_stac` function
    :returns:
        dataframe with references to found Sentinel-1  RTC scenes
    """

    # check STAC provider and status
    if not Settings.USE_STAC:
        raise ValueError('This method requires STAC')
    if Settings.STAC_BACKEND != STAC_Providers.MSPC:
        raise ValueError('This method requires Microsoft Planetary Computer')
    if Settings.PC_SDK_SUBSCRIPTION_KEY == '':
        raise ValueError('This method requires a valid Planetary Computer API key')

    # set collection to sentinel1-rtc
    kwargs.update({'collection': 'sentinel-1-rtc'})

    # query the catalog
    scenes = query_stac(**kwargs)
    metadata_list = []
    for scene in scenes:
        metadata_dict = scene['properties']
        metadata_dict['assets'] = scene['assets']
        metadata_list.append(metadata_dict)

    return pd.DataFrame(metadata_list)

# unit test
if __name__ == "__main__":

    import geopandas as gpd
    from shapely.geometry import box

    # define time period
    date_start = date(2022, 5, 1)
    date_end = date(2022, 5, 31)
    # select processing level
    processing_level = ProcessingLevels.L2A

    # provide bounding box
    bounding_box_fpath = Path(
        '/home/graflu/public/Evaluation/Projects/KP0031_lgraf_PhenomEn/02_Field-Campaigns/Strickhof/WW_2022/Bramenwies.shp'
    )

    # set scene cloud cover threshold [%]
    cloud_cover_threshold = 80

    # Sentinel-1
    res_s1 = sentinel1_rtc(
        date_start=date_start,
        date_end=date_end,
        vector_features=bounding_box_fpath
    )

    # run stack query and make sure some items are returned
    res_s2 = sentinel2(
        date_start=date_start,
        date_end=date_end,
        processing_level=processing_level,
        cloud_cover_threshold=cloud_cover_threshold,
        vector_features=bounding_box_fpath,
    )
    assert res_s2.empty, "no results found"
