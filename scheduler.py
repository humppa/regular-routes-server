import datetime
from datetime import timedelta

import json
import os
import sys
import time
import re
import urllib2
from pyfiles.database_interface import(
    init_db, get_filtered_device_data_points, data_points_by_user_id)
from pyfiles.device_data_filterer import DeviceDataFilterer
from pyfiles.energy_rating import EnergyRating
from pyfiles.constants import *
from pyfiles.common_helpers import get_distance_between_coordinates
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask
from sqlalchemy.sql import text

import logging
logging.basicConfig()





SETTINGS_FILE_ENV_VAR = 'REGULARROUTES_SETTINGS'
CLIENT_SECRET_FILE_NAME = 'client_secrets.json'

# set settings dir from env.var for settings file. fallback dir is server.py file's parent dir
settings_dir_path = os.path.abspath(os.path.dirname(os.getenv(SETTINGS_FILE_ENV_VAR, os.path.abspath(__file__))))
CLIENT_SECRET_FILE = os.path.join(settings_dir_path, CLIENT_SECRET_FILE_NAME)

app = Flask(__name__)

env_var_value = os.getenv(SETTINGS_FILE_ENV_VAR, None)
if env_var_value is not None:
    print 'loading settings from: "' + str(env_var_value) + '"'
    app.config.from_envvar(SETTINGS_FILE_ENV_VAR)
else:
    print 'Environment variable "SETTINGS_FILE_ENV_VAR" was not defined -> using debug mode'
    # assume debug environment
    app.config.from_pyfile('regularroutes.cfg')
    app.debug = True

db, store = init_db(app)

users_table = db.metadata.tables['users']
devices_table = db.metadata.tables['devices']
device_data_table = db.metadata.tables['device_data']
device_data_filtered_table = db.metadata.tables['device_data_filtered']
travelled_distances_table = db.metadata.tables['travelled_distances']
mass_transit_data_table = db.metadata.tables['mass_transit_data']
global_statistics_table = db.metadata.tables['global_statistics']


def initialize():
    print "initialising scheduler"
    scheduler = BackgroundScheduler()
    scheduler.add_job(retrieve_hsl_data, "cron", second="*/28")
    scheduler.add_job(run_daily_tasks, "cron", hour="3")
    run_daily_tasks()
    print "scheduler init done"
    scheduler.start()

def run_daily_tasks():
    # The order is important.
    filter_device_data()
    generate_distance_data()
    update_global_statistics()

def filter_device_data():
    #TODO: Don't check for users that have been inactive for a long time.
    user_ids =  db.engine.execute(text("SELECT id FROM users;"))
    for id_row in user_ids:
        time = get_max_time_from_table("time", "device_data_filtered", "user_id", id_row["id"])
        device_data_rows = data_points_by_user_id(id_row["id"], time, datetime.datetime.now())
        device_data_filterer = DeviceDataFilterer()
        device_data_filterer.analyse_unfiltered_data(device_data_rows, id_row["id"])


def generate_distance_data():
    user_ids =  db.engine.execute(text("SELECT id FROM users;"))
    ratings = []
    last_midnight = datetime.datetime.now().replace(
        hour=0, minute=0, second=0, microsecond=0)
    for id_row in user_ids:
        time = get_max_time_from_table("time", "travelled_distances", "user_id", id_row["id"]) + timedelta(days=1)
        data_rows = get_filtered_device_data_points(id_row["id"], time, last_midnight)
        ratings += get_ratings_from_rows(data_rows, id_row["id"])
    if len(ratings) > 0:
        db.engine.execute(travelled_distances_table.insert(ratings))

    # update rankings based on ratings
    query = text("""
        SELECT DISTINCT time FROM travelled_distances
        WHERE ranking IS NULL AND total_distance IS NOT NULL""")
    for row in db.engine.execute(query):
        generate_rankings(row[0])


def get_ratings_from_rows(filtered_data_rows, user_id):
    ratings = []
    rows = filtered_data_rows.fetchall()
    if len(rows) == 0:
        return ratings
    previous_time = rows[0]["time"]
    current_date = rows[0]["time"].replace(hour = 0, minute = 0, second = 0, microsecond = 0)
    previous_location = json.loads(rows[0]["geojson"])["coordinates"]
    rating = EnergyRating(user_id, date=current_date)
    for row in rows[1:]:
        current_activity = row["activity"]
        current_time = row["time"]
        current_location = json.loads(row["geojson"])["coordinates"]

        if (current_time - current_date).total_seconds() >= 60*60*24: #A full day
            current_date = current_time.replace(hour = 0, minute = 0, second = 0, microsecond = 0)
            rating.calculate_rating()
            if not rating.is_empty():
                ratings.append(rating.get_data_dict())
            rating = EnergyRating(user_id, date=current_date)

        if (current_time - previous_time).total_seconds() > MAX_POINT_TIME_DIFFERENCE:
            previous_time = current_time
            previous_location = current_location
            continue

        distance = get_distance_between_coordinates(previous_location, current_location) / 1000.0

        previous_location = current_location

        if current_activity == "IN_VEHICLE":
            #TODO: handle FERRY somehow.
            if row["line_type"] == "TRAIN":
                rating.add_in_mass_transit_A_distance(distance)
            elif row["line_type"] in ("TRAM", "SUBWAY"):
                rating.add_in_mass_transit_B_distance(distance)
            elif row["line_type"] == "BUS":
                rating.add_in_mass_transit_C_distance(distance)
            else:
                rating.add_in_vehicle_distance(distance)
        elif current_activity == "ON_BICYCLE":
            rating.add_on_bicycle_distance(distance)
        elif current_activity == "RUNNING":
            rating.add_running_distance(distance)
        elif current_activity == "WALKING":
            rating.add_walking_distance(distance)

    rating.calculate_rating()
    if not rating.is_empty():
        ratings.append(rating.get_data_dict())
    return ratings


def update_global_statistics():
    query = """
        SELECT COALESCE(
            (SELECT max(time) + interval '1 day' FROM global_statistics),
            (SELECT min(time) FROM travelled_distances))"""
    time_start = db.engine.execute(text(query)).scalar()
    if time_start is None:
        return

    last_midnight = datetime.datetime.now().replace(
        hour=0, minute=0, second=0, microsecond=0)
    items = []
    while (time_start < last_midnight):
        time_end = time_start + timedelta(days=1)
        query = '''
            SELECT total_distance, average_co2
            FROM travelled_distances
            WHERE time >= :time_start
            AND time < :time_end
        '''
        travelled_distances_rows = db.engine.execute(text(query), time_start=time_start, time_end=time_end)
        items.append(get_global_statistics_for_day(travelled_distances_rows, time_start))
        time_start += timedelta(days=1)
    if items:
        db.engine.execute(global_statistics_table.insert(items))


def get_global_statistics_for_day(travelled_distances_rows, time):
    time_end = time + timedelta(days=1)
    time_start = time_end - timedelta(days=7)
    query = '''
        SELECT COUNT(DISTINCT user_id)
        FROM travelled_distances
        WHERE time < :time_end
        AND time >= :time_start
    '''
    user_id_count_row = db.engine.execute(text(query), time_start=time_start, time_end=time_end).fetchone()
    id_count = user_id_count_row["count"]

    distance_sum = 0
    total_co2 = 0
    for row in travelled_distances_rows:
        if row["total_distance"]:
            distance_sum += row["total_distance"]
            total_co2 += row["total_distance"] * row["average_co2"]
    if distance_sum == 0:
        average_co2 = 0
    else:
        average_co2 = total_co2 / distance_sum
    return {'time':time,
            'average_co2_usage':average_co2,
            'past_week_certificates_number':id_count,
            'total_distance':distance_sum}


def generate_rankings(time):
    time_end = time + timedelta(days=1)
    time_start = time_end - timedelta(days=7)
    query = '''
        SELECT user_id, total_distance, average_co2
        FROM travelled_distances
        WHERE time < :time_end
        AND time >= :time_start
    '''
    travelled_distances_rows = db.engine.execute(text(query), time_start=time_start, time_end=time_end)

    total_distances = {}
    total_co2 = {}
    totals = []
    for row in travelled_distances_rows:
        if row["total_distance"] is not None:
            if row["user_id"] in total_distances:
                total_distances[row["user_id"]] += row["total_distance"]
                total_co2[row["user_id"]] += row["average_co2"] * row["total_distance"]
            else:
                total_distances[row["user_id"]] = row["total_distance"]
                total_co2[row["user_id"]] = row["average_co2"] * row["total_distance"]
    for user_id in total_distances:
        totals.append((user_id, total_co2[user_id] / total_distances[user_id]))
    totals_sorted = sorted(totals, key=lambda average_co2: average_co2[1])
    batch = [
        {   "user_id": totals_sorted[i][0],
            "time": time,
            "ranking": i + 1 }
        for i in range(len(totals_sorted))]
    if batch:
        db.engine.execute(travelled_distances_table.insert(batch))


def retrieve_hsl_data():
    url = "http://dev.hsl.fi/siriaccess/vm/json"
    response = urllib2.urlopen(url)
    json_data = json.loads(response.read())
    vehicle_data = json_data["Siri"]["ServiceDelivery"]["VehicleMonitoringDelivery"][0]["VehicleActivity"]

    all_vehicles = []

    for vehicle in vehicle_data:
        timestamp = datetime.datetime.fromtimestamp(vehicle["RecordedAtTime"] / 1000) #datetime doesn't like millisecond accuracy
        line_name, line_type = interpret_jore(vehicle["MonitoredVehicleJourney"]["LineRef"]["value"])
        longitude = vehicle["MonitoredVehicleJourney"]["VehicleLocation"]["Longitude"]
        latitude = vehicle["MonitoredVehicleJourney"]["VehicleLocation"]["Latitude"]
        coordinate = 'POINT(%f %f)' % (longitude, latitude)
        vehicle_ref = vehicle["MonitoredVehicleJourney"]["VehicleRef"]["value"]

        vehicle_item = {
            'coordinate': coordinate,
            'line_name': line_name,
            'line_type': line_type,
            'time': timestamp,
            'vehicle_ref': vehicle_ref
        }
        all_vehicles.append(vehicle_item)

    db.engine.execute(mass_transit_data_table.insert(all_vehicles))


def interpret_jore(jore_code):
    if re.search(jore_ferry_regex, jore_code):
        line_name = "Ferry"
        line_type = "FERRY"
    elif re.search(jore_subway_regex, jore_code):
        line_name = jore_code[4:5]
        line_type = "SUBWAY"
    elif re.search(jore_rail_regex, jore_code):
        line_name = jore_code[4:5]
        line_type = "TRAIN"
    elif re.search(jore_tram_regex, jore_code):
        line_name = re.sub(jore_tram_replace_regex, "", jore_code)
        line_type = "TRAM"
    elif re.search(jore_bus_regex, jore_code):
        line_name = re.sub(jore_tram_replace_regex, "", jore_code)
        line_type = "BUS"
    else:
        # unknown, assume bus
        line_name = jore_code
        line_type = "BUS"
    return line_name, line_type



def get_max_time_from_table(time_column_name, table_name, id_field_name, id):
    query = '''
        SELECT MAX({0}) as time
        FROM {1}
        GROUP BY {2}
        HAVING {2} = :id;
    '''.format(time_column_name, table_name, id_field_name)
    time_row = db.engine.execute(text(query),
                                 id = id).fetchone()
    if time_row is None:
        time = datetime.datetime.strptime("1971-01-01", '%Y-%m-%d')
    else:
        time = time_row["time"]
    return time


def main_loop():
    while 1:
        time.sleep(1)
if __name__ == "__main__":
    initialize()
    try:
        main_loop()
    except KeyboardInterrupt:
        print >> sys.stderr, '\nExiting by user request.\n'
        sys.exit(0)