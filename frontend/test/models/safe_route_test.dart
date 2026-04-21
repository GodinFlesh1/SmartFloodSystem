import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/models/safe_route.dart';

Map<String, dynamic> _placeJson({String type = 'community_centre'}) => {
      'name':        'Test Hall',
      'type':        type,
      'latitude':    51.51,
      'longitude':   -0.09,
      'distance_m':  800,
      'distance_km': 0.8,
      'address':     'High Street',
    };

void main() {
  group('SafePlace.fromJson', () {
    test('parses all fields', () {
      final place = SafePlace.fromJson(_placeJson());
      expect(place.name,        'Test Hall');
      expect(place.type,        'community_centre');
      expect(place.latitude,    51.51);
      expect(place.longitude,   -0.09);
      expect(place.distanceM,   800);
      expect(place.distanceKm,  0.8);
      expect(place.address,     'High Street');
    });

    test('defaults name and type when missing', () {
      final place = SafePlace.fromJson({
        'latitude': 51.0, 'longitude': -0.1,
      });
      expect(place.name, 'Safe Place');
      expect(place.type, 'shelter');
    });
  });

  group('SafePlace.typeLabel', () {
    test('maps known types to human-readable labels', () {
      expect(SafePlace.fromJson(_placeJson(type: 'community_centre')).typeLabel, 'Community Centre');
      expect(SafePlace.fromJson(_placeJson(type: 'school')).typeLabel,           'School');
      expect(SafePlace.fromJson(_placeJson(type: 'hospital')).typeLabel,         'Hospital');
      expect(SafePlace.fromJson(_placeJson(type: 'place_of_worship')).typeLabel, 'Place of Worship');
      expect(SafePlace.fromJson(_placeJson(type: 'assembly_point')).typeLabel,   'Assembly Point');
    });

    test('uppercases unknown types', () {
      final place = SafePlace.fromJson(_placeJson(type: 'civic_centre'));
      expect(place.typeLabel, 'CIVIC CENTRE');
    });
  });

  group('RouteStep.fromJson', () {
    test('parses correctly', () {
      final step = RouteStep.fromJson({
        'instruction': 'Turn left',
        'distance_m':  200,
        'duration_s':  60,
      });
      expect(step.instruction, 'Turn left');
      expect(step.distanceM,   200);
      expect(step.durationS,   60);
    });

    test('defaults when fields are missing', () {
      final step = RouteStep.fromJson({});
      expect(step.instruction, '');
      expect(step.distanceM,   0);
      expect(step.durationS,   0);
    });
  });

  group('SafeRoute.fromJson', () {
    test('parses complete route', () {
      final json = {
        'shelter': _placeJson(),
        'all_shelters': [_placeJson(), _placeJson(type: 'school')],
        'route': {
          'distance_m':   800,
          'distance_km':  0.8,
          'duration_s':   120,
          'duration_min': 2,
          'coordinates':  [[51.5, -0.1], [51.51, -0.09]],
          'steps':        [{'instruction': 'Head north', 'distance_m': 800, 'duration_s': 120}],
          'profile':      'driving-car',
        },
      };
      final route = SafeRoute.fromJson(json);

      expect(route.shelter.name,     'Test Hall');
      expect(route.allShelters,      hasLength(2));
      expect(route.distanceM,        800);
      expect(route.distanceKm,       0.8);
      expect(route.durationMin,      2);
      expect(route.coordinates,      hasLength(2));
      expect(route.steps,            hasLength(1));
      expect(route.profile,          'driving-car');
      expect(route.coordinates[0],   [51.5, -0.1]);
    });

    test('handles missing route object', () {
      final json = {
        'shelter':      _placeJson(),
        'all_shelters': [],
      };
      final route = SafeRoute.fromJson(json);
      expect(route.distanceM,   0);
      expect(route.coordinates, isEmpty);
      expect(route.steps,       isEmpty);
    });
  });
}
