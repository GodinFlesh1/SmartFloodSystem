class FloodPrediction {
  final String riskLevel;
  final double probability;
  final String confidence;
  final String reason;
  final String topStation;

  FloodPrediction({
    required this.riskLevel,
    required this.probability,
    required this.confidence,
    required this.reason,
    required this.topStation,
  });

  factory FloodPrediction.fromJson(Map<String, dynamic> json) {
    return FloodPrediction(
      riskLevel:  json['risk_level']  ?? 'UNKNOWN',
      probability: (json['probability'] as num?)?.toDouble() ?? 0.0,
      confidence: json['confidence']  ?? 'low',
      reason:     json['reason']      ?? '',
      topStation: json['top_station'] ?? '',
    );
  }

  Map<String, dynamic> toJson() => {
        'risk_level': riskLevel,
        'probability': probability,
        'confidence': confidence,
        'reason': reason,
        'top_station': topStation,
      };
}
