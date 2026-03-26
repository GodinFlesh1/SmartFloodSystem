class Station {
  final String eaStationId;
  final String stationName;
  final double latitude;
  final double longitude;
  final String? town;
  final String? riverName;
  final double? waterLevel;
  final double? flow;
  final double? rainfall;
  final double? groundwater;
  final double? tidal;
  final String riskLevel;
  final double? distanceKm;

  Station({
    required this.eaStationId,
    required this.stationName,
    required this.latitude,
    required this.longitude,
    this.town,
    this.riverName,
    this.waterLevel,
    this.flow,
    this.rainfall,
    this.groundwater,
    this.tidal,
    required this.riskLevel,
    this.distanceKm,
  });

  factory Station.fromJson(Map<String, dynamic> json) {
    return Station(
      eaStationId: json['ea_station_id'] ?? '',
      stationName: json['station_name'] ?? 'Unknown Station',
      latitude: (json['latitude'] as num?)?.toDouble() ?? 0,
      longitude: (json['longitude'] as num?)?.toDouble() ?? 0,
      town: json['town'],
      riverName: json['river_name'],
      waterLevel: (json['water_level'] as num?)?.toDouble(),
      flow: (json['flow'] as num?)?.toDouble(),
      rainfall: (json['rainfall'] as num?)?.toDouble(),
      groundwater: (json['groundwater'] as num?)?.toDouble(),
      tidal: (json['tidal'] as num?)?.toDouble(),
      riskLevel: json['risk_level'] ?? 'UNKNOWN',
      distanceKm: (json['distance_km'] as num?)?.toDouble(),
    );
  }

  /// True if this station has any live reading
  bool get hasAnyReading =>
      waterLevel != null ||
      flow != null ||
      rainfall != null ||
      groundwater != null ||
      tidal != null;
}
