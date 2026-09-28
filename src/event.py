# Environment and simulation controller
import geopandas as gpd 
import matplotlib.pyplot as plt
from shapely.geometry import Point
from datetime import datetime
from tqdm import tqdm
import os
import numpy as np
from .utils import *
from .base import *
import rasterio 

class HeatEvent:
    """Represents an extreme heat event simulation"""
    def __init__(self, temperature, study_area=None):
        self.temperature = temperature
        self.parcels = []  # Dictionary of parcel objects
        self.cooling_centers = []  # Dictionary of cooling center objects
        self.transit_points = []  # Dictionary of transit access points
        self.census_data = []  # Dictionary of census tract data
        self.gdf = None
        self.temp_raster = None
    
    def assign_binary(self, group):
        try:
            n_ac = int(group['AC'].unique()[0])
        except:
            n_ac = 0
        n = len(group)
        if n_ac <= n:
            ac_flags = np.array([1]*n_ac + [0]*(n - n_ac))
        else:
            ac_flags = np.ones(shape=n)
        np.random.shuffle(ac_flags)
        group['ac_ownership'] = ac_flags
        return group

    def load_data(self):
        """Load parcel data from PostgreSQL"""
        query = """
        SELECT *
        FROM parcels_with_cooling_centers_v5
        WHERE prop_type_res = 'Residential'
        """
        parcel_gdf = fetch_spatial_data(query)
        if parcel_gdf is not None and not parcel_gdf.empty:
            print(f"Loaded {len(parcel_gdf)} parcels")
            parcel_gdf['AC'] = parcel_gdf['hh_owns_central_ac_2024'] + parcel_gdf['hh_owns_ductless_ac_2024']
            parcel_gdf = parcel_gdf.groupby('block_group_id', group_keys=False).apply(self.assign_binary)
            for idx, row in parcel_gdf.iterrows():
                attrs = {
                    'geometry': row['geom'],
                    'medianhhi': row['medianhhi'],
                    'ageunder18': row['ageunder18'],
                    'age18_39': row['age18_39'],
                    'age40_64': row['age40_64'],
                    'age65up': row['age65up'],
                    'pubtransit': row['pubtransit'],
                    'povertyn': row['povertyn'],
                    'poptotal': row['poptotal'],
                    'popinhh': row['popinhh'],
                    'avghhsize': row['avghhsize'],
                    'AC': row['ac_ownership']
                }
                self.parcels.append(Parcel(
                    parcel_id = row['pid'],
                    nearest_cooling_centers = row['nearest_center_names'],
                    cooling_distance = row['nearest_center_distances'][0],
                    attributes = attrs
                ))
            assert len(self.parcels)!=0, "No parcels loaded!"
            return True
        return False

    def join_temps_to_parcels(self, temp_raster=None, temperature=70):
        """
        Join temperature values to parcels.
        
        Args:
            temp_raster (str, optional): Path to temperature raster file.
            temperature (float, optional): Static temperature value to use if no raster is provided.
        """
        # If temp_raster is provided, use it to extract temperature values
        if temp_raster:
            try:
                src = rasterio.open(temp_raster)
                for parcel in self.parcels:
                    try:
                        centroid = parcel.attributes['geometry'].centroid
                        coords = [(centroid.x, centroid.y)]
                        values = list(src.sample(coords))
                        
                        # If needed, flatten
                        values = [v[0] for v in values]
                        if values:
                            parcel.attributes['temperature'] = values[0]
                        else:
                            parcel.attributes['temperature'] = temperature
                    except Exception as e:
                        print(f"Error sampling parcel: {e}")
                        parcel.attributes['temperature'] = temperature
                src.close()
            except Exception as e:
                print(f"Error opening raster: {e}")
                # Fall back to static temperature
                for parcel in self.parcels:
                    parcel.attributes['temperature'] = temperature
        # If no temp_raster is provided, use the static temperature value
        else:
            for parcel in self.parcels:
                parcel.attributes['temperature'] = temperature
    
    def assign_synthetic_population(self):
        """Create synthetic population by assigning census tract attributes to parcels"""
        print("Generating synthetic population...")

        for parcel in self.parcels:
            # Income assignment 
            median_income = parcel.attributes['medianhhi']
            std = 0.2 * median_income # play around with the scaling factor for std
            income = np.random.normal(loc=median_income, scale=std)
            parcel.attributes['medianhhi'] = income
            
            # Age assignment 
            ageunder18 = parcel.attributes['ageunder18'] / parcel.attributes['poptotal']
            age18_39 = ageunder18 + parcel.attributes['age18_39'] / parcel.attributes['poptotal']
            age40_64 = age18_39 + parcel.attributes['age40_64'] / parcel.attributes['poptotal']
            age65up = age40_64 + parcel.attributes['age65up'] / parcel.attributes['poptotal']
            random_bin = np.random.uniform(0,1)

            if random_bin <= ageunder18:
                age = np.random.randint(0,18)
            elif random_bin <= age18_39:
                age = np.random.randint(18, 39)
            elif random_bin <= age40_64:
                age = np.random.randint(40, 64)
            elif random_bin <= age65up:
                age = np.random.randint(65, 100)

            std = 0.1 * age # play around with the scaling factor for std
            age65up = np.random.normal(loc=age, scale=std)
            parcel.attributes['total_age'] = age65up

        print("Synthetic population is generated!")
    
    def run_simulation(self, temp_raster=None, temperature=None):
        """
        Run the heat event simulation.
        
        Args:
            temp_raster (str, optional): Path to temperature raster file.
            temperature (int/float, optional): Static temperature value for the simulation.
                                              If not provided, uses self.temperature.
        """
        # If temperature parameter is not provided, use the object's temperature attribute
        if temperature is None:
            temperature = self.temperature
    
        if temp_raster:
            print(f"Running simulation with raster: {temp_raster}")
            print(f"(Using {temperature}°F as fallback where raster sampling fails)")
        else:
            print(f"Running simulation at static temperature: {temperature}°F")

        self.load_data()
        
        self.join_temps_to_parcels(temp_raster=temp_raster, temperature=temperature)

        self.assign_synthetic_population()

        for parcel in tqdm(self.parcels, desc="Simulating decisions"):
            parcel.make_decision()
            
            # # If they chose a cooling center, add them as visitor
            # if parcel.decision != 'stay':
            #     cc_id = parcel.decision
            #     self.cooling_centers[cc_id].add_visitor(pid)
    
        print(f"Decision are made!")

    def process_results(self):
        data = []
        for parcel in self.parcels:
           pid = parcel.id
           proba = parcel.proba
           decision = parcel.decision
           geom = parcel.attributes['geometry']
           data.append([pid, proba, decision, geom])
        self.gdf = gpd.GeoDataFrame(data=data, columns=['pid', 'proba', 'decision', 'geometry']).set_crs(epsg=26915)
        os.makedirs(f'./results/{datetime.now().strftime("%Y%m%d_%H%M%S")}', exist_ok=True)
        self.gdf.to_file(f'./results/{datetime.now().strftime("%Y%m%d_%H%M%S")}/file_{datetime.now().strftime("%Y%m%d_%H%M%S")}.shp', driver='ESRI Shapefile')
        
    def visualize_results(self, output_filename=None):
        """Visualize the simulation results"""
        if self.gdf is not None:
            fig, ax = plt.subplots(1,2,figsize=(12,12))
            self.gdf.plot(ax=ax[0], column='decision')
            self.gdf.plot(ax=ax[1], column='proba')
            
            # Create figures directory if it doesn't exist
            figures_dir = './figures'
            os.makedirs(figures_dir, exist_ok=True)
            
            plt.savefig(f'{figures_dir}/result.png')
            plt.show()