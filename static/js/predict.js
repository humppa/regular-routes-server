$(document).ready(function() {
    var mapCanvas = $('#map-canvas');
    var mapOptions = {
	center: { lat: 60.1841396, lng: 24.8300838 },
	zoom: 12
    };
	mapCanvas.css('opacity', 0.1);
    var map = new google.maps.Map(mapCanvas[0], mapOptions);
    map.data.setStyle(function(feature) {
	var type = feature.getProperty('type');
	var title = feature.getProperty('title');
	if (type === 'Prediction') {
	    var pointColor = 'red';
		var pointScale = 1;
	    switch(feature.getProperty('minutes')) {
	    case 5:
			pointColor = 'DeepPink';
			pointScale = 3;
			break;
	    case 15:
			pointColor = 'Fuchsia';
			pointScale = 5;
			break;
	    case 30:
			pointColor = 'FireBrick';
			pointScale = 7;
			break;
	    default:
			pointColor = 'black';
			pointScale = 10;
	    } // end-of-switch
	    return {
		icon: {
		    path: google.maps.SymbolPath.CIRCLE,
		    scale: pointScale,
		    strokeColor: pointColor,
		    strokeOpacity: 1.0,
			strokeWeight: 2
		},
		title: title
	    };
	} else if (type === 'Position') {
	    return {
		icon: {
		    path: google.maps.SymbolPath.BACKWARD_CLOSED_ARROW,
		    scale: 5,
		    fillColor: 'gold',
		    fillOpacity: 1.0,
		    strokeColor: 'black',
			strokeWeight: 1
		},
		title: title
	    };
	}
    });

	$.getJSON('../predictgeojson/' + device_id, function(response) {
	    map.data.addGeoJson(response);
		if (response.features.length > 1) {
			var bounds = new google.maps.LatLngBounds();
			response.features.forEach(function (feature) {
				var coords = feature.geometry.coordinates;
			    bounds.extend(new google.maps.LatLng(coords[1],coords[0]));
			});
			map.fitBounds(bounds);
			mapCanvas.css('opacity', '');
		}
	});
    });
