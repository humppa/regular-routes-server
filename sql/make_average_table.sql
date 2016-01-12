DROP TABLE IF EXISTS averaged_location;

CREATE TABLE averaged_location (
  device_id integer,
  time_stamp timestamp, -- was: integer
  minute integer,
  hour integer,
  year integer,
  day_of_week integer,
  day_of_year integer,
  longitude float,
  latitude float,
  accuracy float
);
  --waypoint_id bigint

INSERT INTO averaged_location
    SELECT
        device_id,
        date_trunc('minute', time) as time_stamp,
        CAST(date_part('minute',time) as integer) as minute,
        CAST(date_part('hour',time) as integer) as hour,
        CAST(date_part('year',time) as integer) as year,
        CAST(date_part('dow',time) as integer) as day_of_week,
        CAST(date_part('doy',time) as integer) as day_of_year,
        CAST(AVG(ST_Y(coordinate::geometry)) as float) as longitude,
        CAST(AVG(ST_X(coordinate::geometry)) as float) as latitude,
        CAST(AVG(accuracy) as float) as accuracy
      FROM device_data
      -- correct one is device_data
      GROUP BY device_id, time_stamp, minute, hour, year, day_of_week, day_of_year
      ORDER BY device_id, time_stamp
;
           
-- TEST: SELECT date_trunc('minute', time) as t,CAST(AVG(ST_Y(coordinate::geometry)) as float) as longitude from device_data where device_id = 98 group by t limit 10;


----------- OLD ----------------
--INSERT INTO averaged_location
--      SELECT
--        device_id,
--	AVG(CAST(extract(epoch from time) as integer)) as time_stamp,
--	CAST(date_part('minute',time) as integer) as minute,
--	CAST(date_part('hour',time) as integer) as hour,
--	CAST(date_part('year',time) as integer) as year,
--	CAST(date_part('dow',time) as integer) as day_of_week,
--	CAST(date_part('doy',time) as integer) as day_of_year,
--        CAST(AVG(ST_Y(coordinate::geometry)) as float) as longitude,
--        CAST(AVG(ST_X(coordinate::geometry)) as float) as latitude,
--        CAST(AVG(accuracy) as float) as accuracy,
--        waypoint_id
--      FROM device_data
--      -- correct one is device_data
--      GROUP BY device_id,year,day_of_year,hour,minute, device_data.time, device_data.waypoint_id
--      ORDER BY device_id, time_stamp
--;
--