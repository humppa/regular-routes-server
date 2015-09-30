#!/usr/bin/python2.4
#
# Small script to show PostgreSQL and Pyscopg together
#

from numpy import *
import psycopg2

try:
    conn = psycopg2.connect("dbname='regularroutes' user='regularroutes' host='localhost' password='TdwqStUh5ptMLeNl' port=5432")
except:
    print "I am unable to connect to the database"


c = conn.cursor()

print "Test ..."
c.execute('SELECT DISTINCT device_id FROM device_data')
rows = c.fetchall()
test = array(rows)
#.fetchall()
print test

print "Loading Device IDs ..."
result = c.execute('SELECT DISTINCT device_id FROM data_averaged').fetchall()
ids = array(result ,dtype={'names':['d_id'], 'formats':['i4']})

for i in ids:
    print "Loading Waypoints for Device ID ", i, "..."
    dat = array(c.execute('SELECT longitude,latitude,time_stamp,device_id FROM data_averaged WHERE device_id=?', (i,)).fetchall(),dtype={'names':['lon', 'lat', 't', 'd_id'], 'formats':['f4','f4','f4','i4']})
    X = column_stack([dat['lat'],dat['lon']])
    
    if len(dat) < 50: 
        print "Not enough points for Clustering!"

    else:
        print "Clustering ..."
        from sklearn.cluster import KMeans
        h = KMeans(50, max_iter=100, n_init=1)
        h.fit(X)
        labels = h.labels_

        print "Inserting Cluster Centres ..."
        for k in labels:
            sql = "INSERT INTO cluster_centers (longitude, latitude, device_id) VALUES (%s, %s, %s)"
            c.execute(sql, k[0], k[1], i)

        print "Commit"
        conn.commit()

print "Done"
