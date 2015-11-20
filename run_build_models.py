#!/usr/bin/python

'''
    runCreateDataset.py
    ----------------------------------
    - turns data from Regular Routes into X/Y.csv datasets.
    - use runPlotAnimation to run an animation based on this.

    Usage: python runCreateDataset.py <win_past> <win_futr>
    defaults:                            (10)        (20)   
'''

# Scientific Libraries
from numpy import *
set_printoptions(precision=5, suppress=True)

# Provides snapping and stacking functionality
import sys
sys.path.append("./src")
from utils import *

import joblib
import psycopg2

def train(DEV_ID,win_past=5,win_futr=5,mod="EML",lim='NOW()'):
    '''
        1. obtain full trace PRIOR OR EQUAL TO 'lim'
        2. fetch clusters from cluster_centers
        3. snap full trace to clusters
        4. stack, filter, and TRAIN a model
        5. dump the model to disk
    '''

    ##################################################################################
    #
    # Load trace
    #
    ##################################################################################

    try:
        conn = psycopg2.connect("dbname='regularroutes' user='regularroutes' host='localhost' password='TdwqStUh5ptMLeNl' port=5432")
    except:
        print "I am unable to connect to the database"

    c = conn.cursor()

    print "Extracting trace"
    c.execute('SELECT device_id,hour,day_of_week,longitude,latitude FROM averaged_location WHERE device_id = %s', (str(DEV_ID),))
    dat = array(c.fetchall(),dtype={'names':['d_id', 'H', 'DoW', 'lon', 'lat'], 'formats':['i4', 'i4', 'i4', 'f4','f4']})
    run = column_stack([dat['lon'],dat['lat']])
    X = column_stack([dat['lon'],dat['lat'],dat['H'],dat['DoW']])

    ##################################################################################
    #
    # Extract nodes
    #
    ##################################################################################

    print "Extracting waypoints"
    c.execute('SELECT latitude, longitude FROM cluster_centers WHERE device_id = %s', (str(DEV_ID),))
    rows = c.fetchall()
    nodes = array(rows)

    #for i in range(len(nodes)):
    #    print i, nodes[i]
    ##################################################################################
    #
    # Snapping
    #
    ##################################################################################
    print "Snapping to ", len(nodes)," waypoints"
    y = snap(run,nodes)

    #for i in range(10):
    #    print X[i,:], y[i]
    #for i in range(5000,5010):
    #    print X[i,:], y[i]
    #for i in range(len(y)-10,len(y)):
    #    print X[i,:], y[i]

    ##################################################################################
    #
    # Filter / Reduce Gradularity
    #
    ##################################################################################

    #DSET = zeros(len(y),X.shape[1]+1)

    ##################################################################################
    #
    # Save ...
    #
    ##################################################################################

    #savetxt('data/data_out/regular_routes_'+str(DEV_ID)+'_stream_X.csv', X, fmt='%1.8f', delimiter=',')
    #savetxt('data/data_out/regular_routes_'+str(DEV_ID)+'_stream_y.csv', y, fmt='%d', delimiter=',')

    ##################################################################################
    #
    # Make Dataset
    #
    ##################################################################################

    # Y Features
    #   1. average speed (y[t-win:t])
    #   2. direction (y[t-win:t])              # i.e., y[t] - y[t-win], y[t] - y[t-1], etc
    #   3. included (nodes[k] \in y[t-win:t]) 
    #   4. average (nodes[y[t-win:t]])
    # X Features
    #   1. hour-of-day
    #      distance_from(hour,k)              # i.e., k-oclock - hour
    #   2. day-of-week

    print "Filter out non-movement (points which are repeated ",win_past," times) ..."
    X,y = filter(X,y,win_past)

    print "Stack into ML dataset ..."
    X,Y = stack(X,y,win_past,win_futr)

    print "Prepare model ..."
    from sklearn import ensemble
    from ML import ML

    L = win_futr
    _h = ensemble.RandomForestClassifier()
    h = ML(L,_h)

    print "Build model ..."
    h.train(X,Y)

    print "Dump model to disk ..."
    fname = "./dat/model_dev"+str(DEV_ID)+".model"
    joblib.dump( h,  fname)

    print "Model saved to "+fname+". Done!"

    return "OK! "+str(DEV_ID)+" Successfully built!"


if __name__ == '__main__':
    train(45)

#import sys
#
#DEV_ID = 45
#if len(sys.argv) > 3:
#    DEV_ID = int(sys.argv[3])
#
#win_past = 5
#if len(sys.argv) > 1:
#    win_past = int(sys.argv[1])
#win_futr = 5
#if len(sys.argv) > 2:
#    win_futr = int(sys.argv[2])
#
#train(DEV_ID,win_past,win_futr)