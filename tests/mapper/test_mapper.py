'''
Created on Dec 14, 2022

@author: graflu
'''

import pytest

import geopandas as gpd

from datetime import datetime
from shapely.geometry import Point, Polygon

from eodal.config import get_settings
from eodal.mapper.feature import Feature
from eodal.mapper.filter import Filter
from eodal.mapper.mapper import MapperConfigs, Mapper

Settings = get_settings()

def test_mapper_configs(tmppath):

    # construct a Feature
    collection = 'sentinel2-msi'
    geom = Point([49,11])
    epsg = 4326
    name = 'Test Point'
    attributes = {'this': 'is a test', 'a': 123}
    feature = Feature(name, geom, epsg, attributes)

    # define further search criteria
    time_start = datetime(2022,12,1)
    time_end = datetime.now()
    metadata_filters = [
        Filter('cloudy_pixel_percentage', '<', 30), Filter('snow_ice_percentage', '<', 10)
    ]

    mapper_configs = MapperConfigs(collection, feature, time_start, time_end, metadata_filters)
    fpath = tmppath.joinpath('test.yml')
    mapper_configs.to_yaml(fpath)

    mapper_configs_rl = MapperConfigs.from_yaml(fpath)
    assert mapper_configs.feature.name == mapper_configs_rl.feature.name, 'wrong feature name'
    assert mapper_configs.feature.epsg == mapper_configs_rl.feature.epsg, 'wrong feature EPSG'
    assert mapper_configs.feature.geometry == mapper_configs_rl.feature.geometry, 'wrong feature geometry'
    assert set(mapper_configs.feature.attributes) == set(mapper_configs_rl.feature.attributes), \
        'wrong feature attributes'
    assert mapper_configs.time_start == mapper_configs_rl.time_start, 'wrong start time'
    assert mapper_configs.time_end == mapper_configs_rl.time_end, 'wrong end time'
    assert mapper_configs.collection == mapper_configs_rl.collection, 'wrong collection'
    for idx, _filter in enumerate(mapper_configs.metadata_filters):
        assert _filter.expression == mapper_configs_rl.metadata_filters[idx].expression, \
            'wrong filtering expression'
        assert _filter.entity == mapper_configs_rl.metadata_filters[idx].entity, \
            'wrong filtering entity'

@pytest.mark.parametrize(
    'collection,time_start,time_end,geom,metadata_filters',
    [(
        'sentinel2-msi',
        datetime(2022,7,1),
        datetime(2022,7,15),
        Polygon(
            [[493504.953633058525156, 5258840.576098721474409],
            [493511.206339373020455, 5258839.601945200935006],
            [493510.605988947849255, 5258835.524093257263303],
            [493504.296645800874103, 5258836.554883609525859],
            [493504.953633058525156, 5258840.576098721474409]]
        ),
        [Filter('cloudy_pixel_percentage','<', 100), Filter('processing_level', '==', 'Level-2A')],
    ),
    (
        'sentinel1-grd',
        datetime(2020,7,1),
        datetime(2020,7,15),
        Polygon(
            [[493504.953633058525156, 5258840.576098721474409],
            [493511.206339373020455, 5258839.601945200935006],
            [493510.605988947849255, 5258835.524093257263303],
            [493504.296645800874103, 5258836.554883609525859],
            [493504.953633058525156, 5258840.576098721474409]]
        ),
        [Filter('product_type','==', 'GRD')],
    )]
)
def test_mapper_get_scenes_db(collection, time_start, time_end, geom, metadata_filters):
    """
    testing the get_scenes() method of the mapper class

    IMPORTANT:
        This tests only works within the ETH EOdal environment as it expects
        certain entries (scenes) in the database (see TODO-statement)

    TODO: Create a test database instance
    """
    Settings.USE_STAC = False
    feature = Feature(
        name='Test Area',
        geometry=geom,
        epsg=32632,
        attributes={'id': 1}
    )
    mapper_configs = MapperConfigs(
        collection=collection,
        time_start=time_start,
        time_end=time_end,
        feature=feature,
        metadata_filters=metadata_filters
    )
    mapper = Mapper(mapper_configs)
    mapper.query_scenes()

    assert isinstance(mapper.metadata, gpd.GeoDataFrame), 'expected a GeoDataFrame'
    assert not mapper.metadata.empty, 'expected some items to be returned'


@pytest.mark.parametrize(
    'collection,time_start,time_end,geom,metadata_filters',
    [(
        'sentinel2-msi',
        datetime(2022,7,1),
        datetime(2022,7,15),
        Polygon(
            [[493504.953633058525156, 5258840.576098721474409],
            [493511.206339373020455, 5258839.601945200935006],
            [493510.605988947849255, 5258835.524093257263303],
            [493504.296645800874103, 5258836.554883609525859],
            [493504.953633058525156, 5258840.576098721474409]]
        ),
        [Filter('cloudy_pixel_percentage','<', 100), Filter('processing_level', '==', 'Level-2A')],
    ),
    (
        'sentinel1-grd',
        datetime(2020,7,1),
        datetime(2020,7,15),
        Polygon(
            [[493504.953633058525156, 5258840.576098721474409],
            [493511.206339373020455, 5258839.601945200935006],
            [493510.605988947849255, 5258835.524093257263303],
            [493504.296645800874103, 5258836.554883609525859],
            [493504.953633058525156, 5258840.576098721474409]]
        ),
        [Filter('product_type','==', 'GRD')],
    )]
)
def test_mapper_get_scenes_stac(collection, time_start, time_end, geom, metadata_filters):
    """"""
    Settings.USE_STAC = True
    feature = Feature(
        name='Test Area',
        geometry=geom,
        epsg=32632,
        attributes={'id': 1}
    )
    mapper_configs = MapperConfigs(
        collection=collection,
        time_start=time_start,
        time_end=time_end,
        feature=feature,
        metadata_filters=metadata_filters
    )
    mapper = Mapper(mapper_configs)
    mapper.query_scenes()

    assert isinstance(mapper.metadata, gpd.GeoDataFrame), 'expected a GeoDataFrame'
    assert not mapper.metadata.empty, 'expected some items to be returned'

@pytest.fixture
def get_mapper():
    def _get_mapper():

        Settings.USE_STAC = True

        collection = 'sentinel2-msi'
        time_start = datetime(2022,7,1)
        time_end = datetime(2022,7,15)
        geometry = Polygon(
            [[493504.953633058525156, 5258840.576098721474409],
            [493511.206339373020455, 5258839.601945200935006],
            [493510.605988947849255, 5258835.524093257263303],
            [493504.296645800874103, 5258836.554883609525859],
            [493504.953633058525156, 5258840.576098721474409]]
        )
        filters = [Filter('cloudy_pixel_percentage','<', 100), Filter('processing_level', '==', 'Level-2A')]
        feature = Feature(
            name='Test Area',
            geometry=geometry,
            epsg=32632,
            attributes={'id': 1}
        )
        mapper_configs = MapperConfigs(
            collection=collection,
            time_start=time_start,
            time_end=time_end,
            feature=feature,
            metadata_filters=filters
        )
        mapper = Mapper(mapper_configs)
        mapper.query_scenes()

        return mapper
    return _get_mapper

def test_mapper_load_scenes(get_mapper):
    
    mapper = get_mapper()
    scene_constructor_kwargs = {'band_names_src': ['B02', 'B03', 'B04']}
    mapper.load_scenes(scene_constructor_kwargs=scene_constructor_kwargs)


    