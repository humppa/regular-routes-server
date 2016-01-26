#!/usr/bin/python

'''
    
    Build Models
    ----------------------------------

    Build a model for the specified device ID.
'''

# Scientific Libraries
from numpy import *
set_printoptions(precision=5, suppress=True)

def train(DEV_ID,use_test_server=False):
    '''
        TRAIN A MODEL, DUMP IT TO DISK
    '''

    print "WARNING: The averaged_location table is no longer built automatically for each user individually! Call train_all() for this to happen."

    ##################################################################################
    #
    # 1. Load trace from database
    #
    ##################################################################################

    from db_utils import get_conn, get_cursor

    conn = get_conn(use_test_server) 
    c = conn.cursor()

    print "Extracting trace (limited to at most 2 weeks worth of data!)"
    c.execute('SELECT hour,minute,day_of_week,longitude,latitude FROM averaged_location WHERE device_id = %s LIMIT 1209600', (str(DEV_ID),))
    dat = array(c.fetchall(),dtype={'names':['H', 'M', 'DoW', 'lon', 'lat'], 'formats':['f4', 'f4', 'i4', 'f4','f4']})
    X = column_stack([dat['lon'],dat['lat'],dat['H']+(dat['M']/60.),dat['DoW']])

    T,D = X.shape

    ##################################################################################
    #
    # 2. Filtering
    #
    ##################################################################################
    print "Filtering"

    from pred_utils import do_movement_filtering, do_feature_filtering

    X = do_movement_filtering(X,30) # to within 30 metres
    Z = do_feature_filtering(X)

    ##################################################################################
    #
    # 3. Get clusters (should be done separately, but we will do it 'manually' here.
    #
    ##################################################################################
    print "Clustering and Snapping"

    from pred_utils import do_cluster, do_snapping

    nodes = do_cluster(X)
    Y = do_snapping(X,nodes)

    ## SAVE THEM ALSO
    print "Save the cluster nodes to the database (and delete any old ones)"
    sql = "DELETE FROM cluster_centers WHERE device_id = %s"
    c.execute(sql, (DEV_ID,))
    sql = "INSERT INTO cluster_centers (device_id, cluster_id, longitude, latitude, location, time_stamp) VALUES (%s, %s, %s, %s, ST_MakePoint(%s, %s), NOW())"
    for i in range(len(nodes)):
        c.execute(sql, (DEV_ID, i,  nodes[i,0], nodes[i,1],  nodes[i,1], nodes[i,0],)) 
    conn.commit()

    ##################################################################################
    #
    # 4. Build Model(s)
    #
    ##################################################################################
    print "Build Model(s)"

    from sklearn.ensemble import RandomForestClassifier

    # Model 1 / Predict 1 min ahead
    h = RandomForestClassifier(n_estimators=100)
    h.fit(Z[0:-1],Y[1:])   

    # Model 2 / Predict 5 min ahead
    h5 = RandomForestClassifier(n_estimators=100)
    h5.fit(Z[0:-5],Y[5:])

    # Model 3 / Predict 30 min ahead
    h30 = RandomForestClassifier(n_estimators=100)
    h30.fit(Z[0:-30],Y[30:])

    ##################################################################################
    #
    # 5. Dump to Disk
    #
    ##################################################################################
    print "Dump to Disk"

    import joblib
    joblib.dump(h,  './pyfiles/prediction/dat/model-'+str(DEV_ID)+'.dat')
    joblib.dump(h5,  './pyfiles/prediction/dat/model_5-'+str(DEV_ID)+'.dat')
    joblib.dump(h30,  './pyfiles/prediction/dat/model_30-'+str(DEV_ID)+'.dat')

    return "OK! "+str(DEV_ID)+" Successfully built!"

def train_all(use_test_server):

    from db_utils import get_conn, get_cursor

    conn = get_conn(use_test_server) 
    c = conn.cursor()

    ##################################################################################
    #
    # 1. Build the averaged_location table
    #
    ##################################################################################
    print "Building averaged_location table from scratch ..."
    sql = open('./sql/create_averaged_location.sql', 'r').read()
    c.execute(sql)
    sql = open('./sql/make_average_table.sql', 'r').read()
    c.execute(sql)
    conn.commit()

    ##################################################################################
    #
    # 2. List active device IDs, and train models for each device
    #
    ##################################################################################
    print "Getting active device IDs ..."
    sql = open('./sql/list_active_devices.sql', 'r').read()
    c.execute(sql)
    rows = c.fetchall()
    for row in rows:
        print "Training models for device ", row[0]
        train(int(row[0]),use_test_server)

if __name__ == '__main__':
    train_all(use_test_server=True)
    #train(45,use_test_server=True)

