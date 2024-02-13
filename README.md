# Occupancy Schedule Generator (OSG) for Residential Buildings
The goal of this Python package is to convert the 5-min motion detection data provided by Ecobee DYD dataset into an hourly occupancy status profile representative for the whole-house.
# How to get started?
+ Install directly from github using `pip install --upgrade git+https://github.com/AyaDoma/OccupancyScheduleGenerator-OSG-`
+ Launch Jupyter Notebook/Lab
+ `import OSG` and run the package with `OSG.start(..., df)` replacing ... with the path of the DYD raw data, and df with a dataframe of the metadata.



