class MeasureReading {
  final String parameter;
  final String qualifier;
  final String unit;
  final double? value;
  final String? dateTime;

  MeasureReading({
    required this.parameter,
    required this.qualifier,
    required this.unit,
    required this.value,
    required this.dateTime,
  });

  factory MeasureReading.fromJson(Map<String, dynamic> json) {
    return MeasureReading(
      parameter: json['parameter'] ?? '',
      qualifier: json['qualifier'] ?? '',
      unit: json['unit'] ?? '',
      value: json['value'] != null ? (json['value'] as num).toDouble() : null,
      dateTime: json['date_time'],
    );
  }

  /// Human-readable label: e.g. "Level (Stage)", "Flow", "Groundwater"
  String get label {
    final p = _paramLabel(parameter);
    final q = qualifier.isNotEmpty ? ' (${_capitalize(qualifier)})' : '';
    return '$p$q';
  }

  String _paramLabel(String param) {
    switch (param.toLowerCase()) {
      case 'level':
        return 'Water Level';
      case 'flow':
        return 'Flow Rate';
      case 'groundwater':
        return 'Groundwater';
      case 'rainfall':
        return 'Rainfall';
      case 'tidal':
        return 'Tidal Level';
      case 'wind':
        return 'Wind Speed';
      case 'temperature':
        return 'Temperature';
      case 'ph':
        return 'pH';
      default:
        return _capitalize(param);
    }
  }

  String _capitalize(String s) =>
      s.isEmpty ? s : s[0].toUpperCase() + s.substring(1);

  String get displayUnit {
    switch (unit.toLowerCase()) {
      case 'masd':
      case 'maodn':
      case 'm':
        return 'm';
      case 'm3_s':
        return 'm³/s';
      case 'mm':
        return 'mm';
      case 'deg_c':
        return '°C';
      case 'knots':
        return 'knots';
      default:
        return unit;
    }
  }
}

class StationDetail {
  final String stationId;
  final String stationName;
  final String? riverName;
  final String? town;
  final double? typicalRangeLow;
  final double? typicalRangeHigh;
  final String status;
  final List<MeasureReading> measures;

  StationDetail({
    required this.stationId,
    required this.stationName,
    this.riverName,
    this.town,
    this.typicalRangeLow,
    this.typicalRangeHigh,
    required this.status,
    required this.measures,
  });

  factory StationDetail.fromJson(Map<String, dynamic> json) {
    final measures = (json['measures'] as List<dynamic>? ?? [])
        .map((m) => MeasureReading.fromJson(m as Map<String, dynamic>))
        .toList();
    return StationDetail(
      stationId: json['station_id'] ?? '',
      stationName: json['station_name'] ?? '',
      riverName: json['river_name'],
      town: json['town'],
      typicalRangeLow: (json['typical_range_low'] as num?)?.toDouble(),
      typicalRangeHigh: (json['typical_range_high'] as num?)?.toDouble(),
      status: json['status'] ?? 'NO_SENSOR',
      measures: measures,
    );
  }
}
