import numpy as np

class Parcel:
    """Represents a land parcel with associated demographic data"""
    def __init__(self, parcel_id, nearest_cooling_centers, cooling_distance, attributes=None):
        self.id = parcel_id
        self.attributes = attributes or {} # TODO: split into different vars?
        
        self.decision = None  # 'stay' or cooling_center_id
        self.proba = None
        self.nearest_cooling_centers = nearest_cooling_centers  # Ordered list of nearest cooling centers (pre-computed)
        self.cooling_distance = cooling_distance  # Distance to cooling center (pre-computed)
        self.transit_distance = None  # Distance to nearest transit (pre-computed)
        self.nearest_transit = None  # Nearest transit access point (pre-computed)
        self.transit_distance = None  # Distance to nearest transit (pre-computed)
        
    def move2cooling_proba(self, temp_thr=70, age_thr=70, income_thr=70000):
        """Calculate probability of moving to a cooling center based on attributes and temperature"""
        temp = self.attributes['temperature']

        age = self.attributes.get('total_age', 0)
        income = self.attributes.get('medianhhi', 0)
        transit_dist = self.transit_distance
        cooling_dist = self.cooling_distance
        ac = self.attributes.get('AC', 0)
        
        # The higher the temperature the higher the proba of moving to a cooling center
        temp_proba = max(0.1, np.log(temp - temp_thr)/np.log(temp)) # start moving at temp_threshold
        #temp_proba = 1 / (1 + np.exp(-0.3*(temp - temp_thr)))
        temp_weight = 1

        age_proba = max(0.1, 1 - 1 / (1  + np.exp(0.1*(age_thr-age))))  # drops after 70 
        age_weight = 2

        income_proba = max(0.1,1 / (1 + np.exp((income/10000 - income_thr/10000) * 0.5)))
        # income_weight = 1

        cooling_proba = max(0.1,1 / (1 + np.exp((cooling_dist - 1609) * 0.001)))
        cooling_weight = 1
        
        ac_proba = 0.01 if ac==1 else 0.3
        ac_weight = 4
        
        # print(age, age_proba)
        # final_score = temp_weight*temp_proba + age_weight*age_proba + income_weight*income_proba + cooling_weight*cooling_proba + ac_proba*ac_weight

        # final_proba = final_score / (temp_weight + age_weight + income_weight + cooling_weight + ac_weight)

        #final_proba = temp_proba * age_proba * income_proba * cooling_proba * ac_proba
        final_proba = (temp_proba * age_proba * income_proba * cooling_proba * ac_proba) ** (1/5) #geometric mean
        return final_proba 

    def make_decision(self):
        """Choose which cooling center to go to, if deciding to move"""
        # TODO: choose a cooling center out of 5 closest

        total_score = self.move2cooling_proba()
        decision = bool(round(total_score)) #0 if total<0.5; 1 if total >= 0.5

        self.proba = total_score
        if decision==True:
            self.decision = self.nearest_cooling_centers[0] #move to the closest cooling center
        else:
            self.decision = 'stay'
    
