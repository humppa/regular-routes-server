#!/usr/bin/env python

import json
import itertools
import geoalchemy2 as ga2
from datetime import datetime, date, timedelta
from flask import Flask, abort, jsonify, request, render_template, Response
from flask.ext.sqlalchemy import SQLAlchemy
from sqlalchemy import MetaData, Table, Column, ForeignKey, Integer, String, desc, subquery
from sqlalchemy.dialects.postgres import DOUBLE_PRECISION, TIMESTAMP, UUID
from sqlalchemy.exc import DataError
from sqlalchemy.sql import text, func, column, table, select
from uuid import uuid4


class SortableActivityData(object):
    """Class used to sort activity data by confidence level"""

    def __init__(self, activity_type, activity_type_id, confidence):
        self.activity_type = activity_type
        self.activity_type_id = activity_type_id
        self.confidence = confidence

    def __cmp__(self, other):
        if hasattr(other, 'confidence'):
            return cmp(self.confidence, other.confidence)

    def __repr__(self):
        return '{type:%s, conf:%d}' % (str(self.activity_type), int(self.confidence))


app = Flask(__name__)
#app.config.from_pyfile('regularroutes.cfg')
#app.debug = True
app.config.from_envvar('REGULARROUTES_SETTINGS')
db = SQLAlchemy(app)
metadata = MetaData()

# Schema definitions:
devices_table = Table('devices', metadata,
                      Column('id', Integer, primary_key=True),
                      Column('token', UUID, unique=True, nullable=False),
                      Column('created', TIMESTAMP, nullable=False, default=func.current_timestamp(),
                             server_default=func.current_timestamp()),
                      Column('last_activity', TIMESTAMP, nullable=False, default=func.current_timestamp(),
                             server_default=func.current_timestamp()))

device_data_table = Table('device_data', metadata,
                          Column('id', Integer, primary_key=True),
                          Column('device_id', Integer, ForeignKey('devices.id'), nullable=False),
                          Column('coordinate', ga2.Geography('point', 4326), nullable=False),
                          Column('accuracy', DOUBLE_PRECISION, nullable=False),
                          Column('time', TIMESTAMP, nullable=False))

activity_type_table = Table('activity_type', metadata,
                            Column('id', Integer, primary_key=True),
                            Column('activity_type', String(16), nullable=False))

activity_data_table = Table('activity_data', metadata,
                            Column('id', Integer, primary_key=True),
                            Column('activity_type_id', Integer, ForeignKey('activity_type.id'), nullable=False),
                            Column('device_data_id', Integer, ForeignKey('device_data.id'), nullable=False),
                            Column('ordinal', Integer, nullable=False),
                            Column('confidence', Integer))

# Table Creations with initial setup:

if not activity_type_table.exists(bind=db.engine):
    """
        Activity type table is created separately to test if data insertion is required
    """
    activity_type_table.create(bind=db.engine)
    ''' Add type values: IN_VEHICLE, ON_BICYCLE, ON_FOOT, RUNNING, WALKING, STILL, TILTING, UNKNOWN
        These types are the same as are defined in:
        https://developer.android.com/reference/com/google/android/gms/location/DetectedActivity.html
    '''
    activity_types = \
        [{'id': 0, 'activity_type': 'IN_VEHICLE'},
         {'id': 1, 'activity_type': 'ON_BICYCLE'},
         {'id': 2, 'activity_type': 'ON_FOOT'},
         {'id': 3, 'activity_type': 'RUNNING'},
         {'id': 4, 'activity_type': 'STILL'},
         {'id': 5, 'activity_type': 'TILTING'},
         {'id': 6, 'activity_type': 'UNKNOWN'},
         {'id': 7, 'activity_type': 'WALKING'}]

    for activity_type in activity_types:
        stmt = activity_type_table.insert(activity_type)
        db.engine.execute(stmt)

"""
    Other schema tables are created at once, if not exists
"""
metadata.create_all(bind=db.engine, checkfirst=True)


def fetch_activity_types():
    rows = db.engine.execute(select([activity_type_table]))
    result = {}
    for row in rows:
        id = row[activity_type_table.c.id]
        activity_type = row[activity_type_table.c.activity_type]
        result[activity_type] = id
    return result

activity_types_cache = fetch_activity_types()

# REST interface:


@app.route('/register', methods=['POST'])
def register_post():
    token = uuid4()

    insertion = devices_table.insert({'token': token.hex})
    db.engine.execute(insertion)

    return jsonify({
        'deviceToken': token,
        'sessionId': token
    })


@app.route('/authenticate', methods=['POST'])
def authenticate_post():
    device_token = request.form['deviceToken']
    device_id = verify_device_token(device_token)

    update = devices_table.update().values({'last_activity': datetime.now()}).where("id=" + str(device_id))
    db.engine.execute(update)

    return jsonify({
        'sessionId': device_id
    })


@app.route('/data', methods=['POST'])
def data_post():
    """
     Note: to link activity data to corresponding location data, primary key is returned from single insert.
           Multi insert does not provide such mean to link data -> for performance improvement, some better
           approach should be investigated.
    """
    session_id = request.args['sessionId']
    device_id = session_id
    data_points = request.json['dataPoints']

    batch_size = 1024
    def batch_chunks(x):
        for i in xrange(0, len(x), batch_size):
            yield x[i:i+batch_size]

    def prepare_point(point):
        location = point['location']

        return {
            'device_id': device_id,
            'coordinate': 'POINT(%f %f)' % (float(location['longitude']), float(location['latitude'])),
            'accuracy': float(location['accuracy']),
            'time': datetime.fromtimestamp(long(point['time']) / 1000.0)
        }

    def prepare_point_activities(id, point):
        if not 'activityData' in point or not 'activities' in point['activityData']:
            return
        activities = point['activityData']['activities']

        def parse_activities():
            for activity in activities:
                activity_type = activity['activityType']
                if activity_type in activity_types_cache:
                    yield {
                        'type_id': activity_types_cache[activity_type],
                        'confidence': int(activity['confidence'])
                    }

        sorted_activities = sorted(parse_activities(), key=lambda x: x['confidence'], reverse=True)
        for (i, x) in enumerate(sorted_activities):
            yield {
                'activity_type_id': x['type_id'],
                'device_data_id': id,
                'confidence': x['confidence'],
                'ordinal': i + 1
            }

    for chunk in batch_chunks(data_points):
        batch = [prepare_point(x) for x in chunk]
        result_ids = [row[0] for row in db.engine.execute(
                device_data_table.insert(batch).returning(device_data_table.c.id))]

        def prepare_activities():
            for (id, x) in zip(result_ids, chunk):
                for point_activity in prepare_point_activities(id, x):
                    yield point_activity

        activity_batch = list(prepare_activities())
        db.engine.execute(activity_data_table.insert(activity_batch))
    return jsonify({
    })

@app.route('/devices')
def devices():
    try:
        cols = table('devices', column('id'), column('token'))
        query = select([cols]).order_by(desc('token'))
        rows = db.engine.execute(query.compile())

        result = ""
        for row in rows:
            result += '%s = %s\n' % (row[1], row[0])
        return str(result)
    except Exception as e:
        print('Exception: ' + e.message)

    return ""


@app.route('/device/<device_value>')
def device(device_value):
    try:
        device_id = int(device_value)
        device_token = get_device_token(device_id)

    except ValueError:
        device_token = device_value
        device_id = get_device_id(device_token)
    except Exception as e:
        print 'Exception: ' + e.message

    return jsonify({'device_token': device_token, 'device_id': device_id})


massive_advanced_csv_query = """
      SELECT
        device_id, time,
        ST_Y(coordinate::geometry) as longitude,
        ST_X(coordinate::geometry) as latitude,
        accuracy,
        activity_types[1] AS activity_guess_1,
        confidences[1]    AS activity_guess_1_conf,
        activity_types[2] AS activity_guess_2,
        confidences[2]    AS activity_guess_2_conf,
        activity_types[3] AS activity_guess_3,
        confidences[3]    AS activity_guess_3_conf
      FROM device_data
      LEFT JOIN LATERAL (
        SELECT DISTINCT ON (device_data_id)
          device_data_id,
          array_agg(activity_type) OVER device_data_point AS activity_types,
          array_agg(confidence)    OVER device_data_point AS confidences
        FROM
          activity_data
        JOIN activity_type
        ON activity_type.id = activity_type_id
        WINDOW device_data_point AS (
          PARTITION BY device_data_id ORDER BY ordinal
          RANGE BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING
        )
      ) AS activity_data
      ON device_data.id = device_data_id
      ORDER BY time ASC
"""

@app.route('/csv/')
def export_csv():
    rows = db.engine.execute(text(massive_advanced_csv_query))
    return Response(generate_csv(rows), mimetype='text/csv')

@app.route('/csv/<page>')
def export_csv_block(page):
    entry_block_size = 10000

    if int(page) == 0:
        offset = int(page) * entry_block_size
    else:
        offset = (int(page)-1) * entry_block_size
    limit = entry_block_size

    query = text(massive_advanced_csv_query + ' LIMIT :limit OFFSET :offset')
    rows = db.engine.execute(query, limit=limit, offset=offset)
    return Response(generate_csv(rows), mimetype='text/csv')


@app.route('/csv/waypoints')
def export_csv_waypoints():
    query = text(
        'SELECT wpt_id,\
            ST_Y(geom::geometry) as longitude,\
            ST_X(geom::geometry) as latitude\
            FROM waypointsclustered')
    rows = db.engine.execute(query)
    return Response(generate_csv_waypoints(rows), mimetype='text/csv')


def generate_csv_waypoints(rows):
    yield '"wpt_id";"longitude";"latitude"\n'
    for row in rows:
        yield ';'.join(['"%s"' % (str(x)) for x in row]) + '\n'

@app.route('/visualize/<int:device_id>')
def visualize(device_id):
    return render_template('visualize.html',
                           api_key=app.config['MAPS_API_KEY'],
                           device_id=device_id)


@app.route('/visualize/<int:device_id>/geojson')
def visualize_device_geojson(device_id):
    if 'date' in request.args:
        date_start = datetime.strptime(request.args['date'], '%Y-%m-%d').date()
    else:
        date_start = date.today()

    date_end = date_start + timedelta(days=1)

    points = data_points(device_id, datetime.fromordinal(date_start.toordinal()),
                         datetime.fromordinal(date_end.toordinal()))

    features = []
    links = set()
    waypoints = set()
    for point in points:
        device_data_id = point['id']
        activity_data = get_activity_data(device_data_id)
        activity_info = 'activities: ' + ', '.join([str(x) for x in activity_data])

        point_geo = json.loads(point['geojson'])
        features.append({
            'type': 'Feature',
            'geometry': point_geo,
            'properties': {
                'type': 'raw-point',
                'title': 'accuracy: %d\n%s' % (point['accuracy'], activity_info)
            }
        })
        if point['accuracy'] < 500:
            link = db.engine.execute(text(
                'SELECT lnk_id, lnk_1, lnk_2, ST_AsGeoJSON(ST_ShortestLine(lnk_geom, :coordinate ::geometry)) as geojson\
          FROM links\
          WHERE lnk_geom && (ST_Buffer(:coordinate ::geography, 500) ::geometry)\
          ORDER BY ST_Distance(lnk_geom, :coordinate ::geometry) ASC\
          LIMIT 1'), coordinate=point['coordinate']).first()
            if link:
                links.add(link['lnk_id'])
                waypoints.add(link['lnk_1'])
                waypoints.add(link['lnk_2'])
                link_geo = json.loads(link['geojson'])
                features.append({
                    'type': 'Feature',
                    'geometry': link_geo,
                    'properties': {
                        'type': 'snap-line'
                    }
                })
    rows = db.engine.execute(text(
        'SELECT ST_AsGeoJSON(geom), wpt_id\
      FROM waypointsclustered'
    ))
    for row in rows:
        if row[1] in waypoints:
            feature_type = 'route-point'
        else:
            feature_type = 'link-point'
        features.append({
            'type': 'Feature',
            'geometry': json.loads(row[0]),
            'properties': {
                'type': feature_type
            }
        })
    rows = db.engine.execute(text(
        'SELECT ST_AsGeoJSON(lnk_geom), lnk_id\
      FROM links'
    ))
    for row in rows:
        if row[1] in links:
            feature_type = 'route-line'
        else:
            feature_type = 'link-line'
        features.append({
            'type': 'Feature',
            'geometry': json.loads(row[0]),
            'properties': {
                'type': feature_type
            }
        })
    geojson = {
        'type': 'FeatureCollection',
        'features': features
    }
    # for query in sorted(get_debug_queries(), key=lambda x: x.duration):
    # print query.statement
    # result = db.engine.execute('EXPLAIN ANALYZE %s' % (query.statement), query.parameters)
    # for row in result:
    # print row[0]
    # print '  %s seconds' % (query.duration)
    return jsonify(geojson)


# Helper Functions:


def generate_csv(rows):
    # Poor man's CSV generation. Doesn't handle escaping properly.
    # Python's CSV library doesn't handle unicode, and seems to be
    # tricky to wrap as a generator (expected by Flask)
    yield '"device_id";"time";"longitude";"latitude";"accuracy";"activity_guess_1";"activity_guess_1_conf";"activity_guess_2";"activity_guess_2_conf";"activity_guess_3";"activity_guess_3_conf"\n'

    def to_str(x):
        if x is None:
            return ''
        return str(x)

    for row in rows:
        yield ';'.join(['"%s"' % (to_str(x)) for x in row]) + '\n'


def data_points(device_id, datetime_start, datetime_end):
    return db.engine.execute(text(
        'SELECT id, ST_Y(coordinate::geometry) as longitude, ST_X(coordinate::geometry) as latitude, ST_AsGeoJSON(coordinate) as geojson, coordinate, accuracy, time\
      FROM device_data\
      WHERE device_id = :device_id\
      AND time >= :time_start\
      AND time < :time_end\
      ORDER BY time ASC'
    ), device_id=device_id, time_start=datetime_start, time_end=datetime_end)


def get_activity_data(device_data_id):
    """Get activities linked to device data row, sorted descending by confidence level """
    activity_data_query_text = 'SELECT id, activity_type_id, confidence FROM activity_data WHERE device_data_id = :device_data_id AND ordinal = :ordinal'
    activity_type_query_text = 'SELECT activity_type FROM activity_type WHERE id in (SELECT activity_type_id FROM activity_data WHERE id = :activity_data_id)'

    activities = []
    try:
        for i in range(1, 4):

            act_data_res = db.engine.execute(text(activity_data_query_text), device_data_id=int(device_data_id),
                                             ordinal=int(i)).first()
            if act_data_res is None:
                break
            else:
                act_type_id = int(act_data_res['activity_type_id'])
                act_type_res = db.engine.execute(text(activity_type_query_text),
                                                 activity_data_id=act_data_res['id']).first()
                act_type_str = act_type_res[
                    'activity_type'] if act_type_res is not None else 'UNKNOWN'
                confidence = int(act_data_res['confidence'])
                activities.append(SortableActivityData(act_type_str, act_type_id, confidence))
    except TypeError as e:
        print 'Exception: ' + e.message

    activities.sort(reverse=True)
    return activities


def verify_device_token(token):
    try:
        query = select([table('devices', column('id'))]).where("token='" + token + "'")
        row = db.engine.execute(query).first()

        if not row:
            abort(403)
        return row[0]
    except DataError as e:
        print 'Exception: ' + e.message
        abort(403)


def get_device_id(token):
    try:
        query = select([table('devices', column('id'))]).where("token='" + token + "'")
        row = db.engine.execute(query).first()
        if not row:
            return -1
        return int(row[0])
    except DataError as e:
        print 'Exception: ' + e.message

    return -1


def get_device_token(device_id):
    try:
        query = select([table('devices', column('token'))]).where("id='" + str(device_id) + "'")
        row = db.engine.execute(query).first()
        if not row:
            return None
        return row[0]
    except DataError as e:
        print 'Exception: ' + e.message

    return None

# App starting point:
if __name__ == '__main__':
    if app.debug:
        app.run(host='0.0.0.0')
    else:
        app.run()
