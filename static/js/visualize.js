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
    zoom: 16
  };
  var map = new google.maps.Map(mapCanvas[0], mapOptions);
  map.data.setStyle(function(feature) {
    var type = feature.getProperty('type');
    var title = feature.getProperty('title');
    if (type === 'raw-point') {
      return {
        icon: {
          path: google.maps.SymbolPath.CIRCLE,
          scale: 3,
          strokeColor: '#ff00ff',
          strokeOpacity: 0.5
        },
        title: title
      }
    } else if (type === 'snap-line') {
      return {
        strokeColor: 'blue',
        strokeOpacity: 0.5
      };
    } else if (type === 'route-line') {
      return {
        strokeColor: 'red',
      }
    } else if (type === 'route-point') {
      return {
        icon: {
          path: google.maps.SymbolPath.CIRCLE,
          scale: 3,
          strokeColor: 'red',
        },
        title: title
      }
    } else if (type === 'link-line') {
      return {
        strokeColor: 'green',
        strokeOpacity: 0.5
      }
    } else if (type === 'link-point') {
      return {
        icon: {
          path: google.maps.SymbolPath.CIRCLE,
          scale: 2,
          strokeColor: 'green',
          strokeOpacity: 0.5,
        },
        title: title
      };
    }
  });

  function update(date) {
    mapCanvas.css('opacity', 0.1);
    map.data.forEach(function(feature) {
      map.data.remove(feature);
    });
    $.getJSON('../visualize/' + device_id + '/geojson?date=' + date, function(response) {
      map.data.addGeoJson(response);
      mapCanvas.css('opacity', '');
    });
  }
});
