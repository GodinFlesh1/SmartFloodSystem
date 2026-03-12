class Station {
  final String name;
  final String river;
  final double latitude;
  final double longitude;
  final double? waterLevel;

  Station({
    required this.name,
    required this.river,
    required this.latitude,
    required this.longitude,
    this.waterLevel,
  });

  factory Station.fromJson(Map<String, dynamic> json) {
    return Station(
      name: json["station_name"],
      river: json["river_name"] ?? "",
      latitude: json["latitude"],
      longitude: json["longitude"],
      waterLevel: json["latest_reading"]?["water_level"],
    );
  }
}