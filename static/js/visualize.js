$(document).ready(function() {
    var date = $('#date');
    date.pickadate({
	clear: '',
	firstDay: 1,
	format: 'dd.mm.yyyy',
	hiddenName: true,
	onClose: function() {
	    update(this.get('select', 'yyyy-mm-dd'));
	}
    });
    date.pickadate('picker').open();

    var mapCanvas = $('#map-canvas');
    var mapOptions = {
	center: { lat: 60.1841396, lng: 24.8300838 },
	zoom: 12
    };
    var map = new google.maps.Map(mapCanvas[0], mapOptions);
    map.data.setStyle(function(feature) {
	var type = feature.getProperty('type');
	var title = feature.getProperty('title');
	if (type === 'raw-point') {
	    var pointColor = 'magenta';
	    switch(feature.getProperty('activity')) {
	    case 'ON_BICYCLE':
		pointColor = 'green';
		break;
	    case 'WALKING':
	    case 'ON_FOOT':
		pointColor = 'limegreen';
		break;
	    case 'RUNNING':
		pointColor = 'greenyellow';
		break;
	    case 'IN_VEHICLE':
		pointColor = 'red';
		break;
	    case 'TILTING':
		pointColor = 'blue';
		break;
	    case 'STILL':
		pointColor = 'white';
		break;
	    case 'UNKNOWN':
		pointColor = 'gray';
		break;
	    default:
		pointColor = 'black';
	    } // end-of-switch
	    return {
		icon: {
		    path: google.maps.SymbolPath.CIRCLE,
		    scale: 3,
		    strokeColor: pointColor,
		    strokeOpacity: 0.5
		},
		title: title
	    };
	} else if (type === 'route-point') {
	    return {
		icon: {
		    path: google.maps.SymbolPath.BACKWARD_CLOSED_ARROW,
		    scale: 3,
		    fillColor: 'red',
		    fillOpacity: 1.0,
		    strokeColor: 'black'
		},
		title: title
	    };
	}
    });

    var currentDate;

    function update(date) {
	if (date === currentDate)
	    return;
	currentDate = date;
	mapCanvas.css('opacity', 0.1);
	map.data.forEach(function(feature) {
	    map.data.remove(feature);
	});
	$.getJSON('../visualize/' + device_id + '/geojson?date=' + date, function(response) {
	    map.data.addGeoJson(response);
	    mapCanvas.css('opacity', '');
		if (response.features.length > 1) {
			var bounds = new google.maps.LatLngBounds();
			response.features.forEach(function (feature) {
				var coords = feature.geometry.coordinates;
		    	bounds.extend(new google.maps.LatLng(coords[1],coords[0]));
			});
			map.fitBounds(bounds);
		}
	});
    }
});
