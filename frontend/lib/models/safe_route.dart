class SafePlace {
  final String name;
  final String type;
  final double latitude;
  final double longitude;
  final int distanceM;
  final double distanceKm;
  final String address;

  SafePlace({
    required this.name,
    required this.type,
    required this.latitude,
    required this.longitude,
    required this.distanceM,
    required this.distanceKm,
    required this.address,
  });

  factory SafePlace.fromJson(Map<String, dynamic> json) => SafePlace(
        name:        json['name'] ?? 'Safe Place',
        type:        json['type'] ?? 'shelter',
        latitude:    (json['latitude'] as num).toDouble(),
        longitude:   (json['longitude'] as num).toDouble(),
        distanceM:   (json['distance_m'] as num?)?.toInt() ?? 0,
        distanceKm:  (json['distance_km'] as num?)?.toDouble() ?? 0,
        address:     json['address'] ?? '',
      );

  String get typeLabel {
    switch (type) {
      case 'community_centre': return 'Community Centre';
      case 'school':           return 'School';
      case 'hospital':         return 'Hospital';
      case 'place_of_worship': return 'Place of Worship';
      case 'assembly_point':   return 'Assembly Point';
      case 'police':           return 'Police Station';
      case 'fire_station':     return 'Fire Station';
      case 'shelter':          return 'Shelter';
      default:                 return type.replaceAll('_', ' ').toUpperCase();
    }
  }
}

class RouteStep {
  final String instruction;
  final int distanceM;
  final int durationS;

  RouteStep({
    required this.instruction,
    required this.distanceM,
    required this.durationS,
  });

  factory RouteStep.fromJson(Map<String, dynamic> json) => RouteStep(
        instruction: json['instruction'] ?? '',
        distanceM:   (json['distance_m'] as num?)?.toInt() ?? 0,
        durationS:   (json['duration_s'] as num?)?.toInt() ?? 0,
      );
}

/// Route-only data returned by /api/route (no shelter info).
class RouteData {
  final List<List<double>> coordinates;
  final int distanceM;
  final double distanceKm;
  final int durationMin;
  final List<RouteStep> steps;
  final String profile;

  RouteData({
    required this.coordinates,
    required this.distanceM,
    required this.distanceKm,
    required this.durationMin,
    required this.steps,
    required this.profile,
  });

  factory RouteData.fromJson(Map<String, dynamic> json) {
    final rawCoords = json['coordinates'] as List<dynamic>? ?? [];
    return RouteData(
      coordinates: rawCoords
          .map((c) => [(c[0] as num).toDouble(), (c[1] as num).toDouble()])
          .toList(),
      distanceM:   (json['distance_m'] as num?)?.toInt() ?? 0,
      distanceKm:  (json['distance_km'] as num?)?.toDouble() ?? 0,
      durationMin: (json['duration_min'] as num?)?.toInt() ?? 0,
      steps: (json['steps'] as List<dynamic>? ?? [])
          .map((s) => RouteStep.fromJson(s as Map<String, dynamic>))
          .toList(),
      profile: json['profile'] ?? 'driving-car',
    );
  }
}

class SafeRoute {
  final SafePlace shelter;
  final List<SafePlace> allShelters;
  final List<List<double>> coordinates;
  final int distanceM;
  final double distanceKm;
  final int durationMin;
  final List<RouteStep> steps;
  final String profile;
  final String? routeWarning;

  SafeRoute({
    required this.shelter,
    required this.allShelters,
    required this.coordinates,
    required this.distanceM,
    required this.distanceKm,
    required this.durationMin,
    required this.steps,
    required this.profile,
    this.routeWarning,
  });

  factory SafeRoute.fromJson(Map<String, dynamic> json) {
    final route     = json['route'] as Map<String, dynamic>? ?? {};
    final rawCoords = route['coordinates'] as List<dynamic>? ?? [];

    return SafeRoute(
      shelter:      SafePlace.fromJson(json['shelter'] as Map<String, dynamic>),
      allShelters:  (json['all_shelters'] as List<dynamic>? ?? [])
          .map((p) => SafePlace.fromJson(p as Map<String, dynamic>))
          .toList(),
      coordinates:  rawCoords
          .map((c) => [
                (c[0] as num).toDouble(),
                (c[1] as num).toDouble(),
              ])
          .toList(),
      distanceM:    (route['distance_m'] as num?)?.toInt() ?? 0,
      distanceKm:   (route['distance_km'] as num?)?.toDouble() ?? 0,
      durationMin:  (route['duration_min'] as num?)?.toInt() ?? 0,
      steps:        (route['steps'] as List<dynamic>? ?? [])
          .map((s) => RouteStep.fromJson(s as Map<String, dynamic>))
          .toList(),
      profile:      route['profile'] ?? 'driving-car',
      routeWarning: json['route_warning'] as String?,
    );
  }
}
